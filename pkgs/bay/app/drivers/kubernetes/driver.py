"""
Kubernetes container driver implementation.

This module implements the ContainerDriver interface using Kubernetes API
to manage Ship containers as Pods with PVC storage.
"""

from __future__ import annotations

import asyncio
import logging
import os
from typing import Optional

from kubernetes_asyncio import client, config
from kubernetes_asyncio.client.rest import ApiException

from app.config import settings
from app.models import Ship, ShipSpec
from app.drivers.core.base import ContainerDriver, ContainerInfo, ContainerIPAddressError
from app.drivers.kubernetes.utils import (
    build_pod_manifest,
    build_pvc_manifest,
    get_pod_name,
    get_pvc_name,
)

logger = logging.getLogger(__name__)


def _get_current_namespace() -> str:
    """
    Get the current namespace from in-cluster config or settings.

    For in-cluster deployment, reads from the service account namespace file.
    Falls back to settings.kube_namespace if not in cluster.
    """
    namespace_file = "/var/run/secrets/kubernetes.io/serviceaccount/namespace"
    if os.path.exists(namespace_file):
        with open(namespace_file, "r") as f:
            return f.read().strip()
    return settings.kube_namespace


class KubernetesDriver(ContainerDriver):
    """
    Kubernetes implementation of the ContainerDriver interface.

    This driver creates Ship containers as Kubernetes Pods with attached PVCs
    for persistent storage. It is designed for in-cluster deployment where
    Bay runs in the same Kubernetes cluster as the Ship pods.

    Use this driver when:
        - Bay is running inside a Kubernetes cluster
        - You need persistent storage for Ship workspaces
        - You want to leverage Kubernetes for container orchestration

    Configuration:
        - Set CONTAINER_DRIVER=kubernetes
        - Set KUBE_NAMESPACE to specify the target namespace
        - Set KUBE_PVC_SIZE for storage size
        - Set KUBE_STORAGE_CLASS for storage class (optional)
    """

    def __init__(self) -> None:
        self._api_client: Optional[client.ApiClient] = None
        self.core_api: Optional[client.CoreV1Api] = None
        self.namespace: str = _get_current_namespace()
        self._initialized: bool = False

    async def initialize(self) -> None:
        """Initialize Kubernetes client."""
        if self._initialized:
            return

        try:
            # Try to load in-cluster config first
            try:
                config.load_incluster_config()
                logger.info("Loaded in-cluster Kubernetes config")
            except config.ConfigException:
                # Fall back to kubeconfig file
                kubeconfig = settings.kube_config_path
                await config.load_kube_config(config_file=kubeconfig)
                logger.info(
                    "Loaded kubeconfig from %s",
                    kubeconfig or "default location"
                )

            # Create and save the ApiClient instance for proper cleanup
            self._api_client = client.ApiClient()
            self.core_api = client.CoreV1Api(self._api_client)

            # Test connection by listing namespaces
            await self.core_api.list_namespace(limit=1)

            self._initialized = True
            logger.info(
                "KubernetesDriver initialized successfully (namespace: %s)",
                self.namespace
            )

        except Exception as e:
            logger.error("Failed to initialize KubernetesDriver: %s", e)
            raise

    async def close(self) -> None:
        """Close Kubernetes client."""
        if self.core_api:
            # Close the actual ApiClient instance that backs CoreV1Api
            if self._api_client is not None:
                await self._api_client.close()
                self._api_client = None
            self.core_api = None
            self._initialized = False
            logger.info("KubernetesDriver closed")

    async def create_ship_container(
        self, ship: Ship, spec: Optional[ShipSpec] = None
    ) -> ContainerInfo:
        """
        Create a Ship as a Kubernetes Pod with PVC.

        This method:
        1. Creates a PVC for the ship's workspace
        2. Creates a Pod that mounts the PVC
        3. Waits for the Pod to be ready
        4. Returns the Pod's IP address

        Args:
            ship: The Ship model instance
            spec: Optional resource specifications

        Returns:
            ContainerInfo with pod name, IP address, and status

        Raises:
            ContainerIPAddressError: If Pod IP cannot be obtained
            ApiException: If Kubernetes API call fails
        """
        if not self._initialized:
            await self.initialize()

        assert self.core_api is not None

        pod_name = get_pod_name(ship.id)
        pvc_name = get_pvc_name(ship.id)

        try:
            # Step 1: Create PVC
            logger.info("Creating PVC %s for ship %s", pvc_name, ship.id)
            pvc_manifest = build_pvc_manifest(ship.id)

            try:
                await self.core_api.create_namespaced_persistent_volume_claim(
                    namespace=self.namespace,
                    body=pvc_manifest,
                )
                logger.debug("PVC %s created successfully", pvc_name)
            except ApiException as e:
                if e.status == 409:  # Already exists
                    logger.warning("PVC %s already exists, reusing", pvc_name)
                else:
                    raise

            # Step 2: Create Pod
            logger.info("Creating Pod %s for ship %s", pod_name, ship.id)

            cpus = spec.cpus if spec else None
            memory = spec.memory if spec else None

            pod_manifest = build_pod_manifest(
                ship_id=ship.id,
                image=settings.docker_image,
                cpus=cpus,
                memory=memory,
            )

            try:
                await self.core_api.create_namespaced_pod(
                    namespace=self.namespace,
                    body=pod_manifest,
                )
                logger.debug("Pod %s created successfully", pod_name)
            except ApiException as e:
                if e.status == 409:  # Already exists
                    logger.warning("Pod %s already exists", pod_name)
                else:
                    # Clean up PVC if pod creation fails
                    await self._cleanup_pvc(pvc_name)
                    raise

            # Step 3: Wait for Pod to be ready and get IP
            ip_address = await self._wait_for_pod_ready(pod_name, ship.id)

            if not ip_address:
                # Cleanup on failure
                await self._cleanup_pod_and_pvc(pod_name, pvc_name)
                raise ContainerIPAddressError(
                    container_id=pod_name,
                    ship_id=ship.id,
                    details="Pod did not get an IP address within timeout",
                )

            logger.info(
                "Ship %s created successfully: pod=%s, ip=%s",
                ship.id, pod_name, ip_address
            )

            return ContainerInfo(
                container_id=pod_name,
                ip_address=ip_address,
                status="running",
            )

        except ApiException as e:
            logger.error(
                "Failed to create ship %s: %s (status=%s)",
                ship.id, e.reason, e.status
            )
            raise
        except Exception as e:
            logger.error("Failed to create ship %s: %s", ship.id, e)
            raise

    async def stop_ship_container(self, container_id: str) -> bool:
        """
        Stop and remove a Ship Pod and its PVC.

        Args:
            container_id: The Pod name (ship-{ship_id})

        Returns:
            True if successful, False otherwise
        """
        if not self._initialized:
            await self.initialize()

        assert self.core_api is not None

        pod_name = container_id
        # Extract ship_id from pod name
        pvc_name = pod_name  # PVC uses same naming convention

        success = True

        # Delete Pod
        success = await self._cleanup_pod(pod_name) and success

        # Delete PVC
        success = await self._cleanup_pvc(pvc_name) and success

        return success

    def ship_data_exists(self, ship_id: str) -> bool:
        """
        Check if ship PVC exists.

        In Kubernetes mode, we check for PVC existence instead of local directories.
        This is a synchronous method, so we can't make API calls here.
        We return True to indicate that data might exist (conservative approach).
        """
        # In K8s mode, we can't synchronously check PVC existence
        # Return True as a conservative approach - actual check happens during creation
        return True

    async def get_container_logs(self, container_id: str) -> str:
        """
        Get Pod logs.

        Args:
            container_id: The Pod name

        Returns:
            Pod logs as a string
        """
        if not self._initialized:
            await self.initialize()

        assert self.core_api is not None

        try:
            logs = await self.core_api.read_namespaced_pod_log(
                name=container_id,
                namespace=self.namespace,
                tail_lines=1000,
            )
            return logs or ""

        except ApiException as e:
            if e.status == 404:
                logger.warning("Pod %s not found", container_id)
                return ""
            logger.error("Failed to get logs for pod %s: %s", container_id, e)
            return ""

    async def is_container_running(self, container_id: str) -> bool:
        """
        Check if Pod is running.

        Args:
            container_id: The Pod name

        Returns:
            True if Pod is in Running phase
        """
        if not self._initialized:
            await self.initialize()

        assert self.core_api is not None

        try:
            pod = await self.core_api.read_namespaced_pod(
                name=container_id,
                namespace=self.namespace,
            )
            return pod.status.phase == "Running"

        except ApiException as e:
            if e.status == 404:
                return False
            logger.error("Failed to check pod %s status: %s", container_id, e)
            return False

    async def _wait_for_pod_ready(
        self,
        pod_name: str,
        ship_id: str,
        timeout: int = 60,
        interval: int = 2,
    ) -> Optional[str]:
        """
        Wait for Pod to be ready and return its IP address.

        Args:
            pod_name: Name of the Pod
            ship_id: Ship ID for logging
            timeout: Maximum time to wait in seconds
            interval: Check interval in seconds

        Returns:
            Pod IP address if ready, None otherwise
        """
        assert self.core_api is not None

        elapsed = 0
        while elapsed < timeout:
            try:
                pod = await self.core_api.read_namespaced_pod(
                    name=pod_name,
                    namespace=self.namespace,
                )

                phase = pod.status.phase
                pod_ip = pod.status.pod_ip

                logger.debug(
                    "Pod %s status: phase=%s, ip=%s",
                    pod_name, phase, pod_ip
                )

                if phase == "Running" and pod_ip:
                    # Check if container is ready
                    if pod.status.container_statuses:
                        container_ready = all(
                            cs.ready for cs in pod.status.container_statuses
                        )
                        if container_ready:
                            return pod_ip

                elif phase in ("Failed", "Succeeded"):
                    logger.error(
                        "Pod %s for ship %s entered terminal phase: %s",
                        pod_name, ship_id, phase
                    )
                    return None

            except ApiException as e:
                logger.warning(
                    "Error checking pod %s status: %s", pod_name, e.reason
                )

            await asyncio.sleep(interval)
            elapsed += interval

        logger.error(
            "Timeout waiting for pod %s to be ready (ship %s)",
            pod_name, ship_id
        )
        return None

    async def _cleanup_pod(self, pod_name: str) -> bool:
        """Delete a Pod if it exists."""
        assert self.core_api is not None

        try:
            await self.core_api.delete_namespaced_pod(
                name=pod_name,
                namespace=self.namespace,
                grace_period_seconds=0,
            )
            logger.info("Pod %s deleted", pod_name)
            return True

        except ApiException as e:
            if e.status == 404:
                logger.debug("Pod %s not found, skipping deletion", pod_name)
                return True
            logger.error("Failed to delete pod %s: %s", pod_name, e)
            return False

    async def _cleanup_pvc(self, pvc_name: str) -> bool:
        """Delete a PVC if it exists."""
        assert self.core_api is not None

        try:
            await self.core_api.delete_namespaced_persistent_volume_claim(
                name=pvc_name,
                namespace=self.namespace,
            )
            logger.info("PVC %s deleted", pvc_name)
            return True

        except ApiException as e:
            if e.status == 404:
                logger.debug("PVC %s not found, skipping deletion", pvc_name)
                return True
            logger.error("Failed to delete PVC %s: %s", pvc_name, e)
            return False

    async def _cleanup_pod_and_pvc(self, pod_name: str, pvc_name: str) -> None:
        """Clean up both Pod and PVC on failure."""
        await self._cleanup_pod(pod_name)
        await self._cleanup_pvc(pvc_name)

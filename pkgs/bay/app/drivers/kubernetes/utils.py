"""
Kubernetes manifest generation utilities.

This module provides functions to generate Kubernetes Pod and PVC manifests
for Ship containers.
"""

from __future__ import annotations

from typing import Any, Dict, Optional

from kubernetes_asyncio.client import (
    V1Container,
    V1ContainerPort,
    V1EnvVar,
    V1ObjectMeta,
    V1PersistentVolumeClaim,
    V1PersistentVolumeClaimSpec,
    V1Pod,
    V1PodSpec,
    V1ResourceRequirements,
    V1Volume,
    V1VolumeMount,
    V1PersistentVolumeClaimVolumeSource,
)

from app.config import settings


def build_pvc_manifest(
    ship_id: str,
    storage_size: Optional[str] = None,
    storage_class: Optional[str] = None,
) -> V1PersistentVolumeClaim:
    """
    Build a PVC manifest for a Ship container.

    Args:
        ship_id: The unique identifier for the ship
        storage_size: Size of the PVC (default: from settings)
        storage_class: Storage class to use (default: from settings)

    Returns:
        V1PersistentVolumeClaim: The PVC manifest
    """
    pvc_name = f"ship-{ship_id}"
    size = storage_size or settings.kube_pvc_size
    sc = storage_class or settings.kube_storage_class

    return V1PersistentVolumeClaim(
        api_version="v1",
        kind="PersistentVolumeClaim",
        metadata=V1ObjectMeta(
            name=pvc_name,
            labels={
                "app": "ship",
                "ship_id": ship_id,
            },
        ),
        spec=V1PersistentVolumeClaimSpec(
            access_modes=["ReadWriteOnce"],
            resources=V1ResourceRequirements(
                requests={"storage": size},
            ),
            storage_class_name=sc if sc else None,
        ),
    )


from app.drivers.core.utils import parse_and_enforce_minimum_memory, parse_memory_string


def normalize_memory_for_k8s(memory: str) -> str:
    """
    Normalize memory unit for Kubernetes.

    Converts Docker-style memory units (like '512m', '1g') to Kubernetes-style
    binary units (like '512Mi', '1Gi') to prevent the dangerous 'm' suffix
    issue in Kubernetes (where 'm' means milli-bytes, not megabytes).

    Also enforces a minimum memory limit of 128 MiB.

    Args:
        memory: Memory string to normalize

    Returns:
        Normalized memory string safe for Kubernetes

    Examples:
        >>> normalize_memory_for_k8s("512m")
        "512Mi"
        >>> normalize_memory_for_k8s("64Mi")  # Too small
        "134217728"  # 128 MiB in bytes
    """
    if not memory:
        return memory

    # First, enforce minimum memory limit
    # This will log a warning if memory is too small
    safe_bytes = parse_and_enforce_minimum_memory(memory)
    original_bytes = parse_memory_string(memory)

    # If memory was increased to meet minimum, return the safe byte value
    if safe_bytes > original_bytes:
        return str(safe_bytes)

    # Otherwise, proceed with unit normalization for the original string
    memory = memory.strip()

    # Already using Kubernetes binary units
    if memory.endswith("Ki") or memory.endswith("Mi") or memory.endswith("Gi"):
        return memory

    # Also allow uppercase binary units
    if memory.endswith("KI") or memory.endswith("MI") or memory.endswith("GI"):
        return memory

    # Convert Docker-style units to Kubernetes binary units
    if memory.endswith("kb") or memory.endswith("KB"):
        return memory[:-2] + "Ki"
    if memory.endswith("k") or memory.endswith("K"):
        return memory[:-1] + "Ki"
    if memory.endswith("mb") or memory.endswith("MB"):
        return memory[:-2] + "Mi"
    if memory.endswith("m") or memory.endswith("M"):
        # This is the critical case: '512m' in Docker means 512 MiB,
        # but in Kubernetes '512m' means 0.512 bytes!
        return memory[:-1] + "Mi"
    if memory.endswith("gb") or memory.endswith("GB"):
        return memory[:-2] + "Gi"
    if memory.endswith("g") or memory.endswith("G"):
        return memory[:-1] + "Gi"

    # No unit suffix, assume bytes
    return memory


def build_pod_manifest(
    ship_id: str,
    image: str,
    cpus: Optional[float] = None,
    memory: Optional[str] = None,
    env: Optional[Dict[str, str]] = None,
) -> V1Pod:
    """
    Build a Pod manifest for a Ship container.

    Args:
        ship_id: The unique identifier for the ship
        image: Container image to use
        cpus: CPU allocation (optional)
        memory: Memory allocation (optional, will be normalized for K8s)
        env: Additional environment variables (optional)

    Returns:
        V1Pod: The Pod manifest
    """
    # Normalize memory for Kubernetes
    normalized_memory = normalize_memory_for_k8s(memory) if memory else None

    pod_name = f"ship-{ship_id}"
    pvc_name = f"ship-{ship_id}"

    # Build resource requirements
    resources: Dict[str, Any] = {}
    if cpus is not None or normalized_memory is not None:
        requests: Dict[str, str] = {}
        limits: Dict[str, str] = {}

        if cpus is not None:
            cpu_str = str(cpus)
            requests["cpu"] = cpu_str
            limits["cpu"] = cpu_str

        if normalized_memory is not None:
            requests["memory"] = normalized_memory
            limits["memory"] = normalized_memory

        resources = V1ResourceRequirements(
            requests=requests,
            limits=limits,
        )

    # Build environment variables
    env_vars = [
        V1EnvVar(name="PORT", value=str(settings.ship_container_port)),
    ]
    if env:
        for key, value in env.items():
            env_vars.append(V1EnvVar(name=key, value=value))

    # Build container
    container = V1Container(
        name="ship",
        image=image,
        image_pull_policy=settings.kube_image_pull_policy,
        ports=[
            V1ContainerPort(container_port=settings.ship_container_port),
        ],
        env=env_vars,
        resources=resources if resources else None,
        volume_mounts=[
            V1VolumeMount(
                name="workspace",
                mount_path="/workspace",
            ),
        ],
    )

    # Build pod
    return V1Pod(
        api_version="v1",
        kind="Pod",
        metadata=V1ObjectMeta(
            name=pod_name,
            labels={
                "app": "ship",
                "ship_id": ship_id,
            },
        ),
        spec=V1PodSpec(
            containers=[container],
            volumes=[
                V1Volume(
                    name="workspace",
                    persistent_volume_claim=V1PersistentVolumeClaimVolumeSource(
                        claim_name=pvc_name,
                    ),
                ),
            ],
            restart_policy="Never",
        ),
    )


def get_pod_name(ship_id: str) -> str:
    """Get the Pod name for a ship ID."""
    return f"ship-{ship_id}"


def get_pvc_name(ship_id: str) -> str:
    """Get the PVC name for a ship ID."""
    return f"ship-{ship_id}"

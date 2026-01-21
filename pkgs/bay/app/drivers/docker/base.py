"""
Base Docker driver with shared functionality.

This module provides a base class for Docker drivers that shares common
functionality like client lifecycle management and container operations.
"""

import logging
from typing import Optional, Dict, Any

import aiodocker
from aiodocker.exceptions import DockerError

from app.config import settings
from app.models import Ship, ShipSpec
from app.drivers.core.base import (
    ContainerDriver,
    ContainerInfo,
    ContainerIPAddressError,
)
from app.drivers.core.utils import (
    parse_and_enforce_minimum_memory,
    parse_and_enforce_minimum_disk,
    ensure_ship_dirs,
    ship_data_exists,
)

logger = logging.getLogger(__name__)


class BaseDockerDriver(ContainerDriver):
    """
    Base Docker driver with shared functionality.

    This class provides common Docker operations that are shared between
    DockerDriver (container mode) and DockerHostDriver (host mode).

    Subclasses should override:
        - _get_ip_address(): To determine how to extract the container's address
        - Optionally _build_container_config(): If different configuration is needed
    """

    def __init__(self) -> None:
        self.client: Optional[aiodocker.Docker] = None

    async def initialize(self) -> None:
        """Initialize Docker client."""
        if self.client:
            return

        try:
            self.client = aiodocker.Docker()
            # Test connection
            await self.client.version()
            logger.info("%s initialized successfully", self.__class__.__name__)
        except DockerError as e:
            logger.error("Failed to initialize %s: %s", self.__class__.__name__, e)
            raise

    async def close(self) -> None:
        """Close Docker client."""
        if self.client:
            await self.client.close()
            self.client = None

    async def create_ship_container(
        self, ship: Ship, spec: Optional[ShipSpec] = None
    ) -> ContainerInfo:
        """Create and start a ship container using Docker."""
        if not self.client:
            await self.initialize()

        assert self.client is not None  # For type checker

        container_config = self._build_container_config(ship, spec)
        container = None

        try:
            # Create container
            container = await self.client.containers.create_or_replace(
                name=container_config["name"], config=container_config["config"]
            )

            # Start container
            await container.start()
        except DockerError as e:
            # Check if the error is due to unsupported storage quota
            error_msg = str(e)
            if "storage-opt" in error_msg.lower() or "storageopt" in error_msg.lower():
                logger.warning(
                    "Storage quota not supported by container runtime. "
                    "Retrying without disk limit. Error: %s",
                    error_msg,
                )
                # Retry without storage quota
                if "StorageOpt" in container_config["config"].get("HostConfig", {}):
                    del container_config["config"]["HostConfig"]["StorageOpt"]
                    container = await self.client.containers.create_or_replace(
                        name=container_config["name"], config=container_config["config"]
                    )
                    await container.start()
            else:
                logger.error("Failed to create container for ship %s: %s", ship.id, e)
                raise

        try:
            # Get container info
            container_info = await container.show()

            # Get IP address (implementation varies by driver mode)
            ip_address = self._get_ip_address(container_info, ship.id)

            # Validate IP address - fail fast if not available
            if not ip_address:
                # Log detailed diagnostic information
                network_settings = container_info.get("NetworkSettings", {})
                ports = network_settings.get("Ports", {})
                networks = network_settings.get("Networks", {})
                logger.error(
                    "Failed to obtain IP address for ship %s (container %s). "
                    "NetworkSettings: Ports=%s, Networks=%s, IPAddress=%s",
                    ship.id,
                    container.id,
                    ports,
                    list(networks.keys()) if networks else None,
                    network_settings.get("IPAddress"),
                )
                # Stop the container since we can't use it
                try:
                    await container.stop()
                    await container.delete()
                except Exception as cleanup_error:
                    logger.warning(
                        "Failed to cleanup container %s after IP address error: %s",
                        container.id,
                        cleanup_error,
                    )
                raise ContainerIPAddressError(
                    container_id=container.id,
                    ship_id=ship.id,
                    details="Network settings may be misconfigured or port mapping failed",
                )

            logger.debug(
                "Container %s for ship %s obtained IP address: %s",
                container.id,
                ship.id,
                ip_address,
            )

            return ContainerInfo(
                container_id=container.id,
                ip_address=ip_address,
                status=container_info.get("State", {}).get("Status", "unknown"),
            )

        except DockerError as e:
            logger.error("Failed to get container info for ship %s: %s", ship.id, e)
            raise

    async def stop_ship_container(self, container_id: str) -> bool:
        """Stop and remove ship container."""
        if not self.client:
            await self.initialize()

        assert self.client is not None  # For type checker

        try:
            # Get container
            container = await self.client.containers.get(container_id)

            # Stop container
            await container.stop()

            # Remove container
            await container.delete()

            return True

        except DockerError as e:
            if "No such container" in str(e):
                logger.warning("Container %s not found", container_id)
                return True  # Already removed
            logger.error("Failed to stop container %s: %s", container_id, e)
            return False

    def ship_data_exists(self, ship_id: str) -> bool:
        """Check if ship data directory exists."""
        return ship_data_exists(ship_id)

    async def get_container_logs(self, container_id: str) -> str:
        """Get container logs."""
        if not self.client:
            await self.initialize()

        assert self.client is not None  # For type checker

        try:
            # Get container
            container = await self.client.containers.get(container_id)

            # Get logs
            logs_stream = await container.log(stdout=True, stderr=True)
            logs = "".join(logs_stream)

            return logs

        except DockerError as e:
            if "No such container" in str(e):
                logger.warning("Container %s not found", container_id)
                return ""
            logger.error("Failed to get logs for container %s: %s", container_id, e)
            return ""

    async def is_container_running(self, container_id: str) -> bool:
        """Check if container is running."""
        if not self.client:
            await self.initialize()

        assert self.client is not None  # For type checker

        try:
            # Get container
            container = await self.client.containers.get(container_id)

            # Get container info
            container_info = await container.show()
            return container_info.get("State", {}).get("Status") == "running"

        except DockerError as e:
            if "No such container" in str(e):
                return False
            logger.error("Failed to check container %s status: %s", container_id, e)
            return False

    def _build_container_config(
        self, ship: Ship, spec: Optional[ShipSpec] = None
    ) -> Dict[str, Any]:
        """
        Build container configuration for aiodocker.

        Subclasses can override this to customize container configuration.
        """
        # Ensure ship directories exist with proper permissions
        dirs = ensure_ship_dirs(ship.id)
        home_dir = dirs["home"]
        metadata_dir = dirs["metadata"]

        # Host configuration for resource limits
        port_key = f"{settings.ship_container_port}/tcp"
        host_config: Dict[str, Any] = {
            "RestartPolicy": {"Name": "no"},
            "PortBindings": {port_key: [{"HostPort": ""}]},
            "Binds": [
                f"{home_dir}:/home",
                f"{metadata_dir}:/app/metadata",
            ],
        }

        # Apply spec if provided
        if spec:
            if spec.cpus:
                host_config["CpuQuota"] = int(spec.cpus * 100000)
                host_config["CpuPeriod"] = 100000

            if spec.memory:
                host_config["Memory"] = parse_and_enforce_minimum_memory(spec.memory)

            if spec.disk:
                # Docker storage quota using StorageOpt
                # Note: This requires Docker's overlay2 driver with xfs filesystem
                # and pquota mount option, or ext4 with quota enabled.
                # If unsupported, Docker will ignore this option.
                disk_bytes = parse_and_enforce_minimum_disk(spec.disk)
                host_config["StorageOpt"] = {"size": str(disk_bytes)}
                logger.debug(
                    "Setting storage quota for ship: %d bytes (%s)",
                    disk_bytes,
                    spec.disk,
                )

        # Container configuration
        config: Dict[str, Any] = {
            "Image": settings.docker_image,
            "Env": [f"SHIP_ID={ship.id}", f"TTL={ship.ttl}"],
            "Labels": {"ship_id": ship.id, "created_by": "bay"},
            "ExposedPorts": {port_key: {}},
            "HostConfig": host_config,
        }

        # Add network if configured
        if settings.docker_network:
            config["NetworkingConfig"] = {
                "EndpointsConfig": {settings.docker_network: {}}
            }

        return {"name": f"ship-{ship.id}", "config": config}

    def _get_ip_address(
        self, container_info: Dict[str, Any], ship_id: str
    ) -> Optional[str]:
        """
        Extract IP address from container info.

        This method should be overridden by subclasses to implement
        mode-specific address resolution:
        - DockerDriver: Uses Docker network internal IP
        - DockerHostDriver: Uses localhost with mapped port

        Args:
            container_info: Container inspection data from Docker
            ship_id: The ship ID (for logging)

        Returns:
            The IP address or address:port string to reach the container
        """
        # Default implementation: use Docker network IP
        network_settings = container_info.get("NetworkSettings", {})

        if settings.docker_network and settings.docker_network in network_settings.get(
            "Networks", {}
        ):
            return network_settings["Networks"][settings.docker_network].get(
                "IPAddress"
            )
        else:
            return network_settings.get("IPAddress")

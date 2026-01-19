"""
Base Podman driver with shared functionality.

This module provides a base class for Podman drivers that shares common
functionality like client lifecycle management and container operations.
"""

from __future__ import annotations

import asyncio
import os
import logging
from typing import Any, Callable, Dict, Optional, TypeVar

from app.config import settings
from app.models import Ship, ShipSpec
from app.drivers.core.base import ContainerDriver, ContainerInfo
from app.drivers.core.utils import parse_memory_string, ensure_ship_dirs, ship_data_exists

logger = logging.getLogger(__name__)

# Try importing podman
try:
    from podman import PodmanClient
    from podman.errors import PodmanError
except ImportError:
    PodmanClient = None  # type: ignore
    PodmanError = Exception  # type: ignore

T = TypeVar("T")


def get_podman_socket() -> str:
    """
    Return the path to the Podman socket.

    For rootless Podman, the socket is typically in XDG_RUNTIME_DIR.
    """
    xdg = os.environ.get("XDG_RUNTIME_DIR", f"/run/user/{os.getuid()}")
    return f"unix://{xdg}/podman/podman.sock"


class BasePodmanDriver(ContainerDriver):
    """
    Base Podman driver with shared functionality.

    This class provides common Podman operations that are shared between
    PodmanDriver (container mode) and PodmanHostDriver (host mode).

    Subclasses should override:
        - _get_ip_address(): To determine how to extract the container's address
        - Optionally _build_container_config(): If different configuration is needed
    """

    def __init__(self) -> None:
        self.client: Optional[PodmanClient] = None

    async def _run_sync(self, fn: Callable[..., T], *args: Any, **kwargs: Any) -> T:
        """
        Run a synchronous function in an executor.

        Podman client is synchronous, so we wrap calls in run_in_executor
        to avoid blocking the event loop.
        """
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, lambda: fn(*args, **kwargs))

    async def initialize(self) -> None:
        """Initialize Podman client."""
        if self.client:
            return

        if PodmanClient is None:
            raise ImportError(
                "podman-py is not installed. Install with: pip install podman"
            )

        socket = get_podman_socket()
        try:
            self.client = await self._run_sync(PodmanClient, base_url=socket)
            await self._run_sync(self.client.version)
            logger.info("%s initialized successfully (socket: %s)",
                       self.__class__.__name__, socket)
        except Exception as e:
            logger.error("Failed to initialize %s: %s", self.__class__.__name__, e)
            raise

    async def close(self) -> None:
        """Close Podman client."""
        if self.client:
            await self._run_sync(self.client.close)
            self.client = None

    async def create_ship_container(
        self, ship: Ship, spec: Optional[ShipSpec] = None
    ) -> ContainerInfo:
        """Create and start a ship container using Podman."""
        if not self.client:
            await self.initialize()
        assert self.client is not None

        container_cfg = self._build_container_config(ship, spec)

        try:
            container = await self._run_sync(
                self.client.containers.run,
                **container_cfg,
                detach=True,
            )

            # Reload to get network info
            await self._run_sync(container.reload)

            # Get IP address (implementation varies by driver mode)
            ip_address = self._get_ip_address(container, ship.id)

            return ContainerInfo(
                container_id=container.id,
                ip_address=ip_address,
                status=container.status,
            )
        except PodmanError as e:
            logger.error("Failed to create container for ship %s: %s", ship.id, e)
            raise

    async def stop_ship_container(self, container_id: str) -> bool:
        """Stop and remove ship container."""
        if not self.client:
            await self.initialize()
        assert self.client is not None

        try:
            container = await self._run_sync(
                self.client.containers.get, container_id
            )
            await self._run_sync(container.stop)
            await self._run_sync(container.remove)
            return True
        except PodmanError as e:
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
        assert self.client is not None

        try:
            container = await self._run_sync(
                self.client.containers.get, container_id
            )
            logs = await self._run_sync(
                container.logs, stdout=True, stderr=True
            )
            if isinstance(logs, bytes):
                return logs.decode(errors="replace")
            return str(logs)
        except PodmanError as e:
            if "No such container" in str(e):
                logger.warning("Container %s not found", container_id)
                return ""
            logger.error("Failed to get logs for container %s: %s", container_id, e)
            return ""

    async def is_container_running(self, container_id: str) -> bool:
        """Check if container is running."""
        if not self.client:
            await self.initialize()
        assert self.client is not None

        try:
            container = await self._run_sync(
                self.client.containers.get, container_id
            )
            await self._run_sync(container.reload)
            return container.status == "running"
        except PodmanError as e:
            if "No such container" in str(e):
                return False
            logger.error("Failed to check container %s status: %s", container_id, e)
            return False

    def _build_container_config(
        self, ship: Ship, spec: Optional[ShipSpec] = None
    ) -> Dict[str, Any]:
        """
        Build kwargs for containers.run().

        Subclasses can override this to customize container configuration.
        """
        # Ensure ship directories exist with proper permissions
        dirs = ensure_ship_dirs(ship.id)
        home_dir = dirs["home"]
        metadata_dir = dirs["metadata"]

        port_key = f"{settings.ship_container_port}/tcp"
        config: Dict[str, Any] = {
            "image": settings.docker_image,
            "name": f"ship-{ship.id}",
            "environment": {"SHIP_ID": ship.id, "TTL": str(ship.ttl)},
            "labels": {"ship_id": ship.id, "created_by": "bay"},
            "ports": {port_key: None},  # Random port
            "volumes": {
                home_dir: {"bind": "/home", "mode": "rw"},
                metadata_dir: {"bind": "/app/metadata", "mode": "rw"},
            },
        }

        if spec:
            if spec.cpus:
                config["cpu_quota"] = int(spec.cpus * 100000)
                config["cpu_period"] = 100000
            if spec.memory:
                config["mem_limit"] = parse_memory_string(spec.memory)

        if settings.docker_network:
            config["network"] = settings.docker_network

        return config

    def _get_ip_address(self, container: Any, ship_id: str) -> Optional[str]:
        """
        Extract IP address from container.

        This method should be overridden by subclasses to implement
        mode-specific address resolution:
        - PodmanDriver: Uses Podman network internal IP
        - PodmanHostDriver: Uses localhost with mapped port

        Args:
            container: The Podman container object
            ship_id: The ship ID (for logging)

        Returns:
            The IP address or address:port string to reach the container
        """
        # Default implementation: use Podman network IP
        network_settings = container.attrs.get("NetworkSettings", {})

        if (
            settings.docker_network
            and settings.docker_network in network_settings.get("Networks", {})
        ):
            return network_settings["Networks"][settings.docker_network].get(
                "IPAddress"
            )
        else:
            return network_settings.get("IPAddress")

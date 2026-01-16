"""
Podman Host container driver implementation.

This module implements the ContainerDriver interface for running Bay on the host
machine (not inside a container). It uses port mapping to communicate with Ship
containers instead of internal network IPs.
"""

from __future__ import annotations

import asyncio
import os
import logging
from typing import Any, Dict, Optional

from app.config import settings
from app.models import Ship, ShipSpec
from app.drivers.core.base import ContainerDriver, ContainerInfo

logger = logging.getLogger(__name__)

try:
    from podman import PodmanClient
    from podman.errors import PodmanError
except ImportError:
    PodmanClient = None  # type: ignore
    PodmanError = Exception  # type: ignore


def _get_podman_socket() -> str:
    """Return the path to the Podman socket."""
    xdg = os.environ.get("XDG_RUNTIME_DIR", f"/run/user/{os.getuid()}")
    return f"unix://{xdg}/podman/podman.sock"


class PodmanHostDriver(ContainerDriver):
    """
    Podman driver for host-mode Bay deployment.

    Uses localhost and mapped ports to communicate with Ship containers.
    """

    def __init__(self) -> None:
        self.client: Optional[PodmanClient] = None

    async def initialize(self) -> None:
        """Initialize Podman client."""
        if PodmanClient is None:
            raise ImportError(
                "podman-py is not installed. Install with: pip install podman"
            )

        socket = _get_podman_socket()
        try:
            loop = asyncio.get_running_loop()
            self.client = await loop.run_in_executor(
                None,
                lambda: PodmanClient(base_url=socket),
            )
            await loop.run_in_executor(None, lambda: self.client.version())
            logger.info(f"Podman Host driver initialized (socket: {socket})")
        except Exception as e:
            logger.error(f"Failed to initialize Podman Host driver: {e}")
            raise

    async def close(self) -> None:
        """Close Podman client."""
        if self.client:
            loop = asyncio.get_running_loop()
            await loop.run_in_executor(None, self.client.close)

    async def create_ship_container(
        self, ship: Ship, spec: Optional[ShipSpec] = None
    ) -> ContainerInfo:
        """Create and start a ship container, returning localhost:port for ip."""
        if not self.client:
            await self.initialize()
        assert self.client is not None

        container_cfg = self._build_container_config(ship, spec)
        loop = asyncio.get_running_loop()

        try:
            container = await loop.run_in_executor(
                None,
                lambda: self.client.containers.run(
                    **container_cfg,
                    detach=True,
                ),
            )

            await loop.run_in_executor(None, container.reload)

            ip_address: Optional[str] = None
            network_settings = container.attrs.get("NetworkSettings", {})
            ports = network_settings.get("Ports", {})
            if "8123/tcp" in ports and ports["8123/tcp"]:
                host_port = ports["8123/tcp"][0].get("HostPort")
                if host_port:
                    ip_address = f"127.0.0.1:{host_port}"
                    logger.info(f"Ship {ship.id} accessible at {ip_address}")

            if not ip_address:
                logger.warning(
                    f"Could not get port mapping for ship {ship.id}, "
                    "falling back to container IP"
                )
                if (
                    settings.docker_network
                    and settings.docker_network
                    in network_settings.get("Networks", {})
                ):
                    ip_address = network_settings["Networks"][
                        settings.docker_network
                    ].get("IPAddress")
                else:
                    ip_address = network_settings.get("IPAddress")

            return ContainerInfo(
                container_id=container.id,
                ip_address=ip_address,
                status=container.status,
            )
        except PodmanError as e:
            logger.error(f"Failed to create container for ship {ship.id}: {e}")
            raise

    async def stop_ship_container(self, container_id: str) -> bool:
        """Stop and remove ship container."""
        if not self.client:
            await self.initialize()
        assert self.client is not None

        loop = asyncio.get_running_loop()
        try:
            container = await loop.run_in_executor(
                None,
                lambda: self.client.containers.get(container_id),
            )
            await loop.run_in_executor(None, lambda: container.stop())
            await loop.run_in_executor(None, lambda: container.remove())
            return True
        except PodmanError as e:
            if "No such container" in str(e):
                logger.warning(f"Container {container_id} not found")
                return True
            logger.error(f"Failed to stop container {container_id}: {e}")
            return False

    def ship_data_exists(self, ship_id: str) -> bool:
        """Check if ship data directory exists."""
        ship_data_dir = os.path.expanduser(f"{settings.ship_data_dir}/{ship_id}")
        home_dir = f"{ship_data_dir}/home"
        metadata_dir = f"{ship_data_dir}/metadata"
        return os.path.exists(home_dir) and os.path.exists(metadata_dir)

    async def get_container_logs(self, container_id: str) -> str:
        """Get container logs."""
        if not self.client:
            await self.initialize()
        assert self.client is not None

        loop = asyncio.get_running_loop()
        try:
            container = await loop.run_in_executor(
                None,
                lambda: self.client.containers.get(container_id),
            )
            logs = await loop.run_in_executor(
                None,
                lambda: container.logs(stdout=True, stderr=True),
            )
            if isinstance(logs, bytes):
                return logs.decode(errors="replace")
            return str(logs)
        except PodmanError as e:
            if "No such container" in str(e):
                logger.warning(f"Container {container_id} not found")
                return ""
            logger.error(f"Failed to get logs for container {container_id}: {e}")
            return ""

    async def is_container_running(self, container_id: str) -> bool:
        """Check if container is running."""
        if not self.client:
            await self.initialize()
        assert self.client is not None

        loop = asyncio.get_running_loop()
        try:
            container = await loop.run_in_executor(
                None,
                lambda: self.client.containers.get(container_id),
            )
            await loop.run_in_executor(None, container.reload)
            return container.status == "running"
        except PodmanError as e:
            if "No such container" in str(e):
                return False
            logger.error(f"Failed to check container {container_id} status: {e}")
            return False

    def _build_container_config(
        self, ship: Ship, spec: Optional[ShipSpec] = None
    ) -> Dict[str, Any]:
        """Build kwargs for containers.run()."""
        ship_data_dir = os.path.expanduser(f"{settings.ship_data_dir}/{ship.id}")
        home_dir = f"{ship_data_dir}/home"
        metadata_dir = f"{ship_data_dir}/metadata"

        os.makedirs(home_dir, exist_ok=True)
        os.makedirs(metadata_dir, exist_ok=True)

        try:
            os.chmod(home_dir, 0o777)
            os.chmod(metadata_dir, 0o777)
        except Exception as e:
            logger.error(
                f"Failed to set permissions for ship {ship.id} directories: {e}"
            )
            raise

        config: Dict[str, Any] = {
            "image": settings.docker_image,
            "name": f"ship-{ship.id}",
            "environment": {"SHIP_ID": ship.id, "TTL": str(ship.ttl)},
            "labels": {"ship_id": ship.id, "created_by": "bay"},
            "ports": {"8123/tcp": None},
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
                config["mem_limit"] = self._parse_memory_string(spec.memory)

        if settings.docker_network:
            config["network"] = settings.docker_network

        return config

    def _parse_memory_string(self, memory_str: str) -> int:
        """Parse memory string to bytes."""
        memory_str = memory_str.lower().strip()
        if memory_str.endswith("kb"):
            return int(memory_str[:-2]) * 1024
        if memory_str.endswith("k"):
            return int(memory_str[:-1]) * 1024
        if memory_str.endswith("mb"):
            return int(memory_str[:-2]) * 1024 * 1024
        if memory_str.endswith("m"):
            return int(memory_str[:-1]) * 1024 * 1024
        if memory_str.endswith("gb"):
            return int(memory_str[:-2]) * 1024 * 1024 * 1024
        if memory_str.endswith("g"):
            return int(memory_str[:-1]) * 1024 * 1024 * 1024
        return int(memory_str)

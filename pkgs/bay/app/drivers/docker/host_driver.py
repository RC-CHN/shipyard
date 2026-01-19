"""
Docker Host container driver implementation.

This module implements the ContainerDriver interface for running Bay on the host
machine (not inside a Docker container). It uses port mapping to communicate
with Ship containers instead of Docker network internal IPs.
"""

import logging
from typing import Dict, Any, Optional

from app.config import settings
from app.drivers.docker.base import BaseDockerDriver

logger = logging.getLogger(__name__)


class DockerHostDriver(BaseDockerDriver):
    """
    Docker driver for host-mode Bay deployment.

    This driver is designed for when Bay runs directly on the host machine
    (not inside a Docker container). It uses localhost and mapped ports
    to communicate with Ship containers instead of Docker network IPs.

    Use this driver when:
        - Bay is running directly on the host (e.g., `python run.py`)
        - Bay cannot access Docker's internal network IPs

    Configuration:
        - Set CONTAINER_DRIVER=docker-host
    """

    def _get_ip_address(
        self, container_info: Dict[str, Any], ship_id: str
    ) -> Optional[str]:
        """
        Extract IP address from container info using port mapping.

        In host mode, we use localhost:mapped_port instead of container IP.

        Args:
            container_info: Container inspection data from Docker
            ship_id: The ship ID (for logging)

        Returns:
            The localhost:port string to reach the container
        """
        network_settings = container_info.get("NetworkSettings", {})
        ports = network_settings.get("Ports", {})

        port_key = f"{settings.ship_container_port}/tcp"
        if port_key in ports and ports[port_key]:
            host_port = ports[port_key][0].get("HostPort")
            if host_port:
                # Use localhost with the mapped port
                ip_address = f"127.0.0.1:{host_port}"
                logger.info("Ship %s accessible at %s", ship_id, ip_address)
                return ip_address

        # Fallback to container IP (might not work on host)
        logger.warning(
            "Could not get port mapping for ship %s, falling back to container IP",
            ship_id
        )
        return super()._get_ip_address(container_info, ship_id)

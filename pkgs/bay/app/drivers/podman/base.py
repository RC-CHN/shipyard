"""
Base Podman driver with shared functionality.

This module provides a base class for Podman drivers that uses aiodocker
to communicate with Podman via its Docker-compatible API.
"""

from __future__ import annotations

import os
import logging
from typing import Optional

import aiodocker

from app.drivers.docker.base import BaseDockerDriver

logger = logging.getLogger(__name__)


def get_podman_socket() -> str:
    """
    Return the path to the Podman socket.

    For containerized Bay, the socket is mounted at /var/run/podman/podman.sock.
    For rootless Podman on host, the socket is typically in XDG_RUNTIME_DIR.
    """
    # Check for mounted socket first (containerized deployment)
    mounted_socket = "/var/run/podman/podman.sock"
    if os.path.exists(mounted_socket):
        return f"unix://{mounted_socket}"
    
    # Fall back to XDG_RUNTIME_DIR for host deployment
    xdg = os.environ.get("XDG_RUNTIME_DIR", f"/run/user/{os.getuid()}")
    return f"unix://{xdg}/podman/podman.sock"


class BasePodmanDriver(BaseDockerDriver):
    """
    Base Podman driver using Docker-compatible API via aiodocker.

    Podman provides a Docker-compatible API, so we can use aiodocker
    by pointing it to the Podman socket instead of the Docker socket.

    This class provides common Podman operations that are shared between
    PodmanDriver (container mode) and PodmanHostDriver (host mode).

    Subclasses should override:
        - _get_ip_address(): To determine how to extract the container's address
        - Optionally _build_container_config(): If different configuration is needed
    """

    async def initialize(self) -> None:
        """Initialize aiodocker client with Podman socket."""
        if self.client:
            return

        socket = get_podman_socket()
        try:
            self.client = aiodocker.Docker(url=socket)
            # Test connection
            await self.client.version()
            logger.info("%s initialized successfully (socket: %s)",
                       self.__class__.__name__, socket)
        except Exception as e:
            logger.error("Failed to initialize %s: %s", self.__class__.__name__, e)
            raise

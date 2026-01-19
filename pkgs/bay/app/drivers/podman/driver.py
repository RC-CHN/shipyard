"""
Podman container driver implementation.

This module implements the ContainerDriver interface using Podman (via podman-py).
Podman is API-compatible with Docker, so the implementation is similar to
DockerDriver, using the Podman UNIX socket.
"""

from __future__ import annotations

import logging

from app.drivers.podman.base import BasePodmanDriver

logger = logging.getLogger(__name__)


class PodmanDriver(BasePodmanDriver):
    """
    Podman implementation of the ContainerDriver interface.

    Uses podman-py for container operations. Requires access to the Podman socket.

    This driver is designed for when Bay runs inside a container
    and can access other containers via Podman network IPs.

    Use this driver when:
        - Bay is running inside a container with Podman
        - Bay can access Podman's internal network IPs

    Configuration:
        - Set CONTAINER_DRIVER=podman
    """

    # This driver uses the default implementation from BasePodmanDriver
    # which returns Podman network IPs via _get_ip_address()
    pass

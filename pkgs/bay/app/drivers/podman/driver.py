"""
Podman container driver implementation.

This module implements the ContainerDriver interface using Podman's
Docker-compatible API via aiodocker.
"""

from __future__ import annotations

import logging

from app.drivers.podman.base import BasePodmanDriver

logger = logging.getLogger(__name__)


class PodmanDriver(BasePodmanDriver):
    """
    Podman implementation of the ContainerDriver interface.

    Uses aiodocker for container operations via Podman's Docker-compatible socket.

    This driver is designed for when Bay runs inside a container
    and can access other containers via Podman network IPs.

    Use this driver when:
        - Bay is running inside a container with Podman
        - Bay can access Podman's internal network IPs

    Configuration:
        - Set CONTAINER_DRIVER=podman
    """

    # This driver uses the default implementation from BasePodmanDriver
    # which inherits from BaseDockerDriver and returns network IPs via _get_ip_address()
    pass

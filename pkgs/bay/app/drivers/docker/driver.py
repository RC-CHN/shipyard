"""
Docker container driver implementation.

This module implements the ContainerDriver interface using Docker (via aiodocker).
Uses Docker network internal IPs for container-to-container communication.
"""

import logging

from app.drivers.docker.base import BaseDockerDriver

logger = logging.getLogger(__name__)


class DockerDriver(BaseDockerDriver):
    """
    Docker implementation of the ContainerDriver interface.

    Uses aiodocker for async Docker operations. Requires access to the
    Docker socket (typically /var/run/docker.sock).

    This driver is designed for when Bay runs inside a Docker container
    and can access other containers via Docker network IPs.

    Use this driver when:
        - Bay is running inside a Docker container
        - Bay can access Docker's internal network IPs

    Configuration:
        - Set CONTAINER_DRIVER=docker
    """

    # This driver uses the default implementation from BaseDockerDriver
    # which returns Docker network IPs via _get_ip_address()
    pass

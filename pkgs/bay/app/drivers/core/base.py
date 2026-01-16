"""
Abstract base class for container drivers.

This module defines the interface that all container drivers must implement,
enabling support for different container runtimes like Docker, containerd, etc.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional

from app.models import Ship, ShipSpec


@dataclass
class ContainerInfo:
    """Information about a created container."""

    container_id: str
    ip_address: Optional[str]
    status: str


class ContainerDriver(ABC):
    """
    Abstract base class for container runtime drivers.

    Implementations of this class provide the actual container management
    functionality for different runtimes (Docker, containerd, etc.).
    """

    @abstractmethod
    async def initialize(self) -> None:
        """
        Initialize the container runtime client.

        This method should establish connection to the container runtime
        and perform any necessary setup.

        Raises:
            Exception: If initialization fails
        """
        pass

    @abstractmethod
    async def close(self) -> None:
        """
        Close the container runtime client and cleanup resources.
        """
        pass

    @abstractmethod
    async def create_ship_container(
        self, ship: Ship, spec: Optional[ShipSpec] = None
    ) -> ContainerInfo:
        """
        Create and start a container for a ship.

        Args:
            ship: The Ship model instance containing ship configuration
            spec: Optional specifications for CPU, memory, etc.

        Returns:
            ContainerInfo with container_id, ip_address, and status

        Raises:
            Exception: If container creation fails
        """
        pass

    @abstractmethod
    async def stop_ship_container(self, container_id: str) -> bool:
        """
        Stop and remove a ship container.

        Args:
            container_id: The ID of the container to stop

        Returns:
            True if successful (or container already removed), False otherwise
        """
        pass

    @abstractmethod
    def ship_data_exists(self, ship_id: str) -> bool:
        """
        Check if ship data directory exists on the host.

        Args:
            ship_id: The ID of the ship

        Returns:
            True if ship data directories exist, False otherwise
        """
        pass

    @abstractmethod
    async def get_container_logs(self, container_id: str) -> str:
        """
        Get container logs.

        Args:
            container_id: The ID of the container

        Returns:
            Container logs as a string, empty string if container not found
        """
        pass

    @abstractmethod
    async def is_container_running(self, container_id: str) -> bool:
        """
        Check if a container is currently running.

        Args:
            container_id: The ID of the container

        Returns:
            True if container is running, False otherwise
        """
        pass

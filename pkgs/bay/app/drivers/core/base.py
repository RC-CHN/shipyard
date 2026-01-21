"""
Abstract base class for container drivers.

This module defines the interface that all container drivers must implement,
enabling support for different container runtimes like Docker, containerd, etc.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional

from app.models import Ship, ShipSpec


class ContainerIPAddressError(Exception):
    """
    Exception raised when a container's IP address cannot be determined.

    This typically occurs when:
    - Port mapping configuration is incorrect (for host mode drivers)
    - Network configuration issues prevent IP assignment
    - Container failed to properly connect to the network
    """

    def __init__(self, container_id: str, ship_id: str, details: str = ""):
        self.container_id = container_id
        self.ship_id = ship_id
        self.details = details
        message = (
            f"Failed to obtain IP address for container {container_id} (ship {ship_id})"
        )
        if details:
            message += f": {details}"
        super().__init__(message)


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
        Stop and remove a ship container, but preserve data for potential restoration.

        For drivers that support data persistence (e.g., Kubernetes with PVC),
        this method should only stop the container while keeping the data intact.
        For drivers without separate data storage (e.g., Docker with host mounts),
        this may only stop the container.

        Args:
            container_id: The ID of the container to stop

        Returns:
            True if successful (or container already removed), False otherwise
        """
        pass

    async def delete_ship_data(self, container_id: str) -> bool:
        """
        Permanently delete a ship's persistent data.

        This method should be called when a ship is being permanently deleted
        and its data is no longer needed.

        **Important Driver-Specific Behavior:**

        - **Docker/Podman drivers**: Default implementation is a NO-OP.
          Host-mounted directories are NOT automatically deleted to prevent
          accidental data loss or security issues. If cleanup is needed,
          administrators should manually remove the ship data directory
          at `{SHIP_DATA_DIR}/{ship_id}/`.

        - **Kubernetes driver**: Deletes the PVC. The actual data retention
          depends on the StorageClass reclaim policy:
          - Retain: Data preserved after PVC deletion
          - Delete: Data deleted with PVC (default for dynamic provisioning)

        Args:
            container_id: The ID of the container/ship

        Returns:
            True if successful (or data already removed), False otherwise
        """
        # Default implementation: no-op for drivers with host mounts
        # This is intentional - deleting host directories automatically
        # could lead to unintended data loss or security issues.
        return True

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

"""
Driver factory for creating container runtime drivers.

This module provides factory functions to instantiate the appropriate
container driver based on configuration.
"""

from typing import Callable, Dict, Optional, Type
import logging

from app.drivers.core.base import ContainerDriver

logger = logging.getLogger(__name__)

# Driver registry mapping driver type to driver class factory
_DRIVER_REGISTRY: Dict[str, Callable[[], ContainerDriver]] = {}

# Planned but not yet implemented driver types
_PLANNED_DRIVERS = {"containerd"}


def _get_driver_registry() -> Dict[str, Callable[[], ContainerDriver]]:
    """
    Lazily populate and return the driver registry.

    Uses lazy imports to avoid circular dependencies and improve startup time.
    """
    if not _DRIVER_REGISTRY:
        from app.drivers.docker.driver import DockerDriver
        from app.drivers.docker.host_driver import DockerHostDriver
        from app.drivers.podman.driver import PodmanDriver
        from app.drivers.podman.host_driver import PodmanHostDriver
        from app.drivers.kubernetes.driver import KubernetesDriver

        _DRIVER_REGISTRY.update(
            {
                "docker": DockerDriver,
                "docker-host": DockerHostDriver,
                "podman": PodmanDriver,
                "podman-host": PodmanHostDriver,
                "kubernetes": KubernetesDriver,
            }
        )
    return _DRIVER_REGISTRY


# Global driver instance
_driver: Optional[ContainerDriver] = None


def create_driver(driver_type: str) -> ContainerDriver:
    """
    Create a container driver instance based on the specified type.

    Args:
        driver_type: One of:
            - "docker": For Bay running inside a Docker container (uses container IPs)
            - "docker-host": For Bay running on the host machine (uses port mapping)
            - "podman": For Podman runtime inside a container (uses container IPs)
            - "podman-host": For Podman runtime on the host (uses port mapping)
            - "kubernetes": For Kubernetes runtime (uses Pod IPs with PVC storage)
            - "containerd": Planned containerd runtime (not yet implemented)

    Returns:
        A ContainerDriver instance

    Raises:
        ValueError: If the driver type is not supported.
        NotImplementedError: If the driver type is planned but not yet implemented.
    """
    registry = _get_driver_registry()

    if driver_type in registry:
        return registry[driver_type]()

    if driver_type in _PLANNED_DRIVERS:
        raise NotImplementedError(
            f"{driver_type} driver is not yet implemented. "
            "Please use one of: " + ", ".join(sorted(registry))
        )

    raise ValueError(
        f"Unknown driver type: {driver_type}. "
        "Supported types: " + ", ".join(sorted(registry.keys() | _PLANNED_DRIVERS))
    )


def set_driver(driver: ContainerDriver) -> None:
    """
    Explicitly set the global container driver instance.

    This function provides a controlled way to set the global driver,
    making it easier to transition to dependency injection in the future.

    Args:
        driver: The ContainerDriver instance to set as the global driver
    """
    global _driver
    _driver = driver


def get_driver() -> ContainerDriver:
    """
    Get the global container driver instance.

    Returns:
        The global ContainerDriver instance

    Raises:
        RuntimeError: If the driver has not been initialized
    """
    global _driver
    if _driver is None:
        raise RuntimeError(
            "Container driver not initialized. Call initialize_driver() first."
        )
    return _driver


async def initialize_driver(driver_type: str) -> ContainerDriver:
    """
    Initialize and set the global container driver.

    Args:
        driver_type: The type of driver to create

    Returns:
        The initialized ContainerDriver instance
    """
    driver = create_driver(driver_type)
    await driver.initialize()
    set_driver(driver)
    logger.info("Container driver initialized: %s", driver_type)
    return driver


async def close_driver() -> None:
    """Close the global container driver."""
    global _driver
    if _driver is not None:
        await _driver.close()
        _driver = None
        logger.info("Container driver closed")

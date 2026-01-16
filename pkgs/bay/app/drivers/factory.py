"""
Driver factory for creating container runtime drivers.

This module provides factory functions to instantiate the appropriate
container driver based on configuration.
"""

from typing import Optional
import logging

from app.drivers.base import ContainerDriver

logger = logging.getLogger(__name__)

# Global driver instance
_driver: Optional[ContainerDriver] = None


def create_driver(driver_type: str) -> ContainerDriver:
    """
    Create a container driver instance based on the specified type.
    
    Args:
        driver_type: The type of driver to create ("docker", "containerd", etc.)
        
    Returns:
        A ContainerDriver instance
        
    Raises:
        ValueError: If the driver type is not supported
    """
    if driver_type == "docker":
        from app.drivers.docker_driver import DockerDriver
        return DockerDriver()
    elif driver_type == "containerd":
        # Placeholder for future containerd implementation
        raise NotImplementedError(
            "Containerd driver is not yet implemented. "
            "Please use 'docker' driver or implement ContainerdDriver."
        )
    else:
        raise ValueError(
            f"Unknown driver type: {driver_type}. "
            f"Supported types: docker, containerd"
        )


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
            "Container driver not initialized. "
            "Call initialize_driver() first."
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
    global _driver
    _driver = create_driver(driver_type)
    await _driver.initialize()
    logger.info(f"Container driver initialized: {driver_type}")
    return _driver


async def close_driver() -> None:
    """Close the global container driver."""
    global _driver
    if _driver is not None:
        await _driver.close()
        _driver = None
        logger.info("Container driver closed")

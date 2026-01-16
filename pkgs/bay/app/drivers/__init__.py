"""
Container Driver abstraction layer for Bay.

This module provides a pluggable driver architecture for container runtimes,
allowing Bay to work with Docker, containerd, or other container runtimes.
"""

from app.drivers.base import ContainerDriver, ContainerInfo
from app.drivers.factory import get_driver, create_driver, initialize_driver, close_driver

__all__ = [
    "ContainerDriver",
    "ContainerInfo",
    "get_driver",
    "create_driver",
    "initialize_driver",
    "close_driver",
]

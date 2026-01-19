"""
Shared utilities for container drivers.

This module provides common helper functions used across different
container runtime drivers (Docker, Podman, etc.).
"""

import os
import logging
from typing import Dict

from app.config import settings

logger = logging.getLogger(__name__)


def parse_memory_string(memory_str: str) -> int:
    """
    Parse a memory string (e.g., '512m', '1g', '1024kb') to bytes.

    Supported suffixes:
        - k, kb: kilobytes
        - m, mb: megabytes
        - g, gb: gigabytes
        - No suffix: bytes

    Args:
        memory_str: The memory string to parse

    Returns:
        The memory value in bytes

    Raises:
        ValueError: If the memory string format is invalid

    Examples:
        >>> parse_memory_string("512m")
        536870912
        >>> parse_memory_string("1g")
        1073741824
        >>> parse_memory_string("1024")
        1024
    """
    memory_str = memory_str.lower().strip()

    if memory_str.endswith("kb"):
        return int(memory_str[:-2]) * 1024
    if memory_str.endswith("k"):
        return int(memory_str[:-1]) * 1024
    if memory_str.endswith("mb"):
        return int(memory_str[:-2]) * 1024 * 1024
    if memory_str.endswith("m"):
        return int(memory_str[:-1]) * 1024 * 1024
    if memory_str.endswith("gb"):
        return int(memory_str[:-2]) * 1024 * 1024 * 1024
    if memory_str.endswith("g"):
        return int(memory_str[:-1]) * 1024 * 1024 * 1024

    # Assume bytes if no suffix
    return int(memory_str)


def ensure_ship_dirs(ship_id: str) -> Dict[str, str]:
    """
    Ensure ship data directories exist with proper permissions.

    Creates the home and metadata directories for a ship if they don't exist,
    and sets permissions to 0o777 to allow the container to manage users
    and directories.

    Args:
        ship_id: The ID of the ship

    Returns:
        A dictionary with 'home' and 'metadata' keys containing the
        absolute paths to those directories

    Raises:
        Exception: If permissions cannot be set on the directories
    """
    ship_data_dir = os.path.expanduser(f"{settings.ship_data_dir}/{ship_id}")
    home_dir = f"{ship_data_dir}/home"
    metadata_dir = f"{ship_data_dir}/metadata"

    # Create directories if they don't exist
    os.makedirs(home_dir, exist_ok=True)
    os.makedirs(metadata_dir, exist_ok=True)

    # Set permissions to allow container to manage users and directories
    # Using 0o777 to ensure ship container (running as root) can create/manage user directories
    try:
        os.chmod(home_dir, 0o777)
        os.chmod(metadata_dir, 0o777)
    except Exception as e:
        logger.error(
            "Failed to set permissions for ship %s directories: %s", ship_id, e
        )
        raise

    return {"home": home_dir, "metadata": metadata_dir}


def ship_data_exists(ship_id: str) -> bool:
    """
    Check if ship data directories exist.

    Args:
        ship_id: The ID of the ship

    Returns:
        True if both home and metadata directories exist, False otherwise
    """
    ship_data_dir = os.path.expanduser(f"{settings.ship_data_dir}/{ship_id}")
    home_dir = f"{ship_data_dir}/home"
    metadata_dir = f"{ship_data_dir}/metadata"

    return os.path.exists(home_dir) and os.path.exists(metadata_dir)

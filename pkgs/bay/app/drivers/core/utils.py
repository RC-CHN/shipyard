"""
Shared utilities for container drivers.

This module provides common helper functions used across different
container runtime drivers (Docker, Podman, etc.).
"""

import os
import re
import logging
from typing import Dict

from app.config import settings

logger = logging.getLogger(__name__)


# Unit multipliers for memory parsing (lowercase keys)
# Ordered by suffix length (longer suffixes first) to ensure correct matching
_UNIT_MULTIPLIERS = {
    # Two-letter suffixes
    "ki": 1024,
    "mi": 1024**2,
    "gi": 1024**3,
    "kb": 1024,
    "mb": 1024**2,
    "gb": 1024**3,
    # Single-letter suffixes
    "k": 1024,
    "m": 1024**2,
    "g": 1024**3,
    # No suffix = bytes
    "": 1,
}


def parse_memory_string(memory_str: str) -> int:
    """
    Parse a memory string (e.g., '512m', '1g', '512Mi', '1Gi') to bytes.

    Supported suffixes (case-insensitive):
        - Ki, k, kb: kibibytes (1024 bytes)
        - Mi, m, mb: mebibytes (1024^2 bytes)
        - Gi, g, gb: gibibytes (1024^3 bytes)
        - No suffix: bytes

    Note: This function supports both Docker-style (m, g) and
    Kubernetes-style (Mi, Gi) memory units.

    Args:
        memory_str: The memory string to parse

    Returns:
        The memory value in bytes

    Raises:
        ValueError: If the memory string format is invalid

    Examples:
        >>> parse_memory_string("512m")
        536870912
        >>> parse_memory_string("512Mi")
        536870912
        >>> parse_memory_string("1g")
        1073741824
        >>> parse_memory_string("1Gi")
        1073741824
        >>> parse_memory_string("1024")
        1024
    """
    memory_str = memory_str.strip()
    original_str = memory_str

    # Use regex to split number and unit
    match = re.fullmatch(r"(\d+)([a-zA-Z]*)", memory_str)
    if not match:
        raise ValueError(
            f"Invalid memory format: '{original_str}'. "
            "Supported formats: 512Mi, 1Gi, 512m, 1g, 512mb, 1gb, or plain bytes."
        )

    number_str, unit_str = match.groups()
    unit_lower = unit_str.lower()

    if unit_lower not in _UNIT_MULTIPLIERS:
        raise ValueError(
            f"Invalid memory format: '{original_str}'. "
            "Supported formats: 512Mi, 1Gi, 512m, 1g, 512mb, 1gb, or plain bytes."
        )

    return int(number_str) * _UNIT_MULTIPLIERS[unit_lower]


# Minimum memory in bytes (128 MiB)
MIN_MEMORY_BYTES = 128 * 1024 * 1024  # 134217728 bytes

# Minimum disk size in bytes (100 MiB)
MIN_DISK_BYTES = 100 * 1024 * 1024  # 104857600 bytes


def parse_disk_string(disk_str: str) -> int:
    """
    Parse a disk/storage string (e.g., '1Gi', '10G', '512Mi') to bytes.

    Uses the same parsing logic as memory strings for consistency.

    Args:
        disk_str: The disk string to parse

    Returns:
        The disk value in bytes

    Raises:
        ValueError: If the disk string format is invalid

    Examples:
        >>> parse_disk_string("1Gi")
        1073741824
        >>> parse_disk_string("10G")
        10737418240
        >>> parse_disk_string("512Mi")
        536870912
    """
    return parse_memory_string(disk_str)


def parse_and_enforce_minimum_disk(disk_str: str) -> int:
    """
    Parse a disk string and enforce a minimum of 100 MiB.

    If the requested disk size is less than 100 MiB, it will be automatically
    increased to 100 MiB and a warning will be logged.

    Args:
        disk_str: The disk string to parse

    Returns:
        The disk value in bytes, at least 100 MiB

    Examples:
        >>> parse_and_enforce_minimum_disk("50m")  # Too small, will be 100 MiB
        104857600
        >>> parse_and_enforce_minimum_disk("1Gi")  # OK, returns as-is
        1073741824
    """
    disk_bytes = parse_disk_string(disk_str)

    if disk_bytes < MIN_DISK_BYTES:
        logger.warning(
            "Requested disk '%s' (%d bytes) is below minimum 100 MiB. "
            "Automatically increased to 100 MiB.",
            disk_str,
            disk_bytes,
        )
        return MIN_DISK_BYTES

    return disk_bytes


def parse_and_enforce_minimum_memory(memory_str: str) -> int:
    """
    Parse a memory string and enforce a minimum of 128 MiB.

    If the requested memory is less than 128 MiB, it will be automatically
    increased to 128 MiB and a warning will be logged.

    Args:
        memory_str: The memory string to parse

    Returns:
        The memory value in bytes, at least 128 MiB

    Examples:
        >>> parse_and_enforce_minimum_memory("64m")  # Too small, will be 128 MiB
        134217728
        >>> parse_and_enforce_minimum_memory("512Mi")  # OK, returns as-is
        536870912
    """
    memory_bytes = parse_memory_string(memory_str)

    if memory_bytes < MIN_MEMORY_BYTES:
        logger.warning(
            "Requested memory '%s' (%d bytes) is below minimum 128 MiB. "
            "Automatically increased to 128 MiB.",
            memory_str,
            memory_bytes,
        )
        return MIN_MEMORY_BYTES

    return memory_bytes


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

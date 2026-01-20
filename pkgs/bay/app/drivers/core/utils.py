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
    original_str = memory_str  # Keep original for error messages
    memory_str_lower = memory_str.lower()

    # Kubernetes binary units (case-insensitive: Ki, Mi, Gi)
    if memory_str_lower.endswith("ki"):
        return int(memory_str[:-2]) * 1024
    if memory_str_lower.endswith("mi"):
        return int(memory_str[:-2]) * 1024 * 1024
    if memory_str_lower.endswith("gi"):
        return int(memory_str[:-2]) * 1024 * 1024 * 1024

    # Docker/common units (kb, mb, gb)
    if memory_str_lower.endswith("kb"):
        return int(memory_str[:-2]) * 1024
    if memory_str_lower.endswith("mb"):
        return int(memory_str[:-2]) * 1024 * 1024
    if memory_str_lower.endswith("gb"):
        return int(memory_str[:-2]) * 1024 * 1024 * 1024

    # Single letter units (k, m, g) - must check after two-letter suffixes
    if memory_str_lower.endswith("k"):
        return int(memory_str[:-1]) * 1024
    if memory_str_lower.endswith("m"):
        return int(memory_str[:-1]) * 1024 * 1024
    if memory_str_lower.endswith("g"):
        return int(memory_str[:-1]) * 1024 * 1024 * 1024

    # Try to parse as bytes (no suffix)
    try:
        return int(memory_str)
    except ValueError:
        raise ValueError(
            f"Invalid memory format: '{original_str}'. "
            "Supported formats: 512Mi, 1Gi, 512m, 1g, 512mb, 1gb, or plain bytes."
        )


# Minimum memory in bytes (128 MiB)
MIN_MEMORY_BYTES = 128 * 1024 * 1024  # 134217728 bytes


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

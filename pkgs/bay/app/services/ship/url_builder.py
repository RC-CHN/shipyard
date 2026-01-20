"""
URL builder utilities for Ship communication.

This module provides functions to build URLs for communicating with Ship containers,
handling different driver modes (docker vs docker-host).
"""

from typing import Optional
from app.config import settings


def build_ship_url(ship_address: str, path: str = "") -> str:
    """
    Build a complete URL for communicating with a Ship container.

    This function handles the difference between:
    - docker mode: ip_address is like "172.18.0.2" (need to add :8123)
    - docker-host mode: ip_address is like "127.0.0.1:39314" (already has port)

    Args:
        ship_address: The ship's address (IP or IP:port)
        path: The API path (e.g., "health", "shell/exec")

    Returns:
        Complete URL like "http://172.18.0.2:8123/health"
    """
    # Check if the address already includes a port
    if ":" in ship_address:
        # docker-host mode: address already has port (e.g., "127.0.0.1:39314")
        base_url = f"http://{ship_address}"
    else:
        # docker mode: need to add the default port
        base_url = f"http://{ship_address}:{settings.ship_container_port}"

    # Add path if provided
    if path:
        # Ensure path doesn't have leading slash (we'll add it)
        path = path.lstrip("/")
        return f"{base_url}/{path}"

    return base_url


def build_health_url(ship_address: str) -> str:
    """Build the health check URL for a Ship."""
    return build_ship_url(ship_address, "health")


def build_exec_url(ship_address: str, operation_type: str) -> str:
    """Build the exec URL for a Ship operation."""
    return build_ship_url(ship_address, operation_type)


def build_upload_url(ship_address: str) -> str:
    """Build the file upload URL for a Ship."""
    return build_ship_url(ship_address, "upload")


def build_download_url(ship_address: str) -> str:
    """Build the file download URL for a Ship."""
    return build_ship_url(ship_address, "download")

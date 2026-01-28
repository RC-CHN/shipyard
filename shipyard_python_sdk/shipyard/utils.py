"""
Shipyard Python SDK - Convenience functions
"""

from typing import Optional
from .types import Spec
from .client import ShipyardClient
from .session import SessionShip


async def create_session_ship(
    ttl: int = 3600,
    spec: Optional[Spec] = None,
    max_session_num: int | None = None,
    endpoint_url: Optional[str] = None,
    access_token: Optional[str] = None,
    session_id: Optional[str] = None,
    force_create: bool = False,
) -> SessionShip:
    """
    Convenience function to create a SessionShip directly

    Args:
        ttl: Time to live in seconds (default: 1 hour)
        spec: Ship specifications for resource allocation
        max_session_num: Deprecated. Ignored (Shipyard enforces 1:1 binding).
        endpoint_url: Bay API endpoint URL (can also be set via SHIPYARD_ENDPOINT env var)
        access_token: Access token for authentication (can also be set via SHIPYARD_TOKEN env var)
        session_id: Session ID (if not provided, a random one will be generated)
        force_create: If True, skip reuse logic and always create new container

    Returns:
        SessionShip: The created ship session
    """
    client = ShipyardClient(endpoint_url, access_token)
    return await client.create_ship(
        ttl=ttl,
        spec=spec,
        max_session_num=max_session_num,
        session_id=session_id,
        force_create=force_create,
    )

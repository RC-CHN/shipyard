"""Statistics and version information endpoints"""

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from typing import Optional
import tomli
from pathlib import Path
from app.database import db_service
from app.auth import verify_token

router = APIRouter()


def get_version() -> str:
    """Get version from pyproject.toml"""
    try:
        pyproject_path = Path(__file__).parent.parent.parent / "pyproject.toml"
        with open(pyproject_path, "rb") as f:
            data = tomli.load(f)
        return data.get("project", {}).get("version", "unknown")
    except Exception:
        return "unknown"


class ShipStats(BaseModel):
    total: int
    running: int
    stopped: int
    creating: int


class SessionStats(BaseModel):
    total: int
    active: int


class OverviewResponse(BaseModel):
    service: str
    version: str
    status: str
    ships: ShipStats
    sessions: SessionStats


@router.get("/stat")
async def get_stat():
    """Get service statistics and version information"""
    return {
        "service": "bay",
        "version": get_version(),
        "status": "running",
        "author": "AstrBot Team",
    }


@router.get("/stat/overview", response_model=OverviewResponse)
async def get_overview(token: str = Depends(verify_token)):
    """Get system overview statistics for dashboard"""
    from sqlmodel import select
    from app.models import Ship, SessionShip, ShipStatus
    from datetime import datetime, timezone

    session = db_service.get_session()
    try:
        # Get ship statistics
        all_ships_result = await session.execute(select(Ship))
        all_ships = list(all_ships_result.scalars().all())
        
        running_ships = [s for s in all_ships if s.status == ShipStatus.RUNNING]
        stopped_ships = [s for s in all_ships if s.status == ShipStatus.STOPPED]
        creating_ships = [s for s in all_ships if s.status == ShipStatus.CREATING]
        
        # Get session statistics
        all_sessions_result = await session.execute(select(SessionShip))
        all_sessions = list(all_sessions_result.scalars().all())
        
        now = datetime.now(timezone.utc)
        # Handle both timezone-aware and timezone-naive datetimes
        def is_session_active(s) -> bool:
            expires_at = s.expires_at
            if expires_at is None:
                return False
            # If expires_at is naive, make it aware (assume UTC)
            if expires_at.tzinfo is None:
                expires_at = expires_at.replace(tzinfo=timezone.utc)
            return expires_at > now
        
        active_sessions = [s for s in all_sessions if is_session_active(s)]
        
        return OverviewResponse(
            service="bay",
            version=get_version(),
            status="running",
            ships=ShipStats(
                total=len(all_ships),
                running=len(running_ships),
                stopped=len(stopped_ships),
                creating=len(creating_ships)
            ),
            sessions=SessionStats(
                total=len(all_sessions),
                active=len(active_sessions)
            )
        )
    finally:
        await session.close()

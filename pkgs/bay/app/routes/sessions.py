"""Session management endpoints for dashboard"""

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime, timezone
from app.database import db_service
from app.auth import verify_token

router = APIRouter()


def is_session_active(expires_at: datetime, now: datetime) -> bool:
    """Check if session is active, handling timezone-naive datetimes"""
    if expires_at is None:
        return False
    # If expires_at is naive, make it aware (assume UTC)
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    return expires_at > now


class SessionResponse(BaseModel):
    id: str
    session_id: str
    ship_id: str
    created_at: datetime
    last_activity: datetime
    expires_at: datetime
    initial_ttl: int
    is_active: bool


class SessionListResponse(BaseModel):
    sessions: List[SessionResponse]
    total: int


class ShipSessionsResponse(BaseModel):
    ship_id: str
    sessions: List[SessionResponse]
    total: int


@router.get("/sessions", response_model=SessionListResponse)
async def list_sessions(token: str = Depends(verify_token)):
    """List all sessions"""
    from sqlmodel import select
    from app.models import SessionShip

    session = db_service.get_session()
    try:
        result = await session.execute(select(SessionShip))
        all_sessions = list(result.scalars().all())
        
        now = datetime.now(timezone.utc)
        sessions = [
            SessionResponse(
                id=s.id,
                session_id=s.session_id,
                ship_id=s.ship_id,
                created_at=s.created_at,
                last_activity=s.last_activity,
                expires_at=s.expires_at,
                initial_ttl=s.initial_ttl,
                is_active=is_session_active(s.expires_at, now)
            )
            for s in all_sessions
        ]
        
        return SessionListResponse(
            sessions=sessions,
            total=len(sessions)
        )
    finally:
        await session.close()


@router.get("/sessions/{session_id}", response_model=SessionResponse)
async def get_session_detail(session_id: str, token: str = Depends(verify_token)):
    """Get session details by session_id"""
    from sqlmodel import select
    from app.models import SessionShip

    session = db_service.get_session()
    try:
        statement = select(SessionShip).where(SessionShip.session_id == session_id)
        result = await session.execute(statement)
        session_ship = result.scalar_one_or_none()
        
        if not session_ship:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Session not found"
            )
        
        now = datetime.now(timezone.utc)
        return SessionResponse(
            id=session_ship.id,
            session_id=session_ship.session_id,
            ship_id=session_ship.ship_id,
            created_at=session_ship.created_at,
            last_activity=session_ship.last_activity,
            expires_at=session_ship.expires_at,
            initial_ttl=session_ship.initial_ttl,
            is_active=is_session_active(session_ship.expires_at, now)
        )
    finally:
        await session.close()


@router.get("/ship/{ship_id}/sessions", response_model=ShipSessionsResponse)
async def get_ship_sessions(ship_id: str, token: str = Depends(verify_token)):
    """Get all sessions for a specific ship"""
    from sqlmodel import select
    from app.models import SessionShip, Ship

    session = db_service.get_session()
    try:
        # Verify ship exists
        ship_result = await session.execute(select(Ship).where(Ship.id == ship_id))
        ship = ship_result.scalar_one_or_none()
        
        if not ship:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Ship not found"
            )
        
        # Get sessions for this ship
        statement = select(SessionShip).where(SessionShip.ship_id == ship_id)
        result = await session.execute(statement)
        ship_sessions = list(result.scalars().all())
        
        now = datetime.now(timezone.utc)
        sessions = [
            SessionResponse(
                id=s.id,
                session_id=s.session_id,
                ship_id=s.ship_id,
                created_at=s.created_at,
                last_activity=s.last_activity,
                expires_at=s.expires_at,
                initial_ttl=s.initial_ttl,
                is_active=is_session_active(s.expires_at, now)
            )
            for s in ship_sessions
        ]
        
        return ShipSessionsResponse(
            ship_id=ship_id,
            sessions=sessions,
            total=len(sessions)
        )
    finally:
        await session.close()


class ExtendSessionTTLRequest(BaseModel):
    ttl: int  # TTL in seconds


@router.post("/sessions/{session_id}/extend-ttl", response_model=SessionResponse)
async def extend_session_ttl(
    session_id: str,
    request: ExtendSessionTTLRequest,
    token: str = Depends(verify_token)
):
    """Extend the TTL for a session"""
    if request.ttl <= 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="TTL must be greater than 0"
        )
    
    session_ship = await db_service.extend_session_ttl(session_id, request.ttl)
    
    if not session_ship:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Session not found"
        )
    
    now = datetime.now(timezone.utc)
    return SessionResponse(
        id=session_ship.id,
        session_id=session_ship.session_id,
        ship_id=session_ship.ship_id,
        created_at=session_ship.created_at,
        last_activity=session_ship.last_activity,
        expires_at=session_ship.expires_at,
        initial_ttl=session_ship.initial_ttl,
        is_active=is_session_active(session_ship.expires_at, now)
    )


@router.delete("/sessions/{session_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_session(session_id: str, token: str = Depends(verify_token)):
    """Force terminate a session"""
    from sqlmodel import select
    from app.models import SessionShip

    session = db_service.get_session()
    try:
        statement = select(SessionShip).where(SessionShip.session_id == session_id)
        result = await session.execute(statement)
        session_ship = result.scalar_one_or_none()
        
        if not session_ship:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Session not found"
            )
        
        # Try to decrement the ship's session count (may fail if ship already deleted)
        try:
            await db_service.decrement_ship_session_count(session_ship.ship_id)
        except Exception:
            # Ship may have been deleted, ignore the error
            pass
        
        # Delete the session
        await session.delete(session_ship)
        await session.commit()
    finally:
        await session.close()

"""Session management endpoints for dashboard"""

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime, timezone
from app.database import db_service
from app.auth import verify_token
from app.models import ExecutionHistoryResponse, ExecutionHistoryEntry

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

        # Delete the session
        await session.delete(session_ship)
        await session.commit()
    finally:
        await session.close()


@router.get("/sessions/{session_id}/history", response_model=ExecutionHistoryResponse)
async def get_execution_history(
    session_id: str,
    exec_type: Optional[str] = None,
    success_only: bool = False,
    limit: int = 100,
    offset: int = 0,
    token: str = Depends(verify_token),
):
    """Get execution history for a session.

    This enables agents to retrieve their successful execution paths
    for skill library construction (inspired by VOYAGER).

    Args:
        session_id: The session ID
        exec_type: Filter by type ('python' or 'shell')
        success_only: If True, only return successful executions
        limit: Maximum number of entries to return
        offset: Number of entries to skip
    """
    entries, total = await db_service.get_execution_history(
        session_id=session_id,
        exec_type=exec_type,
        success_only=success_only,
        limit=limit,
        offset=offset,
    )

    return ExecutionHistoryResponse(
        entries=[
            ExecutionHistoryEntry.model_validate(e)
            for e in entries
        ],
        total=total,
    )


@router.get("/sessions/{session_id}/history/{execution_id}", response_model=ExecutionHistoryEntry)
async def get_execution_by_id(
    session_id: str,
    execution_id: str,
    token: str = Depends(verify_token),
):
    """Get a specific execution record by ID.

    Args:
        session_id: The session ID
        execution_id: The execution history ID
    """
    entry = await db_service.get_execution_by_id(session_id, execution_id)

    if not entry:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Execution not found"
        )

    return ExecutionHistoryEntry.model_validate(entry)


@router.get("/sessions/{session_id}/history/last", response_model=ExecutionHistoryEntry)
async def get_last_execution(
    session_id: str,
    exec_type: Optional[str] = None,
    token: str = Depends(verify_token),
):
    """Get the most recent execution for a session.

    Args:
        session_id: The session ID
        exec_type: Filter by type ('python' or 'shell'), optional
    """
    entry = await db_service.get_last_execution(session_id, exec_type)

    if not entry:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No execution history found"
        )

    return ExecutionHistoryEntry.model_validate(entry)


class AnnotateExecutionRequest(BaseModel):
    """Request model for annotating an execution."""
    description: Optional[str] = None
    tags: Optional[str] = None
    notes: Optional[str] = None


@router.patch("/sessions/{session_id}/history/{execution_id}", response_model=ExecutionHistoryEntry)
async def annotate_execution(
    session_id: str,
    execution_id: str,
    request: AnnotateExecutionRequest,
    token: str = Depends(verify_token),
):
    """Annotate an execution record with metadata.

    Use this to add descriptions, tags, or notes to an execution after
    it has been recorded. Useful for skill library construction.

    Args:
        session_id: The session ID
        execution_id: The execution history ID
        request: Annotation data (description, tags, notes)
    """
    entry = await db_service.update_execution_history(
        session_id=session_id,
        execution_id=execution_id,
        description=request.description,
        tags=request.tags,
        notes=request.notes,
    )

    if not entry:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Execution not found"
        )

    return ExecutionHistoryEntry.model_validate(entry)

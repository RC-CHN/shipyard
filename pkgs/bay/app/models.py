from sqlmodel import SQLModel, Field, Column, DateTime
from pydantic import BaseModel, ConfigDict
from typing import Optional, Dict, Any
from datetime import datetime, timezone
import uuid


# Ship status constants
class ShipStatus:
    """Ship status constants"""
    STOPPED = 0   # Ship is stopped, container not running
    RUNNING = 1   # Ship is running, container active
    CREATING = 2  # Ship is being created, container not yet ready


# Database Models
class ShipBase(SQLModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()), primary_key=True)
    status: int = Field(default=ShipStatus.CREATING, description="0: stopped, 1: running, 2: creating")
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_column=Column(DateTime(timezone=True)),
    )
    updated_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_column=Column(DateTime(timezone=True)),
    )
    container_id: Optional[str] = Field(default=None)
    ip_address: Optional[str] = Field(default=None)
    ttl: int = Field(description="Time to live in seconds")
    expires_at: Optional[datetime] = Field(
        default=None,
        description="When this ship will expire based on all sessions",
        sa_column=None,  # Not stored in database, calculated dynamically
    )


class Ship(ShipBase, table=True):
    __tablename__ = "ships"  # type: ignore


class SessionShipBase(SQLModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()), primary_key=True)
    session_id: str = Field(description="Session ID")
    ship_id: str = Field(foreign_key="ships.id", description="Ship ID")
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_column=Column(DateTime(timezone=True)),
    )
    last_activity: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_column=Column(DateTime(timezone=True)),
    )
    expires_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_column=Column(DateTime(timezone=True)),
        description="When this session's access to the ship expires",
    )
    initial_ttl: int = Field(
        description="Initial TTL in seconds for this session (used for refresh)"
    )


class SessionShip(SessionShipBase, table=True):
    __tablename__ = "session_ships"  # type: ignore


# Execution History for skill library support
class ExecutionHistoryBase(SQLModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()), primary_key=True)
    session_id: str = Field(description="Session ID", index=True)
    exec_type: str = Field(description="Execution type: 'python' or 'shell'")
    code: Optional[str] = Field(default=None, description="Executed code (for python)")
    command: Optional[str] = Field(default=None, description="Executed command (for shell)")
    success: bool = Field(description="Whether execution succeeded")
    execution_time_ms: Optional[int] = Field(default=None, description="Execution time in ms")
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_column=Column(DateTime(timezone=True)),
    )
    # Skill library metadata fields
    description: Optional[str] = Field(
        default=None,
        description="Human-readable description of what this execution does"
    )
    tags: Optional[str] = Field(
        default=None,
        description="Comma-separated tags for categorization (e.g., 'data-processing,pandas')"
    )
    notes: Optional[str] = Field(
        default=None,
        description="Agent notes/annotations about this execution"
    )


class ExecutionHistory(ExecutionHistoryBase, table=True):
    __tablename__ = "execution_history"  # type: ignore


# API Request/Response Models
class ShipSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")

    cpus: Optional[float] = Field(None, gt=0, description="CPU allocation")
    memory: Optional[str] = Field(
        None, description="Memory allocation, e.g., '512m', '1g'"
    )
    disk: Optional[str] = Field(
        None,
        description="Disk/storage allocation, e.g., '1Gi', '10G'. "
        "For Docker/Podman: used as storage driver quota if supported. "
        "For Kubernetes: used as PVC size.",
    )


class CreateShipRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    ttl: int = Field(..., gt=0, description="Time to live in seconds")
    spec: Optional[ShipSpec] = Field(None, description="Ship specifications")
    force_create: bool = Field(
        default=False,
        description="If True, skip all reuse logic and always create a new container"
    )


class ShipResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    status: int
    created_at: datetime
    updated_at: datetime
    container_id: Optional[str]
    ip_address: Optional[str]
    ttl: int
    expires_at: Optional[datetime] = Field(
        None, description="When this ship will expire based on session expiration"
    )


class ExecRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type: str = Field(
        ..., description="Operation type, e.g., 'shell/exec', 'ipython/exec'"
    )
    payload: Optional[Dict[str, Any]] = Field(None, description="Operation payload")


class ExecResponse(BaseModel):
    success: bool
    data: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    execution_id: Optional[str] = Field(
        default=None,
        description="Execution history ID for this operation (only for python/shell exec)"
    )


class ExtendTTLRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    ttl: int = Field(..., gt=0, description="New TTL in seconds")


class StartShipRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    ttl: int = Field(default=3600, gt=0, description="TTL in seconds for the started ship")


class ErrorResponse(BaseModel):
    detail: str


class LogsResponse(BaseModel):
    logs: str


class UploadFileResponse(BaseModel):
    success: bool
    message: str
    file_path: Optional[str] = None
    error: Optional[str] = None


class DownloadFileResponse(BaseModel):
    success: bool
    message: str
    error: Optional[str] = None


# Execution History API Models
class ExecutionHistoryEntry(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    session_id: str
    exec_type: str
    code: Optional[str] = None
    command: Optional[str] = None
    success: bool
    execution_time_ms: Optional[int] = None
    created_at: datetime
    # Skill library metadata fields
    description: Optional[str] = None
    tags: Optional[str] = None
    notes: Optional[str] = None


class ExecutionHistoryResponse(BaseModel):
    entries: list[ExecutionHistoryEntry]
    total: int

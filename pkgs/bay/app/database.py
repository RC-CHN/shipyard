from sqlmodel import SQLModel, select
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine, AsyncSession
from sqlalchemy.pool import StaticPool
from typing import Optional, List
from app.config import settings
from app.models import Ship, SessionShip, ShipStatus
from datetime import datetime, timezone


class DatabaseService:
    def __init__(self):
        self.engine: Optional[AsyncEngine] = None

    async def initialize(self):
        """Initialize database connection"""
        self.engine = create_async_engine(
            settings.database_url,
            echo=settings.debug,
            future=True,
            # SQLite specific settings
            poolclass=StaticPool,
            connect_args={"check_same_thread": False},
        )

    async def create_tables(self):
        """Create database tables"""
        if not self.engine:
            await self.initialize()

        async with self.engine.begin() as conn:  # type: ignore
            await conn.run_sync(SQLModel.metadata.create_all)

    def get_session(self) -> AsyncSession:
        """Get database session"""
        if not self.engine:
            raise RuntimeError("Database not initialized")

        return AsyncSession(self.engine, expire_on_commit=False)

    async def create_ship(self, ship: Ship) -> Ship:
        """Create a new ship record"""
        session = self.get_session()
        try:
            session.add(ship)
            await session.commit()
            await session.refresh(ship)
            return ship
        finally:
            await session.close()

    async def get_ship(self, ship_id: str) -> Optional[Ship]:
        """Get ship by ID"""
        session = self.get_session()
        try:
            statement = select(Ship).where(Ship.id == ship_id)
            result = await session.execute(statement)
            return result.scalar_one_or_none()
        finally:
            await session.close()

    async def update_ship(self, ship: Ship) -> Ship:
        """Update ship record"""
        ship.updated_at = datetime.now(timezone.utc)
        session = self.get_session()
        try:
            # Use merge() instead of add() to handle detached objects
            # merge() copies the state of the given instance into a persistent instance
            merged_ship = await session.merge(ship)
            await session.commit()
            await session.refresh(merged_ship)
            return merged_ship
        finally:
            await session.close()

    async def delete_ship(self, ship_id: str) -> bool:
        """Delete ship by ID"""
        session = self.get_session()
        try:
            statement = select(Ship).where(Ship.id == ship_id)
            result = await session.execute(statement)
            ship = result.scalar_one_or_none()

            if ship:
                await session.delete(ship)
                await session.commit()
                return True
            return False
        finally:
            await session.close()

    async def list_active_ships(self) -> List[Ship]:
        """List all active ships (running and creating)"""
        session = self.get_session()
        try:
            # Include both RUNNING and CREATING status ships
            statement = select(Ship).where(
                (Ship.status == ShipStatus.RUNNING) | (Ship.status == ShipStatus.CREATING)
            )
            result = await session.execute(statement)
            return list(result.scalars().all())
        finally:
            await session.close()

    async def list_all_ships(self) -> List[Ship]:
        """List all ships (including stopped)"""
        session = self.get_session()
        try:
            statement = select(Ship).order_by(Ship.created_at.desc())
            result = await session.execute(statement)
            return list(result.scalars().all())
        finally:
            await session.close()

    async def count_active_ships(self) -> int:
        """Count active ships"""
        ships = await self.list_active_ships()
        return len(ships)

    # SessionShip operations
    async def create_session_ship(self, session_ship: SessionShip) -> SessionShip:
        """Create a new session-ship relationship"""
        session = self.get_session()
        try:
            session.add(session_ship)
            await session.commit()
            await session.refresh(session_ship)
            return session_ship
        finally:
            await session.close()

    async def get_session_ship(
        self, session_id: str, ship_id: str
    ) -> Optional[SessionShip]:
        """Get session-ship relationship"""
        session = self.get_session()
        try:
            statement = select(SessionShip).where(
                SessionShip.session_id == session_id, SessionShip.ship_id == ship_id
            )
            result = await session.execute(statement)
            return result.scalar_one_or_none()
        finally:
            await session.close()

    async def get_sessions_for_ship(self, ship_id: str) -> List[SessionShip]:
        """Get all sessions for a ship"""
        session = self.get_session()
        try:
            statement = select(SessionShip).where(SessionShip.ship_id == ship_id)
            result = await session.execute(statement)
            return list(result.scalars().all())
        finally:
            await session.close()

    async def update_session_activity(
        self, session_id: str, ship_id: str
    ) -> Optional[SessionShip]:
        """Update last activity for a session"""
        session = self.get_session()
        try:
            statement = select(SessionShip).where(
                SessionShip.session_id == session_id, SessionShip.ship_id == ship_id
            )
            result = await session.execute(statement)
            session_ship = result.scalar_one_or_none()

            if session_ship:
                session_ship.last_activity = datetime.now(timezone.utc)
                session.add(session_ship)
                await session.commit()
                await session.refresh(session_ship)

            return session_ship
        finally:
            await session.close()

    async def update_session_ship(self, session_ship: SessionShip) -> SessionShip:
        """Update session-ship relationship"""
        session = self.get_session()
        try:
            # Use merge() instead of add() to handle detached objects
            merged_session_ship = await session.merge(session_ship)
            await session.commit()
            await session.refresh(merged_session_ship)
            return merged_session_ship
        finally:
            await session.close()

    async def find_ship_for_session(self, session_id: str) -> Optional[Ship]:
        """Find a running ship that belongs to this session (1:1 binding)."""
        session = self.get_session()
        try:
            # With 1:1 binding, each session has exactly one ship
            statement = (
                select(Ship)
                .join(SessionShip, Ship.id == SessionShip.ship_id)
                .where(
                    SessionShip.session_id == session_id,
                    Ship.status == ShipStatus.RUNNING,
                )
            )
            result = await session.execute(statement)
            return result.scalars().first()
        finally:
            await session.close()

    async def find_active_ship_for_session(self, session_id: str) -> Optional[Ship]:
        """Find an active running ship that this session has access to.
        
        If the session has access to multiple running ships, returns the most recently updated one.
        """
        session = self.get_session()
        try:
            # Find RUNNING ships that this session has access to
            # Order by updated_at desc to get the most recently used one
            statement = (
                select(Ship)
                .join(SessionShip, Ship.id == SessionShip.ship_id)
                .where(
                    SessionShip.session_id == session_id,
                    Ship.status == ShipStatus.RUNNING,
                )
                .order_by(Ship.updated_at.desc())
            )
            result = await session.execute(statement)
            # Use scalars().first() instead of scalar_one_or_none() to handle multiple results
            return result.scalars().first()
        finally:
            await session.close()

    async def find_stopped_ship_for_session(self, session_id: str) -> Optional[Ship]:
        """Find a stopped ship that belongs to this session.
        
        If the session has access to multiple stopped ships, returns the most recently updated one.
        """
        session = self.get_session()
        try:
            # Find STOPPED ships that this session has access to
            # Order by updated_at desc to get the most recently stopped one
            statement = (
                select(Ship)
                .join(SessionShip, Ship.id == SessionShip.ship_id)
                .where(
                    SessionShip.session_id == session_id,
                    Ship.status == ShipStatus.STOPPED,
                )
                .order_by(Ship.updated_at.desc())
            )
            result = await session.execute(statement)
            # Use scalars().first() instead of scalar_one_or_none() to handle multiple results
            return result.scalars().first()
        finally:
            await session.close()

    async def delete_sessions_for_ship(self, ship_id: str) -> List[str]:
        """Delete all session-ship relationships for a ship and return deleted session IDs"""
        session = self.get_session()
        try:
            # First, get all session IDs for this ship
            statement = select(SessionShip).where(SessionShip.ship_id == ship_id)
            result = await session.execute(statement)
            session_ships = list(result.scalars().all())
            
            deleted_session_ids = [ss.session_id for ss in session_ships]
            
            # Delete all session-ship relationships
            for ss in session_ships:
                await session.delete(ss)
            
            await session.commit()
            return deleted_session_ids
        finally:
            await session.close()

    async def extend_session_ttl(
        self, session_id: str, ttl: int
    ) -> Optional[SessionShip]:
        """Extend the TTL for a session by updating expires_at"""
        from datetime import timedelta
        
        session = self.get_session()
        try:
            statement = select(SessionShip).where(SessionShip.session_id == session_id)
            result = await session.execute(statement)
            session_ship = result.scalar_one_or_none()

            if session_ship:
                now = datetime.now(timezone.utc)
                session_ship.expires_at = now + timedelta(seconds=ttl)
                session_ship.last_activity = now
                session.add(session_ship)
                await session.commit()
                await session.refresh(session_ship)

            return session_ship
        finally:
            await session.close()

    async def expire_sessions_for_ship(self, ship_id: str) -> int:
        """Mark all sessions for a ship as expired by setting expires_at to current time.
        
        This is called when a ship is stopped to ensure session status
        reflects the actual container state.
        
        Args:
            ship_id: The ship ID
            
        Returns:
            Number of sessions updated
        """
        session = self.get_session()
        try:
            statement = select(SessionShip).where(SessionShip.ship_id == ship_id)
            result = await session.execute(statement)
            session_ships = list(result.scalars().all())
            
            now = datetime.now(timezone.utc)
            updated_count = 0
            
            for ss in session_ships:
                # Only update if session is still active (expires_at > now)
                expires_at = ss.expires_at
                if expires_at is not None:
                    if expires_at.tzinfo is None:
                        expires_at = expires_at.replace(tzinfo=timezone.utc)
                    if expires_at > now:
                        ss.expires_at = now
                        session.add(ss)
                        updated_count += 1
            
            if updated_count > 0:
                await session.commit()
            
            return updated_count
        finally:
            await session.close()

    async def find_warm_pool_ship(self) -> Optional[Ship]:
        """Find an available ship from the warm pool (running ship with no session)."""
        session = self.get_session()
        try:
            # Find running ships that have no session attached
            statement = (
                select(Ship)
                .outerjoin(SessionShip, Ship.id == SessionShip.ship_id)
                .where(
                    Ship.status == ShipStatus.RUNNING,
                    SessionShip.id == None,  # noqa: E711
                )
                .order_by(Ship.created_at.asc())  # Oldest first (FIFO)
            )
            result = await session.execute(statement)
            return result.scalars().first()
        finally:
            await session.close()

    async def count_warm_pool_ships(self) -> int:
        """Count ships in the warm pool (running ships with no session)."""
        session = self.get_session()
        try:
            statement = (
                select(Ship)
                .outerjoin(SessionShip, Ship.id == SessionShip.ship_id)
                .where(
                    Ship.status == ShipStatus.RUNNING,
                    SessionShip.id == None,  # noqa: E711
                )
            )
            result = await session.execute(statement)
            return len(list(result.scalars().all()))
        finally:
            await session.close()


db_service = DatabaseService()

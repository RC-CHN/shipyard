import asyncio
import logging
from typing import Optional

from app.database import db_service
from app.drivers import get_driver
from app.models import ShipStatus

logger = logging.getLogger(__name__)


class StatusChecker:
    """Background worker to check ship container status and sync with database"""

    def __init__(self, check_interval: int = 60):
        """
        Initialize status checker

        Args:
            check_interval: Interval in seconds between status checks (default: 60)
        """
        self.check_interval = check_interval
        self._task: Optional[asyncio.Task] = None
        self._running = False

    async def start(self):
        """Start the background status checker"""
        if self._running:
            logger.warning("Status checker is already running")
            return

        self._running = True
        self._task = asyncio.create_task(self._run())
        logger.info(
            f"Status checker started with interval of {self.check_interval} seconds"
        )

    async def stop(self):
        """Stop the background status checker"""
        if not self._running:
            return

        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        logger.info("Status checker stopped")

    async def _run(self):
        """Main loop for status checking"""
        while self._running:
            try:
                await self._check_all_ships()
            except Exception as e:
                logger.error(f"Error in status checker: {e}", exc_info=True)

            # Wait for next check
            try:
                await asyncio.sleep(self.check_interval)
            except asyncio.CancelledError:
                break

    async def _check_all_ships(self):
        """Check status of all active ships and update database if needed"""
        try:
            # Get all ships from database (running and creating only for status sync)
            ships = await db_service.list_active_ships()

            if ships:
                logger.info(f"Checking status of {len(ships)} active ships")
            else:
                logger.debug("No active ships to check")

            updated_count = 0
            for ship in ships:
                # Skip ships that are still being created
                # These haven't finished initialization yet and shouldn't be checked
                if ship.status == ShipStatus.CREATING:
                    logger.debug(f"Skipping ship {ship.id} - still in CREATING status")
                    continue
                
                # Check if container is actually running
                if ship.container_id:
                    is_running = await get_driver().is_container_running(
                        ship.container_id
                    )

                    # If ship is marked as running but container is not, update status
                    if ship.status == ShipStatus.RUNNING and not is_running:
                        logger.warning(
                            f"Ship {ship.id} is marked as running but container {ship.container_id} is not running. Updating status to stopped."
                        )
                        ship.status = ShipStatus.STOPPED
                        await db_service.update_ship(ship)
                        
                        # Expire all sessions for this ship so they show as inactive
                        expired_count = await db_service.expire_sessions_for_ship(ship.id)
                        if expired_count > 0:
                            logger.info(f"Expired {expired_count} session(s) for stopped ship {ship.id}")
                        
                        updated_count += 1

                    # If ship is marked as stopped but container is running, update status
                    elif ship.status == ShipStatus.STOPPED and is_running:
                        logger.info(
                            f"Ship {ship.id} is marked as stopped but container {ship.container_id} is running. Updating status to running."
                        )
                        ship.status = ShipStatus.RUNNING
                        await db_service.update_ship(ship)
                        updated_count += 1
                else:
                    # Ship has no container_id but is marked as running
                    if ship.status == ShipStatus.RUNNING:
                        logger.warning(
                            f"Ship {ship.id} is marked as running but has no container_id. Updating status to stopped."
                        )
                        ship.status = ShipStatus.STOPPED
                        await db_service.update_ship(ship)
                        
                        # Expire all sessions for this ship so they show as inactive
                        expired_count = await db_service.expire_sessions_for_ship(ship.id)
                        if expired_count > 0:
                            logger.info(f"Expired {expired_count} session(s) for stopped ship {ship.id}")
                        
                        updated_count += 1

            if updated_count > 0:
                logger.info(f"Updated status for {updated_count} ships")
            else:
                logger.debug("All ships are in sync with actual container status")
            
            # Also check for stopped ships with active sessions (data inconsistency fix)
            await self._fix_stopped_ships_with_active_sessions()

        except Exception as e:
            logger.error(f"Failed to check ship status: {e}", exc_info=True)

    async def _fix_stopped_ships_with_active_sessions(self):
        """Fix data inconsistency: expire sessions for stopped ships that still have active sessions.
        
        This handles the case where a ship was stopped before the expire_sessions_for_ship
        logic was added, or if there was any other data inconsistency.
        """
        from datetime import datetime, timezone
        
        try:
            # Get all stopped ships
            all_ships = await db_service.list_all_ships()
            stopped_ships = [s for s in all_ships if s.status == ShipStatus.STOPPED]
            
            if not stopped_ships:
                return
            
            now = datetime.now(timezone.utc)
            fixed_count = 0
            
            for ship in stopped_ships:
                # Check if this ship has any active sessions
                sessions = await db_service.get_sessions_for_ship(ship.id)
                active_sessions = []
                
                for s in sessions:
                    expires_at = s.expires_at
                    if expires_at is not None:
                        if expires_at.tzinfo is None:
                            expires_at = expires_at.replace(tzinfo=timezone.utc)
                        if expires_at > now:
                            active_sessions.append(s)
                
                if active_sessions:
                    # Expire these sessions
                    expired_count = await db_service.expire_sessions_for_ship(ship.id)
                    if expired_count > 0:
                        logger.info(
                            f"Fixed {expired_count} orphaned active session(s) for stopped ship {ship.id}"
                        )
                        fixed_count += expired_count
            
            if fixed_count > 0:
                logger.info(f"Fixed {fixed_count} total orphaned active sessions")
        
        except Exception as e:
            logger.error(f"Failed to fix stopped ships with active sessions: {e}", exc_info=True)


# Global status checker instance
status_checker = StatusChecker(check_interval=60)

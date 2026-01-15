import asyncio
import logging
from typing import Optional
from app.database import db_service
from app.services.docker_service import docker_service

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
            # Get all ships from database (both active and stopped)
            ships = await db_service.list_active_ships()

            if not ships:
                logger.debug("No active ships to check")
                return

            logger.info(f"Checking status of {len(ships)} active ships")

            updated_count = 0
            for ship in ships:
                # Check if container is actually running
                if ship.container_id:
                    is_running = await docker_service.is_container_running(
                        ship.container_id
                    )

                    # If ship is marked as running but container is not, update status
                    if ship.status == 1 and not is_running:
                        logger.warning(
                            f"Ship {ship.id} is marked as running but container {ship.container_id} is not running. Updating status to stopped."
                        )
                        ship.status = 0
                        await db_service.update_ship(ship)
                        updated_count += 1

                    # If ship is marked as stopped but container is running, update status
                    elif ship.status == 0 and is_running:
                        logger.info(
                            f"Ship {ship.id} is marked as stopped but container {ship.container_id} is running. Updating status to running."
                        )
                        ship.status = 1
                        await db_service.update_ship(ship)
                        updated_count += 1
                else:
                    # Ship has no container_id but is marked as running
                    if ship.status == 1:
                        logger.warning(
                            f"Ship {ship.id} is marked as running but has no container_id. Updating status to stopped."
                        )
                        ship.status = 0
                        await db_service.update_ship(ship)
                        updated_count += 1

            if updated_count > 0:
                logger.info(f"Updated status for {updated_count} ships")
            else:
                logger.debug("All ships are in sync with actual container status")

        except Exception as e:
            logger.error(f"Failed to check ship status: {e}", exc_info=True)


# Global status checker instance
status_checker = StatusChecker(check_interval=60)

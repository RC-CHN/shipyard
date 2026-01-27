"""
Ship service module.

This module provides the ShipService class for managing Ship container lifecycle
and operations, including creation, deletion, execution, and file operations.
"""

import asyncio
import logging
from typing import Optional, List, Dict

from datetime import datetime, timedelta, timezone

from app.config import settings
from app.models import (
    Ship,
    ShipStatus,
    CreateShipRequest,
    ExecRequest,
    ExecResponse,
    SessionShip,
    UploadFileResponse,
)
from app.database import db_service
from app.drivers import get_driver
from app.services.ship.http_client import (
    wait_for_ship_ready,
    forward_request_to_ship,
    upload_file_to_ship,
    download_file_from_ship,
)

logger = logging.getLogger(__name__)


class ShipService:
    """Service for managing Ship lifecycle and operations."""

    def __init__(self):
        # Track cleanup tasks for each ship to enable cancellation
        self._cleanup_tasks: Dict[str, asyncio.Task] = {}
        # Warm pool replenishment task
        self._warm_pool_task: Optional[asyncio.Task] = None

    async def start_warm_pool(self):
        """Start the warm pool replenishment background task."""
        if not settings.warm_pool_enabled:
            logger.info("Warm pool is disabled")
            return

        if self._warm_pool_task and not self._warm_pool_task.done():
            return  # Already running

        self._warm_pool_task = asyncio.create_task(self._warm_pool_replenisher())
        logger.info(f"Warm pool started (min_size={settings.warm_pool_min_size})")

    async def stop_warm_pool(self):
        """Stop the warm pool replenishment background task."""
        if self._warm_pool_task and not self._warm_pool_task.done():
            self._warm_pool_task.cancel()
            try:
                await self._warm_pool_task
            except asyncio.CancelledError:
                pass
        self._warm_pool_task = None

    async def _warm_pool_replenisher(self):
        """Background task to maintain warm pool size."""
        while True:
            try:
                await self._replenish_warm_pool()
                await asyncio.sleep(settings.warm_pool_replenish_interval)
            except asyncio.CancelledError:
                logger.info("Warm pool replenisher stopped")
                break
            except Exception as e:
                logger.error(f"Warm pool replenisher error: {e}")
                await asyncio.sleep(settings.warm_pool_replenish_interval)

    async def _replenish_warm_pool(self):
        """Ensure warm pool has enough ships."""
        current_count = await db_service.count_warm_pool_ships()
        active_count = await db_service.count_active_ships()

        # Calculate how many ships we need to create
        needed = settings.warm_pool_min_size - current_count

        # Respect max ship limit
        available_slots = settings.max_ship_num - active_count
        to_create = min(needed, available_slots, settings.warm_pool_max_size - current_count)

        if to_create > 0:
            logger.info(f"Replenishing warm pool: creating {to_create} ships (current={current_count})")
            for _ in range(to_create):
                try:
                    await self._create_warm_pool_ship()
                except Exception as e:
                    logger.error(f"Failed to create warm pool ship: {e}")
                    break  # Stop on first failure

    async def _create_warm_pool_ship(self) -> Ship:
        """Create a ship for the warm pool (no session attached)."""
        ship = Ship(ttl=settings.default_ship_ttl, status=ShipStatus.CREATING)
        ship = await db_service.create_ship(ship)

        try:
            container_info = await get_driver().create_ship_container(ship, None)
            ship.container_id = container_info.container_id
            ship.ip_address = container_info.ip_address
            ship = await db_service.update_ship(ship)

            if not ship.ip_address:
                await db_service.delete_ship(ship.id)
                raise RuntimeError("Ship has no IP address")

            is_ready = await wait_for_ship_ready(ship.ip_address)
            if not is_ready:
                if ship.container_id:
                    await get_driver().stop_ship_container(ship.container_id)
                await db_service.delete_ship(ship.id)
                raise RuntimeError("Ship failed health check")

            ship.status = ShipStatus.RUNNING
            ship = await db_service.update_ship(ship)

            logger.info(f"Warm pool ship {ship.id} created and ready")
            return ship

        except Exception as e:
            await db_service.delete_ship(ship.id)
            raise

    async def create_ship(self, request: CreateShipRequest, session_id: str) -> Ship:
        """Create a new ship or reuse an existing one for the session.

        With 1:1 Session-Ship binding:
        1. If session has an active ship, return it
        2. If session has a stopped ship with data, restore it
        3. Try to allocate from warm pool
        4. Create a new ship on-demand
        """
        # If force_create is True, skip all reuse logic
        if not request.force_create:
            # First, check if this session already has an active running ship
            active_ship = await db_service.find_active_ship_for_session(session_id)
            if active_ship:
                # Verify container is actually running
                if active_ship.container_id and await get_driver().is_container_running(
                    active_ship.container_id
                ):
                    await db_service.update_session_activity(session_id, active_ship.id)
                    logger.info(f"Session {session_id} reusing active ship {active_ship.id}")
                    return active_ship
                else:
                    # Container not running, mark as stopped and restore
                    logger.warning(f"Ship {active_ship.id} container not running, restoring...")
                    active_ship.status = ShipStatus.STOPPED
                    await db_service.update_ship(active_ship)
                    return await self._restore_ship(active_ship, request, session_id)

            # Second, check for stopped ship with existing data
            stopped_ship = await db_service.find_stopped_ship_for_session(session_id)
            if stopped_ship and get_driver().ship_data_exists(stopped_ship.id):
                logger.info(f"Restoring stopped ship {stopped_ship.id} for session {session_id}")
                return await self._restore_ship(stopped_ship, request, session_id)

            # Third, try to allocate from warm pool
            if settings.warm_pool_enabled:
                warm_ship = await db_service.find_warm_pool_ship()
                if warm_ship:
                    logger.info(f"Allocating warm pool ship {warm_ship.id} to session {session_id}")
                    return await self._assign_ship_to_session(warm_ship, request, session_id)
        else:
            logger.info(f"force_create=True, skipping reuse logic for session {session_id}")

        # Fourth, create a new ship on-demand
        # Check ship limits
        if settings.behavior_after_max_ship == "reject":
            active_count = await db_service.count_active_ships()
            if active_count >= settings.max_ship_num:
                raise ValueError("Maximum number of ships reached")
        elif settings.behavior_after_max_ship == "wait":
            await self._wait_for_available_slot()

        # Create new ship
        ship = Ship(ttl=request.ttl, status=ShipStatus.CREATING)
        ship = await db_service.create_ship(ship)

        try:
            container_info = await get_driver().create_ship_container(ship, request.spec)
            ship.container_id = container_info.container_id
            ship.ip_address = container_info.ip_address
            ship = await db_service.update_ship(ship)

            if not ship.ip_address:
                logger.error(f"Ship {ship.id} has no IP address")
                await db_service.delete_ship(ship.id)
                raise RuntimeError("Ship has no IP address")

            logger.info(f"Waiting for ship {ship.id} to become ready...")
            is_ready = await wait_for_ship_ready(ship.ip_address)

            if not is_ready:
                logger.error(f"Ship {ship.id} failed health check, cleaning up")
                if ship.container_id:
                    await get_driver().stop_ship_container(ship.container_id)
                await db_service.delete_ship(ship.id)
                raise RuntimeError(
                    f"Ship failed to become ready within {settings.ship_health_check_timeout} seconds"
                )

            # Assign to session
            ship = await self._assign_ship_to_session(ship, request, session_id)

            logger.info(f"Ship {ship.id} created successfully for session {session_id}")
            return ship

        except Exception as e:
            await db_service.delete_ship(ship.id)
            logger.error(f"Failed to create ship {ship.id}: {e}")
            raise

    async def _assign_ship_to_session(
        self, ship: Ship, request: CreateShipRequest, session_id: str
    ) -> Ship:
        """Assign a ship to a session (1:1 binding)."""
        expires_at = datetime.now(timezone.utc) + timedelta(seconds=request.ttl)

        session_ship = SessionShip(
            session_id=session_id,
            ship_id=ship.id,
            expires_at=expires_at,
            initial_ttl=request.ttl,
        )
        await db_service.create_session_ship(session_ship)

        # Update ship TTL and status
        ship.ttl = request.ttl
        ship.status = ShipStatus.RUNNING
        ship = await db_service.update_ship(ship)

        # Schedule cleanup
        await self._schedule_cleanup(ship.id, request.ttl)

        return ship

    async def get_ship(self, ship_id: str) -> Optional[Ship]:
        """Get ship by ID."""
        ship = await db_service.get_ship(ship_id)
        if ship:
            # Calculate and set the actual expiration time based on all sessions
            await self._set_ship_expires_at(ship)
        return ship

    async def delete_ship(self, ship_id: str, permanent: bool = False) -> bool:
        """
        Delete/stop a ship.

        By default, this performs a "soft delete" - the container is stopped but
        the database record is preserved (marked as status=0), allowing the ship
        to be restored later with its data intact.

        For permanent deletion (including database record), set permanent=True.

        Args:
            ship_id: The ID of the ship to delete
            permanent: If True, also delete the database record

        Returns:
            True if successful, False if ship not found or already stopped
        """
        ship = await db_service.get_ship(ship_id)
        if not ship:
            return False

        # For soft delete, return False if ship is already stopped
        # (cannot "stop" an already stopped ship)
        if not permanent and ship.status == ShipStatus.STOPPED:
            return False

        # Cancel cleanup task if exists
        if ship_id in self._cleanup_tasks:
            task = self._cleanup_tasks[ship_id]
            if not task.done():
                task.cancel()
            del self._cleanup_tasks[ship_id]

        # Stop container if exists
        if ship.container_id:
            try:
                await get_driver().stop_ship_container(ship.container_id)
            except Exception as e:
                logger.error(f"Failed to stop container for ship {ship_id}: {e}")

        if permanent:
            # Permanent delete: first delete all session-ship relationships, then remove ship from database
            deleted_session_ids = await db_service.delete_sessions_for_ship(ship_id)
            if deleted_session_ids:
                logger.info(f"Deleted {len(deleted_session_ids)} session(s) for ship {ship_id}: {deleted_session_ids}")
            logger.info(f"Permanently deleting ship {ship_id} from database")
            return await db_service.delete_ship(ship_id)
        else:
            # Soft delete: mark as stopped, keep database record for restore
            ship.status = ShipStatus.STOPPED
            ship.container_id = None  # Clear container ID since it's stopped
            await db_service.update_ship(ship)
            
            # Expire all sessions for this ship so they show as inactive
            expired_count = await db_service.expire_sessions_for_ship(ship_id)
            if expired_count > 0:
                logger.info(f"Expired {expired_count} session(s) for stopped ship {ship_id}")
            
            logger.info(f"Ship {ship_id} stopped (soft delete), data preserved for restore")
            return True

    async def extend_ttl(self, ship_id: str, additional_ttl: int) -> Optional[Ship]:
        """Extend ship TTL by adding additional time to all sessions.
        
        Args:
            ship_id: The ship ID
            additional_ttl: Additional time in seconds to add
        
        Returns:
            Updated ship or None if not found
        """
        ship = await db_service.get_ship(ship_id)
        if not ship or ship.status == ShipStatus.STOPPED:
            return None

        # Get all sessions for this ship and extend their expiration times
        all_sessions = await db_service.get_sessions_for_ship(ship_id)
        
        for session in all_sessions:
            # Add additional time to the expiration
            if session.expires_at.tzinfo is None:
                session.expires_at = session.expires_at.replace(tzinfo=timezone.utc)
            session.expires_at = session.expires_at + timedelta(seconds=additional_ttl)
            # Also update initial_ttl to reflect the new base TTL
            session.initial_ttl = session.initial_ttl + additional_ttl
            await db_service.update_session_ship(session)
        
        # Update ship's ttl configuration
        ship.ttl = ship.ttl + additional_ttl
        ship = await db_service.update_ship(ship)

        # Recalculate and reschedule cleanup based on new session expiration times
        await self._recalculate_and_schedule_cleanup(ship_id)
        
        # Set expires_at for the response
        await self._set_ship_expires_at(ship)

        return ship

    async def execute_operation(
        self, ship_id: str, request: ExecRequest, session_id: str
    ) -> ExecResponse:
        """Execute operation on ship."""
        ship = await db_service.get_ship(ship_id)
        if not ship or ship.status != ShipStatus.RUNNING:
            return ExecResponse(success=False, error="Ship not found or not running")

        if not ship.ip_address:
            return ExecResponse(success=False, error="Ship IP address not available")

        # Verify that this session has access to this ship
        session_ship = await db_service.get_session_ship(session_id, ship_id)
        if not session_ship:
            return ExecResponse(
                success=False, error="Session does not have access to this ship"
            )

        # Update last activity for this session
        await db_service.update_session_activity(session_id, ship_id)

        # Forward request to ship container
        result = await forward_request_to_ship(ship.ip_address, request, session_id)

        # Extend TTL after successful operation
        if result.success:
            await self._extend_ttl_after_operation(ship_id, session_id)

        return result

    async def get_logs(self, ship_id: str) -> str:
        """Get ship container logs."""
        ship = await db_service.get_ship(ship_id)
        if not ship or not ship.container_id:
            return ""

        return await get_driver().get_container_logs(ship.container_id)

    async def list_active_ships(self) -> List[Ship]:
        """List all active ships."""
        ships = await db_service.list_active_ships()
        # Calculate and set the actual expiration time for each ship
        for ship in ships:
            await self._set_ship_expires_at(ship)
        return ships

    async def list_all_ships(self) -> List[Ship]:
        """List all ships including stopped ones."""
        ships = await db_service.list_all_ships()
        # Calculate and set the actual expiration time for each ship
        for ship in ships:
            await self._set_ship_expires_at(ship)
        return ships

    async def upload_file(
        self, ship_id: str, file_content: bytes, file_path: str, session_id: str
    ) -> UploadFileResponse:
        """Upload file to ship container."""
        # Check file size limit
        if len(file_content) > settings.max_upload_size:
            return UploadFileResponse(
                success=False,
                error=f"File size ({len(file_content)} bytes) exceeds maximum allowed size ({settings.max_upload_size} bytes)",
                message="File upload failed due to size limit",
            )

        ship = await db_service.get_ship(ship_id)
        if not ship or ship.status != ShipStatus.RUNNING:
            return UploadFileResponse(
                success=False,
                error="Ship not found or not running",
                message="File upload failed",
            )

        if not ship.ip_address:
            return UploadFileResponse(
                success=False,
                error="Ship IP address not available",
                message="File upload failed",
            )

        # Verify that this session has access to this ship
        session_ship = await db_service.get_session_ship(session_id, ship_id)
        if not session_ship:
            return UploadFileResponse(
                success=False,
                error="Session does not have access to this ship",
                message="File upload failed",
            )

        # Update last activity for this session
        await db_service.update_session_activity(session_id, ship_id)

        # Forward file upload to ship container
        result = await upload_file_to_ship(
            ship.ip_address, file_content, file_path, session_id
        )

        # Extend TTL after successful upload
        if result.success:
            await self._extend_ttl_after_operation(ship_id, session_id)

        return result

    async def download_file(
        self, ship_id: str, file_path: str, session_id: str
    ) -> tuple[bool, bytes, str]:
        """Download file from ship container.

        Returns:
            tuple: (success, file_content, error_message)
        """
        ship = await db_service.get_ship(ship_id)
        if not ship or ship.status != ShipStatus.RUNNING:
            return (False, b"", "Ship not found or not running")

        if not ship.ip_address:
            return (False, b"", "Ship IP address not available")

        # Verify that this session has access to this ship
        session_ship = await db_service.get_session_ship(session_id, ship_id)
        if not session_ship:
            return (False, b"", "Session does not have access to this ship")

        # Update last activity for this session
        await db_service.update_session_activity(session_id, ship_id)

        # Forward file download request to ship container
        success, file_content, error = await download_file_from_ship(
            ship.ip_address, file_path, session_id
        )

        # Extend TTL after successful download
        if success:
            await self._extend_ttl_after_operation(ship_id, session_id)

        return (success, file_content, error)

    async def _extend_ttl_after_operation(self, ship_id: str, session_id: str):
        """Extend ship TTL after an operation by refreshing the current session's expiration time."""
        # Get the session information
        session_ship = await db_service.get_session_ship(session_id, ship_id)
        if not session_ship:
            logger.warning(f"Session {session_id} not found for ship {ship_id}")
            return

        # Refresh this session's expiration time using its initial TTL
        new_expires_at = datetime.now(timezone.utc) + timedelta(
            seconds=session_ship.initial_ttl
        )
        session_ship.expires_at = new_expires_at
        await db_service.update_session_ship(session_ship)

        # Recalculate ship's cleanup time based on all sessions
        await self._recalculate_and_schedule_cleanup(ship_id)

        logger.info(
            f"Session {session_id} TTL refreshed for ship {ship_id}, new expires_at: {new_expires_at}"
        )

    async def _recalculate_and_schedule_cleanup(self, ship_id: str):
        """Recalculate ship's TTL based on all sessions' expiration times and reschedule cleanup."""
        # Get all sessions for this ship
        all_sessions = await db_service.get_sessions_for_ship(ship_id)

        if not all_sessions:
            logger.warning(f"No sessions found for ship {ship_id}")
            return

        # Find the maximum expiration time among all sessions
        max_expires_at = max(s.expires_at for s in all_sessions)

        # Ensure max_expires_at is timezone-aware
        if max_expires_at.tzinfo is None:
            max_expires_at = max_expires_at.replace(tzinfo=timezone.utc)

        # Calculate remaining time until expiration
        now = datetime.now(timezone.utc)
        remaining_seconds = (max_expires_at - now).total_seconds()

        # Make sure remaining_seconds is not negative
        if remaining_seconds < 0:
            remaining_seconds = 0

        # Update ship's TTL in database for reference
        ship = await db_service.get_ship(ship_id)
        if ship:
            ship.ttl = int(remaining_seconds)
            await db_service.update_ship(ship)

        # Reschedule cleanup
        await self._schedule_cleanup(ship_id, int(remaining_seconds))

        logger.info(
            f"Ship {ship_id} TTL recalculated: {remaining_seconds}s (expires at {max_expires_at})"
        )

    async def _set_ship_expires_at(self, ship: Ship):
        """Calculate and set ship's expiration time based on all sessions."""
        if ship.status == ShipStatus.STOPPED:
            # Stopped ships don't have an expiration time
            ship.expires_at = None
            return
        
        if ship.status == ShipStatus.CREATING:
            # Creating ships don't have an expiration time yet
            ship.expires_at = None
            return

        # Get all sessions for this ship
        all_sessions = await db_service.get_sessions_for_ship(ship.id)

        if not all_sessions:
            # No sessions, ship expires immediately (or already expired)
            ship.expires_at = None
            return

        # Find the maximum expiration time among all sessions
        max_expires_at = max(s.expires_at for s in all_sessions)

        # Ensure max_expires_at is timezone-aware
        if max_expires_at.tzinfo is None:
            max_expires_at = max_expires_at.replace(tzinfo=timezone.utc)

        ship.expires_at = max_expires_at

    async def _wait_for_available_slot(self):
        """Wait for an available ship slot."""
        max_wait_time = 300  # 5 minutes
        check_interval = 5  # 5 seconds
        waited = 0

        while waited < max_wait_time:
            active_count = await db_service.count_active_ships()
            if active_count < settings.max_ship_num:
                return

            await asyncio.sleep(check_interval)
            waited += check_interval

        raise TimeoutError("Timeout waiting for available ship slot")

    async def _schedule_cleanup(self, ship_id: str, ttl: int):
        """Schedule ship cleanup after TTL expires."""
        # Cancel any existing cleanup task for this ship
        if ship_id in self._cleanup_tasks:
            old_task = self._cleanup_tasks[ship_id]
            if not old_task.done():
                old_task.cancel()
            del self._cleanup_tasks[ship_id]

        # Create and store new cleanup task
        task = asyncio.create_task(self._cleanup_ship_after_delay(ship_id, ttl))
        self._cleanup_tasks[ship_id] = task
        return task

    async def _cleanup_ship_after_delay(self, ship_id: str, ttl: int):
        """Perform ship cleanup after TTL delay."""
        try:
            await asyncio.sleep(ttl)

            ship = await db_service.get_ship(ship_id)
            if ship and ship.status == ShipStatus.RUNNING:
                # Mark as stopped
                ship.status = ShipStatus.STOPPED
                await db_service.update_ship(ship)

                # Stop container (but keep ship_data directory)
                if ship.container_id:
                    await get_driver().stop_ship_container(ship.container_id)

                logger.info(f"Ship {ship_id} cleaned up after TTL expiration")
        except asyncio.CancelledError:
            logger.info(f"Cleanup task for ship {ship_id} was cancelled")
            raise
        except Exception as e:
            logger.error(f"Failed to cleanup ship {ship_id}: {e}")
        finally:
            # Remove task from tracking
            if ship_id in self._cleanup_tasks:
                del self._cleanup_tasks[ship_id]

    async def start_ship(
        self, ship_id: str, session_id: str, ttl: int = 3600
    ) -> Optional[Ship]:
        """
        Start a stopped ship container.
        
        This is a public API that allows manually starting a stopped ship.
        Unlike _restore_ship which is called during create_ship flow,
        this method can be called directly to start any stopped ship.
        
        Args:
            ship_id: The ID of the ship to start
            session_id: The session ID requesting the start
            ttl: TTL for the ship (default 1 hour)
            
        Returns:
            The started Ship, or None if ship not found or already running
        """
        ship = await db_service.get_ship(ship_id)
        if not ship:
            return None
            
        if ship.status == ShipStatus.RUNNING:
            # Already running, just return it
            await self._set_ship_expires_at(ship)
            return ship
            
        if ship.status == ShipStatus.CREATING:
            # Ship is being created, cannot start
            return None
            
        # Ship is stopped, restore it
        try:
            # Create a minimal CreateShipRequest for restoration
            from app.models import CreateShipRequest, ShipSpec
            request = CreateShipRequest(ttl=ttl)
            
            return await self._restore_ship(ship, request, session_id)
        except Exception as e:
            logger.error(f"Failed to start ship {ship_id}: {e}")
            raise

    async def _restore_ship(
        self, ship: Ship, request: CreateShipRequest, session_id: str
    ) -> Ship:
        """Restore a stopped ship by recreating its container."""
        try:
            # Recreate container with existing ship data
            container_info = await get_driver().create_ship_container(
                ship, request.spec
            )

            # Update ship with new container info
            ship.container_id = container_info.container_id
            ship.ip_address = container_info.ip_address
            ship.status = ShipStatus.RUNNING  # Mark as running
            ship.ttl = request.ttl  # Update TTL
            ship = await db_service.update_ship(ship)

            # Wait for ship to be ready
            if not ship.ip_address:
                logger.error(f"Restored ship {ship.id} has no IP address")
                raise RuntimeError("Ship has no IP address")

            logger.info(f"Waiting for restored ship {ship.id} to become ready...")
            is_ready = await wait_for_ship_ready(ship.ip_address)

            if not is_ready:
                # Ship failed to become ready, cleanup
                logger.error(f"Restored ship {ship.id} failed health check")
                if ship.container_id:
                    await get_driver().stop_ship_container(ship.container_id)
                ship.status = ShipStatus.STOPPED
                await db_service.update_ship(ship)
                raise RuntimeError(
                    f"Ship failed to become ready within {settings.ship_health_check_timeout} seconds"
                )

            # Update last activity for this session
            await db_service.update_session_activity(session_id, ship.id)

            # Get the session_ship to refresh its expiration time
            session_ship = await db_service.get_session_ship(session_id, ship.id)
            if session_ship:
                # Refresh this session's expiration time with new TTL
                new_expires_at = datetime.now(timezone.utc) + timedelta(
                    seconds=request.ttl
                )
                session_ship.expires_at = new_expires_at
                session_ship.initial_ttl = request.ttl
                await db_service.update_session_ship(session_ship)

            # Recalculate and schedule TTL cleanup
            await self._recalculate_and_schedule_cleanup(ship.id)

            logger.info(
                f"Ship {ship.id} restored successfully for session {session_id}"
            )
            return ship

        except Exception as e:
            # Mark ship as stopped on failure
            ship.status = ShipStatus.STOPPED
            await db_service.update_ship(ship)
            logger.error(f"Failed to restore ship {ship.id}: {e}")
            raise


# Global ship service instance
ship_service = ShipService()

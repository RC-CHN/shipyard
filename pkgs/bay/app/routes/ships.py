import asyncio
import logging
from fastapi import APIRouter, Depends, HTTPException, status, Header, UploadFile, Form, WebSocket, Query
from fastapi.responses import Response
import aiohttp
from app.models import (
    CreateShipRequest,
    ShipResponse,
    ExecRequest,
    ExecResponse,
    ExtendTTLRequest,
    StartShipRequest,
    LogsResponse,
    UploadFileResponse,
    ShipStatus,
)
from app.services.ship import ship_service
from app.auth import verify_token
from app.database import db_service
from app.config import settings

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/ships", response_model=list[ShipResponse])
async def list_ships(token: str = Depends(verify_token)):
    """Get all ships (including stopped)"""
    ships = await ship_service.list_all_ships()
    return [ShipResponse.model_validate(ship) for ship in ships]


@router.post("/ship", response_model=ShipResponse, status_code=status.HTTP_201_CREATED)
async def create_ship(
    request: CreateShipRequest,
    token: str = Depends(verify_token),
    x_session_id: str = Header(..., alias="X-SESSION-ID"),
):
    """Create a new ship environment"""
    try:
        ship = await ship_service.create_ship(request, x_session_id)
        return ShipResponse.model_validate(ship)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)
        )
    except TimeoutError as e:
        raise HTTPException(status_code=status.HTTP_408_REQUEST_TIMEOUT, detail=str(e))
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)
        )


@router.get("/ship/{ship_id}", response_model=ShipResponse)
async def get_ship(ship_id: str, token: str = Depends(verify_token)):
    """Get ship information"""
    ship = await ship_service.get_ship(ship_id)
    if not ship:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Ship not found"
        )

    return ShipResponse.model_validate(ship)


@router.delete("/ship/{ship_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_ship(ship_id: str, token: str = Depends(verify_token)):
    """Delete ship environment (soft delete - stops container but preserves data)"""
    success = await ship_service.delete_ship(ship_id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Ship not found"
        )


@router.delete("/ship/{ship_id}/permanent", status_code=status.HTTP_204_NO_CONTENT)
async def delete_ship_permanent(ship_id: str, token: str = Depends(verify_token)):
    """Permanently delete ship environment (removes container, data, and database record)"""
    success = await ship_service.delete_ship(ship_id, permanent=True)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Ship not found"
        )


@router.post("/ship/{ship_id}/exec", response_model=ExecResponse)
async def execute_operation(
    ship_id: str,
    request: ExecRequest,
    token: str = Depends(verify_token),
    x_session_id: str = Header(..., alias="X-SESSION-ID"),
):
    """Execute operation on ship"""
    response = await ship_service.execute_operation(ship_id, request, x_session_id)
    if not response.success:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=response.error
        )

    return response


@router.get("/ship/logs/{ship_id}", response_model=LogsResponse)
async def get_ship_logs(ship_id: str, token: str = Depends(verify_token)):
    """Get ship container logs"""
    logs = await ship_service.get_logs(ship_id)
    return LogsResponse(logs=logs)


@router.post("/ship/{ship_id}/extend-ttl", response_model=ShipResponse)
async def extend_ship_ttl(
    ship_id: str, request: ExtendTTLRequest, token: str = Depends(verify_token)
):
    """Extend ship TTL"""
    ship = await ship_service.extend_ttl(ship_id, request.ttl)
    if not ship:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Ship not found"
        )

    return ShipResponse.model_validate(ship)


@router.post("/ship/{ship_id}/start", response_model=ShipResponse)
async def start_ship(
    ship_id: str,
    request: StartShipRequest,
    token: str = Depends(verify_token),
    x_session_id: str = Header(..., alias="X-SESSION-ID"),
):
    """
    Start a stopped ship container.
    
    This endpoint starts a stopped ship by recreating its container.
    The ship data is preserved and will be mounted to the new container.
    """
    try:
        ship = await ship_service.start_ship(ship_id, x_session_id, request.ttl)
        if not ship:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Ship not found or is currently being created"
            )
        return ShipResponse.model_validate(ship)
    except HTTPException:
        # Re-raise HTTP exceptions as-is
        raise
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)
        )
    except RuntimeError as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)
        )
    except Exception as e:
        logger.error(f"Failed to start ship {ship_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to start ship: {str(e)}"
        )


@router.post("/ship/{ship_id}/upload", response_model=UploadFileResponse)
async def upload_file(
    ship_id: str,
    file: UploadFile,
    file_path: str = Form(...),
    token: str = Depends(verify_token),
    x_session_id: str = Header(..., alias="X-SESSION-ID"),
):
    """Upload file to ship container"""
    try:
        # Check file size before reading
        if file.size and file.size > settings.max_upload_size:
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail=f"File size ({file.size} bytes) exceeds maximum allowed size ({settings.max_upload_size} bytes)",
            )

        # Read file content
        file_content = await file.read()

        # Double-check actual file size after reading
        if len(file_content) > settings.max_upload_size:
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail=f"File size ({len(file_content)} bytes) exceeds maximum allowed size ({settings.max_upload_size} bytes)",
            )

        response = await ship_service.upload_file(
            ship_id, file_content, file_path, x_session_id
        )

        if not response.success:
            error_msg = response.error or "Unknown error"
            if "size" in error_msg.lower():
                raise HTTPException(
                    status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                    detail=error_msg,
                )
            elif "not found" in error_msg.lower():
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND, detail=error_msg
                )
            elif "access" in error_msg.lower():
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN, detail=error_msg
                )
            else:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST, detail=error_msg
                )

        return response

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"File upload failed: {str(e)}",
        )


@router.get("/ship/{ship_id}/download")
async def download_file(
    ship_id: str,
    file_path: str,
    token: str = Depends(verify_token),
    x_session_id: str = Header(..., alias="X-SESSION-ID"),
):
    """Download file from ship container"""
    try:
        success, file_content, error = await ship_service.download_file(
            ship_id, file_path, x_session_id
        )

        if not success:
            if "not found" in error.lower():
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=error)
            elif "access" in error.lower():
                raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=error)
            else:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST, detail=error
                )

        # Extract filename from file_path
        filename = file_path.split("/")[-1] if "/" in file_path else file_path

        return Response(
            content=file_content,
            media_type="application/octet-stream",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"File download failed: {str(e)}",
        )


@router.websocket("/ship/{ship_id}/term")
async def websocket_terminal_proxy(
    websocket: WebSocket,
    ship_id: str,
    token: str = Query(...),
    session_id: str = Query(...),
    cols: int = Query(80),
    rows: int = Query(24),
):
    """
    WebSocket proxy for interactive terminal.

    Query parameters:
    - token: Authentication token
    - session_id: The session ID for user isolation
    - cols: Terminal columns (default 80)
    - rows: Terminal rows (default 24)
    """
    # Verify token (simple comparison for WebSocket, as we can't use FastAPI Depends)
    if token != settings.access_token:
        await websocket.close(code=4001, reason="Unauthorized")
        return

    # Get ship info
    ship = await db_service.get_ship(ship_id)
    if not ship or ship.status != ShipStatus.RUNNING:
        await websocket.close(code=4004, reason="Ship not found or not running")
        return

    if not ship.ip_address:
        await websocket.close(code=4004, reason="Ship IP address not available")
        return

    # Verify session has access to this ship
    session_ship = await db_service.get_session_ship(session_id, ship_id)
    if not session_ship:
        await websocket.close(code=4003, reason="Session does not have access to this ship")
        return

    await websocket.accept()

    # Build WebSocket URL to Ship container
    # Handle both docker mode (IP only) and docker-host mode (IP:port)
    if ":" in ship.ip_address:
        # docker-host mode: address already has port (e.g., "127.0.0.1:39314")
        ship_ws_url = f"ws://{ship.ip_address}/term/ws?session_id={session_id}&cols={cols}&rows={rows}"
    else:
        # docker mode: need to add the default port
        ship_ws_url = f"ws://{ship.ip_address}:{settings.ship_container_port}/term/ws?session_id={session_id}&cols={cols}&rows={rows}"

    logger.info(f"Proxying terminal WebSocket for ship {ship_id} to {ship_ws_url}")

    ship_ws = None

    try:
        # Connect to Ship's WebSocket
        async with aiohttp.ClientSession() as http_session:
            async with http_session.ws_connect(ship_ws_url) as ship_ws:
                # Create tasks for bidirectional forwarding
                async def forward_to_ship():
                    """Forward messages from frontend to Ship"""
                    try:
                        while True:
                            message = await websocket.receive()
                            if message["type"] == "websocket.disconnect":
                                break
                            if "text" in message:
                                await ship_ws.send_str(message["text"])
                            elif "bytes" in message:
                                await ship_ws.send_bytes(message["bytes"])
                    except Exception as e:
                        logger.debug(f"Forward to ship ended: {e}")

                async def forward_to_frontend():
                    """Forward messages from Ship to frontend"""
                    try:
                        async for msg in ship_ws:
                            if msg.type == aiohttp.WSMsgType.TEXT:
                                await websocket.send_text(msg.data)
                            elif msg.type == aiohttp.WSMsgType.BINARY:
                                await websocket.send_bytes(msg.data)
                            elif msg.type == aiohttp.WSMsgType.CLOSED:
                                break
                            elif msg.type == aiohttp.WSMsgType.ERROR:
                                logger.error(f"Ship WebSocket error: {ship_ws.exception()}")
                                break
                    except Exception as e:
                        logger.debug(f"Forward to frontend ended: {e}")

                # Run both tasks concurrently
                await asyncio.gather(
                    forward_to_ship(),
                    forward_to_frontend(),
                    return_exceptions=True,
                )

    except aiohttp.ClientError as e:
        logger.error(f"Failed to connect to Ship WebSocket: {e}")
        try:
            await websocket.close(code=1011, reason=f"Failed to connect to Ship: {str(e)}")
        except Exception:
            pass
    except Exception as e:
        logger.error(f"Terminal proxy error: {e}")
        try:
            await websocket.close(code=1011, reason=str(e))
        except Exception:
            pass
    finally:
        # Update session activity
        try:
            await db_service.update_session_activity(session_id, ship_id)
        except Exception:
            pass

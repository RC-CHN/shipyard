"""
HTTP client for Ship communication.

This module provides async HTTP client functions for communicating with
Ship containers, including health checks, command execution, and file transfers.
"""

import aiohttp
import asyncio
import logging
from typing import Optional, Dict, Any, Tuple

from app.config import settings
from app.models import ExecRequest, ExecResponse, UploadFileResponse
from app.services.ship.url_builder import (
    build_health_url,
    build_exec_url,
    build_upload_url,
    build_download_url,
)

logger = logging.getLogger(__name__)


async def wait_for_ship_ready(ship_address: str) -> bool:
    """
    Wait for a Ship to be ready by polling its /health endpoint.

    Args:
        ship_address: The ship's address (IP or IP:port)

    Returns:
        True if ship became ready, False if timeout
    """
    health_url = build_health_url(ship_address)
    max_wait_time = settings.ship_health_check_timeout
    check_interval = settings.ship_health_check_interval
    waited = 0

    logger.info(f"Starting health check for ship at {ship_address}")

    while waited < max_wait_time:
        try:
            timeout = aiohttp.ClientTimeout(total=5)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.get(health_url) as response:
                    if response.status == 200:
                        logger.info(f"Ship at {ship_address} is ready after {waited}s")
                        return True
        except Exception as e:
            logger.debug(f"Health check failed for {ship_address}: {e}")

        await asyncio.sleep(check_interval)
        waited += check_interval

    logger.error(
        f"Ship at {ship_address} failed to become ready within {max_wait_time}s"
    )
    return False


async def forward_request_to_ship(
    ship_address: str, request: ExecRequest, session_id: str
) -> ExecResponse:
    """
    Forward an execution request to a Ship container.

    Args:
        ship_address: The ship's address (IP or IP:port)
        request: The execution request
        session_id: The session ID for the request

    Returns:
        ExecResponse with the result or error
    """
    url = build_exec_url(ship_address, request.type)

    try:
        timeout = aiohttp.ClientTimeout(total=30)
        headers = {"X-SESSION-ID": session_id}
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.post(
                url, json=request.payload or {}, headers=headers
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    return ExecResponse(success=True, data=data)
                else:
                    error_text = await response.text()
                    return ExecResponse(
                        success=False,
                        error=f"Ship returned {response.status}: {error_text}",
                    )

    except aiohttp.ClientError as e:
        logger.error(f"Failed to forward request to ship {ship_address}: {e}")
        return ExecResponse(success=False, error=f"Connection error: {str(e)}")
    except asyncio.TimeoutError:
        return ExecResponse(success=False, error="Request timeout")
    except Exception as e:
        logger.error(f"Unexpected error forwarding to ship {ship_address}: {e}")
        return ExecResponse(success=False, error=f"Internal error: {str(e)}")


async def upload_file_to_ship(
    ship_address: str, file_content: bytes, file_path: str, session_id: str
) -> UploadFileResponse:
    """
    Upload a file to a Ship container.

    Args:
        ship_address: The ship's address (IP or IP:port)
        file_content: The file content as bytes
        file_path: The destination path in the container
        session_id: The session ID for the request

    Returns:
        UploadFileResponse with the result or error
    """
    url = build_upload_url(ship_address)

    try:
        # Create multipart form data
        data = aiohttp.FormData()
        data.add_field(
            "file",
            file_content,
            filename="upload",
            content_type="application/octet-stream",
        )
        data.add_field("file_path", file_path)

        timeout = aiohttp.ClientTimeout(total=120)  # 2 minutes for file upload
        headers = {"X-SESSION-ID": session_id}

        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.post(url, data=data, headers=headers) as response:
                if response.status == 200:
                    resp = await response.json()
                    return UploadFileResponse(
                        success=True,
                        message="File uploaded successfully",
                        file_path=resp.get("file_path", "unknown"),
                    )
                else:
                    error_text = await response.text()
                    return UploadFileResponse(
                        success=False,
                        error=f"Ship returned {response.status}: {error_text}",
                        message="File upload failed",
                    )

    except aiohttp.ClientError as e:
        logger.error(f"Failed to upload file to ship {ship_address}: {e}")
        return UploadFileResponse(
            success=False,
            error=f"Connection error: {str(e)}",
            message="File upload failed",
        )
    except asyncio.TimeoutError:
        return UploadFileResponse(
            success=False, error="File upload timeout", message="File upload failed"
        )
    except Exception as e:
        logger.error(f"Unexpected error uploading file to ship {ship_address}: {e}")
        return UploadFileResponse(
            success=False,
            error=f"Internal error: {str(e)}",
            message="File upload failed",
        )


async def download_file_from_ship(
    ship_address: str, file_path: str, session_id: str
) -> Tuple[bool, bytes, str]:
    """
    Download a file from a Ship container.

    Args:
        ship_address: The ship's address (IP or IP:port)
        file_path: The source path in the container
        session_id: The session ID for the request

    Returns:
        Tuple of (success, file_content, error_message)
    """
    url = build_download_url(ship_address)

    try:
        timeout = aiohttp.ClientTimeout(total=120)  # 2 minutes for file download
        headers = {"X-SESSION-ID": session_id}
        params = {"file_path": file_path}

        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.get(url, params=params, headers=headers) as response:
                if response.status == 200:
                    file_content = await response.read()
                    return (True, file_content, "")
                else:
                    error_text = await response.text()
                    return (
                        False,
                        b"",
                        f"Ship returned {response.status}: {error_text}",
                    )

    except aiohttp.ClientError as e:
        logger.error(f"Failed to download file from ship {ship_address}: {e}")
        return (False, b"", f"Connection error: {str(e)}")
    except asyncio.TimeoutError:
        return (False, b"", "File download timeout")
    except Exception as e:
        logger.error(f"Unexpected error downloading file from ship {ship_address}: {e}")
        return (False, b"", f"Internal error: {str(e)}")

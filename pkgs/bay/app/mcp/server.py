"""
Shipyard MCP Server

This module provides an MCP server that allows MCP-compatible clients
(Claude Desktop, ChatGPT Desktop, Cursor, VS Code, etc.) to interact
with Shipyard sandboxes.

Supported transports:
- stdio (default): For local integration with desktop apps
- streamable-http: For remote/hosted deployments

Usage:
    # stdio mode (default)
    python -m app.mcp.run

    # HTTP mode
    python -m app.mcp.run --transport http --port 8000

Environment variables:
    SHIPYARD_ENDPOINT: Bay API URL (default: http://localhost:8156)
    SHIPYARD_TOKEN: Access token for Bay API authentication
"""

import os
import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass
from typing import Optional

import aiohttp

from mcp.server.fastmcp import Context, FastMCP


@dataclass
class ShipyardContext:
    """Application context with shared resources."""

    http_session: aiohttp.ClientSession
    bay_url: str
    access_token: str
    ship_id: Optional[str] = None
    session_id: str = ""

    def __post_init__(self):
        if not self.session_id:
            self.session_id = str(uuid.uuid4())


@asynccontextmanager
async def shipyard_lifespan(server: FastMCP) -> AsyncIterator[ShipyardContext]:
    """Manage application lifecycle with type-safe context."""
    bay_url = os.getenv("SHIPYARD_ENDPOINT", "http://localhost:8156").rstrip("/")
    access_token = os.getenv("SHIPYARD_TOKEN", "")

    if not access_token:
        raise ValueError(
            "SHIPYARD_TOKEN environment variable is required. "
            "Set it to your Bay API access token."
        )

    headers = {"Authorization": f"Bearer {access_token}"}
    http_session = aiohttp.ClientSession(headers=headers)

    try:
        yield ShipyardContext(
            http_session=http_session,
            bay_url=bay_url,
            access_token=access_token,
        )
    finally:
        await http_session.close()


# Create MCP server with lifespan management
mcp = FastMCP(
    "Shipyard",
    version="1.0.0",
    lifespan=shipyard_lifespan,
)


async def _ensure_ship(ctx: ShipyardContext, ttl: int = 3600) -> str:
    """Ensure we have an active ship, create one if needed."""
    if ctx.ship_id:
        # Check if ship is still running
        async with ctx.http_session.get(
            f"{ctx.bay_url}/ship/{ctx.ship_id}"
        ) as resp:
            if resp.status == 200:
                ship_data = await resp.json()
                if ship_data.get("status") == 1:  # RUNNING
                    return ctx.ship_id

    # Create new ship
    payload = {"ttl": ttl}
    headers = {"X-SESSION-ID": ctx.session_id}

    async with ctx.http_session.post(
        f"{ctx.bay_url}/ship", json=payload, headers=headers
    ) as resp:
        if resp.status == 201:
            ship_data = await resp.json()
            ctx.ship_id = ship_data["id"]
            return ctx.ship_id
        else:
            error = await resp.text()
            raise Exception(f"Failed to create ship: {error}")


async def _exec_operation(
    ctx: ShipyardContext,
    operation_type: str,
    payload: dict,
) -> dict:
    """Execute an operation on the ship."""
    ship_id = await _ensure_ship(ctx)

    request_payload = {"type": operation_type, "payload": payload}
    headers = {"X-SESSION-ID": ctx.session_id}

    async with ctx.http_session.post(
        f"{ctx.bay_url}/ship/{ship_id}/exec",
        json=request_payload,
        headers=headers,
    ) as resp:
        if resp.status == 200:
            return await resp.json()
        else:
            error = await resp.text()
            raise Exception(f"Execution failed: {error}")


def _get_ctx(ctx: Context) -> ShipyardContext:
    """Get ShipyardContext from request context."""
    return ctx.request_context.lifespan_context


# =============================================================================
# MCP Tools
# =============================================================================


@mcp.tool()
async def execute_python(
    code: str,
    timeout: int = 30,
    ctx: Context = None,
) -> str:
    """Execute Python code in an isolated sandbox.

    The sandbox provides a full Python environment with common libraries
    pre-installed. Code execution is isolated and secure.

    Args:
        code: Python code to execute
        timeout: Execution timeout in seconds (default: 30)

    Returns:
        Execution result including stdout, stderr, and any return value
    """
    shipyard_ctx = _get_ctx(ctx)
    result = await _exec_operation(
        shipyard_ctx,
        "ipython/exec",
        {"code": code, "timeout": timeout},
    )
    data = result.get("data", result)

    # Format output for LLM consumption
    output_parts = []
    if data.get("stdout"):
        output_parts.append(f"Output:\n{data['stdout']}")
    if data.get("stderr"):
        output_parts.append(f"Errors:\n{data['stderr']}")
    if data.get("result"):
        output_parts.append(f"Result: {data['result']}")

    if not output_parts:
        return "Code executed successfully (no output)"

    return "\n\n".join(output_parts)


@mcp.tool()
async def execute_shell(
    command: str,
    cwd: str = None,
    timeout: int = 30,
    ctx: Context = None,
) -> str:
    """Execute a shell command in an isolated sandbox.

    The sandbox provides a Linux environment with common tools available.
    Command execution is isolated and secure.

    Args:
        command: Shell command to execute
        cwd: Working directory (relative to workspace, optional)
        timeout: Execution timeout in seconds (default: 30)

    Returns:
        Command output including stdout and stderr
    """
    shipyard_ctx = _get_ctx(ctx)
    payload = {"command": command, "timeout": timeout}
    if cwd:
        payload["cwd"] = cwd

    result = await _exec_operation(shipyard_ctx, "shell/exec", payload)
    data = result.get("data", result)

    # Format output
    output_parts = []
    if data.get("stdout"):
        output_parts.append(data["stdout"])
    if data.get("stderr"):
        output_parts.append(f"stderr: {data['stderr']}")
    if data.get("exit_code", 0) != 0:
        output_parts.append(f"Exit code: {data['exit_code']}")

    return "\n".join(output_parts) if output_parts else "Command completed (no output)"


@mcp.tool()
async def read_file(
    path: str,
    ctx: Context = None,
) -> str:
    """Read file content from the sandbox.

    Args:
        path: File path (relative to workspace or absolute)

    Returns:
        File content as string
    """
    shipyard_ctx = _get_ctx(ctx)
    result = await _exec_operation(
        shipyard_ctx,
        "fs/read_file",
        {"path": path},
    )
    data = result.get("data", result)
    return data.get("content", str(data))


@mcp.tool()
async def write_file(
    path: str,
    content: str,
    ctx: Context = None,
) -> str:
    """Write content to a file in the sandbox.

    Creates the file if it doesn't exist, or overwrites if it does.
    Parent directories are created automatically.

    Args:
        path: File path (relative to workspace or absolute)
        content: Content to write

    Returns:
        Confirmation message
    """
    shipyard_ctx = _get_ctx(ctx)
    result = await _exec_operation(
        shipyard_ctx,
        "fs/write_file",
        {"path": path, "content": content},
    )
    data = result.get("data", result)
    if data.get("success", True):
        return f"File written: {path}"
    return f"Failed to write file: {data}"


@mcp.tool()
async def list_files(
    path: str = ".",
    ctx: Context = None,
) -> str:
    """List files and directories in the sandbox.

    Args:
        path: Directory path (default: current workspace)

    Returns:
        List of files and directories
    """
    shipyard_ctx = _get_ctx(ctx)
    result = await _exec_operation(
        shipyard_ctx,
        "fs/list_dir",
        {"path": path},
    )
    data = result.get("data", result)
    entries = data.get("entries", [])

    if not entries:
        return f"Directory '{path}' is empty"

    lines = []
    for entry in entries:
        name = entry.get("name", "")
        entry_type = entry.get("type", "file")
        if entry_type == "directory":
            lines.append(f"  {name}/")
        else:
            lines.append(f"  {name}")

    return f"Contents of '{path}':\n" + "\n".join(lines)


@mcp.tool()
async def install_package(
    package: str,
    ctx: Context = None,
) -> str:
    """Install a Python package in the sandbox using pip.

    Args:
        package: Package name (e.g., 'requests', 'pandas==2.0.0')

    Returns:
        Installation result
    """
    shipyard_ctx = _get_ctx(ctx)
    result = await _exec_operation(
        shipyard_ctx,
        "shell/exec",
        {"command": f"pip install {package}", "timeout": 120},
    )
    data = result.get("data", result)

    if data.get("exit_code", 0) == 0:
        return f"Successfully installed: {package}"

    stderr = data.get("stderr", "")
    return f"Installation failed: {stderr}"


@mcp.tool()
async def get_sandbox_info(ctx: Context = None) -> str:
    """Get information about the current sandbox environment.

    Returns:
        Sandbox information including Python version, available tools, etc.
    """
    shipyard_ctx = _get_ctx(ctx)
    ship_id = await _ensure_ship(shipyard_ctx)

    async with shipyard_ctx.http_session.get(
        f"{shipyard_ctx.bay_url}/ship/{ship_id}"
    ) as resp:
        if resp.status == 200:
            ship_data = await resp.json()
            info = [
                f"Ship ID: {ship_id}",
                f"Session ID: {shipyard_ctx.session_id}",
                f"Status: {'Running' if ship_data.get('status') == 1 else 'Unknown'}",
            ]
            if ship_data.get("expires_at"):
                info.append(f"Expires at: {ship_data['expires_at']}")
            return "\n".join(info)
        else:
            return f"Ship ID: {ship_id}\nSession ID: {shipyard_ctx.session_id}"


# =============================================================================
# MCP Resources
# =============================================================================


@mcp.resource("sandbox://info")
async def sandbox_info_resource() -> str:
    """Information about the Shipyard sandbox service."""
    return """Shipyard Sandbox Service

Shipyard provides secure, isolated Python and shell execution environments.

Available tools:
- execute_python: Run Python code
- execute_shell: Run shell commands
- read_file: Read file contents
- write_file: Write to files
- list_files: List directory contents
- install_package: Install Python packages
- get_sandbox_info: Get current sandbox information

Each session gets a dedicated container with:
- Full Python environment
- Common CLI tools (git, curl, etc.)
- Isolated filesystem
- Network access (configurable)
"""


# =============================================================================
# Entry Point
# =============================================================================


def main():
    """Entry point for the MCP server."""
    import argparse

    parser = argparse.ArgumentParser(description="Shipyard MCP Server")
    parser.add_argument(
        "--transport",
        choices=["stdio", "http"],
        default="stdio",
        help="Transport mode (default: stdio)",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=8000,
        help="HTTP port (only used with --transport http)",
    )
    parser.add_argument(
        "--host",
        default="0.0.0.0",
        help="HTTP host (only used with --transport http)",
    )

    args = parser.parse_args()

    if args.transport == "http":
        mcp.run(transport="streamable-http", host=args.host, port=args.port)
    else:
        mcp.run(transport="stdio")


if __name__ == "__main__":
    main()

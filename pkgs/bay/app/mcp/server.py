"""
Shipyard MCP Server

This module provides an MCP server that allows MCP-compatible clients
(Claude Desktop, ChatGPT Desktop, Cursor, VS Code, etc.) to interact
with Shipyard sandboxes.

The MCP Server internally uses the Shipyard SDK to communicate with Bay.

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
    SHIPYARD_TOKEN: Access token for Bay API authentication (required)
"""

import os
import sys
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass
from typing import Optional

# Add SDK to path if running standalone
sdk_path = os.path.join(os.path.dirname(__file__), "..", "..", "..", "..", "shipyard_python_sdk")
if os.path.exists(sdk_path):
    sys.path.insert(0, sdk_path)

from shipyard import Sandbox, ExecResult

from mcp.server.fastmcp import Context, FastMCP


@dataclass
class MCPContext:
    """MCP Server context holding the sandbox instance."""
    sandbox: Sandbox


@asynccontextmanager
async def mcp_lifespan(server: FastMCP) -> AsyncIterator[MCPContext]:
    """Manage MCP server lifecycle with sandbox."""
    endpoint = os.getenv("SHIPYARD_ENDPOINT", "http://localhost:8156")
    token = os.getenv("SHIPYARD_TOKEN", "")

    if not token:
        raise ValueError(
            "SHIPYARD_TOKEN environment variable is required. "
            "Set it to your Bay API access token."
        )

    # Create and start sandbox
    sandbox = Sandbox(endpoint=endpoint, token=token)
    await sandbox.start()

    try:
        yield MCPContext(sandbox=sandbox)
    finally:
        await sandbox.stop()


# Create MCP server
mcp = FastMCP(
    "Shipyard",
    version="1.0.0",
    lifespan=mcp_lifespan,
)


def _get_sandbox(ctx: Context) -> Sandbox:
    """Get sandbox from context."""
    return ctx.request_context.lifespan_context.sandbox


def _format_exec_result(result: ExecResult) -> str:
    """Format execution result for LLM consumption."""
    parts = []

    if result.stdout:
        parts.append(f"Output:\n{result.stdout}")
    if result.stderr:
        parts.append(f"Errors:\n{result.stderr}")
    if result.result is not None:
        parts.append(f"Result: {result.result}")
    if result.exit_code != 0:
        parts.append(f"Exit code: {result.exit_code}")

    if not parts:
        return "Executed successfully (no output)"

    return "\n\n".join(parts)


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
    sandbox = _get_sandbox(ctx)
    result = await sandbox.python.exec(code, timeout=timeout)
    return _format_exec_result(result)


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
    sandbox = _get_sandbox(ctx)
    result = await sandbox.shell.exec(command, cwd=cwd, timeout=timeout)
    return _format_exec_result(result)


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
    sandbox = _get_sandbox(ctx)
    return await sandbox.fs.read(path)


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
    sandbox = _get_sandbox(ctx)
    await sandbox.fs.write(path, content)
    return f"File written: {path}"


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
    sandbox = _get_sandbox(ctx)
    entries = await sandbox.fs.list(path)

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
    sandbox = _get_sandbox(ctx)
    result = await sandbox.shell.exec(f"pip install {package}", timeout=120)

    if result.success:
        return f"Successfully installed: {package}"
    return f"Installation failed: {result.stderr}"


@mcp.tool()
async def get_sandbox_info(ctx: Context = None) -> str:
    """Get information about the current sandbox environment.

    Returns:
        Sandbox information including session ID, ship ID, etc.
    """
    sandbox = _get_sandbox(ctx)
    return f"Session ID: {sandbox.session_id}\nShip ID: {sandbox.ship_id}"


@mcp.tool()
async def get_execution_history(
    exec_type: str = None,
    success_only: bool = False,
    limit: int = 50,
    ctx: Context = None,
) -> str:
    """Get execution history for this session.

    Useful for reviewing past executions or building skill libraries.

    Args:
        exec_type: Filter by 'python' or 'shell' (optional)
        success_only: Only return successful executions
        limit: Maximum entries to return (default: 50)

    Returns:
        Execution history entries
    """
    sandbox = _get_sandbox(ctx)
    history = await sandbox.get_execution_history(
        exec_type=exec_type,
        success_only=success_only,
        limit=limit,
    )

    entries = history.get("entries", [])
    if not entries:
        return "No execution history found"

    lines = [f"Execution History ({history.get('total', 0)} total):"]
    for entry in entries:
        status = "✓" if entry.get("success") else "✗"
        exec_t = entry.get("exec_type", "?")
        time_ms = entry.get("execution_time_ms", 0)
        code = entry.get("code", "")[:50]  # Truncate long code
        if len(entry.get("code", "")) > 50:
            code += "..."
        lines.append(f"  {status} [{exec_t}] {time_ms}ms: {code}")

    return "\n".join(lines)


# =============================================================================
# MCP Resources
# =============================================================================


@mcp.resource("sandbox://info")
async def sandbox_info_resource() -> str:
    """Information about the Shipyard sandbox service."""
    return """Shipyard Sandbox Service

Shipyard provides secure, isolated Python and shell execution environments
for AI agents and assistants.

Available tools:
- execute_python: Run Python code
- execute_shell: Run shell commands
- read_file: Read file contents
- write_file: Write to files
- list_files: List directory contents
- install_package: Install Python packages via pip
- get_sandbox_info: Get current sandbox information
- get_execution_history: View past executions

Each session gets a dedicated container with:
- Full Python environment (3.13+)
- Node.js LTS
- Common CLI tools (git, curl, etc.)
- Isolated filesystem
- Network access

Session state persists across tool calls within the same MCP session.
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

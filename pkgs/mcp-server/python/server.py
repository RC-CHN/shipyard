"""
Shipyard MCP Server - Standalone Python Module

This module can be run directly or via the npm package launcher.
It provides MCP protocol support for Shipyard sandbox execution.

Internally uses the Shipyard SDK to communicate with Bay.

In HTTP mode, each MCP client session gets its own isolated Sandbox.
Session state persists across tool calls within the same MCP session.

Usage:
    python -m server [--transport stdio|http] [--port 8000] [--host 0.0.0.0]

Environment:
    SHIPYARD_ENDPOINT: Bay API URL (default: http://localhost:8156)
    SHIPYARD_TOKEN: Access token (required)
    SHIPYARD_SANDBOX_TTL: Sandbox TTL in seconds (default: 1800)
"""

import argparse
import asyncio
import json
import os
import sys
import uuid
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Optional

# Try to import FastMCP for full MCP support
try:
    from mcp.server.fastmcp import Context, FastMCP
    FASTMCP_AVAILABLE = True
except ImportError:
    FASTMCP_AVAILABLE = False

# Try to import SDK, fall back to inline implementation if not available
try:
    from shipyard import Sandbox, ExecResult
    SDK_AVAILABLE = True
except ImportError:
    SDK_AVAILABLE = False

# Inline minimal SDK implementation for standalone npm package
if not SDK_AVAILABLE:
    import aiohttp

    @dataclass
    class ExecResult:
        success: bool
        stdout: str = ""
        stderr: str = ""
        result: Any = None
        exit_code: int = 0
        execution_time_ms: int = 0
        code: str = ""

    class Sandbox:
        def __init__(self, endpoint: str = None, token: str = None, ttl: int = 3600, session_id: str = None):
            self.endpoint = (endpoint or os.getenv("SHIPYARD_ENDPOINT", "http://localhost:8156")).rstrip("/")
            self.token = token or os.getenv("SHIPYARD_TOKEN", "")
            self.ttl = ttl
            self.session_id = session_id or str(uuid.uuid4())
            self._ship_id = None
            self._http = None

        async def start(self):
            if not self.token:
                raise ValueError("SHIPYARD_TOKEN is required")
            self._http = aiohttp.ClientSession(headers={"Authorization": f"Bearer {self.token}"})
            async with self._http.post(
                f"{self.endpoint}/ship",
                json={"ttl": self.ttl},
                headers={"X-SESSION-ID": self.session_id}
            ) as resp:
                if resp.status == 201:
                    data = await resp.json()
                    self._ship_id = data["id"]
                else:
                    error = await resp.text()
                    await self._http.close()
                    raise RuntimeError(f"Failed to create sandbox: {error}")
            self.python = _PythonExec(self)
            self.shell = _ShellExec(self)
            self.fs = _FileSystem(self)
            return self

        async def stop(self):
            if self._http:
                await self._http.close()

        async def _exec(self, op_type: str, payload: dict) -> dict:
            async with self._http.post(
                f"{self.endpoint}/ship/{self._ship_id}/exec",
                json={"type": op_type, "payload": payload},
                headers={"X-SESSION-ID": self.session_id}
            ) as resp:
                if resp.status == 200:
                    return await resp.json()
                error = await resp.text()
                raise RuntimeError(f"Execution failed: {error}")

        async def extend_ttl(self, ttl: int):
            async with self._http.post(
                f"{self.endpoint}/ship/{self._ship_id}/extend-ttl",
                json={"ttl": ttl}
            ) as resp:
                if resp.status != 200:
                    error = await resp.text()
                    raise RuntimeError(f"Failed to extend TTL: {error}")

        async def get_execution_history(self, exec_type=None, success_only=False, limit=100):
            params = {"limit": limit}
            if exec_type:
                params["exec_type"] = exec_type
            if success_only:
                params["success_only"] = "true"
            async with self._http.get(
                f"{self.endpoint}/sessions/{self.session_id}/history",
                params=params
            ) as resp:
                if resp.status == 200:
                    return await resp.json()
                return {"entries": [], "total": 0}

        @property
        def ship_id(self):
            return self._ship_id

        async def __aenter__(self):
            return await self.start()

        async def __aexit__(self, *args):
            await self.stop()

    class _PythonExec:
        def __init__(self, sandbox):
            self._s = sandbox
        async def exec(self, code: str, timeout: int = 30) -> ExecResult:
            r = await self._s._exec("ipython/exec", {"code": code, "timeout": timeout})
            d = r.get("data", r)
            return ExecResult(d.get("success", True), d.get("stdout", ""), d.get("stderr", ""),
                              d.get("result"), 0, d.get("execution_time_ms", 0), d.get("code", code))

    class _ShellExec:
        def __init__(self, sandbox):
            self._s = sandbox
        async def exec(self, command: str, cwd: str = None, timeout: int = 30) -> ExecResult:
            p = {"command": command, "timeout": timeout}
            if cwd:
                p["cwd"] = cwd
            r = await self._s._exec("shell/exec", p)
            d = r.get("data", r)
            return ExecResult(d.get("exit_code", 0) == 0, d.get("stdout", ""), d.get("stderr", ""),
                              None, d.get("exit_code", 0), d.get("execution_time_ms", 0), d.get("command", command))

    class _FileSystem:
        def __init__(self, sandbox):
            self._s = sandbox
        async def read(self, path: str) -> str:
            r = await self._s._exec("fs/read_file", {"path": path})
            return r.get("data", r).get("content", "")
        async def write(self, path: str, content: str):
            await self._s._exec("fs/write_file", {"path": path, "content": content})
        async def list(self, path: str = ".") -> list:
            r = await self._s._exec("fs/list_dir", {"path": path})
            return r.get("data", r).get("entries", [])


def _format_result(result: ExecResult) -> str:
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
    return "\n\n".join(parts) if parts else "Executed successfully (no output)"


# =============================================================================
# FastMCP Implementation (preferred, supports HTTP mode with session isolation)
# =============================================================================

if FASTMCP_AVAILABLE:
    from collections.abc import AsyncIterator
    from contextlib import asynccontextmanager

    @dataclass
    class GlobalConfig:
        """Global configuration initialized during server lifespan."""
        endpoint: str
        token: str
        default_ttl: int = 1800
        ttl_renew_threshold: int = 600

    @asynccontextmanager
    async def mcp_lifespan(server: FastMCP) -> AsyncIterator[GlobalConfig]:
        """Initialize global configuration."""
        endpoint = os.getenv("SHIPYARD_ENDPOINT", "http://localhost:8156")
        token = os.getenv("SHIPYARD_TOKEN", "")
        ttl = int(os.getenv("SHIPYARD_SANDBOX_TTL", "1800"))

        if not token:
            raise ValueError("SHIPYARD_TOKEN environment variable is required")

        yield GlobalConfig(endpoint=endpoint, token=token, default_ttl=ttl)

    mcp = FastMCP("Shipyard", version="1.0.0", lifespan=mcp_lifespan)

    _sandbox_locks: dict[str, asyncio.Lock] = {}

    async def get_or_create_sandbox(ctx: Context) -> Sandbox:
        """Get or create per-session Sandbox."""
        session_id = ctx.session_id

        if session_id not in _sandbox_locks:
            _sandbox_locks[session_id] = asyncio.Lock()

        async with _sandbox_locks[session_id]:
            sandbox = await ctx.get_state("sandbox")
            last_renew = await ctx.get_state("last_ttl_renew")
            config: GlobalConfig = ctx.request_context.lifespan_context

            if sandbox is None:
                sandbox = Sandbox(
                    endpoint=config.endpoint,
                    token=config.token,
                    ttl=config.default_ttl,
                    session_id=session_id,
                )
                try:
                    await sandbox.start()
                except Exception as e:
                    raise RuntimeError(f"Failed to create sandbox: {e}")

                await ctx.set_state("sandbox", sandbox)
                await ctx.set_state("last_ttl_renew", datetime.now())
            else:
                now = datetime.now()
                if last_renew is None or (now - last_renew).total_seconds() > config.ttl_renew_threshold:
                    try:
                        await sandbox.extend_ttl(config.default_ttl)
                        await ctx.set_state("last_ttl_renew", now)
                    except Exception:
                        sandbox = Sandbox(
                            endpoint=config.endpoint,
                            token=config.token,
                            ttl=config.default_ttl,
                            session_id=session_id,
                        )
                        await sandbox.start()
                        await ctx.set_state("sandbox", sandbox)
                        await ctx.set_state("last_ttl_renew", now)

            return sandbox

    @mcp.tool()
    async def execute_python(code: str, timeout: int = 30, ctx: Context = None) -> str:
        """Execute Python code in an isolated sandbox."""
        sandbox = await get_or_create_sandbox(ctx)
        result = await sandbox.python.exec(code, timeout=timeout)
        return _format_result(result)

    @mcp.tool()
    async def execute_shell(command: str, cwd: str = None, timeout: int = 30, ctx: Context = None) -> str:
        """Execute a shell command in an isolated sandbox."""
        sandbox = await get_or_create_sandbox(ctx)
        result = await sandbox.shell.exec(command, cwd=cwd, timeout=timeout)
        return _format_result(result)

    @mcp.tool()
    async def read_file(path: str, ctx: Context = None) -> str:
        """Read file content from the sandbox."""
        sandbox = await get_or_create_sandbox(ctx)
        return await sandbox.fs.read(path)

    @mcp.tool()
    async def write_file(path: str, content: str, ctx: Context = None) -> str:
        """Write content to a file in the sandbox."""
        sandbox = await get_or_create_sandbox(ctx)
        await sandbox.fs.write(path, content)
        return f"File written: {path}"

    @mcp.tool()
    async def list_files(path: str = ".", ctx: Context = None) -> str:
        """List files and directories in the sandbox."""
        sandbox = await get_or_create_sandbox(ctx)
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
    async def install_package(package: str, ctx: Context = None) -> str:
        """Install a Python package in the sandbox using pip."""
        sandbox = await get_or_create_sandbox(ctx)
        result = await sandbox.shell.exec(f"pip install {package}", timeout=120)

        if result.success:
            return f"Successfully installed: {package}"
        return f"Installation failed: {result.stderr}"

    @mcp.tool()
    async def get_sandbox_info(ctx: Context = None) -> str:
        """Get information about the current sandbox environment."""
        sandbox = await get_or_create_sandbox(ctx)
        return f"Session ID: {sandbox.session_id}\nShip ID: {sandbox.ship_id}"

    @mcp.tool()
    async def get_execution_history(
        exec_type: str = None, success_only: bool = False, limit: int = 50, ctx: Context = None
    ) -> str:
        """Get execution history for this session."""
        sandbox = await get_or_create_sandbox(ctx)
        history = await sandbox.get_execution_history(
            exec_type=exec_type, success_only=success_only, limit=limit
        )

        entries = history.get("entries", [])
        if not entries:
            return "No execution history found"

        lines = [f"Execution History ({history.get('total', 0)} total):"]
        for entry in entries:
            status = "✓" if entry.get("success") else "✗"
            exec_t = entry.get("exec_type", "?")
            time_ms = entry.get("execution_time_ms", 0)
            lines.append(f"  {status} [{exec_t}] {time_ms}ms")

        return "\n".join(lines)

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
# Fallback stdio-only implementation (when FastMCP is not available)
# =============================================================================

class ShipyardMCPServer:
    """MCP Server using JSON-RPC over stdio (fallback when FastMCP unavailable)."""

    PROTOCOL_VERSION = "2024-11-05"

    def __init__(self):
        self.sandbox: Optional[Sandbox] = None

    async def start(self):
        endpoint = os.getenv("SHIPYARD_ENDPOINT", "http://localhost:8156")
        token = os.getenv("SHIPYARD_TOKEN", "")
        ttl = int(os.getenv("SHIPYARD_SANDBOX_TTL", "1800"))
        if not token:
            raise ValueError("SHIPYARD_TOKEN environment variable is required")
        self.sandbox = Sandbox(endpoint=endpoint, token=token, ttl=ttl)
        await self.sandbox.start()

    async def stop(self):
        if self.sandbox:
            await self.sandbox.stop()

    def get_tools(self) -> list[dict]:
        return [
            {"name": "execute_python", "description": "Execute Python code in sandbox",
             "inputSchema": {"type": "object", "properties": {
                 "code": {"type": "string", "description": "Python code"},
                 "timeout": {"type": "integer", "default": 30}}, "required": ["code"]}},
            {"name": "execute_shell", "description": "Execute shell command in sandbox",
             "inputSchema": {"type": "object", "properties": {
                 "command": {"type": "string", "description": "Shell command"},
                 "cwd": {"type": "string"}, "timeout": {"type": "integer", "default": 30}},
                 "required": ["command"]}},
            {"name": "read_file", "description": "Read file from sandbox",
             "inputSchema": {"type": "object", "properties": {
                 "path": {"type": "string"}}, "required": ["path"]}},
            {"name": "write_file", "description": "Write file to sandbox",
             "inputSchema": {"type": "object", "properties": {
                 "path": {"type": "string"}, "content": {"type": "string"}},
                 "required": ["path", "content"]}},
            {"name": "list_files", "description": "List files in sandbox directory",
             "inputSchema": {"type": "object", "properties": {"path": {"type": "string", "default": "."}}}},
            {"name": "install_package", "description": "Install Python package via pip",
             "inputSchema": {"type": "object", "properties": {
                 "package": {"type": "string"}}, "required": ["package"]}},
            {"name": "get_sandbox_info", "description": "Get sandbox information",
             "inputSchema": {"type": "object", "properties": {}}},
            {"name": "get_execution_history", "description": "Get execution history",
             "inputSchema": {"type": "object", "properties": {
                 "exec_type": {"type": "string"}, "success_only": {"type": "boolean"},
                 "limit": {"type": "integer", "default": 50}}}},
        ]

    async def call_tool(self, name: str, args: dict) -> dict:
        try:
            if name == "execute_python":
                result = await self.sandbox.python.exec(args["code"], args.get("timeout", 30))
                text = _format_result(result)
            elif name == "execute_shell":
                result = await self.sandbox.shell.exec(args["command"], args.get("cwd"), args.get("timeout", 30))
                text = _format_result(result)
            elif name == "read_file":
                text = await self.sandbox.fs.read(args["path"])
            elif name == "write_file":
                await self.sandbox.fs.write(args["path"], args["content"])
                text = f"File written: {args['path']}"
            elif name == "list_files":
                entries = await self.sandbox.fs.list(args.get("path", "."))
                if not entries:
                    text = "Directory is empty"
                else:
                    lines = [f"  {e['name']}/" if e.get("type") == "directory" else f"  {e['name']}" for e in entries]
                    text = "\n".join(lines)
            elif name == "install_package":
                result = await self.sandbox.shell.exec(f"pip install {args['package']}", timeout=120)
                text = f"Installed: {args['package']}" if result.success else f"Failed: {result.stderr}"
            elif name == "get_sandbox_info":
                text = f"Session ID: {self.sandbox.session_id}\nShip ID: {self.sandbox.ship_id}"
            elif name == "get_execution_history":
                history = await self.sandbox.get_execution_history(
                    args.get("exec_type"), args.get("success_only", False), args.get("limit", 50))
                entries = history.get("entries", [])
                if not entries:
                    text = "No history"
                else:
                    lines = [f"History ({history.get('total', 0)} total):"]
                    for e in entries:
                        s = "✓" if e.get("success") else "✗"
                        lines.append(f"  {s} [{e.get('exec_type', '?')}] {e.get('execution_time_ms', 0)}ms")
                    text = "\n".join(lines)
            else:
                return {"content": [{"type": "text", "text": f"Unknown tool: {name}"}], "isError": True}
            return {"content": [{"type": "text", "text": text}], "isError": False}
        except Exception as e:
            return {"content": [{"type": "text", "text": str(e)}], "isError": True}

    async def handle_request(self, request: dict) -> Optional[dict]:
        method = request.get("method")
        params = request.get("params", {})
        req_id = request.get("id")

        try:
            if method == "initialize":
                result = {"protocolVersion": self.PROTOCOL_VERSION,
                          "capabilities": {"tools": {}},
                          "serverInfo": {"name": "shipyard", "version": "1.0.0"}}
            elif method == "tools/list":
                result = {"tools": self.get_tools()}
            elif method == "tools/call":
                result = await self.call_tool(params.get("name", ""), params.get("arguments", {}))
            elif method == "notifications/initialized":
                return None
            else:
                return {"jsonrpc": "2.0", "id": req_id,
                        "error": {"code": -32601, "message": f"Method not found: {method}"}}
            return {"jsonrpc": "2.0", "id": req_id, "result": result}
        except Exception as e:
            return {"jsonrpc": "2.0", "id": req_id, "error": {"code": -32000, "message": str(e)}}

    async def run_stdio(self):
        reader = asyncio.StreamReader()
        protocol = asyncio.StreamReaderProtocol(reader)
        await asyncio.get_event_loop().connect_read_pipe(lambda: protocol, sys.stdin)

        await self.start()
        try:
            while True:
                line = await reader.readline()
                if not line:
                    break
                line_str = line.decode("utf-8").strip()
                if not line_str:
                    continue
                try:
                    request = json.loads(line_str)
                    response = await self.handle_request(request)
                    if response is not None:
                        sys.stdout.write(json.dumps(response) + "\n")
                        sys.stdout.flush()
                except json.JSONDecodeError:
                    pass
        finally:
            await self.stop()


# =============================================================================
# Entry Point
# =============================================================================

async def main_async(transport: str, host: str, port: int):
    if transport == "stdio":
        if FASTMCP_AVAILABLE:
            mcp.run(transport="stdio")
        else:
            server = ShipyardMCPServer()
            await server.run_stdio()
    else:
        if FASTMCP_AVAILABLE:
            mcp.run(transport="streamable-http", host=host, port=port)
        else:
            print("HTTP transport requires mcp package. Use: pip install mcp", file=sys.stderr)
            sys.exit(1)


def main():
    parser = argparse.ArgumentParser(description="Shipyard MCP Server")
    parser.add_argument("--transport", choices=["stdio", "http"], default="stdio")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--host", default="0.0.0.0")
    args = parser.parse_args()

    if args.transport == "stdio" and FASTMCP_AVAILABLE:
        mcp.run(transport="stdio")
    elif args.transport == "http" and FASTMCP_AVAILABLE:
        mcp.run(transport="streamable-http", host=args.host, port=args.port)
    else:
        asyncio.run(main_async(args.transport, args.host, args.port))


if __name__ == "__main__":
    main()

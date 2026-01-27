"""
Shipyard MCP Server - Standalone Python Module

This module can be run directly or via the npm package launcher.
It provides MCP protocol support for Shipyard sandbox execution.

Usage:
    python -m server [--transport stdio|http] [--port 8000] [--host 0.0.0.0]

Environment:
    SHIPYARD_ENDPOINT: Bay API URL (default: http://localhost:8156)
    SHIPYARD_TOKEN: Access token (required)
"""

import argparse
import asyncio
import json
import os
import sys
import uuid
from dataclasses import dataclass, field
from typing import Any, Optional

# Check for required dependencies
try:
    import aiohttp
except ImportError:
    print("Error: aiohttp is required. Install with: pip install aiohttp", file=sys.stderr)
    sys.exit(1)


@dataclass
class ShipyardContext:
    """Context for Shipyard MCP server."""

    http_session: aiohttp.ClientSession
    bay_url: str
    access_token: str
    ship_id: Optional[str] = None
    session_id: str = field(default_factory=lambda: str(uuid.uuid4()))


class ShipyardMCPServer:
    """MCP Server that bridges to Shipyard Bay."""

    PROTOCOL_VERSION = "2024-11-05"

    def __init__(self, bay_url: str, access_token: str):
        self.bay_url = bay_url.rstrip("/")
        self.access_token = access_token
        self.ctx: Optional[ShipyardContext] = None

    async def start(self) -> None:
        """Initialize the server context."""
        headers = {"Authorization": f"Bearer {self.access_token}"}
        http_session = aiohttp.ClientSession(headers=headers)
        self.ctx = ShipyardContext(
            http_session=http_session,
            bay_url=self.bay_url,
            access_token=self.access_token,
        )

    async def stop(self) -> None:
        """Clean up resources."""
        if self.ctx and self.ctx.http_session:
            await self.ctx.http_session.close()

    async def _ensure_ship(self, ttl: int = 3600) -> str:
        """Ensure we have an active ship."""
        if not self.ctx:
            raise RuntimeError("Server not started")

        if self.ctx.ship_id:
            async with self.ctx.http_session.get(
                f"{self.ctx.bay_url}/ship/{self.ctx.ship_id}"
            ) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    if data.get("status") == 1:
                        return self.ctx.ship_id

        payload = {"ttl": ttl}
        headers = {"X-SESSION-ID": self.ctx.session_id}

        async with self.ctx.http_session.post(
            f"{self.ctx.bay_url}/ship", json=payload, headers=headers
        ) as resp:
            if resp.status == 201:
                data = await resp.json()
                self.ctx.ship_id = data["id"]
                return self.ctx.ship_id
            else:
                error = await resp.text()
                raise Exception(f"Failed to create ship: {error}")

    async def _exec(self, op_type: str, payload: dict) -> dict:
        """Execute operation on ship."""
        if not self.ctx:
            raise RuntimeError("Server not started")

        ship_id = await self._ensure_ship()
        headers = {"X-SESSION-ID": self.ctx.session_id}

        async with self.ctx.http_session.post(
            f"{self.ctx.bay_url}/ship/{ship_id}/exec",
            json={"type": op_type, "payload": payload},
            headers=headers,
        ) as resp:
            if resp.status == 200:
                return await resp.json()
            else:
                error = await resp.text()
                raise Exception(f"Execution failed: {error}")

    def get_tools(self) -> list[dict]:
        """Return MCP tools definition."""
        return [
            {
                "name": "execute_python",
                "description": "Execute Python code in an isolated sandbox",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "code": {"type": "string", "description": "Python code to execute"},
                        "timeout": {"type": "integer", "description": "Timeout in seconds", "default": 30},
                    },
                    "required": ["code"],
                },
            },
            {
                "name": "execute_shell",
                "description": "Execute shell command in an isolated sandbox",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "command": {"type": "string", "description": "Shell command"},
                        "cwd": {"type": "string", "description": "Working directory"},
                        "timeout": {"type": "integer", "description": "Timeout in seconds", "default": 30},
                    },
                    "required": ["command"],
                },
            },
            {
                "name": "read_file",
                "description": "Read file content from sandbox",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "path": {"type": "string", "description": "File path"},
                    },
                    "required": ["path"],
                },
            },
            {
                "name": "write_file",
                "description": "Write content to file in sandbox",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "path": {"type": "string", "description": "File path"},
                        "content": {"type": "string", "description": "Content to write"},
                    },
                    "required": ["path", "content"],
                },
            },
            {
                "name": "list_files",
                "description": "List files in sandbox directory",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "path": {"type": "string", "description": "Directory path", "default": "."},
                    },
                },
            },
            {
                "name": "install_package",
                "description": "Install Python package via pip",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "package": {"type": "string", "description": "Package name"},
                    },
                    "required": ["package"],
                },
            },
            {
                "name": "get_sandbox_info",
                "description": "Get current sandbox information",
                "inputSchema": {"type": "object", "properties": {}},
            },
        ]

    async def call_tool(self, name: str, args: dict) -> dict:
        """Call a tool and return MCP-formatted result."""
        try:
            if name == "execute_python":
                result = await self._exec(
                    "ipython/exec",
                    {"code": args["code"], "timeout": args.get("timeout", 30)},
                )
                data = result.get("data", result)
                parts = []
                if data.get("stdout"):
                    parts.append(f"Output:\n{data['stdout']}")
                if data.get("stderr"):
                    parts.append(f"Errors:\n{data['stderr']}")
                if data.get("result"):
                    parts.append(f"Result: {data['result']}")
                text = "\n\n".join(parts) if parts else "Code executed (no output)"

            elif name == "execute_shell":
                payload = {"command": args["command"], "timeout": args.get("timeout", 30)}
                if args.get("cwd"):
                    payload["cwd"] = args["cwd"]
                result = await self._exec("shell/exec", payload)
                data = result.get("data", result)
                parts = []
                if data.get("stdout"):
                    parts.append(data["stdout"])
                if data.get("stderr"):
                    parts.append(f"stderr: {data['stderr']}")
                if data.get("exit_code", 0) != 0:
                    parts.append(f"Exit code: {data['exit_code']}")
                text = "\n".join(parts) if parts else "Command completed"

            elif name == "read_file":
                result = await self._exec("fs/read_file", {"path": args["path"]})
                data = result.get("data", result)
                text = data.get("content", str(data))

            elif name == "write_file":
                result = await self._exec(
                    "fs/write_file", {"path": args["path"], "content": args["content"]}
                )
                data = result.get("data", result)
                text = f"File written: {args['path']}" if data.get("success", True) else str(data)

            elif name == "list_files":
                result = await self._exec("fs/list_dir", {"path": args.get("path", ".")})
                data = result.get("data", result)
                entries = data.get("entries", [])
                if not entries:
                    text = "Directory is empty"
                else:
                    lines = []
                    for e in entries:
                        n = e.get("name", "")
                        t = e.get("type", "file")
                        lines.append(f"  {n}/" if t == "directory" else f"  {n}")
                    text = "\n".join(lines)

            elif name == "install_package":
                result = await self._exec(
                    "shell/exec",
                    {"command": f"pip install {args['package']}", "timeout": 120},
                )
                data = result.get("data", result)
                if data.get("exit_code", 0) == 0:
                    text = f"Installed: {args['package']}"
                else:
                    text = f"Failed: {data.get('stderr', '')}"

            elif name == "get_sandbox_info":
                ship_id = await self._ensure_ship()
                text = f"Ship ID: {ship_id}\nSession ID: {self.ctx.session_id}"

            else:
                return {
                    "content": [{"type": "text", "text": f"Unknown tool: {name}"}],
                    "isError": True,
                }

            return {"content": [{"type": "text", "text": text}], "isError": False}

        except Exception as e:
            return {"content": [{"type": "text", "text": str(e)}], "isError": True}

    async def handle_request(self, request: dict) -> Optional[dict]:
        """Handle an MCP JSON-RPC request."""
        method = request.get("method")
        params = request.get("params", {})
        req_id = request.get("id")

        try:
            if method == "initialize":
                result = {
                    "protocolVersion": self.PROTOCOL_VERSION,
                    "capabilities": {"tools": {}},
                    "serverInfo": {"name": "shipyard", "version": "1.0.0"},
                }
            elif method == "tools/list":
                result = {"tools": self.get_tools()}
            elif method == "tools/call":
                result = await self.call_tool(params.get("name", ""), params.get("arguments", {}))
            elif method == "notifications/initialized":
                return None  # No response for notifications
            else:
                return {
                    "jsonrpc": "2.0",
                    "id": req_id,
                    "error": {"code": -32601, "message": f"Method not found: {method}"},
                }

            return {"jsonrpc": "2.0", "id": req_id, "result": result}

        except Exception as e:
            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "error": {"code": -32000, "message": str(e)},
            }

    async def run_stdio(self) -> None:
        """Run server using stdio transport."""
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


async def main_async(transport: str, host: str, port: int) -> None:
    """Main async entry point."""
    bay_url = os.getenv("SHIPYARD_ENDPOINT", "http://localhost:8156")
    access_token = os.getenv("SHIPYARD_TOKEN", "")

    if not access_token:
        print("Error: SHIPYARD_TOKEN environment variable is required.", file=sys.stderr)
        sys.exit(1)

    server = ShipyardMCPServer(bay_url, access_token)

    if transport == "stdio":
        await server.run_stdio()
    else:
        # HTTP transport - use FastMCP if available
        try:
            from mcp.server.fastmcp import FastMCP
            print(f"Starting HTTP server on {host}:{port}", file=sys.stderr)
            # For HTTP, we'd use FastMCP's run method
            # This is a placeholder - full HTTP implementation would use FastMCP
            print("HTTP transport requires mcp package. Use: pip install mcp", file=sys.stderr)
            sys.exit(1)
        except ImportError:
            print("HTTP transport requires mcp package. Use: pip install mcp", file=sys.stderr)
            sys.exit(1)


def main() -> None:
    """Entry point."""
    parser = argparse.ArgumentParser(description="Shipyard MCP Server")
    parser.add_argument("--transport", choices=["stdio", "http"], default="stdio")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--host", default="0.0.0.0")
    args = parser.parse_args()

    asyncio.run(main_async(args.transport, args.host, args.port))


if __name__ == "__main__":
    main()

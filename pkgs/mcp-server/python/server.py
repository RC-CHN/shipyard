"""
Shipyard MCP Server - Standalone Python Module

This module can be run directly or via the npm package launcher.
It provides MCP protocol support for Shipyard sandbox execution.

Internally uses the Shipyard SDK to communicate with Bay.

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
from dataclasses import dataclass
from typing import Any, Optional

# Try to import SDK, fall back to inline implementation if not available
try:
    # If SDK is installed as a package
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
        def __init__(self, endpoint: str = None, token: str = None, ttl: int = 3600):
            self.endpoint = (endpoint or os.getenv("SHIPYARD_ENDPOINT", "http://localhost:8156")).rstrip("/")
            self.token = token or os.getenv("SHIPYARD_TOKEN", "")
            self.ttl = ttl
            self.session_id = str(uuid.uuid4())
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


class ShipyardMCPServer:
    """MCP Server using Shipyard SDK."""

    PROTOCOL_VERSION = "2024-11-05"

    def __init__(self):
        self.sandbox: Optional[Sandbox] = None

    async def start(self):
        endpoint = os.getenv("SHIPYARD_ENDPOINT", "http://localhost:8156")
        token = os.getenv("SHIPYARD_TOKEN", "")
        if not token:
            raise ValueError("SHIPYARD_TOKEN environment variable is required")
        self.sandbox = Sandbox(endpoint=endpoint, token=token)
        await self.sandbox.start()

    async def stop(self):
        if self.sandbox:
            await self.sandbox.stop()

    def _format_result(self, result: ExecResult) -> str:
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
                text = self._format_result(result)
            elif name == "execute_shell":
                result = await self.sandbox.shell.exec(args["command"], args.get("cwd"), args.get("timeout", 30))
                text = self._format_result(result)
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


async def main_async(transport: str, host: str, port: int):
    if transport == "stdio":
        server = ShipyardMCPServer()
        await server.run_stdio()
    else:
        print("HTTP transport requires mcp package. Use: pip install mcp", file=sys.stderr)
        sys.exit(1)


def main():
    parser = argparse.ArgumentParser(description="Shipyard MCP Server")
    parser.add_argument("--transport", choices=["stdio", "http"], default="stdio")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--host", default="0.0.0.0")
    args = parser.parse_args()
    asyncio.run(main_async(args.transport, args.host, args.port))


if __name__ == "__main__":
    main()

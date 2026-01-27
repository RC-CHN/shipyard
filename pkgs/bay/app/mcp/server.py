"""
Shipyard MCP Server Adapter

This module provides an MCP (Model Context Protocol) server that allows
MCP-compatible clients (Claude Desktop, Cursor, etc.) to interact with
Shipyard sandboxes.

Transport: stdio (standard input/output)
"""

import asyncio
import json
import sys
import uuid
import logging
from typing import Any, Optional

import aiohttp

logger = logging.getLogger(__name__)


class ShipyardMCPServer:
    """MCP Server that bridges MCP clients to Shipyard Bay."""

    def __init__(self, bay_url: str, access_token: str):
        """
        Initialize the MCP Server.

        Args:
            bay_url: URL of the Shipyard Bay API
            access_token: Access token for Bay API authentication
        """
        self.bay_url = bay_url.rstrip("/")
        self.access_token = access_token
        self._session: Optional[aiohttp.ClientSession] = None
        self._ship_id: Optional[str] = None
        self._session_id: str = str(uuid.uuid4())

    async def _get_http_session(self) -> aiohttp.ClientSession:
        """Get or create aiohttp session."""
        if self._session is None or self._session.closed:
            headers = {"Authorization": f"Bearer {self.access_token}"}
            self._session = aiohttp.ClientSession(headers=headers)
        return self._session

    async def _ensure_ship(self) -> str:
        """Ensure we have an active ship, create one if needed."""
        if self._ship_id:
            # Check if ship is still running
            session = await self._get_http_session()
            async with session.get(f"{self.bay_url}/ship/{self._ship_id}") as resp:
                if resp.status == 200:
                    ship_data = await resp.json()
                    if ship_data.get("status") == 1:  # RUNNING
                        return self._ship_id

        # Create new ship
        session = await self._get_http_session()
        payload = {"ttl": 3600}
        headers = {"X-SESSION-ID": self._session_id}

        async with session.post(
            f"{self.bay_url}/ship", json=payload, headers=headers
        ) as resp:
            if resp.status == 201:
                ship_data = await resp.json()
                self._ship_id = ship_data["id"]
                logger.info(f"Created ship {self._ship_id} for MCP session")
                return self._ship_id
            else:
                error = await resp.text()
                raise Exception(f"Failed to create ship: {error}")

    async def _exec_operation(
        self, operation_type: str, payload: dict[str, Any]
    ) -> dict[str, Any]:
        """Execute an operation on the ship."""
        ship_id = await self._ensure_ship()
        session = await self._get_http_session()

        request_payload = {"type": operation_type, "payload": payload}
        headers = {"X-SESSION-ID": self._session_id}

        async with session.post(
            f"{self.bay_url}/ship/{ship_id}/exec",
            json=request_payload,
            headers=headers,
        ) as resp:
            if resp.status == 200:
                return await resp.json()
            else:
                error = await resp.text()
                raise Exception(f"Execution failed: {error}")

    # Tool implementations
    async def execute_python(self, code: str, timeout: int = 30) -> dict[str, Any]:
        """Execute Python code in the sandbox."""
        result = await self._exec_operation(
            "ipython/exec",
            {"code": code, "timeout": timeout},
        )
        return result.get("data", result)

    async def execute_shell(
        self, command: str, cwd: Optional[str] = None, timeout: int = 30
    ) -> dict[str, Any]:
        """Execute shell command in the sandbox."""
        payload: dict[str, Any] = {"command": command, "timeout": timeout}
        if cwd:
            payload["cwd"] = cwd

        result = await self._exec_operation("shell/exec", payload)
        return result.get("data", result)

    async def read_file(self, path: str) -> dict[str, Any]:
        """Read file content from the sandbox."""
        result = await self._exec_operation(
            "fs/read_file",
            {"path": path},
        )
        return result.get("data", result)

    async def write_file(self, path: str, content: str) -> dict[str, Any]:
        """Write content to a file in the sandbox."""
        result = await self._exec_operation(
            "fs/write_file",
            {"path": path, "content": content},
        )
        return result.get("data", result)

    def get_tools_definition(self) -> list[dict[str, Any]]:
        """Return MCP tools definition."""
        return [
            {
                "name": "execute_python",
                "description": "Execute Python code in an isolated sandbox",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "code": {
                            "type": "string",
                            "description": "Python code to execute",
                        },
                        "timeout": {
                            "type": "integer",
                            "description": "Execution timeout in seconds",
                            "default": 30,
                        },
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
                        "command": {
                            "type": "string",
                            "description": "Shell command to execute",
                        },
                        "cwd": {
                            "type": "string",
                            "description": "Working directory (relative to workspace)",
                        },
                        "timeout": {
                            "type": "integer",
                            "description": "Execution timeout in seconds",
                            "default": 30,
                        },
                    },
                    "required": ["command"],
                },
            },
            {
                "name": "read_file",
                "description": "Read file content from the sandbox",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "path": {
                            "type": "string",
                            "description": "File path (relative to workspace)",
                        },
                    },
                    "required": ["path"],
                },
            },
            {
                "name": "write_file",
                "description": "Write content to a file in the sandbox",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "path": {
                            "type": "string",
                            "description": "File path (relative to workspace)",
                        },
                        "content": {
                            "type": "string",
                            "description": "Content to write",
                        },
                    },
                    "required": ["path", "content"],
                },
            },
        ]

    async def handle_request(self, request: dict[str, Any]) -> dict[str, Any]:
        """Handle an MCP JSON-RPC request."""
        method = request.get("method")
        params = request.get("params", {})
        request_id = request.get("id")

        try:
            if method == "initialize":
                result = {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {
                        "tools": {},
                    },
                    "serverInfo": {
                        "name": "shipyard",
                        "version": "1.0.0",
                    },
                }
            elif method == "tools/list":
                result = {"tools": self.get_tools_definition()}
            elif method == "tools/call":
                tool_name = params.get("name")
                arguments = params.get("arguments", {})
                result = await self._call_tool(tool_name, arguments)
            elif method == "notifications/initialized":
                # This is a notification, no response needed
                return None  # type: ignore
            else:
                return {
                    "jsonrpc": "2.0",
                    "id": request_id,
                    "error": {
                        "code": -32601,
                        "message": f"Method not found: {method}",
                    },
                }

            return {
                "jsonrpc": "2.0",
                "id": request_id,
                "result": result,
            }
        except Exception as e:
            logger.exception(f"Error handling request: {e}")
            return {
                "jsonrpc": "2.0",
                "id": request_id,
                "error": {
                    "code": -32000,
                    "message": str(e),
                },
            }

    async def _call_tool(
        self, tool_name: str, arguments: dict[str, Any]
    ) -> dict[str, Any]:
        """Call a tool and return the result."""
        if tool_name == "execute_python":
            result = await self.execute_python(
                code=arguments["code"],
                timeout=arguments.get("timeout", 30),
            )
        elif tool_name == "execute_shell":
            result = await self.execute_shell(
                command=arguments["command"],
                cwd=arguments.get("cwd"),
                timeout=arguments.get("timeout", 30),
            )
        elif tool_name == "read_file":
            result = await self.read_file(path=arguments["path"])
        elif tool_name == "write_file":
            result = await self.write_file(
                path=arguments["path"],
                content=arguments["content"],
            )
        else:
            raise ValueError(f"Unknown tool: {tool_name}")

        # Format result as MCP content
        return {
            "content": [
                {
                    "type": "text",
                    "text": json.dumps(result, indent=2),
                }
            ],
            "isError": not result.get("success", True),
        }

    async def run_stdio(self):
        """Run the MCP server using stdio transport."""
        logger.info("Starting Shipyard MCP Server (stdio)")

        # Read from stdin, write to stdout
        reader = asyncio.StreamReader()
        protocol = asyncio.StreamReaderProtocol(reader)
        await asyncio.get_event_loop().connect_read_pipe(lambda: protocol, sys.stdin)

        while True:
            try:
                # Read line from stdin
                line = await reader.readline()
                if not line:
                    break

                line_str = line.decode("utf-8").strip()
                if not line_str:
                    continue

                # Parse JSON-RPC request
                request = json.loads(line_str)
                logger.debug(f"Received: {request}")

                # Handle request
                response = await self.handle_request(request)

                # Send response (if not a notification)
                if response is not None:
                    response_str = json.dumps(response) + "\n"
                    sys.stdout.write(response_str)
                    sys.stdout.flush()
                    logger.debug(f"Sent: {response}")

            except json.JSONDecodeError as e:
                logger.error(f"Invalid JSON: {e}")
            except Exception as e:
                logger.exception(f"Error processing request: {e}")

    async def close(self):
        """Clean up resources."""
        if self._session and not self._session.closed:
            await self._session.close()


async def main():
    """Main entry point for MCP server."""
    import os

    bay_url = os.getenv("SHIPYARD_ENDPOINT", "http://localhost:8156")
    access_token = os.getenv("SHIPYARD_TOKEN", "secret-token")

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        stream=sys.stderr,  # Log to stderr to not interfere with stdio
    )

    server = ShipyardMCPServer(bay_url, access_token)
    try:
        await server.run_stdio()
    finally:
        await server.close()


if __name__ == "__main__":
    asyncio.run(main())

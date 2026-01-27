"""
Shipyard Python SDK - Sandbox Interface

This module provides a simple interface for code execution in Shipyard sandboxes.
It connects to a Bay service which manages container lifecycle, session state,
and execution history.

Usage:
    from shipyard import Sandbox

    async with Sandbox() as sandbox:
        result = await sandbox.python.exec("print('hello')")
        print(result.stdout)

Environment Variables:
    SHIPYARD_ENDPOINT: Bay API URL (default: http://localhost:8156)
    SHIPYARD_TOKEN: Access token for authentication (required)
"""

import os
import uuid
from dataclasses import dataclass
from typing import Any, Dict, Optional

import aiohttp


@dataclass
class ExecResult:
    """Result of code execution."""

    success: bool
    stdout: str = ""
    stderr: str = ""
    result: Any = None
    exit_code: int = 0
    execution_time_ms: int = 0
    code: str = ""
    execution_id: Optional[str] = None  # ID for precise history lookup


class PythonExecutor:
    """Python execution interface."""

    def __init__(self, sandbox: "Sandbox"):
        self._sandbox = sandbox

    async def exec(
        self,
        code: str,
        timeout: int = 30,
        description: Optional[str] = None,
        tags: Optional[str] = None,
    ) -> ExecResult:
        """Execute Python code in the sandbox.

        Args:
            code: Python code to execute
            timeout: Execution timeout in seconds
            description: Human-readable description of what this code does
            tags: Comma-separated tags for categorization
        """
        payload: Dict[str, Any] = {"code": code, "timeout": timeout}
        if description:
            payload["description"] = description
        if tags:
            payload["tags"] = tags

        result = await self._sandbox._exec("ipython/exec", payload)
        data = result.get("data", result)
        return ExecResult(
            success=data.get("success", True),
            stdout=data.get("stdout", ""),
            stderr=data.get("stderr", ""),
            result=data.get("result"),
            execution_time_ms=data.get("execution_time_ms", 0),
            code=data.get("code", code),
            execution_id=result.get("execution_id"),
        )


class ShellExecutor:
    """Shell execution interface."""

    def __init__(self, sandbox: "Sandbox"):
        self._sandbox = sandbox

    async def exec(
        self,
        command: str,
        cwd: Optional[str] = None,
        timeout: int = 30,
        description: Optional[str] = None,
        tags: Optional[str] = None,
    ) -> ExecResult:
        """Execute shell command in the sandbox.

        Args:
            command: Shell command to execute
            cwd: Working directory (optional)
            timeout: Execution timeout in seconds
            description: Human-readable description of what this command does
            tags: Comma-separated tags for categorization
        """
        payload: Dict[str, Any] = {"command": command, "timeout": timeout}
        if cwd:
            payload["cwd"] = cwd
        if description:
            payload["description"] = description
        if tags:
            payload["tags"] = tags

        result = await self._sandbox._exec("shell/exec", payload)
        data = result.get("data", result)
        return ExecResult(
            success=data.get("exit_code", 0) == 0,
            stdout=data.get("stdout", ""),
            stderr=data.get("stderr", ""),
            exit_code=data.get("exit_code", 0),
            execution_time_ms=data.get("execution_time_ms", 0),
            code=data.get("command", command),
            execution_id=result.get("execution_id"),
        )


class FileSystem:
    """File system interface."""

    def __init__(self, sandbox: "Sandbox"):
        self._sandbox = sandbox

    async def read(self, path: str) -> str:
        """Read file content from the sandbox."""
        result = await self._sandbox._exec("fs/read_file", {"path": path})
        data = result.get("data", result)
        return data.get("content", "")

    async def write(self, path: str, content: str) -> None:
        """Write content to a file in the sandbox."""
        await self._sandbox._exec("fs/write_file", {"path": path, "content": content})

    async def list(self, path: str = ".") -> list:
        """List files in a directory."""
        result = await self._sandbox._exec("fs/list_dir", {"path": path})
        data = result.get("data", result)
        return data.get("entries", [])


class Sandbox:
    """
    Sandbox interface for code execution via Shipyard Bay.

    Requires a running Bay service for container management,
    session state, and execution history.

    Usage:
        async with Sandbox() as sandbox:
            result = await sandbox.python.exec("print('hello')")
            print(result.stdout)

        # With custom configuration
        async with Sandbox(
            endpoint="http://bay.example.com:8156",
            token="your-token",
            ttl=7200,
            session_id="my-session"
        ) as sandbox:
            result = await sandbox.shell.exec("ls -la")
    """

    def __init__(
        self,
        endpoint: Optional[str] = None,
        token: Optional[str] = None,
        ttl: int = 3600,
        session_id: Optional[str] = None,
    ):
        """
        Initialize sandbox connection to Bay.

        Args:
            endpoint: Bay API URL (or SHIPYARD_ENDPOINT env var)
            token: Access token (or SHIPYARD_TOKEN env var)
            ttl: Session TTL in seconds (default: 1 hour)
            session_id: Session ID for state persistence (auto-generated if not provided)
        """
        self.endpoint = (
            endpoint or os.getenv("SHIPYARD_ENDPOINT", "http://localhost:8156")
        ).rstrip("/")
        self.token = token or os.getenv("SHIPYARD_TOKEN", "")
        self.ttl = ttl
        self.session_id = session_id or str(uuid.uuid4())

        self._ship_id: Optional[str] = None
        self._http: Optional[aiohttp.ClientSession] = None

        # Component interfaces (initialized on start)
        self.python: PythonExecutor
        self.shell: ShellExecutor
        self.fs: FileSystem

    async def start(self) -> "Sandbox":
        """Start the sandbox session."""
        if not self.token:
            raise ValueError(
                "SHIPYARD_TOKEN is required. Set it via environment variable or constructor."
            )

        headers = {"Authorization": f"Bearer {self.token}"}
        self._http = aiohttp.ClientSession(headers=headers)

        # Create ship via Bay
        payload = {"ttl": self.ttl}
        req_headers = {"X-SESSION-ID": self.session_id}

        async with self._http.post(
            f"{self.endpoint}/ship", json=payload, headers=req_headers
        ) as resp:
            if resp.status == 201:
                data = await resp.json()
                self._ship_id = data["id"]
            else:
                error = await resp.text()
                await self._http.close()
                raise RuntimeError(f"Failed to create sandbox: {error}")

        # Initialize component interfaces
        self.python = PythonExecutor(self)
        self.shell = ShellExecutor(self)
        self.fs = FileSystem(self)

        return self

    async def stop(self) -> None:
        """Stop the sandbox session (resources managed by TTL)."""
        if self._http:
            await self._http.close()
            self._http = None

    async def _exec(self, op_type: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Execute operation on the sandbox."""
        if not self._http or not self._ship_id:
            raise RuntimeError("Sandbox not started. Use 'async with Sandbox()' or call start().")

        headers = {"X-SESSION-ID": self.session_id}
        async with self._http.post(
            f"{self.endpoint}/ship/{self._ship_id}/exec",
            json={"type": op_type, "payload": payload},
            headers=headers,
        ) as resp:
            if resp.status == 200:
                return await resp.json()
            else:
                error = await resp.text()
                raise RuntimeError(f"Execution failed: {error}")

    async def extend_ttl(self, ttl: int) -> None:
        """Extend the sandbox TTL."""
        if not self._http or not self._ship_id:
            raise RuntimeError("Sandbox not started.")

        async with self._http.post(
            f"{self.endpoint}/ship/{self._ship_id}/extend-ttl",
            json={"ttl": ttl},
        ) as resp:
            if resp.status != 200:
                error = await resp.text()
                raise RuntimeError(f"Failed to extend TTL: {error}")

    async def get_execution_history(
        self,
        exec_type: Optional[str] = None,
        success_only: bool = False,
        limit: int = 100,
    ) -> Dict[str, Any]:
        """
        Get execution history for this session.

        Useful for building skill libraries (VOYAGER-style).

        Args:
            exec_type: Filter by 'python' or 'shell'
            success_only: Only return successful executions
            limit: Maximum entries to return

        Returns:
            Dict with 'entries' and 'total'
        """
        if not self._http:
            raise RuntimeError("Sandbox not started.")

        params: Dict[str, Any] = {"limit": limit}
        if exec_type:
            params["exec_type"] = exec_type
        if success_only:
            params["success_only"] = "true"

        async with self._http.get(
            f"{self.endpoint}/sessions/{self.session_id}/history",
            params=params,
        ) as resp:
            if resp.status == 200:
                return await resp.json()
            else:
                error = await resp.text()
                raise RuntimeError(f"Failed to get history: {error}")

    async def get_execution(self, execution_id: str) -> Dict[str, Any]:
        """
        Get a specific execution record by ID.

        Args:
            execution_id: The execution history ID

        Returns:
            Dict with execution details including code, success, output, etc.
        """
        if not self._http:
            raise RuntimeError("Sandbox not started.")

        async with self._http.get(
            f"{self.endpoint}/sessions/{self.session_id}/history/{execution_id}",
        ) as resp:
            if resp.status == 200:
                return await resp.json()
            elif resp.status == 404:
                raise RuntimeError(f"Execution {execution_id} not found")
            else:
                error = await resp.text()
                raise RuntimeError(f"Failed to get execution: {error}")

    async def get_last_execution(
        self,
        exec_type: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Get the most recent execution for this session.

        Args:
            exec_type: Filter by 'python' or 'shell' (optional)

        Returns:
            Dict with execution details including code, success, output, etc.
        """
        if not self._http:
            raise RuntimeError("Sandbox not started.")

        params: Dict[str, Any] = {}
        if exec_type:
            params["exec_type"] = exec_type

        async with self._http.get(
            f"{self.endpoint}/sessions/{self.session_id}/history/last",
            params=params,
        ) as resp:
            if resp.status == 200:
                return await resp.json()
            elif resp.status == 404:
                raise RuntimeError("No execution history found")
            else:
                error = await resp.text()
                raise RuntimeError(f"Failed to get last execution: {error}")

    async def annotate_execution(
        self,
        execution_id: str,
        description: Optional[str] = None,
        tags: Optional[str] = None,
        notes: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Annotate an execution record with metadata.

        Use this to add descriptions, tags, or notes to an execution after
        it has been recorded. Useful for skill library construction.

        Args:
            execution_id: The execution history ID
            description: Human-readable description of what this execution does
            tags: Comma-separated tags for categorization
            notes: Agent notes/annotations about this execution

        Returns:
            Dict with updated execution details
        """
        if not self._http:
            raise RuntimeError("Sandbox not started.")

        payload: Dict[str, Any] = {}
        if description is not None:
            payload["description"] = description
        if tags is not None:
            payload["tags"] = tags
        if notes is not None:
            payload["notes"] = notes

        async with self._http.patch(
            f"{self.endpoint}/sessions/{self.session_id}/history/{execution_id}",
            json=payload,
        ) as resp:
            if resp.status == 200:
                return await resp.json()
            elif resp.status == 404:
                raise RuntimeError(f"Execution {execution_id} not found")
            else:
                error = await resp.text()
                raise RuntimeError(f"Failed to annotate execution: {error}")

    @property
    def ship_id(self) -> Optional[str]:
        """Get the Ship container ID."""
        return self._ship_id

    async def __aenter__(self) -> "Sandbox":
        return await self.start()

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        await self.stop()


# Convenience functions
async def run_python(code: str, **kwargs) -> ExecResult:
    """
    Quick helper to run Python code.

    Usage:
        result = await run_python("print('hello')")
    """
    async with Sandbox(**kwargs) as sandbox:
        return await sandbox.python.exec(code)


async def run_shell(command: str, **kwargs) -> ExecResult:
    """
    Quick helper to run shell command.

    Usage:
        result = await run_shell("ls -la")
    """
    async with Sandbox(**kwargs) as sandbox:
        return await sandbox.shell.exec(command)

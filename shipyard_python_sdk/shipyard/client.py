"""
Shipyard Python SDK - Main client implementation
"""

import os
import aiohttp
from typing import Optional, Dict, Any, Union
import warnings

from .types import Spec
from .session import SessionShip


class ShipyardClient:
    """Main Shipyard SDK client"""

    def __init__(
        self, endpoint_url: Optional[str] = None, access_token: Optional[str] = None
    ):
        """
        Initialize the Shipyard client

        Args:
            endpoint_url: Bay API endpoint URL (can also be set via SHIPYARD_ENDPOINT env var)
            access_token: Access token for authentication (can also be set via SHIPYARD_TOKEN env var)
        """
        self.endpoint_url = endpoint_url or os.getenv("SHIPYARD_ENDPOINT")
        self.access_token = access_token or os.getenv("SHIPYARD_TOKEN")

        if not self.endpoint_url:
            raise ValueError(
                "Endpoint URL must be provided either as parameter or SHIPYARD_ENDPOINT env var"
            )

        if not self.access_token:
            raise ValueError(
                "Access token must be provided either as parameter or SHIPYARD_TOKEN env var"
            )

        # Remove trailing slash from endpoint URL
        self.endpoint_url = self.endpoint_url.rstrip("/")

        self._session: Optional[aiohttp.ClientSession] = None

    async def _get_session(self) -> aiohttp.ClientSession:
        """Get or create aiohttp session"""
        if self._session is None or self._session.closed:
            headers = {
                "Authorization": f"Bearer {self.access_token}",
            }
            self._session = aiohttp.ClientSession(headers=headers)
        return self._session

    async def close(self):
        """Close the HTTP session"""
        if self._session and not self._session.closed:
            await self._session.close()

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()

    async def create_ship(
        self,
        ttl: int,
        spec: Optional[Spec] = None,
        max_session_num: int | None = None,
        session_id: Optional[str] = None,
        force_create: bool = False,
    ) -> SessionShip:
        """
        Create a new ship or reuse an existing one for the session.

        With 1:1 Session-Ship binding, each session gets a dedicated ship.

        Args:
            ttl: Time to live in seconds
            spec: Ship specifications for resource allocation
            max_session_num: Deprecated. Ignored (Shipyard enforces 1:1 binding).
            session_id: Session ID (if not provided, a random one will be generated)
            force_create: If True, skip reuse logic and always create new container

        Returns:
            SessionShip: The created or reused ship session
        """
        if max_session_num is not None:
            warnings.warn(
                "`max_session_num` is deprecated and ignored (Shipyard enforces 1:1 Session-Ship binding).",
                DeprecationWarning,
                stacklevel=2,
            )
        if session_id is None:
            import uuid

            session_id = str(uuid.uuid4())

        session = await self._get_session()

        # Prepare request payload
        payload: Dict[str, Any] = {"ttl": ttl}

        if force_create:
            payload["force_create"] = True

        if spec:
            spec_dict: Dict[str, Union[float, str]] = {}
            if spec.cpus is not None:
                spec_dict["cpus"] = spec.cpus
            if spec.memory is not None:
                spec_dict["memory"] = spec.memory
            if spec_dict:
                payload["spec"] = spec_dict

        headers = {"X-SESSION-ID": session_id}

        async with session.post(
            f"{self.endpoint_url}/ship", json=payload, headers=headers
        ) as response:
            if response.status == 201:
                ship_data = await response.json()
                return SessionShip(self, ship_data, session_id)
            else:
                error_text = await response.text()
                raise Exception(
                    f"Failed to create ship: {response.status} {error_text}"
                )

    async def get_or_create_session(
        self,
        session_id: str,
        ttl: int = 3600,
        spec: Optional[Spec] = None,
    ) -> SessionShip:
        """
        Get or create a session with a dedicated ship.

        This is the recommended Session-First API. If a session already exists
        with a running ship, it will be returned. Otherwise, a new ship will
        be created (or allocated from the warm pool).

        Args:
            session_id: The session ID to get or create
            ttl: Time to live in seconds (default: 1 hour)
            spec: Ship specifications for resource allocation

        Returns:
            SessionShip: The session's ship
        """
        return await self.create_ship(ttl=ttl, spec=spec, session_id=session_id)

    def session(
        self,
        session_id: str,
        ttl: int = 3600,
        spec: Optional[Spec] = None,
    ) -> "SessionContext":
        """
        Context manager for working with a session.

        Usage:
            async with client.session("my-session") as session:
                result = await session.python.exec("print('hello')")

        Args:
            session_id: The session ID
            ttl: Time to live in seconds (default: 1 hour)
            spec: Ship specifications for resource allocation

        Returns:
            SessionContext: Context manager that yields a SessionShip
        """
        return SessionContext(self, session_id, ttl, spec)

    async def get_ship(self, ship_id: str) -> Optional[Dict[str, Any]]:
        """Get ship information by ID"""
        session = await self._get_session()

        async with session.get(f"{self.endpoint_url}/ship/{ship_id}") as response:
            if response.status == 200:
                return await response.json()
            elif response.status == 404:
                return None
            else:
                error_text = await response.text()
                raise Exception(f"Failed to get ship: {response.status} {error_text}")

    async def extend_ship_ttl(self, ship_id: str, ttl: int) -> Dict[str, Any]:
        """Extend ship TTL"""
        session = await self._get_session()

        payload = {"ttl": ttl}

        async with session.post(
            f"{self.endpoint_url}/ship/{ship_id}/extend-ttl", json=payload
        ) as response:
            if response.status == 200:
                return await response.json()
            else:
                error_text = await response.text()
                raise Exception(f"Failed to extend TTL: {response.status} {error_text}")

    async def get_ship_logs(self, ship_id: str) -> str:
        """Get ship container logs"""
        session = await self._get_session()

        async with session.get(f"{self.endpoint_url}/ship/logs/{ship_id}") as response:
            if response.status == 200:
                logs_data = await response.json()
                return logs_data.get("logs", "")
            else:
                error_text = await response.text()
                raise Exception(f"Failed to get logs: {response.status} {error_text}")

    async def _exec_operation(
        self,
        ship_id: str,
        operation_type: str,
        payload: Dict[str, Any],
        session_id: str,
    ) -> Dict[str, Any]:
        """Execute operation on ship"""
        session = await self._get_session()

        request_payload = {"type": operation_type, "payload": payload}

        headers = {"X-SESSION-ID": session_id}

        async with session.post(
            f"{self.endpoint_url}/ship/{ship_id}/exec",
            json=request_payload,
            headers=headers,
        ) as response:
            if response.status == 200:
                exec_response = await response.json()
                return exec_response
            else:
                error_text = await response.text()
                raise Exception(
                    f"Failed to execute operation: {response.status} {error_text}"
                )

    async def upload_file(
        self, ship_id: str, file_path: str, session_id: str, remote_file_path: str
    ) -> Dict[str, Any]:
        """Upload file to ship container"""
        session = await self._get_session()

        # Create multipart form data
        form_data = aiohttp.FormData()

        with open(file_path, "rb") as f:
            form_data.add_field(
                "file", f, filename="upload", content_type="application/octet-stream"
            )
            form_data.add_field("file_path", remote_file_path)

            headers = {"X-SESSION-ID": session_id}

            async with session.post(
                f"{self.endpoint_url}/ship/{ship_id}/upload",
                data=form_data,
                headers=headers,
            ) as response:
                if response.status == 200:
                    return await response.json()
                else:
                    error_text = await response.text()
                    raise Exception(
                        f"Failed to upload file: {response.status} {error_text}"
                    )

    async def download_file(
        self, ship_id: str, remote_file_path: str, session_id: str, local_file_path: str
    ) -> None:
        """Download file from ship container"""
        session = await self._get_session()

        headers = {"X-SESSION-ID": session_id}
        params = {"file_path": remote_file_path}

        async with session.get(
            f"{self.endpoint_url}/ship/{ship_id}/download",
            params=params,
            headers=headers,
        ) as response:
            if response.status == 200:
                # Write file content to local file
                content = await response.read()
                with open(local_file_path, "wb") as f:
                    f.write(content)
            else:
                error_text = await response.text()
                raise Exception(
                    f"Failed to download file: {response.status} {error_text}"
                )

    async def get_execution_history(
        self,
        session_id: str,
        exec_type: Optional[str] = None,
        success_only: bool = False,
        limit: int = 100,
        offset: int = 0,
    ) -> Dict[str, Any]:
        """
        Get execution history for a session.

        This enables agents to retrieve their successful execution paths
        for skill library construction (inspired by VOYAGER).

        Args:
            session_id: The session ID
            exec_type: Filter by type ('python' or 'shell')
            success_only: If True, only return successful executions
            limit: Maximum number of entries to return
            offset: Number of entries to skip

        Returns:
            Dict with 'entries' list and 'total' count
        """
        session = await self._get_session()

        params: Dict[str, Any] = {"limit": limit, "offset": offset}
        if exec_type:
            params["exec_type"] = exec_type
        if success_only:
            params["success_only"] = "true"

        async with session.get(
            f"{self.endpoint_url}/sessions/{session_id}/history",
            params=params,
        ) as response:
            if response.status == 200:
                return await response.json()
            else:
                error_text = await response.text()
                raise Exception(
                    f"Failed to get execution history: {response.status} {error_text}"
                )


class SessionContext:
    """Context manager for working with a session."""

    def __init__(
        self,
        client: ShipyardClient,
        session_id: str,
        ttl: int,
        spec: Optional[Spec],
    ):
        self._client = client
        self._session_id = session_id
        self._ttl = ttl
        self._spec = spec
        self._ship: Optional[SessionShip] = None

    async def __aenter__(self) -> SessionShip:
        self._ship = await self._client.get_or_create_session(
            session_id=self._session_id,
            ttl=self._ttl,
            spec=self._spec,
        )
        return self._ship

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        # Session resources are managed by TTL, no cleanup needed
        pass

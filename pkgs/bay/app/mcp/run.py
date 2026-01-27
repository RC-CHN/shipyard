#!/usr/bin/env python3
"""
Shipyard MCP Server Entry Point

Run the MCP server in stdio mode for integration with
MCP-compatible clients (Claude Desktop, Cursor, etc.)

Usage:
    python -m app.mcp.run

Environment variables:
    SHIPYARD_ENDPOINT: Bay API URL (default: http://localhost:8156)
    SHIPYARD_TOKEN: Access token (default: secret-token)
"""

import asyncio
from .server import main

if __name__ == "__main__":
    asyncio.run(main())

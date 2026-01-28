#!/usr/bin/env python3
"""
Shipyard MCP Server Entry Point

Run the MCP server in stdio mode for integration with
MCP-compatible clients (Claude Desktop, ChatGPT, Cursor, VS Code, etc.)

Usage:
    # Default stdio mode
    python -m app.mcp.run

    # HTTP mode for remote deployments
    python -m app.mcp.run --transport http --port 8000

Environment variables:
    SHIPYARD_ENDPOINT: Bay API URL (default: http://localhost:8156)
    SHIPYARD_TOKEN: Access token for Bay API authentication (required)
"""

from .server import main

if __name__ == "__main__":
    main()

# shipyard-mcp

Shipyard MCP Server - Execute Python and shell commands in isolated sandboxes via Model Context Protocol.

## Overview

This package provides an MCP (Model Context Protocol) server that enables AI assistants to execute code in secure, isolated sandbox environments powered by [Shipyard](https://github.com/AstrBotDevs/shipyard).

**Compatible with all major MCP clients:**
- Claude Desktop (Anthropic)
- ChatGPT Desktop (OpenAI)
- Cursor
- VS Code (GitHub Copilot)
- Gemini (Google)
- Any MCP-compatible client

## Installation

```bash
npm install -g shipyard-mcp
```

**Prerequisites:**
- Node.js 18+
- Python 3.11+
- A running Shipyard Bay instance

## Quick Start

1. Set your Shipyard access token:
```bash
export SHIPYARD_TOKEN=your-access-token
```

2. Run the MCP server:
```bash
shipyard-mcp
```

3. Configure your MCP client (see below)

## Configuration

### Claude Desktop

Add to `~/.config/claude/claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "shipyard": {
      "command": "shipyard-mcp",
      "env": {
        "SHIPYARD_ENDPOINT": "http://localhost:8156",
        "SHIPYARD_TOKEN": "your-access-token"
      }
    }
  }
}
```

### Cursor

Add to `~/.cursor/mcp.json`:

```json
{
  "mcpServers": {
    "shipyard": {
      "command": "shipyard-mcp",
      "env": {
        "SHIPYARD_ENDPOINT": "http://localhost:8156",
        "SHIPYARD_TOKEN": "your-access-token"
      }
    }
  }
}
```

### VS Code (GitHub Copilot)

Add to VS Code settings:

```json
{
  "github.copilot.chat.mcpServers": {
    "shipyard": {
      "command": "shipyard-mcp",
      "env": {
        "SHIPYARD_ENDPOINT": "http://localhost:8156",
        "SHIPYARD_TOKEN": "your-access-token"
      }
    }
  }
}
```

## Available Tools

| Tool | Description |
|------|-------------|
| `execute_python` | Execute Python code in the sandbox |
| `execute_shell` | Execute shell commands |
| `read_file` | Read file contents |
| `write_file` | Write to files |
| `list_files` | List directory contents |
| `install_package` | Install Python packages via pip |
| `get_sandbox_info` | Get current sandbox information |
| `get_execution_history` | View past executions |

## CLI Options

```bash
shipyard-mcp [options]

Options:
  --transport <stdio|http>  Transport mode (default: stdio)
  --port <number>           HTTP port (default: 8000)
  --host <string>           HTTP host (default: 0.0.0.0)
  --help, -h                Show help
```

## Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `SHIPYARD_ENDPOINT` | Bay API URL | `http://localhost:8156` |
| `SHIPYARD_TOKEN` | Access token | (required) |
| `SHIPYARD_SANDBOX_TTL` | Sandbox TTL in seconds | `1800` (30 min) |

## Transport Modes

### stdio (Default)

Standard I/O transport for local integration with desktop apps. One process = one session = one sandbox.

```bash
shipyard-mcp
```

### HTTP (Streamable HTTP)

HTTP transport for remote/hosted deployments. **Each MCP client session gets its own isolated sandbox.**

```bash
shipyard-mcp --transport http --port 8000
```

In HTTP mode:
- Each client connection gets a unique session ID
- Sessions are isolated - Client A cannot see Client B's variables or files
- Sandboxes are automatically cleaned up via TTL when clients disconnect
- TTL is renewed on each tool call to keep active sessions alive

## Architecture

```
┌─────────────────┐     MCP Protocol      ┌─────────────────┐
│   MCP Client    │◄────────────────────►│  shipyard-mcp   │
│ (Claude/Cursor) │       (stdio)         │    (Node.js)    │
└─────────────────┘                       └────────┬────────┘
                                                   │
                                                   │ spawns
                                                   ▼
                                          ┌─────────────────┐
                                          │  Python Server  │
                                          │   (FastMCP)     │
                                          └────────┬────────┘
                                                   │
                                                   │ HTTP/REST
                                                   ▼
                                          ┌─────────────────┐
                                          │    Bay API      │
                                          └────────┬────────┘
                                                   │
                                                   ▼
                                          ┌─────────────────┐
                                          │  Ship Container │
                                          │  (Python/Shell) │
                                          └─────────────────┘
```

## Session Isolation (HTTP Mode)

When running in HTTP mode, each MCP client session is completely isolated:

```
Client A (mcp-session-aaa) ──► Sandbox A (ship-111)
    │
    │ execute_python("x = 123")  ✓
    │
Client B (mcp-session-bbb) ──► Sandbox B (ship-222)
    │
    │ execute_python("print(x)")  ✗ NameError (isolated!)
```

This ensures:
- **State isolation**: Different clients have separate Python variables
- **File isolation**: File operations are container-specific
- **Security**: One client cannot access another's data
- **Resource management**: Each sandbox has its own TTL

## Security

- Each session gets a dedicated, isolated container
- Code execution is sandboxed
- Containers have configurable network access
- Resources are automatically cleaned up via TTL
- HTTP mode provides per-client session isolation

## Development

```bash
# Clone the repository
git clone https://github.com/AstrBotDevs/shipyard.git
cd shipyard/pkgs/mcp-server

# Install dependencies
npm install

# Run locally
npm run build
./bin/shipyard-mcp.js
```

## License

MIT

## Links

- [Shipyard GitHub](https://github.com/AstrBotDevs/shipyard)
- [MCP Specification](https://modelcontextprotocol.io)
- [MCP Python SDK](https://github.com/modelcontextprotocol/python-sdk)

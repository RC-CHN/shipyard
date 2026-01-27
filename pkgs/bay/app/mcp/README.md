# Shipyard MCP Server

Shipyard provides an MCP (Model Context Protocol) server that enables AI assistants to execute Python code and shell commands in isolated sandbox environments.

## Compatibility

Shipyard MCP Server is compatible with all MCP clients:

| Client | Status | Notes |
|--------|--------|-------|
| Claude Desktop | ✅ Supported | Anthropic's official client |
| ChatGPT Desktop | ✅ Supported | OpenAI adopted MCP in March 2025 |
| Cursor | ✅ Supported | Built-in MCP support |
| VS Code (Copilot) | ✅ Supported | GitHub Copilot Agent Mode |
| Gemini | ✅ Supported | Google DeepMind MCP support |
| Any MCP Client | ✅ Supported | Standard MCP protocol |

## Installation

### Prerequisites

1. Install the MCP SDK:
```bash
pip install mcp
```

2. Set up environment variables:
```bash
export SHIPYARD_ENDPOINT=http://localhost:8156  # Bay API URL
export SHIPYARD_TOKEN=your-access-token         # Required
```

### Install from source

```bash
cd pkgs/bay
pip install -e .
```

## Usage

### stdio mode (for desktop apps)

This is the default mode for integration with Claude Desktop, ChatGPT, Cursor, etc.

```bash
python -m app.mcp.run
```

Or using the installed script:
```bash
shipyard-mcp
```

### HTTP mode (for remote deployments)

For hosted/remote MCP servers:

```bash
python -m app.mcp.run --transport http --port 8000
```

## Configuration

### Claude Desktop

Add to `~/.config/claude/claude_desktop_config.json` (Linux) or `~/Library/Application Support/Claude/claude_desktop_config.json` (macOS):

```json
{
  "mcpServers": {
    "shipyard": {
      "command": "python",
      "args": ["-m", "app.mcp.run"],
      "cwd": "/path/to/shipyard/pkgs/bay",
      "env": {
        "SHIPYARD_ENDPOINT": "http://localhost:8156",
        "SHIPYARD_TOKEN": "your-access-token"
      }
    }
  }
}
```

### Cursor

Add to Cursor settings (`~/.cursor/mcp.json`):

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

### VS Code with GitHub Copilot

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

The MCP server exposes the following tools:

| Tool | Description |
|------|-------------|
| `execute_python` | Execute Python code in the sandbox |
| `execute_shell` | Execute shell commands |
| `read_file` | Read file contents |
| `write_file` | Write to files |
| `list_files` | List directory contents |
| `install_package` | Install Python packages via pip |
| `get_sandbox_info` | Get current sandbox information |

### Example: execute_python

```python
# Request
{
    "tool": "execute_python",
    "arguments": {
        "code": "import pandas as pd\ndf = pd.DataFrame({'a': [1,2,3]})\nprint(df)",
        "timeout": 30
    }
}

# Response
"Output:\n   a\n0  1\n1  2\n2  3"
```

### Example: execute_shell

```python
# Request
{
    "tool": "execute_shell",
    "arguments": {
        "command": "ls -la /workspace"
    }
}

# Response
"total 4\ndrwxr-xr-x 2 user user 4096 Jan 27 00:00 .\n..."
```

## Resources

The server provides an informational resource:

- `sandbox://info` - Information about the Shipyard sandbox service

## Architecture

```
┌─────────────────┐     MCP Protocol      ┌─────────────────┐
│   MCP Client    │◄────────────────────►│  Shipyard MCP   │
│ (Claude/Cursor) │   (stdio or HTTP)     │     Server      │
└─────────────────┘                       └────────┬────────┘
                                                   │
                                                   │ HTTP/REST
                                                   ▼
                                          ┌─────────────────┐
                                          │    Bay API      │
                                          │   (FastAPI)     │
                                          └────────┬────────┘
                                                   │
                                                   │ Container API
                                                   ▼
                                          ┌─────────────────┐
                                          │  Ship Container │
                                          │  (Python/Shell) │
                                          └─────────────────┘
```

## Security

- Each session gets a dedicated, isolated container
- Code execution is sandboxed
- Containers have configurable network access
- Resources are automatically cleaned up via TTL

## Troubleshooting

### "SHIPYARD_TOKEN environment variable is required"

Set the `SHIPYARD_TOKEN` environment variable to your Bay API access token.

### Connection refused

Ensure the Bay API is running at the configured `SHIPYARD_ENDPOINT`.

### Tool execution timeout

Increase the `timeout` parameter in tool arguments (default: 30 seconds).

## Development

### Testing with MCP Inspector

```bash
# Install MCP Inspector
npm install -g @modelcontextprotocol/inspector

# Start the MCP server
python -m app.mcp.run

# In another terminal, run the inspector
npx @modelcontextprotocol/inspector
```

### Running tests

```bash
cd pkgs/bay
pytest tests/ -v
```

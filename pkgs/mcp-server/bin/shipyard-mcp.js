#!/usr/bin/env node
/**
 * Shipyard MCP Server CLI Entry Point
 *
 * This launcher finds and runs the Python-based MCP server.
 */

import { spawn } from "node:child_process";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";
import { existsSync } from "node:fs";

const __filename = fileURLToPath(import.meta.url);
const __dirname = dirname(__filename);

// Parse command line arguments
const args = process.argv.slice(2);
let transport = "stdio";
let port = "8000";
let host = "0.0.0.0";
let showHelp = false;

for (let i = 0; i < args.length; i++) {
  if (args[i] === "--transport" && args[i + 1]) {
    transport = args[++i];
  } else if (args[i] === "--port" && args[i + 1]) {
    port = args[++i];
  } else if (args[i] === "--host" && args[i + 1]) {
    host = args[++i];
  } else if (args[i] === "--help" || args[i] === "-h") {
    showHelp = true;
  }
}

if (showHelp) {
  console.log(`
Shipyard MCP Server

Execute Python and shell commands in isolated sandboxes via MCP protocol.

Usage:
  shipyard-mcp [options]

Options:
  --transport <stdio|http>  Transport mode (default: stdio)
  --port <number>           HTTP port (default: 8000)
  --host <string>           HTTP host (default: 0.0.0.0)
  --help, -h                Show this help

Environment:
  SHIPYARD_ENDPOINT  Bay API URL (default: http://localhost:8156)
  SHIPYARD_TOKEN     Access token for Bay API (required)

Examples:
  shipyard-mcp
  shipyard-mcp --transport http --port 8000
  SHIPYARD_TOKEN=xxx shipyard-mcp

More info: https://github.com/AstrBotDevs/shipyard
`);
  process.exit(0);
}

// Check for SHIPYARD_TOKEN
if (!process.env.SHIPYARD_TOKEN) {
  console.error("Error: SHIPYARD_TOKEN environment variable is required.");
  console.error("Example: export SHIPYARD_TOKEN=your-access-token");
  process.exit(1);
}

// Find Python
const pythonCmds = ["python3", "python"];
let pythonCmd = null;

for (const cmd of pythonCmds) {
  try {
    const result = spawn(cmd, ["--version"], { stdio: "pipe" });
    if (result.pid) {
      pythonCmd = cmd;
      result.kill();
      break;
    }
  } catch {
    // Continue
  }
}

if (!pythonCmd) {
  console.error("Error: Python 3 is required but not found.");
  process.exit(1);
}

// Path to Python server
const pythonServerPath = join(__dirname, "..", "python");

if (!existsSync(pythonServerPath)) {
  console.error("Error: Python MCP server not found at:", pythonServerPath);
  process.exit(1);
}

// Build args
const pythonArgs = ["-m", "server"];
if (transport !== "stdio") {
  pythonArgs.push("--transport", transport);
}
if (transport === "http") {
  pythonArgs.push("--port", port, "--host", host);
}

// Spawn Python
const child = spawn(pythonCmd, pythonArgs, {
  cwd: pythonServerPath,
  stdio: "inherit",
  env: { ...process.env, PYTHONUNBUFFERED: "1" },
});

child.on("error", (err) => {
  console.error("Failed to start:", err.message);
  process.exit(1);
});

child.on("exit", (code) => process.exit(code ?? 0));

process.on("SIGINT", () => child.kill("SIGINT"));
process.on("SIGTERM", () => child.kill("SIGTERM"));

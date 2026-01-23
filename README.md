# Shipyard

> This project is in technical preview, contributions and feedback are welcome!

✨ **Shipyard** is a lightweight Agent Sandbox environment designed for AI Agents. It supports multi-session sandbox reuse and provides isolated environments for **Python code execution**, **Shell commands**, and **File System** operations. ✨

## Key Features

- 🚀 **Lightweight & Fast**: Quick sandbox provisioning and low overhead.
- 🔄 **Session Reuse**: Efficiently manages and reuses sandboxes across multiple sessions.
- 🛡️ **Isolated Execution**: Securely runs Python and Shell commands in containerized environments.
- 🔌 **Pluggable Drivers**: Supports Docker, Podman, and Kubernetes.
- 💾 **Persistence**: Built-in support for data persistence across container restarts.
- 📦 **Python SDK**: Easy-to-use async SDK for seamless integration.

## Quick Start

Docker images are available on Docker Hub:
- **Bay (Controller)**: `soulter/shipyard-bay:latest`
- **Ship (Sandbox)**: `soulter/shipyard-ship:latest`
 
## Architecture

```text
User <───> Bay <───> Ship
```

- **Bay**: The central management and scheduling service. It orchestrates Ship lifecycles and routes requests.
- **Ship**: An isolated, containerized execution environment that provides Python, Shell, and File System APIs.

## Environment Configuration

- `MAX_SHIP_NUM`: Maximum number of allowed Ships (Default: `10`).
- `BEHAVIOR_AFTER_MAX_SHIP`: Strategy when the limit is reached (Default: `reject`).
  - `reject`: Deny new Ship requests.
  - `wait`: Wait until a Ship is released.
- `ACCESS_TOKEN`: Security token for API access (Default: `secret-token`).
- `CONTAINER_DRIVER`: The runtime driver to use (`docker`, `docker-host`, `podman`, `podman-host`, `kubernetes`).

## Packages

### Bay (Management Service)

The mid-office service built with FastAPI.

#### Main API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/ship` | `POST` | Create/Request a new sandbox session. |
| `/ship/{id}` | `GET` | Get information about a specific Ship. |
| `/ship/{id}` | `DELETE` | Manually terminate a Ship. |
| `/ship/{id}/exec` | `POST` | Execute operations (Shell, Python, FS) in the Ship. |
| `/ship/logs/{id}` | `GET` | Retrieve container logs. |
| `/ship/{id}/upload` | `POST` | Upload files to the sandbox workspace. |

**Required Headers:**
- `Authorization`: `Bearer <token>`
- `X-SESSION-ID`: Used for tracking and sandbox reuse.

---

### Ship (Sandbox Environment)

A containerized environment running a FastAPI-based execution service.

#### 1. Python Interpreter
Execute Python code with persistent state using IPython.
- `type: ipython/exec`

#### 2. Shell
Execute standard shell commands and manage processes.
- `type: shell/exec`
- `type: shell/processes`
- `type: shell/cwd`

#### 3. File System (FS)
Standard file and directory operations.
- `type: fs/create_file`, `fs/read_file`, `fs/write_file`, `fs/delete_file`, `fs/list_dir`

---

### Shipyard Python SDK

Integrate Shipyard into your Python applications effortlessly.

```python
from shipyard_python_sdk import ShipyardClient, Spec

async def main():
    client = ShipyardClient(endpoint_url="http://localhost:8156", access_token="your-token")
    
    # Create or get a ship
    ship = await client.create_ship(ttl=3600, spec=Spec(cpus=1.0, memory="512m"))
    
    # Execute Python code
    result = await ship.python.exec("print('Hello from Shipyard!')")
    
    # File operations
    await ship.fs.write_file("data.txt", "Some content")
    
    await client.close()
```

## Drivers & Persistence

| Driver | Deployment | Network Mode |
|--------|------------|--------------|
| **docker-host** | Bay on Host | Localhost + Port Mapping |
| **docker** | Bay in Docker | Container Network IPs |
| **kubernetes** | K8s Cluster | Pod IPs + PVC Storage |
| **podman** | Podman Env | Container Network IPs |

For **Docker/Podman**, data is persisted in `~/.shipyard/ships/{ship_id}/`. 
For **Kubernetes**, Shipyard utilizes Persistent Volume Claims (PVCs) to ensure data is retained even if a Pod is rescheduled.

## Development

```bash
# Install dependencies
uv pip install -e .

# Run linting
ruff check app/

# Run tests
pytest
```

## License

Apache-2.0 License

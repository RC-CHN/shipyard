"""
Shipyard Python SDK

A Python SDK for interacting with Shipyard containerized execution environments.
Provides convenient access to file system, shell, and Python execution capabilities.

Quick Start:
    from shipyard import Sandbox

    async with Sandbox() as sandbox:
        result = await sandbox.python.exec("print('hello')")
        print(result.stdout)
"""

from .types import Spec, ShipInfo
from .client import ShipyardClient
from .session import SessionShip
from .filesystem import FileSystemComponent
from .shell import ShellComponent
from .python import PythonComponent
from .utils import create_session_ship
from .sandbox import Sandbox, ExecResult, run_python, run_shell

__version__ = "1.0.0"

__all__ = [
    # New unified interface
    "Sandbox",
    "ExecResult",
    "run_python",
    "run_shell",
    # Legacy interface (still supported)
    "Spec",
    "ShipInfo",
    "ShipyardClient",
    "SessionShip",
    "FileSystemComponent",
    "ShellComponent",
    "PythonComponent",
    "create_session_ship",
]

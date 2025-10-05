"""
Workspace management utilities for handling session-based file system operations.

This module provides utilities for managing per-session workspaces, ensuring
that each session has its own isolated file system environment while maintaining
security by preventing access outside the designated workspace directories.
"""

from pathlib import Path
from fastapi import HTTPException

# 工作目录根路径
WORKSPACE_ROOT = Path("workspace")
WORKSPACE_ROOT.mkdir(exist_ok=True)


def get_session_workspace(session_id: str) -> Path:
    """
    获取 session 的工作目录

    Args:
        session_id: 会话ID

    Returns:
        Path: session 的工作目录路径
    """
    workspace_dir = WORKSPACE_ROOT / session_id
    workspace_dir.mkdir(parents=True, exist_ok=True)
    return workspace_dir


def resolve_path(session_id: str, path: str) -> Path:
    """
    安全的路径解析，适用于上传等需要额外安全检查的场景

    Args:
        session_id: 会话ID
        path: 要解析的路径

    Returns:
        Path: 解析后的绝对路径

    Raises:
        HTTPException: 当路径在工作目录外时抛出403错误
    """
    workspace_dir = get_session_workspace(session_id).resolve()
    candidate = Path(path)

    if not candidate.is_absolute():
        candidate = workspace_dir / candidate

    candidate = candidate.resolve()
    try:
        candidate.relative_to(workspace_dir)
    except ValueError:
        raise HTTPException(
            status_code=403,
            detail=f"Access denied: path must be within workspace {workspace_dir}",
        )

    return candidate


def get_workspace_root() -> Path:
    """
    获取工作目录根路径

    Returns:
        Path: 工作目录根路径
    """
    return WORKSPACE_ROOT


def ensure_workspace_exists(session_id: str) -> None:
    """
    确保指定 session 的工作目录存在

    Args:
        session_id: 会话ID
    """
    get_session_workspace(session_id)

import asyncio
import os
import signal
from typing import Dict, Optional, Any
from fastapi import APIRouter, HTTPException, Header
from pydantic import BaseModel
from pathlib import Path
from ..workspace import get_session_workspace
from .user_manager import run_as_user

router = APIRouter()


class ExecuteShellRequest(BaseModel):
    command: str
    cwd: Optional[str] = None
    env: Optional[Dict[str, str]] = None
    timeout: Optional[int] = 30
    shell: bool = True
    background: bool = False


class ExecuteShellResponse(BaseModel):
    success: bool
    return_code: Optional[int] = None
    stdout: str = ""
    stderr: str = ""
    pid: Optional[int] = None
    # process_id: Optional[str] = None  # 用于后台进程
    error: Optional[str] = None


class ProcessInfo(BaseModel):
    # process_id: str
    pid: int
    command: str
    status: str


def generate_process_id() -> str:
    """生成进程ID"""
    import uuid

    return str(uuid.uuid4())[:8]


async def run_command(
    session_id: str,
    command: str,
    cwd: Optional[str] = None,
    env: Optional[Dict[str, str]] = None,
    timeout: Optional[int] = None,
    shell: bool = True,
    background: bool = False,
) -> Dict[str, Any]:
    """执行shell命令"""

    # 准备环境变量
    process_env = os.environ.copy()
    if env:
        process_env.update(env)

    # 准备工作目录。如果未指定，使用 session 工作目录
    if cwd is None:
        working_dir = await get_session_workspace(session_id)
    else:
        # 相对路径相对于 session 工作目录解析
        if not os.path.isabs(cwd):
            working_dir = await get_session_workspace(session_id) / cwd
        else:
            working_dir = Path(cwd)

    if not working_dir.exists():
        raise ValueError(f"Working directory does not exist: {working_dir}")

    try:
        if shell:
            # 使用shell模式
            process = await asyncio.create_subprocess_shell(
                command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=str(working_dir),
                env=process_env,
            )
        else:
            # 分割命令参数
            args = command.split()
            process = await asyncio.create_subprocess_exec(
                *args,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=str(working_dir),
                env=process_env,
            )

        if background:
            # 后台进程
            process_id = generate_process_id()

            return {
                "success": True,
                "pid": process.pid,
                "process_id": process_id,
                "return_code": None,
                "stdout": "",
                "stderr": "",
                "error": None,
            }
        else:
            # 前台进程，等待完成
            try:
                stdout, stderr = await asyncio.wait_for(
                    process.communicate(), timeout=timeout
                )

                return {
                    "success": process.returncode == 0,
                    "return_code": process.returncode,
                    "stdout": stdout.decode("utf-8", errors="replace"),
                    "stderr": stderr.decode("utf-8", errors="replace"),
                    "pid": process.pid,
                    "process_id": None,
                    "error": None,
                }

            except asyncio.TimeoutError:
                # 超时，终止进程
                try:
                    process.terminate()
                    await asyncio.wait_for(process.wait(), timeout=5)
                except asyncio.TimeoutError:
                    process.kill()
                    await process.wait()

                return {
                    "success": False,
                    "return_code": -signal.SIGTERM,
                    "stdout": "",
                    "stderr": "",
                    "pid": process.pid,
                    "process_id": None,
                    "error": f"Command timed out after {timeout} seconds",
                }

    except Exception as e:
        return {
            "success": False,
            "return_code": None,
            "stdout": "",
            "stderr": "",
            "pid": None,
            "process_id": None,
            "error": str(e),
        }


@router.post("/exec", response_model=ExecuteShellResponse)
async def execute_shell_command(
    request: ExecuteShellRequest, x_session_id: str = Header(..., alias="X-SESSION-ID")
):
    """执行Shell命令"""
    try:
        result = await run_as_user(
            username=x_session_id,
            command=request.command,
            cwd=request.cwd,
            env=request.env,
            timeout=request.timeout,
            shell=request.shell,
            background=request.background,
        )

        return ExecuteShellResponse(**result.__dict__)

    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to execute command: {str(e)}"
        )

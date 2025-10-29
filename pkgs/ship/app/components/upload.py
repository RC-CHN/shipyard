import aiofiles
from fastapi import APIRouter, HTTPException, Header, UploadFile, File, Form
from pydantic import BaseModel
from typing import Optional
from ..workspace import resolve_path

router = APIRouter()


class UploadResponse(BaseModel):
    success: bool
    message: str
    file_path: Optional[str] = None
    size: Optional[int] = None
    error: Optional[str] = None


@router.post("/upload", response_model=UploadResponse)
async def upload_file(
    file: UploadFile = File(...),
    file_path: str = Form(...),
    x_session_id: str = Header(..., alias="X-SESSION-ID"),
):
    """上传文件到session工作目录"""
    try:
        # 解析并验证目标路径
        target_path = await resolve_path(x_session_id, file_path)

        # 确保父目录存在
        target_path.parent.mkdir(parents=True, exist_ok=True)

        # 读取文件内容并写入目标路径
        content = await file.read()

        async with aiofiles.open(target_path, "wb") as f:
            await f.write(content)

        return UploadResponse(
            success=True,
            message="File uploaded successfully",
            file_path=str(target_path),
            size=len(content),
        )

    except HTTPException:
        # 重新抛出HTTP异常（如路径验证失败）
        raise
    except Exception as e:
        return UploadResponse(success=False, message="File upload failed", error=str(e))


@router.get("/health")
async def upload_health():
    """上传服务健康检查"""
    return {"status": "healthy", "service": "upload"}

"""
Bay API E2E 测试

需要 Bay 服务运行，测试完整的 API 功能。

使用方法:
    # 确保 Bay 服务正在运行
    # 设置环境变量（可选）：
    #   BAY_URL=http://localhost:8156
    #   BAY_ACCESS_TOKEN=secret-token

    pytest tests/e2e/ -v
"""

from __future__ import annotations

import io
import os
import time
import uuid
from contextlib import contextmanager
from typing import Any, Generator

import pytest
import requests


# 配置 - 支持从环境变量覆盖
BAY_URL = os.getenv("BAY_URL", "http://localhost:8156")
ACCESS_TOKEN = os.getenv("BAY_ACCESS_TOKEN", "secret-token")


def get_auth_headers(session_id: str | None = None) -> dict[str, str]:
    """获取认证请求头"""
    sid = session_id or str(uuid.uuid4())
    return {
        "Authorization": f"Bearer {ACCESS_TOKEN}",
        "X-SESSION-ID": sid,
    }


@contextmanager
def fresh_ship(
    session_id: str | None = None,
    ttl: int = 60,
    cpus: float = 0.5,
    memory: str = "256m",
    disk: str | None = None,
) -> Generator[tuple[str, dict], None, None]:
    """
    创建独立的 Ship 容器用于单个测试，测试结束后自动清理。

    Yields:
        tuple[ship_id, headers]: Ship ID 和请求头
    """
    # 生成唯一的 session ID
    test_session_id = session_id or f"test-{uuid.uuid4().hex[:12]}"
    headers = get_auth_headers(test_session_id)

    ship_id = None
    try:
        # 创建 Ship
        spec: dict[str, Any] = {"cpus": cpus, "memory": memory}
        if disk:
            spec["disk"] = disk
        payload = {"ttl": ttl, "max_session_num": 1, "spec": spec}

        resp = requests.post(
            f"{BAY_URL}/ship",
            headers={**headers, "Content-Type": "application/json"},
            json=payload,
            timeout=120,
        )
        if resp.status_code != 201:
            raise RuntimeError(f"创建 Ship 失败: {resp.status_code} - {resp.text}")

        data = resp.json()
        ship_id = data.get("id")

        # 等待容器就绪
        time.sleep(2)

        yield ship_id, headers

    finally:
        # 清理容器
        if ship_id:
            try:
                requests.delete(
                    f"{BAY_URL}/ship/{ship_id}",
                    headers=headers,
                    timeout=30,
                )
            except Exception:
                pass  # 清理失败不影响测试结果


@pytest.fixture(scope="module")
def bay_url() -> str:
    """返回 Bay 服务 URL"""
    return BAY_URL


@pytest.fixture(scope="module")
def auth_headers() -> dict[str, str]:
    """返回认证请求头"""
    return get_auth_headers()


@pytest.mark.e2e
class TestHealthAndBasicEndpoints:
    """阶段 1: 健康检查和基础端点测试（无容器）"""

    def test_health(self, bay_url):
        """/health 健康检查"""
        resp = requests.get(f"{bay_url}/health", timeout=5)
        assert resp.status_code == 200, f"健康检查失败: {resp.text}"

    def test_root(self, bay_url):
        """/ 根路由"""
        resp = requests.get(f"{bay_url}/", timeout=5)
        assert resp.status_code == 200, f"根路由失败: {resp.text}"

    def test_stat(self, bay_url):
        """/stat 版本信息"""
        resp = requests.get(f"{bay_url}/stat", timeout=5)
        assert resp.status_code == 200, f"统计信息失败: {resp.text}"


@pytest.mark.e2e
class TestAuthentication:
    """阶段 2: 认证测试"""

    def test_auth_required(self, bay_url):
        """未授权访问应被拒绝"""
        resp = requests.get(f"{bay_url}/ships", timeout=5)
        assert resp.status_code in [401, 403], f"未授权访问未被拒绝: {resp.status_code}"

    def test_list_ships_with_auth(self, bay_url, auth_headers):
        """/ships 列出 Ships（需要认证）"""
        resp = requests.get(f"{bay_url}/ships", headers=auth_headers, timeout=5)
        assert resp.status_code == 200, f"列出 ships 失败: {resp.text}"


@pytest.mark.e2e
class TestShipCreation:
    """阶段 3: Ship 创建相关测试"""

    def test_create_ship_invalid_payload(self, bay_url, auth_headers):
        """/ship 创建 Ship（非法参数）"""
        payload = {"ttl": 0, "max_session_num": 0}
        resp = requests.post(
            f"{bay_url}/ship",
            headers={**auth_headers, "Content-Type": "application/json"},
            json=payload,
            timeout=10,
        )
        assert resp.status_code == 422, f"非法参数未被拒绝: {resp.status_code}"

    def test_create_ship_with_small_memory(self, bay_url, auth_headers):
        """创建 Ship（极小内存自动修正）"""
        # 使用 1m 内存 (1 MiB)，如果没有修正，容器必死无疑
        payload = {
            "ttl": 60,
            "max_session_num": 1,
            "spec": {"cpus": 0.1, "memory": "1m"},
        }
        resp = requests.post(
            f"{bay_url}/ship",
            headers={**auth_headers, "Content-Type": "application/json"},
            json=payload,
            timeout=120,
        )
        assert resp.status_code == 201, f"极小内存 Ship 创建失败: {resp.text}"

        data = resp.json()
        ship_id = data.get("id")

        # 清理
        requests.delete(f"{bay_url}/ship/{ship_id}", headers=auth_headers, timeout=30)

    def test_create_ship_with_disk(self, bay_url, auth_headers):
        """创建 Ship（带磁盘限制）"""
        payload = {
            "ttl": 60,
            "max_session_num": 1,
            "spec": {"cpus": 0.5, "memory": "256m", "disk": "2Gi"},
        }
        resp = requests.post(
            f"{bay_url}/ship",
            headers={**auth_headers, "Content-Type": "application/json"},
            json=payload,
            timeout=120,
        )
        assert resp.status_code == 201, f"带磁盘限制的 Ship 创建失败: {resp.text}"

        data = resp.json()
        ship_id = data.get("id")

        # 清理
        requests.delete(f"{bay_url}/ship/{ship_id}", headers=auth_headers, timeout=30)


@pytest.mark.e2e
class TestShipOperations:
    """阶段 4: Ship 操作测试（每个测试使用独立容器）"""

    def test_create_and_get_ship(self, bay_url):
        """创建和获取 Ship"""
        with fresh_ship(ttl=60) as (ship_id, headers):
            # 验证可以获取 Ship 信息
            resp = requests.get(
                f"{bay_url}/ship/{ship_id}", headers=headers, timeout=5
            )
            assert resp.status_code == 200, f"获取 ship 信息失败: {resp.text}"

    def test_get_ship_not_found(self, bay_url, auth_headers):
        """获取不存在的 Ship"""
        resp = requests.get(
            f"{bay_url}/ship/not-exists-id",
            headers=auth_headers,
            timeout=5,
        )
        assert resp.status_code == 404, f"不存在 ship 未返回 404: {resp.status_code}"

    def test_exec_shell(self, bay_url):
        """执行 Shell 命令"""
        with fresh_ship() as (ship_id, headers):
            payload = {"type": "shell/exec", "payload": {"command": "echo Bay"}}
            resp = requests.post(
                f"{bay_url}/ship/{ship_id}/exec",
                headers={**headers, "Content-Type": "application/json"},
                json=payload,
                timeout=30,
            )
            assert resp.status_code == 200, f"Shell 命令执行失败: {resp.text}"

    def test_exec_invalid_type(self, bay_url):
        """非法操作类型"""
        with fresh_ship() as (ship_id, headers):
            payload = {"type": "unknown/exec", "payload": {"foo": "bar"}}
            resp = requests.post(
                f"{bay_url}/ship/{ship_id}/exec",
                headers={**headers, "Content-Type": "application/json"},
                json=payload,
                timeout=30,
            )
            assert resp.status_code == 400, f"非法操作未被拒绝: {resp.status_code}"

    def test_extend_ttl(self, bay_url):
        """扩展 TTL"""
        with fresh_ship() as (ship_id, headers):
            payload = {"ttl": 600}
            resp = requests.post(
                f"{bay_url}/ship/{ship_id}/extend-ttl",
                headers={**headers, "Content-Type": "application/json"},
                json=payload,
                timeout=10,
            )
            assert resp.status_code == 200, f"TTL 扩展失败: {resp.text}"

    def test_get_logs(self, bay_url):
        """获取日志"""
        with fresh_ship() as (ship_id, headers):
            resp = requests.get(
                f"{bay_url}/ship/logs/{ship_id}", headers=headers, timeout=10
            )
            assert resp.status_code == 200, f"获取日志失败: {resp.text}"

    def test_upload_download(self, bay_url):
        """上传和下载文件"""
        with fresh_ship() as (ship_id, headers):
            content = b"hello from bay upload"
            file_obj = io.BytesIO(content)
            files = {"file": ("hello.txt", file_obj, "text/plain")}
            # 使用相对路径，会自动相对于 workspace 目录解析
            workspace_path = "hello.txt"
            data = {"file_path": workspace_path}

            upload_resp = requests.post(
                f"{bay_url}/ship/{ship_id}/upload",
                headers=headers,
                files=files,
                data=data,
                timeout=30,
            )
            assert upload_resp.status_code == 200, f"上传失败: {upload_resp.text}"

            download_resp = requests.get(
                f"{bay_url}/ship/{ship_id}/download",
                headers=headers,
                params={"file_path": workspace_path},
                timeout=30,
            )
            assert download_resp.status_code == 200, f"下载失败: {download_resp.status_code}"
            assert download_resp.content == content, "下载内容不匹配"

    def test_filesystem_operations(self, bay_url):
        """文件系统操作测试（创建、读取、写入、列表、删除）"""
        with fresh_ship() as (ship_id, headers):
            headers_with_content_type = {**headers, "Content-Type": "application/json"}

            # 1. 创建文件
            create_file_data = {
                "type": "fs/create_file",
                "payload": {"path": "test_file.txt", "content": "Hello, World!"},
            }
            resp = requests.post(
                f"{bay_url}/ship/{ship_id}/exec",
                headers=headers_with_content_type,
                json=create_file_data,
                timeout=30,
            )
            assert resp.status_code == 200, f"创建文件失败: {resp.text}"
            result = resp.json()
            assert result.get("success") is True, f"创建文件操作失败: {result}"

            # 2. 读取文件
            read_file_data = {
                "type": "fs/read_file",
                "payload": {"path": "test_file.txt"},
            }
            resp = requests.post(
                f"{bay_url}/ship/{ship_id}/exec",
                headers=headers_with_content_type,
                json=read_file_data,
                timeout=30,
            )
            assert resp.status_code == 200, f"读取文件失败: {resp.text}"
            result = resp.json()
            assert result.get("success") is True, f"读取文件操作失败: {result}"
            assert result["data"]["content"] == "Hello, World!", "文件内容不匹配"

            # 3. 写入文件
            write_file_data = {
                "type": "fs/write_file",
                "payload": {"path": "test_file.txt", "content": "Updated content!"},
            }
            resp = requests.post(
                f"{bay_url}/ship/{ship_id}/exec",
                headers=headers_with_content_type,
                json=write_file_data,
                timeout=30,
            )
            assert resp.status_code == 200, f"写入文件失败: {resp.text}"
            result = resp.json()
            assert result.get("success") is True, f"写入文件操作失败: {result}"

            # 4. 列表目录
            list_dir_data = {
                "type": "fs/list_dir",
                "payload": {"path": "./"},
            }
            resp = requests.post(
                f"{bay_url}/ship/{ship_id}/exec",
                headers=headers_with_content_type,
                json=list_dir_data,
                timeout=30,
            )
            assert resp.status_code == 200, f"列表目录失败: {resp.text}"
            result = resp.json()
            assert result.get("success") is True, f"列表目录操作失败: {result}"

            # 5. 删除文件
            delete_file_data = {
                "type": "fs/delete_file",
                "payload": {"path": "test_file.txt"},
            }
            resp = requests.post(
                f"{bay_url}/ship/{ship_id}/exec",
                headers=headers_with_content_type,
                json=delete_file_data,
                timeout=30,
            )
            assert resp.status_code == 200, f"删除文件失败: {resp.text}"
            result = resp.json()
            assert result.get("success") is True, f"删除文件操作失败: {result}"

    def test_ipython_operations(self, bay_url):
        """IPython 操作测试"""
        with fresh_ship() as (ship_id, headers):
            headers_with_content_type = {**headers, "Content-Type": "application/json"}

            # 1. 执行简单 Python 代码
            ipython_data = {
                "type": "ipython/exec",
                "payload": {"code": "x = 5 + 3\nprint(f'Result: {x}')", "timeout": 10},
            }
            resp = requests.post(
                f"{bay_url}/ship/{ship_id}/exec",
                headers=headers_with_content_type,
                json=ipython_data,
                timeout=30,
            )
            assert resp.status_code == 200, f"IPython 执行失败: {resp.text}"
            result = resp.json()
            assert result.get("success") is True, f"IPython 操作失败: {result}"
            assert "Result: 8" in result["data"]["output"]["text"], f"IPython 输出不匹配: {result}"

            # 2. 执行带 import 的代码
            import_data = {
                "type": "ipython/exec",
                "payload": {
                    "code": "import math\nresult = math.sqrt(16)\nprint(f'Square root of 16 is {result}')",
                    "timeout": 10,
                },
            }
            resp = requests.post(
                f"{bay_url}/ship/{ship_id}/exec",
                headers=headers_with_content_type,
                json=import_data,
                timeout=30,
            )
            assert resp.status_code == 200, f"IPython import 执行失败: {resp.text}"
            result = resp.json()
            assert result.get("success") is True, f"IPython import 操作失败: {result}"
            assert "Square root of 16 is 4.0" in result["data"]["output"]["text"], f"IPython import 输出不匹配: {result}"


@pytest.mark.e2e
class TestShipDeletion:
    """阶段 5: Ship 删除测试"""

    def test_delete_ship_not_found(self, bay_url):
        """删除不存在的 Ship（创建-删除-再删除）"""
        # 创建独立的 session
        test_session_id = f"delete-test-{uuid.uuid4().hex[:8]}"
        headers = get_auth_headers(test_session_id)

        # 创建 Ship
        spec: dict[str, Any] = {"cpus": 0.5, "memory": "256m"}
        payload = {"ttl": 60, "max_session_num": 1, "spec": spec}

        resp = requests.post(
            f"{bay_url}/ship",
            headers={**headers, "Content-Type": "application/json"},
            json=payload,
            timeout=120,
        )
        assert resp.status_code == 201, f"创建 Ship 失败: {resp.status_code}"

        data = resp.json()
        ship_id = data.get("id")

        # 等待容器就绪
        time.sleep(2)

        # 第一次删除，应该成功
        resp = requests.delete(
            f"{bay_url}/ship/{ship_id}",
            headers=headers,
            timeout=30,
        )
        assert resp.status_code == 204, f"第一次删除失败: {resp.status_code}"

        # 第二次删除，应该返回 404
        resp = requests.delete(
            f"{bay_url}/ship/{ship_id}",
            headers=headers,
            timeout=10,
        )
        assert resp.status_code == 404, f"重复删除未返回 404: {resp.status_code}"


@pytest.mark.e2e
class TestMultipleSessions:
    """阶段 5.5: 多会话复用测试"""

    def test_multiple_sessions(self, bay_url):
        """测试 Ship 多会话复用功能

        创建一个 max_session_num=2 的 Ship，然后用不同的 session ID 访问，
        验证是否可以复用同一个 Ship。
        """
        # 创建第一个 session
        session_id_1 = f"multi-session-test-{uuid.uuid4().hex[:8]}"
        headers_1 = get_auth_headers(session_id_1)

        # 创建 Ship with max_session_num = 2
        payload = {
            "ttl": 600,
            "max_session_num": 2,
            "spec": {"cpus": 0.5, "memory": "256m"},
        }

        resp = requests.post(
            f"{bay_url}/ship",
            headers={**headers_1, "Content-Type": "application/json"},
            json=payload,
            timeout=120,
        )
        assert resp.status_code == 201, f"创建 Ship 失败: {resp.status_code}"

        ship_data = resp.json()
        ship_id = ship_data.get("id")
        assert ship_data.get("current_session_num") == 1, "初始会话数应为 1"

        try:
            # 等待 Ship 就绪
            time.sleep(3)

            # 用第二个 session ID 请求
            session_id_2 = f"multi-session-test-{uuid.uuid4().hex[:8]}"
            headers_2 = get_auth_headers(session_id_2)

            resp = requests.post(
                f"{bay_url}/ship",
                headers={**headers_2, "Content-Type": "application/json"},
                json=payload,
                timeout=120,
            )
            # 应该成功创建或复用
            assert resp.status_code == 201, f"第二个会话请求失败: {resp.status_code}"

            reused_ship = resp.json()
            # 记录是否复用了同一个 Ship
            if reused_ship.get("id") == ship_id:
                # 复用了同一个 Ship
                assert reused_ship.get("current_session_num") == 2, "复用后会话数应为 2"
            # 如果是新 Ship 也是可以接受的行为

        finally:
            # 清理
            requests.delete(
                f"{bay_url}/ship/{ship_id}",
                headers=headers_1,
                timeout=30,
            )


@pytest.mark.e2e
class TestDataPersistence:
    """阶段 6: 数据持久化测试

    验证容器停止后重新启动时数据是否保留。
    注意：此测试有特定的执行顺序要求，必须按步骤执行。
    """

    def test_data_persistence(self, bay_url):
        """
        测试数据持久化完整流程：
        1. 创建 Ship
        2. 写入测试文件
        3. 删除 Ship
        4. 使用相同 Session ID 重新创建 Ship
        5. 验证测试文件仍然存在
        """
        # 使用一个固定的 Session ID 以便测试恢复功能
        persistence_session_id = f"persistence-test-{uuid.uuid4().hex[:8]}"
        persistence_headers = get_auth_headers(persistence_session_id)

        test_filename = "persistence_test.txt"
        test_content = f"Persistence test content - {uuid.uuid4().hex}"
        ship_id = None

        try:
            # Step 1: 创建 Ship
            payload = {
                "ttl": 120,
                "max_session_num": 1,
                "spec": {"cpus": 0.5, "memory": "256m"},
            }
            resp = requests.post(
                f"{bay_url}/ship",
                headers={**persistence_headers, "Content-Type": "application/json"},
                json=payload,
                timeout=120,
            )
            assert resp.status_code == 201, f"创建 Ship 失败: {resp.status_code} - {resp.text}"

            data = resp.json()
            ship_id = data.get("id")

            # 等待 Ship 完全就绪
            time.sleep(3)

            # Step 2: 写入测试文件
            exec_payload = {
                "type": "fs/write_file",
                "payload": {
                    "path": test_filename,
                    "content": test_content,
                },
            }
            resp = requests.post(
                f"{bay_url}/ship/{ship_id}/exec",
                headers={**persistence_headers, "Content-Type": "application/json"},
                json=exec_payload,
                timeout=30,
            )
            assert resp.status_code == 200, f"写入文件失败: {resp.status_code} - {resp.text}"

            # Step 3: 验证文件已写入
            exec_payload = {
                "type": "fs/read_file",
                "payload": {"path": test_filename},
            }
            resp = requests.post(
                f"{bay_url}/ship/{ship_id}/exec",
                headers={**persistence_headers, "Content-Type": "application/json"},
                json=exec_payload,
                timeout=30,
            )
            assert resp.status_code == 200, f"读取文件失败: {resp.status_code} - {resp.text}"
            exec_result = resp.json()
            read_data = exec_result.get("data", {})
            actual_content = read_data.get("content")
            assert actual_content == test_content, f"文件内容不匹配: 期望 {test_content!r}, 实际 {actual_content!r}"

            # Step 4: 删除 Ship
            resp = requests.delete(
                f"{bay_url}/ship/{ship_id}",
                headers=persistence_headers,
                timeout=30,
            )
            assert resp.status_code == 204, f"删除 Ship 失败: {resp.status_code} - {resp.text}"

            # 等待容器完全停止
            time.sleep(3)

            # Step 5: 使用相同 Session ID 重新创建 Ship
            payload = {
                "ttl": 120,
                "max_session_num": 1,
                "spec": {"cpus": 0.5, "memory": "256m"},
            }
            resp = requests.post(
                f"{bay_url}/ship",
                headers={**persistence_headers, "Content-Type": "application/json"},
                json=payload,
                timeout=120,
            )
            assert resp.status_code == 201, f"重新创建 Ship 失败: {resp.status_code} - {resp.text}"

            data = resp.json()
            new_ship_id = data.get("id")

            # 更新 ship_id 用于后续清理
            if new_ship_id != ship_id:
                ship_id = new_ship_id

            # 等待 Ship 完全就绪
            time.sleep(3)

            # Step 6: 验证文件仍然存在
            exec_payload = {
                "type": "fs/read_file",
                "payload": {"path": test_filename},
            }
            resp = requests.post(
                f"{bay_url}/ship/{ship_id}/exec",
                headers={**persistence_headers, "Content-Type": "application/json"},
                json=exec_payload,
                timeout=30,
            )
            assert resp.status_code == 200, f"读取文件失败（持久化验证）: {resp.status_code} - {resp.text}"

            exec_result = resp.json()
            read_data = exec_result.get("data", {})
            actual_content = read_data.get("content")
            assert actual_content == test_content, f"持久化失败：文件内容不匹配: 期望 {test_content!r}, 实际 {actual_content!r}"

        finally:
            # 清理：删除测试 Ship
            if ship_id:
                try:
                    requests.delete(
                        f"{bay_url}/ship/{ship_id}",
                        headers=persistence_headers,
                        timeout=30,
                    )
                except Exception:
                    pass

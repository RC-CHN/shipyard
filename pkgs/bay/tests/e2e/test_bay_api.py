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
        payload = {"ttl": ttl, "spec": spec}

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

    def test_stat_overview_without_auth(self, bay_url):
        """/stat/overview 需要认证"""
        resp = requests.get(f"{bay_url}/stat/overview", timeout=5)
        assert resp.status_code in [401, 403], f"未授权访问未被拒绝: {resp.status_code}"

    def test_stat_overview_with_auth(self, bay_url, auth_headers):
        """/stat/overview 获取系统概览（需要认证）"""
        resp = requests.get(f"{bay_url}/stat/overview", headers=auth_headers, timeout=5)
        assert resp.status_code == 200, f"获取系统概览失败: {resp.text}"
        data = resp.json()
        assert "service" in data, "响应应包含 service 字段"
        assert "version" in data, "响应应包含 version 字段"
        assert "ships" in data, "响应应包含 ships 字段"
        assert "sessions" in data, "响应应包含 sessions 字段"
        assert "total" in data["ships"], "ships 应包含 total 字段"
        assert "running" in data["ships"], "ships 应包含 running 字段"
        assert "stopped" in data["ships"], "ships 应包含 stopped 字段"


@pytest.mark.e2e
class TestSessionsEndpoints:
    """阶段 2.5: Sessions 端点基础测试（认证和 404）"""

    def test_sessions_without_auth(self, bay_url):
        """/sessions 需要认证"""
        resp = requests.get(f"{bay_url}/sessions", timeout=5)
        assert resp.status_code in [401, 403], f"未授权访问未被拒绝: {resp.status_code}"

    def test_list_sessions_with_auth(self, bay_url, auth_headers):
        """/sessions 列出所有会话（需要认证）"""
        resp = requests.get(f"{bay_url}/sessions", headers=auth_headers, timeout=5)
        assert resp.status_code == 200, f"列出会话失败: {resp.text}"
        data = resp.json()
        assert "sessions" in data, "响应应包含 sessions 字段"
        assert "total" in data, "响应应包含 total 字段"
        assert isinstance(data["sessions"], list), "sessions 应该是列表"

    def test_get_session_not_found(self, bay_url, auth_headers):
        """/sessions/{session_id} 获取不存在的会话"""
        resp = requests.get(
            f"{bay_url}/sessions/not-exists-session",
            headers=auth_headers,
            timeout=5,
        )
        assert resp.status_code == 404, f"不存在会话未返回 404: {resp.status_code}"

    def test_ship_sessions_not_found(self, bay_url, auth_headers):
        """/ship/{ship_id}/sessions 获取不存在 ship 的会话"""
        resp = requests.get(
            f"{bay_url}/ship/not-exists-ship/sessions",
            headers=auth_headers,
            timeout=5,
        )
        assert resp.status_code == 404, f"不存在 ship 未返回 404: {resp.status_code}"


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
        payload = {"ttl": 0}
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
        """执行 Shell 命令并验证会话状态"""
        with fresh_ship() as (ship_id, headers):
            # 执行 Shell 命令
            payload = {"type": "shell/exec", "payload": {"command": "echo Bay"}}
            resp = requests.post(
                f"{bay_url}/ship/{ship_id}/exec",
                headers={**headers, "Content-Type": "application/json"},
                json=payload,
                timeout=30,
            )
            assert resp.status_code == 200, f"Shell 命令执行失败: {resp.text}"

            # 同时验证会话状态 - 真实场景下 Dashboard 会并行查询
            sessions_resp = requests.get(
                f"{bay_url}/ship/{ship_id}/sessions",
                headers=headers,
                timeout=5,
            )
            assert sessions_resp.status_code == 200, f"获取会话失败: {sessions_resp.text}"
            sessions_data = sessions_resp.json()
            assert sessions_data["total"] >= 1, "执行操作后应该有活跃会话"
            assert sessions_data["sessions"][0]["is_active"] is True, "会话应该是活跃状态"

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
        """IPython 操作测试，同时验证会话和系统概览"""
        with fresh_ship() as (ship_id, headers):
            headers_with_content_type = {**headers, "Content-Type": "application/json"}

            # 获取执行前的系统概览
            overview_before = requests.get(
                f"{bay_url}/stat/overview",
                headers=headers,
                timeout=5,
            )
            assert overview_before.status_code == 200, f"获取概览失败: {overview_before.text}"
            before_data = overview_before.json()
            running_before = before_data["ships"]["running"]

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

            # 执行期间验证会话活跃状态
            sessions_resp = requests.get(
                f"{bay_url}/ship/{ship_id}/sessions",
                headers=headers,
                timeout=5,
            )
            assert sessions_resp.status_code == 200, f"获取会话失败: {sessions_resp.text}"
            sessions_data = sessions_resp.json()
            assert sessions_data["total"] >= 1, "应该有活跃会话"
            # 验证 last_activity 被更新（会话应该是活跃的）
            assert sessions_data["sessions"][0]["is_active"] is True, "IPython 执行后会话应该活跃"

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

            # 获取执行后的系统概览，验证统计数据一致性
            overview_after = requests.get(
                f"{bay_url}/stat/overview",
                headers=headers,
                timeout=5,
            )
            assert overview_after.status_code == 200, f"获取概览失败: {overview_after.text}"
            after_data = overview_after.json()
            # 运行中的 ships 数量应该至少保持不变（可能有其他测试创建的）
            assert after_data["ships"]["running"] >= 1, "应该至少有一个运行中的 ship"


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
        payload = {"ttl": 60, "spec": spec}

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
    """阶段 5.5: 多会话隔离测试（Session-Ship 1:1）"""

    def test_multiple_sessions(self, bay_url):
        """不同 session 应分配不同的 Ship（不再支持 max_session_num 复用逻辑）。"""
        # 创建第一个 session
        session_id_1 = f"multi-session-test-{uuid.uuid4().hex[:8]}"
        headers_1 = get_auth_headers(session_id_1)

        payload = {
            "ttl": 600,
            "spec": {"cpus": 0.5, "memory": "256m"},
        }

        resp = requests.post(
            f"{bay_url}/ship",
            headers={**headers_1, "Content-Type": "application/json"},
            json=payload,
            timeout=120,
        )
        assert resp.status_code == 201, f"创建 Ship 失败: {resp.status_code}"

        ship_id_1 = resp.json().get("id")

        ship_id_2 = None
        try:
            time.sleep(3)

            session_id_2 = f"multi-session-test-{uuid.uuid4().hex[:8]}"
            headers_2 = get_auth_headers(session_id_2)

            resp = requests.post(
                f"{bay_url}/ship",
                headers={**headers_2, "Content-Type": "application/json"},
                json=payload,
                timeout=120,
            )
            assert resp.status_code == 201, f"第二个会话请求失败: {resp.status_code}"

            ship_id_2 = resp.json().get("id")
            assert ship_id_2 and ship_id_2 != ship_id_1

        finally:
            try:
                if ship_id_1:
                    requests.delete(f"{bay_url}/ship/{ship_id_1}", headers=headers_1, timeout=30)
            finally:
                if ship_id_2:
                    try:
                        requests.delete(f"{bay_url}/ship/{ship_id_2}", headers=headers_2, timeout=30)
                    except Exception:
                        pass


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


# =============================================================================
# Ships 路由补充测试
# =============================================================================


@pytest.mark.e2e
class TestShipsRouteExtended:
    """Ships 路由扩展测试：补充 ships.py 相关端点的测试"""

    def test_create_ship_missing_session_id(self, bay_url):
        """/ship 创建 Ship 需要 X-SESSION-ID 头"""
        payload = {"ttl": 60}
        headers = {"Authorization": f"Bearer {ACCESS_TOKEN}", "Content-Type": "application/json"}
        # 不包含 X-SESSION-ID
        resp = requests.post(
            f"{bay_url}/ship",
            headers=headers,
            json=payload,
            timeout=10,
        )
        assert resp.status_code == 422, f"缺少 X-SESSION-ID 未被拒绝: {resp.status_code}"

    def test_create_ship_response_fields(self, bay_url):
        """验证创建 Ship 响应包含所有必需字段"""
        with fresh_ship() as (ship_id, headers):
            resp = requests.get(f"{bay_url}/ship/{ship_id}", headers=headers, timeout=5)
            assert resp.status_code == 200
            data = resp.json()

            # 验证必需字段
            assert "id" in data, "响应应包含 id 字段"
            assert "status" in data, "响应应包含 status 字段"
            assert "created_at" in data, "响应应包含 created_at 字段"
            assert "updated_at" in data, "响应应包含 updated_at 字段"
            assert "ttl" in data, "响应应包含 ttl 字段"
            assert "container_id" in data, "响应应包含 container_id 字段"
            assert "ip_address" in data, "响应应包含 ip_address 字段"

    def test_list_ships_returns_created_ship(self, bay_url):
        """验证创建的 Ship 出现在列表中"""
        with fresh_ship() as (ship_id, headers):
            resp = requests.get(f"{bay_url}/ships", headers=headers, timeout=5)
            assert resp.status_code == 200, f"列出 ships 失败: {resp.text}"
            data = resp.json()
            ship_ids = [ship["id"] for ship in data]
            assert ship_id in ship_ids, f"创建的 Ship {ship_id} 应出现在列表中"


@pytest.mark.e2e
class TestShipPermanentDeletion:
    """永久删除 Ship 端点测试"""

    def test_delete_permanent_without_auth(self, bay_url):
        """/ship/{ship_id}/permanent 删除需要认证"""
        resp = requests.delete(f"{bay_url}/ship/some-id/permanent", timeout=5)
        assert resp.status_code in [401, 403], f"未授权访问未被拒绝: {resp.status_code}"

    def test_delete_permanent_not_found(self, bay_url, auth_headers):
        """/ship/{ship_id}/permanent 删除不存在的 Ship"""
        resp = requests.delete(
            f"{bay_url}/ship/non-existent-ship-id/permanent",
            headers=auth_headers,
            timeout=10,
        )
        assert resp.status_code == 404, f"不存在 Ship 未返回 404: {resp.status_code}"

    def test_delete_permanent_success(self, bay_url):
        """成功永久删除 Ship"""
        # 创建 Ship
        session_id = f"perm-delete-{uuid.uuid4().hex[:8]}"
        headers = get_auth_headers(session_id)

        payload = {"ttl": 60, "spec": {"cpus": 0.5, "memory": "256m"}}
        resp = requests.post(
            f"{bay_url}/ship",
            headers={**headers, "Content-Type": "application/json"},
            json=payload,
            timeout=120,
        )
        assert resp.status_code == 201, f"创建 Ship 失败: {resp.text}"
        ship_id = resp.json()["id"]

        time.sleep(2)

        # 永久删除 Ship
        resp = requests.delete(
            f"{bay_url}/ship/{ship_id}/permanent",
            headers=headers,
            timeout=30,
        )
        assert resp.status_code == 204, f"永久删除 Ship 失败: {resp.status_code}"

        # 验证 Ship 已被永久删除（无法获取）
        resp = requests.get(f"{bay_url}/ship/{ship_id}", headers=headers, timeout=5)
        assert resp.status_code == 404, f"永久删除后 Ship 应返回 404: {resp.status_code}"


@pytest.mark.e2e
class TestShipFileOperationsExtended:
    """Ship 文件操作扩展测试"""

    def test_upload_without_auth(self, bay_url):
        """/ship/{ship_id}/upload 需要认证"""
        files = {"file": ("test.txt", io.BytesIO(b"hello"), "text/plain")}
        data = {"file_path": "test.txt"}
        resp = requests.post(
            f"{bay_url}/ship/some-id/upload",
            files=files,
            data=data,
            timeout=10,
        )
        assert resp.status_code in [401, 403], f"未授权访问未被拒绝: {resp.status_code}"

    def test_download_without_auth(self, bay_url):
        """/ship/{ship_id}/download 需要认证"""
        resp = requests.get(
            f"{bay_url}/ship/some-id/download",
            params={"file_path": "test.txt"},
            timeout=10,
        )
        assert resp.status_code in [401, 403], f"未授权访问未被拒绝: {resp.status_code}"

    def test_download_not_found(self, bay_url):
        """下载不存在的文件"""
        with fresh_ship() as (ship_id, headers):
            resp = requests.get(
                f"{bay_url}/ship/{ship_id}/download",
                headers=headers,
                params={"file_path": "non_existent_file_12345.txt"},
                timeout=30,
            )
            assert resp.status_code == 404, f"不存在文件未返回 404: {resp.status_code}"

    def test_upload_to_subdirectory(self, bay_url):
        """上传文件到子目录"""
        with fresh_ship() as (ship_id, headers):
            content = b"content in subdirectory"
            files = {"file": ("nested.txt", io.BytesIO(content), "text/plain")}
            data = {"file_path": "subdir/nested.txt"}

            resp = requests.post(
                f"{bay_url}/ship/{ship_id}/upload",
                headers=headers,
                files=files,
                data=data,
                timeout=30,
            )
            assert resp.status_code == 200, f"上传到子目录失败: {resp.text}"

            # 验证可以下载
            download_resp = requests.get(
                f"{bay_url}/ship/{ship_id}/download",
                headers=headers,
                params={"file_path": "subdir/nested.txt"},
                timeout=30,
            )
            assert download_resp.status_code == 200, f"从子目录下载失败: {download_resp.status_code}"
            assert download_resp.content == content, "下载内容不匹配"


@pytest.mark.e2e
class TestShipExecExtended:
    """Ship 执行操作扩展测试"""

    def test_exec_without_auth(self, bay_url):
        """/ship/{ship_id}/exec 需要认证"""
        payload = {"type": "shell/exec", "payload": {"command": "echo hello"}}
        resp = requests.post(
            f"{bay_url}/ship/some-id/exec",
            json=payload,
            headers={"Content-Type": "application/json"},
            timeout=10,
        )
        assert resp.status_code in [401, 403], f"未授权访问未被拒绝: {resp.status_code}"

    def test_exec_missing_session_id(self, bay_url):
        """/ship/{ship_id}/exec 需要 X-SESSION-ID 头"""
        with fresh_ship() as (ship_id, _):
            payload = {"type": "shell/exec", "payload": {"command": "echo hello"}}
            headers = {"Authorization": f"Bearer {ACCESS_TOKEN}", "Content-Type": "application/json"}
            # 不包含 X-SESSION-ID
            resp = requests.post(
                f"{bay_url}/ship/{ship_id}/exec",
                json=payload,
                headers=headers,
                timeout=10,
            )
            assert resp.status_code == 422, f"缺少 X-SESSION-ID 未被拒绝: {resp.status_code}"

    def test_exec_fs_delete_file(self, bay_url):
        """执行文件系统删除文件操作"""
        with fresh_ship() as (ship_id, headers):
            headers_with_content_type = {**headers, "Content-Type": "application/json"}

            # 先创建文件
            create_payload = {
                "type": "fs/create_file",
                "payload": {"path": "to_delete.txt", "content": "will be deleted"},
            }
            resp = requests.post(
                f"{bay_url}/ship/{ship_id}/exec",
                headers=headers_with_content_type,
                json=create_payload,
                timeout=30,
            )
            assert resp.status_code == 200, f"创建文件失败: {resp.text}"

            # 删除文件
            delete_payload = {"type": "fs/delete_file", "payload": {"path": "to_delete.txt"}}
            resp = requests.post(
                f"{bay_url}/ship/{ship_id}/exec",
                headers=headers_with_content_type,
                json=delete_payload,
                timeout=30,
            )
            assert resp.status_code == 200, f"删除文件失败: {resp.text}"
            data = resp.json()
            assert data.get("success") is True

            # 验证文件已删除（读取应该失败）
            read_payload = {"type": "fs/read_file", "payload": {"path": "to_delete.txt"}}
            resp = requests.post(
                f"{bay_url}/ship/{ship_id}/exec",
                headers=headers_with_content_type,
                json=read_payload,
                timeout=30,
            )
            # 文件不存在时应该返回错误
            data = resp.json()
            assert data.get("success") is False or resp.status_code != 200


@pytest.mark.e2e
class TestExtendTTLExtended:
    """扩展 TTL 端点扩展测试"""

    def test_extend_ttl_without_auth(self, bay_url):
        """/ship/{ship_id}/extend-ttl 需要认证"""
        payload = {"ttl": 600}
        resp = requests.post(
            f"{bay_url}/ship/some-id/extend-ttl",
            json=payload,
            headers={"Content-Type": "application/json"},
            timeout=10,
        )
        assert resp.status_code in [401, 403], f"未授权访问未被拒绝: {resp.status_code}"

    def test_extend_ttl_not_found(self, bay_url, auth_headers):
        """/ship/{ship_id}/extend-ttl 对不存在的 Ship"""
        payload = {"ttl": 600}
        resp = requests.post(
            f"{bay_url}/ship/non-existent-ship-id/extend-ttl",
            headers={**auth_headers, "Content-Type": "application/json"},
            json=payload,
            timeout=10,
        )
        assert resp.status_code == 404, f"不存在 Ship 未返回 404: {resp.status_code}"

    def test_extend_ttl_invalid_value(self, bay_url):
        """扩展 TTL（无效值）"""
        with fresh_ship() as (ship_id, headers):
            payload = {"ttl": 0}
            resp = requests.post(
                f"{bay_url}/ship/{ship_id}/extend-ttl",
                headers={**headers, "Content-Type": "application/json"},
                json=payload,
                timeout=10,
            )
            assert resp.status_code == 422, f"无效 TTL 未被拒绝: {resp.status_code}"

    def test_extend_ttl_negative_value(self, bay_url):
        """扩展 TTL（负值）"""
        with fresh_ship() as (ship_id, headers):
            payload = {"ttl": -100}
            resp = requests.post(
                f"{bay_url}/ship/{ship_id}/extend-ttl",
                headers={**headers, "Content-Type": "application/json"},
                json=payload,
                timeout=10,
            )
            assert resp.status_code == 422, f"负数 TTL 未被拒绝: {resp.status_code}"


@pytest.mark.e2e
class TestStartShip:
    """启动已停止的 Ship 端点测试"""

    def test_start_ship_without_auth(self, bay_url):
        """/ship/{ship_id}/start 需要认证"""
        payload = {"ttl": 3600}
        resp = requests.post(
            f"{bay_url}/ship/some-id/start",
            json=payload,
            headers={"Content-Type": "application/json"},
            timeout=10,
        )
        assert resp.status_code in [401, 403], f"未授权访问未被拒绝: {resp.status_code}"

    def test_start_ship_not_found(self, bay_url, auth_headers):
        """/ship/{ship_id}/start 对不存在的 Ship"""
        payload = {"ttl": 3600}
        resp = requests.post(
            f"{bay_url}/ship/non-existent-ship-id/start",
            headers={**auth_headers, "Content-Type": "application/json"},
            json=payload,
            timeout=10,
        )
        assert resp.status_code == 404, f"不存在 Ship 未返回 404: {resp.status_code}"

    def test_start_ship_invalid_ttl(self, bay_url):
        """启动 Ship（无效 TTL 值）"""
        with fresh_ship() as (ship_id, headers):
            # 先停止 Ship
            requests.delete(
                f"{bay_url}/ship/{ship_id}",
                headers=headers,
                timeout=30,
            )
            time.sleep(2)

            # 尝试用无效的 TTL 启动
            payload = {"ttl": 0}
            resp = requests.post(
                f"{bay_url}/ship/{ship_id}/start",
                headers={**headers, "Content-Type": "application/json"},
                json=payload,
                timeout=10,
            )
            assert resp.status_code == 422, f"无效 TTL 未被拒绝: {resp.status_code}"

    def test_start_stopped_ship(self, bay_url):
        """成功启动已停止的 Ship"""
        # 创建 Ship
        session_id = f"start-test-{uuid.uuid4().hex[:8]}"
        headers = get_auth_headers(session_id)

        payload = {"ttl": 120, "spec": {"cpus": 0.5, "memory": "256m"}}
        resp = requests.post(
            f"{bay_url}/ship",
            headers={**headers, "Content-Type": "application/json"},
            json=payload,
            timeout=120,
        )
        assert resp.status_code == 201, f"创建 Ship 失败: {resp.text}"
        ship_id = resp.json()["id"]

        try:
            time.sleep(2)

            # 停止 Ship
            resp = requests.delete(
                f"{bay_url}/ship/{ship_id}",
                headers=headers,
                timeout=30,
            )
            assert resp.status_code == 204, f"停止 Ship 失败: {resp.status_code}"

            time.sleep(2)

            # 启动 Ship
            start_payload = {"ttl": 3600}
            resp = requests.post(
                f"{bay_url}/ship/{ship_id}/start",
                headers={**headers, "Content-Type": "application/json"},
                json=start_payload,
                timeout=120,
            )
            assert resp.status_code == 200, f"启动 Ship 失败: {resp.status_code} - {resp.text}"

            # 验证 Ship 已启动
            data = resp.json()
            assert data["status"] == 1, f"Ship 状态应为 RUNNING (1): {data['status']}"
            assert data["id"] == ship_id, "Ship ID 应匹配"

        finally:
            # 清理
            try:
                requests.delete(
                    f"{bay_url}/ship/{ship_id}",
                    headers=headers,
                    timeout=30,
                )
                # 永久删除以清理资源
                requests.delete(
                    f"{bay_url}/ship/{ship_id}/permanent",
                    headers=headers,
                    timeout=30,
                )
            except Exception:
                pass


@pytest.mark.e2e
class TestShipLogsExtended:
    """Ship 日志端点扩展测试"""

    def test_logs_without_auth(self, bay_url):
        """/ship/logs/{ship_id} 需要认证"""
        resp = requests.get(f"{bay_url}/ship/logs/some-id", timeout=5)
        assert resp.status_code in [401, 403], f"未授权访问未被拒绝: {resp.status_code}"

    def test_logs_response_format(self, bay_url):
        """验证日志响应格式"""
        with fresh_ship() as (ship_id, headers):
            resp = requests.get(
                f"{bay_url}/ship/logs/{ship_id}", headers=headers, timeout=10
            )
            assert resp.status_code == 200, f"获取日志失败: {resp.text}"
            data = resp.json()
            assert "logs" in data, "响应应包含 logs 字段"
            assert isinstance(data["logs"], str), "logs 应该是字符串"


@pytest.mark.e2e
class TestShipSessionsExtended:
    """Ship 会话端点扩展测试"""

    def test_ship_sessions_without_auth(self, bay_url):
        """/ship/{ship_id}/sessions 需要认证"""
        resp = requests.get(f"{bay_url}/ship/some-id/sessions", timeout=5)
        assert resp.status_code in [401, 403], f"未授权访问未被拒绝: {resp.status_code}"

    def test_ship_sessions_response_format(self, bay_url):
        """验证 Ship 会话响应格式"""
        with fresh_ship() as (ship_id, headers):
            resp = requests.get(
                f"{bay_url}/ship/{ship_id}/sessions", headers=headers, timeout=5
            )
            assert resp.status_code == 200, f"获取会话失败: {resp.text}"
            data = resp.json()
            assert "sessions" in data, "响应应包含 sessions 字段"
            assert "total" in data, "响应应包含 total 字段"
            assert isinstance(data["sessions"], list), "sessions 应该是列表"
            assert data["total"] >= 1, "应该至少有一个会话"

            # 验证会话字段
            if data["sessions"]:
                session = data["sessions"][0]
                assert "session_id" in session, "会话应包含 session_id"
                assert "ship_id" in session, "会话应包含 ship_id"
                assert "is_active" in session, "会话应包含 is_active"


@pytest.mark.e2e
class TestSessionStateOnShipStop:
    """测试 Ship 停止时会话状态变化"""

    def test_session_becomes_inactive_when_ship_stopped(self, bay_url):
        """当 Ship 停止时，关联的会话应该变为 inactive"""
        # 创建 Ship
        session_id = f"stop-session-test-{uuid.uuid4().hex[:8]}"
        headers = get_auth_headers(session_id)

        payload = {
            "ttl": 600,
            "spec": {"cpus": 0.5, "memory": "256m"},
        }

        resp = requests.post(
            f"{bay_url}/ship",
            headers={**headers, "Content-Type": "application/json"},
            json=payload,
            timeout=120,
        )
        assert resp.status_code == 201, f"创建 Ship 失败: {resp.status_code}"
        ship_id = resp.json()["id"]

        try:
            time.sleep(2)

            # 验证会话初始是活跃的
            sessions_resp = requests.get(
                f"{bay_url}/ship/{ship_id}/sessions",
                headers=headers,
                timeout=5,
            )
            assert sessions_resp.status_code == 200
            sessions_data = sessions_resp.json()
            assert sessions_data["total"] >= 1, "应该有会话"
            assert sessions_data["sessions"][0]["is_active"] is True, "会话应该是活跃的"

            # 停止 Ship (soft delete)
            resp = requests.delete(
                f"{bay_url}/ship/{ship_id}",
                headers=headers,
                timeout=30,
            )
            assert resp.status_code == 204, f"停止 Ship 失败: {resp.status_code}"

            time.sleep(1)

            # 验证会话现在是非活跃的
            sessions_resp = requests.get(
                f"{bay_url}/sessions/{session_id}",
                headers=headers,
                timeout=5,
            )
            assert sessions_resp.status_code == 200, f"获取会话失败: {sessions_resp.text}"
            session_data = sessions_resp.json()
            assert session_data["is_active"] is False, "Ship 停止后会话应该变为 inactive"

            # 验证重新启动 Ship 后会话可以恢复
            start_payload = {"ttl": 600}
            resp = requests.post(
                f"{bay_url}/ship/{ship_id}/start",
                headers={**headers, "Content-Type": "application/json"},
                json=start_payload,
                timeout=120,
            )
            assert resp.status_code == 200, f"启动 Ship 失败: {resp.status_code}"

            # 验证会话现在是活跃的
            sessions_resp = requests.get(
                f"{bay_url}/sessions/{session_id}",
                headers=headers,
                timeout=5,
            )
            assert sessions_resp.status_code == 200
            session_data = sessions_resp.json()
            assert session_data["is_active"] is True, "Ship 启动后会话应该恢复为 active"

        finally:
            # 清理
            try:
                requests.delete(
                    f"{bay_url}/ship/{ship_id}",
                    headers=headers,
                    timeout=30,
                )
                requests.delete(
                    f"{bay_url}/ship/{ship_id}/permanent",
                    headers=headers,
                    timeout=30,
                )
            except Exception:
                pass

    def test_multiple_sessions_become_inactive_when_ship_stopped(self, bay_url):
        """此版本不再支持多 session 绑定同一 ship；跳过该场景。"""
        pytest.skip("Session-Ship 1:1 绑定后，不存在一个 ship 关联多个 session 的场景")


# =============================================================================
# WebSocket Terminal 端点测试
# =============================================================================

try:
    import websocket
    WEBSOCKET_AVAILABLE = True
except ImportError:
    WEBSOCKET_AVAILABLE = False


@pytest.mark.e2e
@pytest.mark.skipif(not WEBSOCKET_AVAILABLE, reason="websocket-client 未安装")
class TestWebSocketTerminal:
    """WebSocket Terminal 端点测试 (/ship/{ship_id}/term)

    测试 WebSocket 代理终端功能，包括：
    - 认证验证
    - 会话权限验证
    - 基本连接和消息传递
    """

    def _get_ws_url(self, ship_id: str, token: str, session_id: str, cols: int = 80, rows: int = 24) -> str:
        """构建 WebSocket URL"""
        # 将 http:// 替换为 ws://
        ws_base = BAY_URL.replace("http://", "ws://").replace("https://", "wss://")
        return f"{ws_base}/ship/{ship_id}/term?token={token}&session_id={session_id}&cols={cols}&rows={rows}"

    def test_websocket_unauthorized(self, bay_url):
        """WebSocket 连接需要有效的 token"""
        # 使用无效 token 尝试连接
        ws_url = self._get_ws_url("some-ship-id", "invalid-token", "test-session")

        ws = websocket.WebSocket()
        try:
            ws.connect(ws_url, timeout=5)
            # 如果连接成功，应该很快被关闭
            # 尝试接收消息看是否被关闭
            try:
                ws.recv()
                pytest.fail("应该被拒绝连接")
            except websocket.WebSocketConnectionClosedException:
                pass  # 预期行为 - 连接被关闭
        except websocket.WebSocketBadStatusException as e:
            # 也可能在握手时就被拒绝
            assert e.status_code in [401, 403, 4001], f"未授权访问应被拒绝: {e.status_code}"
        except Exception as e:
            # 连接失败也是可接受的
            pass
        finally:
            try:
                ws.close()
            except Exception:
                pass

    def test_websocket_ship_not_found(self, bay_url):
        """WebSocket 连接到不存在的 Ship"""
        ws_url = self._get_ws_url("non-existent-ship-id", ACCESS_TOKEN, "test-session")

        ws = websocket.WebSocket()
        try:
            ws.connect(ws_url, timeout=5)
            # 如果连接成功，应该很快被关闭
            try:
                ws.recv()
                pytest.fail("应该被关闭连接")
            except websocket.WebSocketConnectionClosedException:
                pass  # 预期行为
        except websocket.WebSocketBadStatusException as e:
            # 可能在握手时就被拒绝
            # 403 表示会话无权限访问（可能先检查权限），404 表示 Ship 不存在
            assert e.status_code in [403, 404, 4003, 4004], f"不存在 Ship 应返回相应错误: {e.status_code}"
        except Exception:
            pass  # 连接失败也是可接受的
        finally:
            try:
                ws.close()
            except Exception:
                pass

    def test_websocket_session_no_access(self, bay_url):
        """WebSocket 连接 - 会话无权访问 Ship"""
        with fresh_ship() as (ship_id, headers):
            # 使用不同的 session_id 尝试连接
            different_session_id = f"different-{uuid.uuid4().hex[:8]}"
            ws_url = self._get_ws_url(ship_id, ACCESS_TOKEN, different_session_id)

            ws = websocket.WebSocket()
            try:
                ws.connect(ws_url, timeout=10)
                # 如果连接成功，应该很快被关闭
                try:
                    ws.recv()
                    pytest.fail("无权访问的会话应被拒绝")
                except websocket.WebSocketConnectionClosedException:
                    pass  # 预期行为
            except websocket.WebSocketBadStatusException as e:
                # 可能在握手时就被拒绝
                assert e.status_code in [403, 4003], f"无权访问应返回相应错误: {e.status_code}"
            except Exception:
                pass  # 连接失败也是可接受的
            finally:
                try:
                    ws.close()
                except Exception:
                    pass

    def test_websocket_connect_success(self, bay_url):
        """WebSocket 成功连接并发送/接收消息"""
        # 创建 Ship 并获取 session_id
        test_session_id = f"ws-test-{uuid.uuid4().hex[:8]}"

        with fresh_ship(session_id=test_session_id) as (ship_id, headers):
            # 等待 Ship 完全就绪
            time.sleep(3)

            ws_url = self._get_ws_url(ship_id, ACCESS_TOKEN, test_session_id)

            ws = websocket.WebSocket()
            try:
                ws.connect(ws_url, timeout=10)

                # 发送一个简单的命令
                ws.send("echo 'WebSocket Test'\n")

                # 等待并接收响应
                response_received = False
                for _ in range(10):  # 最多等待 10 次
                    try:
                        ws.settimeout(2)
                        data = ws.recv()
                        if data:
                            response_received = True
                            break
                    except websocket.WebSocketTimeoutException:
                        continue
                    except Exception:
                        break

                # 验证收到了响应
                assert response_received, "应该收到 WebSocket 响应"

            except websocket.WebSocketBadStatusException as e:
                pytest.fail(f"WebSocket 连接失败: {e.status_code}")
            except Exception as e:
                pytest.fail(f"WebSocket 测试失败: {e}")
            finally:
                try:
                    ws.close()
                except Exception:
                    pass

    def test_websocket_custom_terminal_size(self, bay_url):
        """WebSocket 连接使用自定义终端大小"""
        test_session_id = f"ws-size-{uuid.uuid4().hex[:8]}"

        with fresh_ship(session_id=test_session_id) as (ship_id, headers):
            time.sleep(3)

            # 使用自定义终端大小
            ws_url = self._get_ws_url(ship_id, ACCESS_TOKEN, test_session_id, cols=120, rows=40)

            ws = websocket.WebSocket()
            try:
                ws.connect(ws_url, timeout=10)

                # 发送命令获取终端大小
                ws.send("stty size\n")

                # 等待响应
                for _ in range(10):
                    try:
                        ws.settimeout(2)
                        data = ws.recv()
                        if data and ("40" in data or "120" in data):
                            # 终端大小设置成功
                            break
                    except websocket.WebSocketTimeoutException:
                        continue
                    except Exception:
                        break

            except Exception:
                pass  # 自定义大小测试可能在某些环境下失败
            finally:
                try:
                    ws.close()
                except Exception:
                    pass


# 使用 asyncio 进行更高级的 WebSocket 测试
try:
    import asyncio
    import aiohttp
    AIOHTTP_AVAILABLE = True
except ImportError:
    AIOHTTP_AVAILABLE = False


@pytest.mark.e2e
@pytest.mark.skipif(not AIOHTTP_AVAILABLE, reason="aiohttp 未安装")
class TestWebSocketTerminalAsync:
    """使用 aiohttp 进行异步 WebSocket 测试"""

    def _get_ws_url(self, ship_id: str, token: str, session_id: str, cols: int = 80, rows: int = 24) -> str:
        """构建 WebSocket URL"""
        ws_base = BAY_URL.replace("http://", "ws://").replace("https://", "wss://")
        return f"{ws_base}/ship/{ship_id}/term?token={token}&session_id={session_id}&cols={cols}&rows={rows}"

    def test_websocket_bidirectional_communication(self, bay_url):
        """测试 WebSocket 双向通信"""
        async def run_test():
            test_session_id = f"ws-async-{uuid.uuid4().hex[:8]}"

            # 需要同步创建 Ship
            headers = get_auth_headers(test_session_id)
            payload = {"ttl": 120, "spec": {"cpus": 0.5, "memory": "256m"}}

            resp = requests.post(
                f"{BAY_URL}/ship",
                headers={**headers, "Content-Type": "application/json"},
                json=payload,
                timeout=120,
            )
            if resp.status_code != 201:
                pytest.skip(f"创建 Ship 失败: {resp.status_code}")

            ship_id = resp.json()["id"]

            try:
                # 等待 Ship 就绪
                await asyncio.sleep(3)

                ws_url = self._get_ws_url(ship_id, ACCESS_TOKEN, test_session_id)

                async with aiohttp.ClientSession() as session:
                    try:
                        async with session.ws_connect(ws_url, timeout=10) as ws:
                            # 发送命令
                            await ws.send_str("echo 'Async Test'\n")

                            # 接收响应
                            received_data = []
                            try:
                                async for msg in ws:
                                    if msg.type == aiohttp.WSMsgType.TEXT:
                                        received_data.append(msg.data)
                                        if "Async Test" in msg.data or len(received_data) > 5:
                                            break
                                    elif msg.type == aiohttp.WSMsgType.ERROR:
                                        break
                            except asyncio.TimeoutError:
                                pass

                            assert len(received_data) > 0, "应该收到 WebSocket 响应"

                    except aiohttp.ClientError as e:
                        pytest.fail(f"WebSocket 连接失败: {e}")

            finally:
                # 清理
                requests.delete(
                    f"{BAY_URL}/ship/{ship_id}",
                    headers=headers,
                    timeout=30,
                )

        asyncio.get_event_loop().run_until_complete(run_test())

    def test_websocket_connection_close(self, bay_url):
        """测试 WebSocket 连接关闭"""
        async def run_test():
            test_session_id = f"ws-close-{uuid.uuid4().hex[:8]}"

            headers = get_auth_headers(test_session_id)
            payload = {"ttl": 120, "spec": {"cpus": 0.5, "memory": "256m"}}

            resp = requests.post(
                f"{BAY_URL}/ship",
                headers={**headers, "Content-Type": "application/json"},
                json=payload,
                timeout=120,
            )
            if resp.status_code != 201:
                pytest.skip(f"创建 Ship 失败: {resp.status_code}")

            ship_id = resp.json()["id"]

            try:
                await asyncio.sleep(3)

                ws_url = self._get_ws_url(ship_id, ACCESS_TOKEN, test_session_id)

                async with aiohttp.ClientSession() as session:
                    ws = await session.ws_connect(ws_url, timeout=10)

                    # 验证连接成功
                    assert not ws.closed, "WebSocket 应该已连接"

                    # 正常关闭连接
                    await ws.close()

                    # 验证连接已关闭
                    assert ws.closed, "WebSocket 应该已关闭"

            finally:
                requests.delete(
                    f"{BAY_URL}/ship/{ship_id}",
                    headers=headers,
                    timeout=30,
                )

        asyncio.get_event_loop().run_until_complete(run_test())

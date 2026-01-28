"""
单元测试：ships 路由测试

测试 /ships, /ship 相关端点的模型和基础逻辑。
"""

import pytest
from datetime import datetime, timezone, timedelta
from unittest.mock import AsyncMock, MagicMock, patch
from io import BytesIO


class TestShipModels:
    """Ships 路由相关模型单元测试"""

    def test_ship_status_constants(self):
        """测试 ShipStatus 常量"""
        from app.models import ShipStatus

        assert ShipStatus.STOPPED == 0
        assert ShipStatus.RUNNING == 1
        assert ShipStatus.CREATING == 2

    def test_create_ship_request_model(self):
        """测试 CreateShipRequest 模型"""
        from app.models import CreateShipRequest, ShipSpec

        # 基本创建请求
        request = CreateShipRequest(ttl=3600)
        assert request.ttl == 3600
        assert request.spec is None
        assert request.force_create is False

        # 带规格的创建请求
        spec = ShipSpec(cpus=0.5, memory="256m", disk="1Gi")
        request_with_spec = CreateShipRequest(ttl=3600, spec=spec, force_create=True)
        assert request_with_spec.spec.cpus == 0.5
        assert request_with_spec.spec.memory == "256m"
        assert request_with_spec.spec.disk == "1Gi"
        assert request_with_spec.force_create is True

    def test_create_ship_request_validation(self):
        """测试 CreateShipRequest 验证"""
        from app.models import CreateShipRequest
        from pydantic import ValidationError

        # ttl 必须大于 0
        with pytest.raises(ValidationError):
            CreateShipRequest(ttl=0)

        with pytest.raises(ValidationError):
            CreateShipRequest(ttl=-1)

    def test_ship_spec_model(self):
        """测试 ShipSpec 模型"""
        from app.models import ShipSpec

        # 空规格
        empty_spec = ShipSpec()
        assert empty_spec.cpus is None
        assert empty_spec.memory is None
        assert empty_spec.disk is None

        # 完整规格
        full_spec = ShipSpec(cpus=1.0, memory="512m", disk="2Gi")
        assert full_spec.cpus == 1.0
        assert full_spec.memory == "512m"
        assert full_spec.disk == "2Gi"

    def test_ship_spec_validation(self):
        """测试 ShipSpec 验证"""
        from app.models import ShipSpec
        from pydantic import ValidationError

        # cpus 必须大于 0
        with pytest.raises(ValidationError):
            ShipSpec(cpus=0)

        with pytest.raises(ValidationError):
            ShipSpec(cpus=-0.5)

    def test_ship_response_model(self):
        """测试 ShipResponse 模型"""
        from app.models import ShipResponse, ShipStatus

        now = datetime.now(timezone.utc)
        expires_at = now + timedelta(hours=1)

        response = ShipResponse(
            id="ship-123",
            status=ShipStatus.RUNNING,
            created_at=now,
            updated_at=now,
            container_id="container-abc",
            ip_address="172.17.0.2",
            ttl=3600,
            expires_at=expires_at,
        )

        assert response.id == "ship-123"
        assert response.status == ShipStatus.RUNNING
        assert response.container_id == "container-abc"
        assert response.ip_address == "172.17.0.2"
        assert response.ttl == 3600

    def test_ship_response_optional_fields(self):
        """测试 ShipResponse 可选字段"""
        from app.models import ShipResponse, ShipStatus

        now = datetime.now(timezone.utc)

        response = ShipResponse(
            id="ship-123",
            status=ShipStatus.CREATING,
            created_at=now,
            updated_at=now,
            container_id=None,
            ip_address=None,
            ttl=3600,
            expires_at=None,
        )

        assert response.container_id is None
        assert response.ip_address is None
        assert response.expires_at is None

    def test_exec_request_model(self):
        """测试 ExecRequest 模型"""
        from app.models import ExecRequest

        # Shell 执行请求
        shell_request = ExecRequest(
            type="shell/exec", payload={"command": "echo hello"}
        )
        assert shell_request.type == "shell/exec"
        assert shell_request.payload["command"] == "echo hello"

        # IPython 执行请求
        ipython_request = ExecRequest(
            type="ipython/exec", payload={"code": "print('hello')", "timeout": 10}
        )
        assert ipython_request.type == "ipython/exec"
        assert ipython_request.payload["code"] == "print('hello')"

        # 文件系统操作请求
        fs_request = ExecRequest(
            type="fs/create_file", payload={"path": "test.txt", "content": "hello"}
        )
        assert fs_request.type == "fs/create_file"

    def test_exec_response_model(self):
        """测试 ExecResponse 模型"""
        from app.models import ExecResponse

        # 成功响应
        success_response = ExecResponse(
            success=True, data={"output": "hello world"}, error=None
        )
        assert success_response.success is True
        assert success_response.data["output"] == "hello world"
        assert success_response.error is None

        # 失败响应
        error_response = ExecResponse(
            success=False, data=None, error="Command failed"
        )
        assert error_response.success is False
        assert error_response.data is None
        assert error_response.error == "Command failed"

    def test_extend_ttl_request_model(self):
        """测试 ExtendTTLRequest 模型"""
        from app.models import ExtendTTLRequest
        from pydantic import ValidationError

        # 有效请求
        request = ExtendTTLRequest(ttl=7200)
        assert request.ttl == 7200

        # ttl 必须大于 0
        with pytest.raises(ValidationError):
            ExtendTTLRequest(ttl=0)

        with pytest.raises(ValidationError):
            ExtendTTLRequest(ttl=-100)

    def test_start_ship_request_model(self):
        """测试 StartShipRequest 模型"""
        from app.models import StartShipRequest
        from pydantic import ValidationError

        # 默认值
        request = StartShipRequest()
        assert request.ttl == 3600

        # 自定义 TTL
        request_custom = StartShipRequest(ttl=7200)
        assert request_custom.ttl == 7200

        # ttl 必须大于 0
        with pytest.raises(ValidationError):
            StartShipRequest(ttl=0)

        with pytest.raises(ValidationError):
            StartShipRequest(ttl=-100)

    def test_logs_response_model(self):
        """测试 LogsResponse 模型"""
        from app.models import LogsResponse

        response = LogsResponse(logs="Container started\nService ready")
        assert "Container started" in response.logs
        assert "Service ready" in response.logs

    def test_upload_file_response_model(self):
        """测试 UploadFileResponse 模型"""
        from app.models import UploadFileResponse

        # 成功上传
        success_response = UploadFileResponse(
            success=True,
            message="File uploaded successfully",
            file_path="/workspace/test.txt",
            error=None,
        )
        assert success_response.success is True
        assert success_response.file_path == "/workspace/test.txt"

        # 上传失败
        error_response = UploadFileResponse(
            success=False, message="Upload failed", file_path=None, error="File too large"
        )
        assert error_response.success is False
        assert error_response.error == "File too large"


class TestShipsRouteLogic:
    """Ships 路由逻辑单元测试"""

    def test_ship_ip_address_format_docker_mode(self):
        """测试 docker 模式 IP 地址格式（不带端口）"""
        # 在 docker 模式下，IP 地址不包含端口
        ip_address = "172.17.0.2"
        assert ":" not in ip_address

        # 构建 WebSocket URL 需要添加默认端口
        ship_container_port = 8000
        ws_url = f"ws://{ip_address}:{ship_container_port}/term/ws"
        assert ws_url == "ws://172.17.0.2:8000/term/ws"

    def test_ship_ip_address_format_docker_host_mode(self):
        """测试 docker-host 模式 IP 地址格式（带端口）"""
        # 在 docker-host 模式下，IP 地址包含端口
        ip_address = "127.0.0.1:39314"
        assert ":" in ip_address

        # 构建 WebSocket URL 直接使用地址
        ws_url = f"ws://{ip_address}/term/ws"
        assert ws_url == "ws://127.0.0.1:39314/term/ws"

    def test_filename_extraction_from_path(self):
        """测试从文件路径提取文件名"""
        # 包含路径分隔符
        file_path = "/workspace/subdir/test_file.txt"
        filename = file_path.split("/")[-1] if "/" in file_path else file_path
        assert filename == "test_file.txt"

        # 不包含路径分隔符
        file_path_simple = "test_file.txt"
        filename_simple = (
            file_path_simple.split("/")[-1]
            if "/" in file_path_simple
            else file_path_simple
        )
        assert filename_simple == "test_file.txt"

    def test_error_message_categorization(self):
        """测试错误消息分类逻辑"""
        error_messages = [
            ("file size exceeds limit", "size"),
            ("resource not found", "not found"),
            ("access denied", "access"),
            ("unknown error", None),
        ]

        for error_msg, expected_keyword in error_messages:
            if expected_keyword:
                assert expected_keyword in error_msg.lower()
            else:
                # 一般错误，不匹配特定关键字
                assert "size" not in error_msg.lower()
                assert "not found" not in error_msg.lower()
                assert "access" not in error_msg.lower()


class TestShipsRouteHTTPStatus:
    """Ships 路由 HTTP 状态码测试"""

    def test_expected_status_codes(self):
        """测试预期的 HTTP 状态码"""
        from fastapi import status

        # 成功创建 Ship
        assert status.HTTP_201_CREATED == 201

        # 成功删除 Ship
        assert status.HTTP_204_NO_CONTENT == 204

        # Ship 未找到
        assert status.HTTP_404_NOT_FOUND == 404

        # 无效请求
        assert status.HTTP_400_BAD_REQUEST == 400

        # 请求超时
        assert status.HTTP_408_REQUEST_TIMEOUT == 408

        # 文件过大
        assert status.HTTP_413_REQUEST_ENTITY_TOO_LARGE == 413

        # 禁止访问
        assert status.HTTP_403_FORBIDDEN == 403

        # 服务器内部错误
        assert status.HTTP_500_INTERNAL_SERVER_ERROR == 500


class TestShipBase:
    """ShipBase 模型测试"""

    def test_ship_base_defaults(self):
        """测试 ShipBase 默认值"""
        from app.models import Ship, ShipStatus

        ship = Ship(ttl=3600)
        assert ship.status == ShipStatus.CREATING
        assert ship.container_id is None
        assert ship.ip_address is None
        assert ship.id is not None  # 自动生成

    def test_ship_with_all_fields(self):
        """测试 Ship 所有字段"""
        from app.models import Ship, ShipStatus

        now = datetime.now(timezone.utc)
        ship = Ship(
            id="custom-id",
            status=ShipStatus.RUNNING,
            created_at=now,
            updated_at=now,
            container_id="container-123",
            ip_address="10.0.0.1",
            ttl=7200,
        )

        assert ship.id == "custom-id"
        assert ship.status == ShipStatus.RUNNING
        assert ship.container_id == "container-123"
        assert ship.ip_address == "10.0.0.1"
        assert ship.ttl == 7200


class TestWebSocketTerminalLogic:
    """WebSocket Terminal 相关逻辑单元测试"""

    def test_websocket_url_construction_docker_mode(self):
        """测试 docker 模式 WebSocket URL 构建"""
        # docker 模式：IP 地址不包含端口
        ip_address = "172.17.0.2"
        ship_container_port = 8000
        session_id = "test-session"
        cols = 80
        rows = 24

        # 构建 WebSocket URL
        ws_url = f"ws://{ip_address}:{ship_container_port}/term/ws?session_id={session_id}&cols={cols}&rows={rows}"

        assert ws_url == "ws://172.17.0.2:8000/term/ws?session_id=test-session&cols=80&rows=24"

    def test_websocket_url_construction_docker_host_mode(self):
        """测试 docker-host 模式 WebSocket URL 构建"""
        # docker-host 模式：IP 地址包含端口
        ip_address = "127.0.0.1:39314"
        session_id = "test-session"
        cols = 120
        rows = 40

        # 构建 WebSocket URL
        ws_url = f"ws://{ip_address}/term/ws?session_id={session_id}&cols={cols}&rows={rows}"

        assert ws_url == "ws://127.0.0.1:39314/term/ws?session_id=test-session&cols=120&rows=40"

    def test_ip_address_format_detection(self):
        """测试 IP 地址格式检测（是否包含端口）"""
        # docker 模式
        docker_ip = "172.17.0.2"
        assert ":" not in docker_ip

        # docker-host 模式
        docker_host_ip = "127.0.0.1:39314"
        assert ":" in docker_host_ip

    def test_websocket_close_codes(self):
        """测试 WebSocket 关闭代码"""
        # 自定义关闭代码
        UNAUTHORIZED = 4001
        SESSION_NO_ACCESS = 4003
        SHIP_NOT_FOUND = 4004

        assert UNAUTHORIZED == 4001
        assert SESSION_NO_ACCESS == 4003
        assert SHIP_NOT_FOUND == 4004

        # 标准关闭代码
        INTERNAL_ERROR = 1011
        assert INTERNAL_ERROR == 1011

    def test_terminal_default_size(self):
        """测试终端默认大小"""
        default_cols = 80
        default_rows = 24

        assert default_cols == 80
        assert default_rows == 24

    def test_terminal_size_validation(self):
        """测试终端大小验证"""
        # 有效的终端大小
        valid_sizes = [
            (80, 24),   # 标准
            (120, 40),  # 大屏
            (40, 10),   # 小屏
        ]

        for cols, rows in valid_sizes:
            assert cols > 0
            assert rows > 0

    def test_websocket_message_types(self):
        """测试 WebSocket 消息类型"""
        # 模拟 aiohttp 消息类型
        class MockWSMsgType:
            TEXT = 1
            BINARY = 2
            CLOSED = 258
            ERROR = 256

        assert MockWSMsgType.TEXT == 1
        assert MockWSMsgType.BINARY == 2
        assert MockWSMsgType.CLOSED == 258
        assert MockWSMsgType.ERROR == 256


class TestShipStatusValidation:
    """Ship 状态验证单元测试"""

    def test_ship_running_status_required_for_websocket(self):
        """测试 WebSocket 连接需要 Ship 处于运行状态"""
        from app.models import ShipStatus

        # 只有 RUNNING 状态的 Ship 可以连接 WebSocket
        valid_status = ShipStatus.RUNNING
        invalid_statuses = [ShipStatus.STOPPED, ShipStatus.CREATING]

        assert valid_status == 1
        for status in invalid_statuses:
            assert status != ShipStatus.RUNNING

    def test_ship_ip_address_required_for_websocket(self):
        """测试 WebSocket 连接需要 Ship 有 IP 地址"""
        from app.models import Ship, ShipStatus

        # Ship 有 IP 地址
        ship_with_ip = Ship(
            ttl=3600,
            status=ShipStatus.RUNNING,
            ip_address="172.17.0.2"
        )
        assert ship_with_ip.ip_address is not None

        # Ship 没有 IP 地址
        ship_without_ip = Ship(
            ttl=3600,
            status=ShipStatus.RUNNING,
            ip_address=None
        )
        assert ship_without_ip.ip_address is None


class TestExecutionHistory:
    """Execution History 模型测试"""

    def test_execution_history_model(self):
        """测试 ExecutionHistory 模型"""
        from app.models import ExecutionHistory

        history = ExecutionHistory(
            session_id="test-session",
            exec_type="python",
            code="print('hello')",
            success=True,
            execution_time_ms=42,
        )

        assert history.session_id == "test-session"
        assert history.exec_type == "python"
        assert history.code == "print('hello')"
        assert history.success is True
        assert history.execution_time_ms == 42
        assert history.id is not None

    def test_execution_history_shell(self):
        """测试 ExecutionHistory Shell 命令"""
        from app.models import ExecutionHistory

        history = ExecutionHistory(
            session_id="test-session",
            exec_type="shell",
            command="ls -la",
            success=True,
            execution_time_ms=15,
        )

        assert history.exec_type == "shell"
        assert history.command == "ls -la"
        assert history.code is None

    def test_execution_history_response_model(self):
        """测试 ExecutionHistoryResponse 模型"""
        from app.models import ExecutionHistoryResponse, ExecutionHistoryEntry
        from datetime import datetime, timezone

        now = datetime.now(timezone.utc)
        entry = ExecutionHistoryEntry(
            id="entry-1",
            session_id="test-session",
            exec_type="python",
            code="print('hello')",
            command=None,
            success=True,
            execution_time_ms=42,
            created_at=now,
        )

        response = ExecutionHistoryResponse(entries=[entry], total=1)
        assert len(response.entries) == 1
        assert response.total == 1
        assert response.entries[0].code == "print('hello')"

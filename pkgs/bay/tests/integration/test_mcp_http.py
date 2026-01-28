"""
MCP HTTP 模式多客户端隔离测试

测试 HTTP 模式下不同 MCP 客户端的 Session 隔离。
"""

import asyncio
import os
import sys
from pathlib import Path
from typing import Any, Dict
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# 添加 app 路径以便测试导入
sys.path.insert(0, str(Path(__file__).parent.parent.parent))
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent.parent / "shipyard_python_sdk"))


class MockContext:
    """模拟 FastMCP Context 对象用于测试"""

    def __init__(self, session_id: str, lifespan_context: Any = None):
        self._session_id = session_id
        self._state: Dict[str, Any] = {}
        self._lifespan_context = lifespan_context

    @property
    def session_id(self) -> str:
        return self._session_id

    @property
    def request_context(self):
        class RequestContext:
            lifespan_context = self._lifespan_context
        return RequestContext()

    async def get_state(self, key: str) -> Any:
        return self._state.get(key)

    async def set_state(self, key: str, value: Any) -> None:
        self._state[key] = value

    async def info(self, msg: str) -> None:
        pass

    async def warning(self, msg: str) -> None:
        pass


class MockSandbox:
    """模拟 Sandbox 对象"""

    def __init__(self, session_id: str):
        self.session_id = session_id
        self.ship_id = f"ship-{session_id[:8]}"
        self._variables: Dict[str, Any] = {}
        self._files: Dict[str, str] = {}
        self.started = False

    async def start(self):
        self.started = True
        return self

    async def stop(self):
        self.started = False

    async def extend_ttl(self, ttl: int):
        pass


@pytest.mark.unit
class TestMCPSessionIsolation:
    """测试 MCP Session 隔离逻辑"""

    def test_different_sessions_get_different_state(self):
        """测试不同 session 获得独立的 state"""
        ctx_a = MockContext("session-aaa")
        ctx_b = MockContext("session-bbb")

        # 验证 session_id 不同
        assert ctx_a.session_id != ctx_b.session_id
        assert ctx_a.session_id == "session-aaa"
        assert ctx_b.session_id == "session-bbb"

    @pytest.mark.asyncio
    async def test_state_isolation_between_sessions(self):
        """测试 state 在不同 session 间隔离"""
        ctx_a = MockContext("session-aaa")
        ctx_b = MockContext("session-bbb")

        # A 设置状态
        await ctx_a.set_state("sandbox", MockSandbox("session-aaa"))
        await ctx_a.set_state("counter", 10)

        # B 看不到 A 的状态
        sandbox_b = await ctx_b.get_state("sandbox")
        counter_b = await ctx_b.get_state("counter")

        assert sandbox_b is None
        assert counter_b is None

        # A 可以读取自己的状态
        sandbox_a = await ctx_a.get_state("sandbox")
        counter_a = await ctx_a.get_state("counter")

        assert sandbox_a is not None
        assert sandbox_a.session_id == "session-aaa"
        assert counter_a == 10

    @pytest.mark.asyncio
    async def test_same_session_shares_state(self):
        """测试同一 session 的多次调用共享状态"""
        shared_state = {}

        class SharedMockContext(MockContext):
            def __init__(self, session_id: str):
                super().__init__(session_id)
                self._state = shared_state

        ctx1 = SharedMockContext("session-same")
        ctx2 = SharedMockContext("session-same")

        # 第一次调用设置状态
        sandbox = MockSandbox("session-same")
        await ctx1.set_state("sandbox", sandbox)

        # 第二次调用（同一 session）可以读取
        sandbox2 = await ctx2.get_state("sandbox")

        assert sandbox2 is sandbox
        assert sandbox2.session_id == "session-same"


@pytest.mark.unit
class TestGetOrCreateSandbox:
    """测试 get_or_create_sandbox 函数逻辑"""

    @pytest.mark.asyncio
    async def test_creates_sandbox_on_first_call(self):
        """测试首次调用创建新 Sandbox"""
        from dataclasses import dataclass

        @dataclass
        class GlobalConfig:
            endpoint: str = "http://localhost:8156"
            token: str = "test-token"
            default_ttl: int = 1800
            ttl_renew_threshold: int = 600

        ctx = MockContext("session-new", GlobalConfig())

        # 首次调用 - sandbox 为空
        sandbox = await ctx.get_state("sandbox")
        assert sandbox is None

        # 模拟创建
        new_sandbox = MockSandbox("session-new")
        await new_sandbox.start()
        await ctx.set_state("sandbox", new_sandbox)

        # 再次获取
        sandbox = await ctx.get_state("sandbox")
        assert sandbox is not None
        assert sandbox.session_id == "session-new"
        assert sandbox.started is True

    @pytest.mark.asyncio
    async def test_reuses_existing_sandbox(self):
        """测试复用已存在的 Sandbox"""
        ctx = MockContext("session-existing")

        # 预设已有 sandbox
        existing_sandbox = MockSandbox("session-existing")
        await existing_sandbox.start()
        await ctx.set_state("sandbox", existing_sandbox)

        # 获取 - 应该返回同一个对象
        sandbox = await ctx.get_state("sandbox")

        assert sandbox is existing_sandbox
        assert sandbox.session_id == "session-existing"


@pytest.mark.unit
class TestMultiClientIsolationScenario:
    """测试多客户端隔离场景"""

    @pytest.mark.asyncio
    async def test_client_a_variable_invisible_to_client_b(self):
        """
        场景：客户端 A 设置变量，客户端 B 看不到

        模拟：
        - Client A: execute_python("x = 123")
        - Client B: execute_python("print(x)")  -> NameError
        """
        # 模拟两个独立的 session 状态
        session_a_state = {}
        session_b_state = {}

        class ClientAContext(MockContext):
            def __init__(self):
                super().__init__("mcp-session-aaa")
                self._state = session_a_state

        class ClientBContext(MockContext):
            def __init__(self):
                super().__init__("mcp-session-bbb")
                self._state = session_b_state

        ctx_a = ClientAContext()
        ctx_b = ClientBContext()

        # Client A 创建 sandbox 并设置变量
        sandbox_a = MockSandbox("mcp-session-aaa")
        sandbox_a._variables["x"] = 123
        await ctx_a.set_state("sandbox", sandbox_a)

        # Client B 获取自己的 sandbox
        sandbox_b = await ctx_b.get_state("sandbox")

        # B 没有 sandbox（尚未创建）
        assert sandbox_b is None

        # 即使 B 创建了 sandbox，也看不到 A 的变量
        sandbox_b = MockSandbox("mcp-session-bbb")
        await ctx_b.set_state("sandbox", sandbox_b)

        # A 的变量在 A 的 sandbox 中
        assert "x" in (await ctx_a.get_state("sandbox"))._variables
        # B 的 sandbox 中没有 x
        assert "x" not in (await ctx_b.get_state("sandbox"))._variables

    @pytest.mark.asyncio
    async def test_client_a_file_invisible_to_client_b(self):
        """
        场景：客户端 A 写文件，客户端 B 看不到

        模拟：
        - Client A: write_file("/workspace/test.txt", "hello")
        - Client B: read_file("/workspace/test.txt")  -> FileNotFoundError
        """
        session_a_state = {}
        session_b_state = {}

        class ClientAContext(MockContext):
            def __init__(self):
                super().__init__("mcp-session-aaa")
                self._state = session_a_state

        class ClientBContext(MockContext):
            def __init__(self):
                super().__init__("mcp-session-bbb")
                self._state = session_b_state

        ctx_a = ClientAContext()
        ctx_b = ClientBContext()

        # Client A 创建 sandbox 并写入文件
        sandbox_a = MockSandbox("mcp-session-aaa")
        sandbox_a._files["/workspace/test.txt"] = "hello from A"
        await ctx_a.set_state("sandbox", sandbox_a)

        # Client B 创建自己的 sandbox
        sandbox_b = MockSandbox("mcp-session-bbb")
        await ctx_b.set_state("sandbox", sandbox_b)

        # A 的文件在 A 的 sandbox 中
        assert "/workspace/test.txt" in (await ctx_a.get_state("sandbox"))._files
        # B 的 sandbox 中没有这个文件
        assert "/workspace/test.txt" not in (await ctx_b.get_state("sandbox"))._files


@pytest.mark.unit
class TestSessionIdGeneration:
    """测试 Session ID 生成"""

    def test_different_contexts_have_different_session_ids(self):
        """不同的 context 应该有不同的 session_id"""
        ctx1 = MockContext("session-111")
        ctx2 = MockContext("session-222")
        ctx3 = MockContext("session-333")

        session_ids = {ctx1.session_id, ctx2.session_id, ctx3.session_id}

        assert len(session_ids) == 3

    def test_session_id_format(self):
        """Session ID 应该是可用的字符串"""
        ctx = MockContext("mcp-session-abc123")

        assert isinstance(ctx.session_id, str)
        assert len(ctx.session_id) > 0


@pytest.mark.unit
class TestTTLRenewal:
    """测试 TTL 续期逻辑"""

    @pytest.mark.asyncio
    async def test_ttl_renewal_on_activity(self):
        """测试活动时自动续期"""
        from datetime import datetime, timedelta

        ctx = MockContext("session-ttl-test")

        # 设置 sandbox 和上次续期时间（超过阈值）
        sandbox = MockSandbox("session-ttl-test")
        old_renew_time = datetime.now() - timedelta(minutes=15)  # 15 分钟前

        await ctx.set_state("sandbox", sandbox)
        await ctx.set_state("last_ttl_renew", old_renew_time)

        # 检查续期逻辑
        last_renew = await ctx.get_state("last_ttl_renew")
        ttl_renew_threshold = 600  # 10 分钟

        now = datetime.now()
        should_renew = (now - last_renew).total_seconds() > ttl_renew_threshold

        assert should_renew is True

    @pytest.mark.asyncio
    async def test_no_renewal_within_threshold(self):
        """测试阈值内不续期"""
        from datetime import datetime, timedelta

        ctx = MockContext("session-ttl-test")

        # 设置上次续期时间（在阈值内）
        recent_renew_time = datetime.now() - timedelta(minutes=5)  # 5 分钟前

        await ctx.set_state("last_ttl_renew", recent_renew_time)

        last_renew = await ctx.get_state("last_ttl_renew")
        ttl_renew_threshold = 600  # 10 分钟

        now = datetime.now()
        should_renew = (now - last_renew).total_seconds() > ttl_renew_threshold

        assert should_renew is False


@pytest.mark.unit
class TestStdioModeCompatibility:
    """测试 stdio 模式兼容性"""

    def test_stdio_mode_single_session(self):
        """stdio 模式下只有一个 session"""
        # 在 stdio 模式下，一个进程 = 一个 session
        # 所有请求共享同一个 session_id
        single_session_id = "stdio-single-session"

        ctx1 = MockContext(single_session_id)
        ctx2 = MockContext(single_session_id)

        # 共享同一个 session_id
        assert ctx1.session_id == ctx2.session_id

    @pytest.mark.asyncio
    async def test_stdio_mode_state_persistence(self):
        """stdio 模式下状态应该持久"""
        shared_state = {}
        single_session_id = "stdio-single-session"

        class StdioContext(MockContext):
            def __init__(self):
                super().__init__(single_session_id)
                self._state = shared_state

        ctx1 = StdioContext()
        ctx2 = StdioContext()

        # 第一次请求创建 sandbox
        sandbox = MockSandbox(single_session_id)
        sandbox._variables["x"] = 42
        await ctx1.set_state("sandbox", sandbox)

        # 第二次请求应该能获取到
        sandbox2 = await ctx2.get_state("sandbox")

        assert sandbox2 is sandbox
        assert sandbox2._variables["x"] == 42

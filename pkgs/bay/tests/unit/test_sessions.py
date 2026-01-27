"""
单元测试：sessions 路由测试

测试 /sessions 相关端点的响应模型。
"""

import pytest
from datetime import datetime, timezone, timedelta


class TestSessionsRoutes:
    """Sessions 路由单元测试"""

    def test_session_response_model(self):
        """测试 SessionResponse 模型"""
        from app.routes.sessions import SessionResponse

        now = datetime.now(timezone.utc)
        expires_at = now + timedelta(hours=1)

        session = SessionResponse(
            id="test-id",
            session_id="session-123",
            ship_id="ship-456",
            created_at=now,
            last_activity=now,
            expires_at=expires_at,
            initial_ttl=3600,
            is_active=True
        )

        assert session.id == "test-id"
        assert session.session_id == "session-123"
        assert session.ship_id == "ship-456"
        assert session.initial_ttl == 3600
        assert session.is_active is True

    def test_session_list_response_model(self):
        """测试 SessionListResponse 模型"""
        from app.routes.sessions import SessionResponse, SessionListResponse

        now = datetime.now(timezone.utc)
        expires_at = now + timedelta(hours=1)

        session = SessionResponse(
            id="test-id",
            session_id="session-123",
            ship_id="ship-456",
            created_at=now,
            last_activity=now,
            expires_at=expires_at,
            initial_ttl=3600,
            is_active=True
        )

        session_list = SessionListResponse(
            sessions=[session],
            total=1
        )

        assert session_list.total == 1
        assert len(session_list.sessions) == 1
        assert session_list.sessions[0].session_id == "session-123"

    def test_ship_sessions_response_model(self):
        """测试 ShipSessionsResponse 模型"""
        from app.routes.sessions import SessionResponse, ShipSessionsResponse

        now = datetime.now(timezone.utc)
        expires_at = now + timedelta(hours=1)

        session = SessionResponse(
            id="test-id",
            session_id="session-123",
            ship_id="ship-456",
            created_at=now,
            last_activity=now,
            expires_at=expires_at,
            initial_ttl=3600,
            is_active=True
        )

        ship_sessions = ShipSessionsResponse(
            ship_id="ship-456",
            sessions=[session],
            total=1
        )

        assert ship_sessions.ship_id == "ship-456"
        assert ship_sessions.total == 1
        assert len(ship_sessions.sessions) == 1

    def test_session_is_active_calculation(self):
        """测试会话活跃状态计算逻辑"""
        from app.routes.sessions import SessionResponse

        now = datetime.now(timezone.utc)

        # 未过期的会话应该是活跃的
        future_expires = now + timedelta(hours=1)
        active_session = SessionResponse(
            id="test-id",
            session_id="session-123",
            ship_id="ship-456",
            created_at=now,
            last_activity=now,
            expires_at=future_expires,
            initial_ttl=3600,
            is_active=True
        )
        assert active_session.is_active is True

        # 已过期的会话应该是非活跃的
        past_expires = now - timedelta(hours=1)
        inactive_session = SessionResponse(
            id="test-id",
            session_id="session-123",
            ship_id="ship-456",
            created_at=now,
            last_activity=now,
            expires_at=past_expires,
            initial_ttl=3600,
            is_active=False
        )
        assert inactive_session.is_active is False

    def test_is_session_active_function(self):
        """测试 is_session_active 辅助函数"""
        from app.routes.sessions import is_session_active
        
        now = datetime.now(timezone.utc)
        
        # 未过期的会话应该是活跃的
        future_expires = now + timedelta(hours=1)
        assert is_session_active(future_expires, now) is True
        
        # 已过期的会话应该是非活跃的
        past_expires = now - timedelta(hours=1)
        assert is_session_active(past_expires, now) is False
        
        # expires_at 为 None 时应该是非活跃的
        assert is_session_active(None, now) is False
        
        # 处理 timezone-naive datetime
        naive_future = datetime.utcnow() + timedelta(hours=1)
        assert is_session_active(naive_future, now) is True
        
        naive_past = datetime.utcnow() - timedelta(hours=1)
        assert is_session_active(naive_past, now) is False


class TestExpireSessionsForShip:
    """测试 expire_sessions_for_ship 数据库方法"""
    
    @pytest.mark.asyncio
    async def test_expire_sessions_for_ship_marks_active_sessions_as_expired(self):
        """测试当 ship 停止时，活跃会话会被标记为已过期"""
        from app.database import db_service
        from app.models import Ship, SessionShip, ShipStatus
        
        # 初始化数据库
        await db_service.initialize()
        await db_service.create_tables()
        
        # 创建测试 ship
        ship = Ship(
            id="test-ship-expire-sessions",
            ttl=3600,
            max_session_num=2,
            status=ShipStatus.RUNNING
        )
        ship = await db_service.create_ship(ship)
        
        try:
            now = datetime.now(timezone.utc)
            future_expires = now + timedelta(hours=1)
            
            # 创建活跃会话
            session1 = SessionShip(
                id="session1-expire-test",
                session_id="user-session-1",
                ship_id=ship.id,
                expires_at=future_expires,
                initial_ttl=3600
            )
            await db_service.create_session_ship(session1)
            
            session2 = SessionShip(
                id="session2-expire-test",
                session_id="user-session-2",
                ship_id=ship.id,
                expires_at=future_expires,
                initial_ttl=3600
            )
            await db_service.create_session_ship(session2)
            
            # 执行 expire_sessions_for_ship
            expired_count = await db_service.expire_sessions_for_ship(ship.id)
            
            # 验证两个会话都被更新
            assert expired_count == 2
            
            # 验证会话现在是非活跃的
            sessions = await db_service.get_sessions_for_ship(ship.id)
            for s in sessions:
                # expires_at 应该是当前时间或更早
                if s.expires_at.tzinfo is None:
                    s.expires_at = s.expires_at.replace(tzinfo=timezone.utc)
                assert s.expires_at <= datetime.now(timezone.utc) + timedelta(seconds=5)
        
        finally:
            # 清理测试数据
            await db_service.delete_sessions_for_ship(ship.id)
            await db_service.delete_ship(ship.id)
    
    @pytest.mark.asyncio
    async def test_expire_sessions_for_ship_skips_already_expired_sessions(self):
        """测试已过期的会话不会被重复更新"""
        from app.database import db_service
        from app.models import Ship, SessionShip, ShipStatus
        
        # 初始化数据库
        await db_service.initialize()
        await db_service.create_tables()
        
        # 创建测试 ship
        ship = Ship(
            id="test-ship-skip-expired",
            ttl=3600,
            max_session_num=2,
            status=ShipStatus.RUNNING
        )
        ship = await db_service.create_ship(ship)
        
        try:
            now = datetime.now(timezone.utc)
            past_expires = now - timedelta(hours=1)
            
            # 创建已过期的会话
            session = SessionShip(
                id="session-already-expired",
                session_id="user-session-expired",
                ship_id=ship.id,
                expires_at=past_expires,
                initial_ttl=3600
            )
            await db_service.create_session_ship(session)
            
            # 执行 expire_sessions_for_ship
            expired_count = await db_service.expire_sessions_for_ship(ship.id)
            
            # 已过期的会话不应该被计入更新数
            assert expired_count == 0
        
        finally:
            # 清理测试数据
            await db_service.delete_sessions_for_ship(ship.id)
            await db_service.delete_ship(ship.id)
    
    @pytest.mark.asyncio
    async def test_expire_sessions_for_ship_with_no_sessions(self):
        """测试没有会话的 ship 不会出错"""
        from app.database import db_service
        from app.models import Ship, ShipStatus
        
        # 初始化数据库
        await db_service.initialize()
        await db_service.create_tables()
        
        # 创建测试 ship
        ship = Ship(
            id="test-ship-no-sessions",
            ttl=3600,
            max_session_num=1,
            status=ShipStatus.RUNNING
        )
        ship = await db_service.create_ship(ship)
        
        try:
            # 执行 expire_sessions_for_ship（没有会话）
            expired_count = await db_service.expire_sessions_for_ship(ship.id)
            
            # 应该返回 0
            assert expired_count == 0
        
        finally:
            # 清理测试数据
            await db_service.delete_ship(ship.id)

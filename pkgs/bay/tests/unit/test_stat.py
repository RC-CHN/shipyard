"""
单元测试：stat 路由测试

测试 /stat 和 /stat/overview 端点。
"""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from datetime import datetime, timezone, timedelta


class TestStatRoutes:
    """Stat 路由单元测试"""

    def test_get_version(self):
        """测试 get_version 函数"""
        from app.routes.stat import get_version

        version = get_version()
        # 版本应该是一个非空字符串
        assert isinstance(version, str)
        assert len(version) > 0

    def test_stat_response_models(self):
        """测试 stat 响应模型"""
        from app.routes.stat import ShipStats, SessionStats, OverviewResponse

        # 测试 ShipStats
        ship_stats = ShipStats(total=10, running=8, stopped=2, creating=0)
        assert ship_stats.total == 10
        assert ship_stats.running == 8
        assert ship_stats.stopped == 2
        assert ship_stats.creating == 0

        # 测试 SessionStats
        session_stats = SessionStats(total=15, active=12)
        assert session_stats.total == 15
        assert session_stats.active == 12

        # 测试 OverviewResponse
        overview = OverviewResponse(
            service="bay",
            version="1.0.0",
            status="running",
            ships=ship_stats,
            sessions=session_stats
        )
        assert overview.service == "bay"
        assert overview.version == "1.0.0"
        assert overview.status == "running"
        assert overview.ships.total == 10
        assert overview.sessions.active == 12

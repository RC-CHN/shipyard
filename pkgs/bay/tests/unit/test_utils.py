"""
单元测试：工具函数测试

测试 memory 和 disk 相关的工具函数，不需要 Bay 服务运行。
"""

import pytest


class TestMemoryUtils:
    """内存工具函数单元测试"""

    def test_parse_memory_string(self):
        """测试 parse_memory_string 函数"""
        from app.drivers.core.utils import parse_memory_string

        # K8s 风格单位
        assert parse_memory_string("512Mi") == 536870912
        assert parse_memory_string("1Gi") == 1073741824

        # Docker 风格单位
        assert parse_memory_string("512m") == 536870912
        assert parse_memory_string("1g") == 1073741824

    def test_parse_and_enforce_minimum_memory(self):
        """测试 parse_and_enforce_minimum_memory 函数"""
        from app.drivers.core.utils import parse_and_enforce_minimum_memory

        # 64Mi < 128Mi，应该被修正
        assert parse_and_enforce_minimum_memory("64Mi") == 134217728
        # 512Mi > 128Mi，应该保持不变
        assert parse_and_enforce_minimum_memory("512Mi") == 536870912

    def test_normalize_memory_for_k8s_docker_style(self):
        """测试 Docker 风格单位转换为 K8s 风格"""
        from app.drivers.kubernetes.utils import normalize_memory_for_k8s

        # KB/kb -> Ki (需要足够大的值，131072KB = 128Mi)
        assert normalize_memory_for_k8s("256000KB") == "256000Ki"
        assert normalize_memory_for_k8s("256000kb") == "256000Ki"

        # MB/mb -> Mi (256MB > 128Mi)
        assert normalize_memory_for_k8s("256MB") == "256Mi"
        assert normalize_memory_for_k8s("256mb") == "256Mi"

        # GB/gb -> Gi
        assert normalize_memory_for_k8s("2GB") == "2Gi"
        assert normalize_memory_for_k8s("2gb") == "2Gi"

        # 简写 k/m/g -> Ki/Mi/Gi
        assert normalize_memory_for_k8s("256000K") == "256000Ki"
        assert normalize_memory_for_k8s("256000k") == "256000Ki"
        assert normalize_memory_for_k8s("256M") == "256Mi"
        assert normalize_memory_for_k8s("256m") == "256Mi"
        assert normalize_memory_for_k8s("2G") == "2Gi"
        assert normalize_memory_for_k8s("2g") == "2Gi"

    def test_normalize_memory_for_k8s_already_k8s_style(self):
        """测试已经是 K8s 单位时保持原样"""
        from app.drivers.kubernetes.utils import normalize_memory_for_k8s

        # 256Mi > 128Mi，不会触发最小值限制
        assert normalize_memory_for_k8s("256Mi") == "256Mi"
        assert normalize_memory_for_k8s("256MI") == "256MI"
        assert normalize_memory_for_k8s("1Gi") == "1Gi"
        assert normalize_memory_for_k8s("1GI") == "1GI"

    def test_normalize_memory_for_k8s_raw_bytes(self):
        """测试纯字节数字原样透传"""
        from app.drivers.kubernetes.utils import normalize_memory_for_k8s

        # >= 128Mi = 134217728 字节
        assert normalize_memory_for_k8s("134217728") == "134217728"
        assert normalize_memory_for_k8s("536870912") == "536870912"

    def test_normalize_memory_for_k8s_minimum_enforcement(self):
        """测试小的值应被提升到最小内存"""
        from app.drivers.kubernetes.utils import normalize_memory_for_k8s

        # 64Mi < 128Mi，应该被提升
        assert normalize_memory_for_k8s("64Mi") == "134217728"
        # 64m（Docker 的 MB 单位）在转换后也应被提升到最小值
        assert normalize_memory_for_k8s("64m") == "134217728"
        # 1k（1024 字节）也应被提升
        assert normalize_memory_for_k8s("1k") == "134217728"
        # 小的 Ki 值也应被提升
        assert normalize_memory_for_k8s("512Ki") == "134217728"

    def test_normalize_memory_for_k8s_empty_string(self):
        """测试空字符串处理"""
        from app.drivers.kubernetes.utils import normalize_memory_for_k8s

        assert normalize_memory_for_k8s("") == ""


class TestDiskUtils:
    """磁盘工具函数单元测试"""

    def test_default_disk_config(self):
        """测试默认磁盘配置"""
        from app.config import settings

        assert settings.default_ship_disk == "1Gi", f"Expected '1Gi', got '{settings.default_ship_disk}'"

    def test_parse_disk_string(self):
        """测试 parse_disk_string 函数"""
        from app.drivers.core.utils import parse_disk_string

        # K8s 风格单位
        assert parse_disk_string("1Gi") == 1073741824
        assert parse_disk_string("512Mi") == 536870912

        # Docker 风格单位
        assert parse_disk_string("1g") == 1073741824
        assert parse_disk_string("512m") == 536870912
        assert parse_disk_string("10G") == 10737418240

        # 纯字节
        assert parse_disk_string("1073741824") == 1073741824

    def test_parse_and_enforce_minimum_disk(self):
        """测试 parse_and_enforce_minimum_disk 函数"""
        from app.drivers.core.utils import (
            parse_and_enforce_minimum_disk,
            MIN_DISK_BYTES,
        )

        # 50Mi < 100Mi，应该被修正到 100Mi
        assert parse_and_enforce_minimum_disk("50Mi") == MIN_DISK_BYTES
        # 1Gi > 100Mi，应该保持不变
        assert parse_and_enforce_minimum_disk("1Gi") == 1073741824

    def test_normalize_disk_for_k8s_docker_style(self):
        """测试 Docker 风格单位转换为 K8s 风格"""
        from app.drivers.kubernetes.utils import normalize_disk_for_k8s

        assert normalize_disk_for_k8s("1g") == "1Gi"
        assert normalize_disk_for_k8s("10G") == "10Gi"
        assert normalize_disk_for_k8s("512m") == "512Mi"
        assert normalize_disk_for_k8s("1024M") == "1024Mi"

    def test_normalize_disk_for_k8s_already_k8s_style(self):
        """测试已经是 K8s 单位时保持原样"""
        from app.drivers.kubernetes.utils import normalize_disk_for_k8s

        assert normalize_disk_for_k8s("1Gi") == "1Gi"
        assert normalize_disk_for_k8s("512Mi") == "512Mi"

    def test_normalize_disk_for_k8s_raw_bytes(self):
        """测试纯字节数字应原样透传"""
        from app.drivers.kubernetes.utils import normalize_disk_for_k8s

        # >= 100Mi
        assert normalize_disk_for_k8s("1073741824") == "1073741824"

    def test_normalize_disk_for_k8s_minimum_enforcement(self):
        """测试小的值应被提升到最小值"""
        from app.drivers.core.utils import MIN_DISK_BYTES
        from app.drivers.kubernetes.utils import normalize_disk_for_k8s

        # 100Mi = 104857600 字节
        assert normalize_disk_for_k8s("50Mi") == str(MIN_DISK_BYTES)
        assert normalize_disk_for_k8s("50m") == str(MIN_DISK_BYTES)

    def test_normalize_disk_for_k8s_empty_string(self):
        """测试空字符串处理"""
        from app.drivers.kubernetes.utils import normalize_disk_for_k8s

        assert normalize_disk_for_k8s("") == ""

    def test_ship_spec_disk_field(self):
        """测试 ShipSpec 包含 disk 字段"""
        from app.models import ShipSpec

        spec = ShipSpec(cpus=2.0, memory="512m", disk="5Gi")
        assert spec.disk == "5Gi"

        # 测试 disk 字段可选
        spec_no_disk = ShipSpec(cpus=1.0, memory="256m")
        assert spec_no_disk.disk is None

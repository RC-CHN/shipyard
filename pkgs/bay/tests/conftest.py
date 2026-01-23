"""
Bay 测试配置

包含通用的 pytest fixtures 和配置。
"""

import os
import time
import uuid
from pathlib import Path

import docker
import pytest
import requests


# ============================================================================
# pytest 标记注册
# ============================================================================

def pytest_configure(config):
    """注册自定义标记"""
    config.addinivalue_line(
        "markers", "e2e: 端到端测试，需要 Bay 服务运行"
    )
    config.addinivalue_line(
        "markers", "integration: 集成测试，需要 Docker 环境"
    )
    config.addinivalue_line(
        "markers", "unit: 单元测试，不需要外部依赖"
    )


# ============================================================================
# 通用配置
# ============================================================================

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


# ============================================================================
# 通用 fixtures
# ============================================================================

@pytest.fixture(scope="module")
def bay_url() -> str:
    """返回 Bay 服务 URL"""
    return BAY_URL


@pytest.fixture(scope="module")
def auth_headers() -> dict[str, str]:
    """返回认证请求头"""
    return get_auth_headers()


# ============================================================================
# Docker/Integration 测试 fixtures
# ============================================================================


@pytest.fixture(scope="session")
def docker_client():
    """创建Docker客户端"""
    return docker.from_env()


@pytest.fixture(scope="session")
def bay_image(docker_client):
    """构建bay Docker镜像"""
    # 获取项目根目录 (bay 包的根目录)
    project_root = Path(__file__).parent.parent

    print(f"Building bay image from {project_root}...")

    # 构建镜像
    image, build_logs = docker_client.images.build(
        path=str(project_root), tag="soulter/shipyard-bay:latest", rm=True, forcerm=True
    )

    # 打印构建日志
    for log in build_logs:
        if "stream" in log:
            print(log["stream"].strip())

    yield image

    # 测试完成后清理镜像
    print("Cleaning up bay image...")
    try:
        docker_client.images.remove(image.id, force=True)
    except Exception as e:
        print(f"Failed to remove image: {e}")


@pytest.fixture(scope="session")
def bay_server(docker_client, bay_image):
    """启动bay容器"""
    print("Starting bay container...")

    # 设置环境变量
    environment = {
        "DATABASE_URL": "sqlite+aiosqlite:///./data/bay_test.db",
        "ACCESS_TOKEN": "secret-token",
        "DEBUG": "false",
        "DOCKER_IMAGE": "soulter/shipyard-ship:latest",
    }

    container = docker_client.containers.run(
        bay_image.id,
        ports={"8156/tcp": ("127.0.0.1", 0)},  # 随机端口映射
        environment=environment,
        detach=True,
        auto_remove=True,
        volumes={
            "/var/run/docker.sock": {"bind": "/var/run/docker.sock", "mode": "rw"}
        },
        network="shipyard",
    )

    # 获取映射的端口
    container.reload()
    port_mapping = container.attrs["NetworkSettings"]["Ports"]["8156/tcp"]
    if not port_mapping:
        raise RuntimeError("Failed to get port mapping")

    host_port = port_mapping[0]["HostPort"]
    base_url = f"http://127.0.0.1:{host_port}"

    # 等待服务启动
    max_retries = 30
    for i in range(max_retries):
        try:
            response = requests.get(f"{base_url}/health", timeout=5)
            if response.status_code == 200:
                print(f"Bay container is ready on port {host_port}")
                break
        except Exception:
            pass

        time.sleep(1)
        if i == max_retries - 1:
            # 打印容器日志用于调试
            logs = container.logs().decode("utf-8")
            print(f"Container logs:\n{logs}")
            raise RuntimeError("Bay container failed to start")

    # 创建一个简单的服务器对象来返回连接信息
    class BayServer:
        def __init__(self, host="127.0.0.1", port=host_port):
            self.host = host
            self.port = port
            self.base_url = base_url
            self.container = container

    server = BayServer()

    yield server

    # 测试完成后停止容器
    print("Stopping bay container...")
    try:
        container.stop(timeout=10)
    except Exception as e:
        print(f"Failed to stop container: {e}")


class TestClient:
    """Test client wrapper for requests.Session"""

    def __init__(self, base_url: str):
        self.base_url = base_url
        self.session = requests.Session()

    def get(self, url, **kwargs):
        full_url = f"{self.base_url}{url}" if not url.startswith("http") else url
        return self.session.get(full_url, **kwargs)

    def post(self, url, **kwargs):
        full_url = f"{self.base_url}{url}" if not url.startswith("http") else url
        return self.session.post(full_url, **kwargs)

    def put(self, url, **kwargs):
        full_url = f"{self.base_url}{url}" if not url.startswith("http") else url
        return self.session.put(full_url, **kwargs)

    def delete(self, url, **kwargs):
        full_url = f"{self.base_url}{url}" if not url.startswith("http") else url
        return self.session.delete(full_url, **kwargs)

    def close(self):
        self.session.close()


@pytest.fixture(scope="session")
def client(bay_server):
    """Create HTTP client for testing"""
    test_client = TestClient(bay_server.base_url)
    yield test_client
    test_client.close()

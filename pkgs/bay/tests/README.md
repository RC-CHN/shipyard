# Bay 测试

本目录包含 Bay 服务的所有测试。

## 目录结构

```
tests/
├── conftest.py         # pytest 配置和通用 fixtures
├── unit/               # 单元测试（不需要外部依赖）
│   └── test_utils.py   # 工具函数测试
├── e2e/                # 端到端测试（需要 Bay 服务运行）
│   └── test_bay_api.py # API 功能测试
├── integration/        # 集成测试（需要 Docker 环境）
│   └── test_integration.py
├── k8s/                # Kubernetes 测试配置
│   ├── k8s-deploy.yaml
│   └── storageclass-retain.yaml
└── scripts/            # 测试脚本
    ├── test_docker_container.sh
    ├── test_docker_host.sh
    ├── test_podman_container.sh
    ├── test_podman_host.sh
    └── test_kubernetes.sh
```

## 运行测试

### 单元测试

单元测试不需要任何外部依赖，可以直接运行：

```bash
cd pkgs/bay
python -m pytest tests/unit/ -v
```

### E2E 测试

E2E 测试需要 Bay 服务运行。可以通过以下方式运行：

1. 确保 Bay 服务正在运行（默认 http://localhost:8156）
2. 运行测试：

```bash
cd pkgs/bay
python -m pytest tests/e2e/ -v
```

可通过环境变量配置：
- `BAY_URL`: Bay 服务地址（默认 http://localhost:8156）
- `BAY_ACCESS_TOKEN`: 访问令牌（默认 secret-token）

### 集成测试

集成测试需要 Docker 环境，会自动构建和启动 Bay 容器：

```bash
cd pkgs/bay
python -m pytest tests/integration/ -v
```

### 使用测试脚本

测试脚本位于 `tests/scripts/` 目录下，用于在不同环境中运行完整的测试流程：

```bash
# Docker 容器模式测试
./tests/scripts/test_docker_container.sh

# Docker 主机模式测试
./tests/scripts/test_docker_host.sh

# Podman 容器模式测试
./tests/scripts/test_podman_container.sh

# Podman 主机模式测试
./tests/scripts/test_podman_host.sh

# Kubernetes 模式测试
./tests/scripts/test_kubernetes.sh [命令] [集群类型]
```

## pytest 标记

测试使用以下标记进行分类：

- `@pytest.mark.unit`: 单元测试
- `@pytest.mark.e2e`: 端到端测试
- `@pytest.mark.integration`: 集成测试

可以使用 `-m` 参数运行特定类型的测试：

```bash
python -m pytest -m unit        # 仅运行单元测试
python -m pytest -m e2e         # 仅运行 E2E 测试
python -m pytest -m integration # 仅运行集成测试
```

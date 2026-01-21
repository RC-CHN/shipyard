# Bay API Service

Bay API是Agent Sandbox的中台服务，负责管理和调度Ship容器环境。

## 安装和运行

### 使用uv（推荐）

1. 安装uv包管理器：

```bash
pip install uv
```

2. 安装依赖：

```bash
uv pip install -e .
```

3. 复制环境配置：

```bash
cp .env.example .env
# 编辑.env文件，设置数据库连接等配置
```

4. 运行数据库迁移：

```bash
alembic upgrade head
```

5. 启动服务：

```bash
python run.py
```

### 使用Docker Compose

**重要**: Bay现在使用宿主机的Docker socket，而不是Docker-in-Docker模式，这提供了更好的性能和稳定性。

1. 确保宿主机上已经安装了Docker并且Docker daemon正在运行。

2. 构建Ship镜像（在宿主机上）：

```bash
cd ../ship
docker build -t ship:latest .
cd ../bay
```

3. 创建Docker网络（用于Ship容器）：

```bash
docker network create shipyard
```

4. 启动所有服务：

```bash
docker-compose up -d
```

## API端点

### 认证

所有API端点都需要Bearer token认证：

```
Authorization: Bearer <your-access-token>
```

### Ship管理

- `POST /ship` - 创建新的Ship环境
- `GET /ship/{ship_id}` - 获取Ship信息
- `DELETE /ship/{ship_id}` - 删除Ship环境
- `POST /ship/{ship_id}/exec/{oper_endpoint}` - 在Ship中执行操作
- `GET /ship/logs/{ship_id}` - 获取Ship容器日志
- `POST /ship/{ship_id}/extend-ttl` - 延长Ship生命周期

### 健康检查

- `GET /health` - 服务健康检查
- `GET /` - 根端点

## 环境变量

参考 `.env.example` 文件了解所有可配置的环境变量。

主要配置项：

- `ACCESS_TOKEN`: API访问令牌
- `DATABASE_URL`: SQLite数据库文件路径
- `MAX_SHIP_NUM`: 最大Ship数量
- `BEHAVIOR_AFTER_MAX_SHIP`: 达到最大Ship数量后的行为（reject/wait）
- `CONTAINER_DRIVER`: 容器运行时驱动（docker/docker-host/podman/podman-host/kubernetes，默认docker-host）
- `DOCKER_IMAGE`: Ship容器镜像名称
- `SHIP_CONTAINER_PORT`: Ship容器内部端口（默认8123）
- `SHIP_HEALTH_CHECK_TIMEOUT`: Ship健康检查最大超时时间（秒，默认60）
- `SHIP_HEALTH_CHECK_INTERVAL`: Ship健康检查间隔时间（秒，默认2）
- `DOCKER_NETWORK`: Docker网络名称

### Kubernetes 专用配置

- `KUBE_NAMESPACE`: Kubernetes 命名空间（默认读取 in-cluster 配置或 default）
- `KUBE_CONFIG_PATH`: Kubeconfig 文件路径（可选，默认使用 in-cluster 配置）
- `KUBE_IMAGE_PULL_POLICY`: 镜像拉取策略（默认 IfNotPresent）
- `KUBE_PVC_SIZE`: 每个 Ship 的 PVC 大小（默认 1Gi）
- `KUBE_STORAGE_CLASS`: PVC 的 StorageClass（可选，使用集群默认）

**注意**: 在配置资源限制时（如通过 API 请求），请务必使用正确的 Kubernetes 单位：
- 内存：使用 `Mi` (Mebibytes) 或 `Gi` (Gibibytes)。例如 `512Mi`。
- **警告**: 不要使用 `m` 作为内存单位（如 `512m`），这在 Kubernetes 中表示 "milli-bytes"（千分之一字节），会导致容器创建失败且报错信息（如 `no space left on device`）极具误导性。

### Kubernetes 数据持久化

Kubernetes 驱动使用 PVC (PersistentVolumeClaim) 实现 Ship 数据持久化。当 Ship 停止时（TTL 过期或手动停止），只会删除 Pod 而保留 PVC，这样 Ship 可以在稍后恢复并保留其数据。

**重要**：数据的实际持久化行为取决于底层 PersistentVolume 的回收策略（在 StorageClass 级别配置）：

| 回收策略 | 行为 | 建议场景 |
|---------|------|---------|
| `Retain` | PVC 删除后 PV 和数据保留 | **生产环境推荐** |
| `Delete` | PVC 删除时 PV 和数据一并删除 | 动态供应的默认策略 |
| `Recycle` | PV 被清理后重新可用（已弃用） | 不推荐使用 |

为确保数据跨 Ship 恢复持久化，请配置 StorageClass 使用 `reclaimPolicy: Retain`：

```yaml
apiVersion: storage.k8s.io/v1
kind: StorageClass
metadata:
  name: ship-storage
provisioner: <your-provisioner>
reclaimPolicy: Retain
volumeBindingMode: WaitForFirstConsumer
```

然后设置环境变量 `KUBE_STORAGE_CLASS=ship-storage`。

**注意**：使用默认 StorageClass 或云提供商存储类时，数据可能在 Ship 被永久删除时丢失。

### Docker/Podman 数据持久化

Docker 和 Podman 驱动通过宿主机目录挂载实现数据持久化：

- 数据目录位置：`{SHIP_DATA_DIR}/{ship_id}/`（默认 `~/.shipyard/ships/{ship_id}/`）
  - `home/` - 挂载到容器 `/home`
  - `metadata/` - 挂载到容器 `/app/metadata`

**重要行为说明**：

| 操作 | 行为 |
|------|------|
| Ship 停止（TTL 过期） | 容器删除，**数据目录保留** |
| Ship 恢复 | 使用同一数据目录创建新容器 |
| Ship 永久删除 | 容器删除，**数据目录不自动删除** |

**为什么不自动删除数据目录？**

出于安全考虑，Bay 不会自动删除宿主机上的挂载目录：
- 防止意外数据丢失
- 避免权限问题导致删除其他重要文件
- 用户可以手动备份后再删除

**手动清理数据目录**：

```bash
# 清理特定 Ship 数据
rm -rf ~/.shipyard/ships/{ship_id}

# 清理所有 Ship 数据（谨慎使用）
rm -rf ~/.shipyard/ships/*
```

## 容器驱动架构

Bay 使用可插拔的驱动架构来支持不同的容器运行时和部署模式：

### 支持的驱动

| 驱动 | 状态 | 说明 | 网络模式 |
|------|------|------|----------|
| **docker** | ✅ 可用 | Bay 运行在 Docker 容器内 | 使用容器内部IP (如 `172.18.0.2:8123`) |
| **docker-host** | ✅ 可用 (默认) | Bay 运行在宿主机上 | 使用 localhost + 端口映射 (如 `127.0.0.1:39314`) |
| **podman** | ✅ 可用 | Bay 运行在 Podman 容器内 | 使用容器内部IP |
| **podman-host** | ✅ 可用 | Bay 运行在宿主机上 (Podman) | 使用 localhost + 端口映射 |
| **kubernetes** | ✅ 可用 | Bay 运行在 Kubernetes 集群内 | 使用 Pod IP + PVC 持久化存储 |
| **containerd** | 🚧 计划中 | 使用 containerd 运行时 | - |

### 选择正确的驱动

- **docker-host** (推荐): 当 Bay 直接运行在宿主机上时使用。这种模式通过端口映射访问 Ship 容器，解决了宿主机无法直接访问容器内部 IP 的问题。

- **docker**: 当 Bay 运行在 Docker 容器内时使用（如通过 docker-compose 部署）。这种模式可以直接使用容器网络 IP 进行通信。

### 驱动架构图

```
┌─────────────────────────────────────────────────────────────────┐
│                         Bay Service                             │
├─────────────────────────────────────────────────────────────────┤
│  ShipService                                                    │
│    ├── url_builder.py    (构建 Ship URL，处理不同地址格式)       │
│    ├── http_client.py    (HTTP 通信：健康检查、exec、文件传输)   │
│    └── service.py        (Ship 生命周期管理)                    │
├─────────────────────────────────────────────────────────────────┤
│  ContainerDriver (抽象接口)                                      │
│    ├── DockerDriver       (容器内部署，返回容器IP)               │
│    ├── DockerHostDriver   (宿主机部署，返回 localhost:port)      │
│    ├── ContainerdDriver   (计划中)                              │
│    └── PodmanDriver       (计划中)                              │
└─────────────────────────────────────────────────────────────────┘
```

### 自定义驱动

要实现自定义容器驱动，需要：

1. 在 `app/drivers/` 目录下创建新的驱动文件
2. 继承 [`ContainerDriver`](app/drivers/base.py) 抽象基类
3. 实现所有必需的方法：
   - `initialize()`: 初始化驱动连接
   - `close()`: 关闭驱动连接
   - `create_ship_container()`: 创建容器，返回 `ContainerInfo`
   - `stop_ship_container()`: 停止并删除容器
   - `ship_data_exists()`: 检查数据目录是否存在
   - `get_container_logs()`: 获取容器日志
   - `is_container_running()`: 检查容器运行状态
4. 在 [`factory.py`](app/drivers/factory.py) 中注册驱动

### ContainerInfo 数据结构

驱动返回的容器信息必须符合 `ContainerInfo` 模型：

```python
@dataclass
class ContainerInfo:
    container_id: str       # 容器 ID
    ip_address: str         # 访问地址 (IP 或 IP:port)
```

**注意**: `ip_address` 字段的格式取决于驱动类型：
- `docker` 驱动: 返回纯 IP 地址，如 `172.18.0.2`
- `docker-host` 驱动: 返回 `IP:port` 格式，如 `127.0.0.1:39314`

## 开发

### 代码格式化

使用 `ruff`:

```bash
ruff format app/
ruff check app/
```

### 类型检查

使用mypy：

```bash
mypy app/
```

### 测试

```bash
pytest
```

### 数据库迁移

创建新的迁移：

```bash
alembic revision --autogenerate -m "description"
```

应用迁移：

```bash
alembic upgrade head
```

#!/usr/bin/env bash
# 本地开发服务器脚本
# 用于前后端联调时启动 Bay 后端服务
#
# 使用方法:
#   cd pkgs/bay
#   ./tests/scripts/dev_server.sh
#
# 说明:
#   - 使用 docker-host 模式运行
#   - Bay 后端运行在 http://localhost:8156
#   - Dashboard 前端运行在 http://localhost:3000 (需另开终端: cd dashboard && npm run dev)
#   - 默认 Token: secret-token
#
set -euo pipefail

SCRIPT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
PROJECT_ROOT=$(cd "${SCRIPT_DIR}/../.." && pwd)

cd "${PROJECT_ROOT}"

echo "============================================"
echo "  Bay 本地开发服务器"
echo "============================================"
echo ""

# 检查 Docker 服务
echo "===> 检查 Docker 服务..."
if ! docker info >/dev/null 2>&1; then
    echo "❌ Docker 服务未运行，请先启动 Docker"
    exit 1
fi
echo "✅ Docker 服务正常"

# 构建 Ship 镜像
echo ""
echo "===> 构建 Ship 镜像 (ship:latest)..."
if ! docker build -t ship:latest "${PROJECT_ROOT}/../ship"; then
    echo "❌ Ship 镜像构建失败"
    exit 1
fi
echo "✅ Ship 镜像构建成功"

# 创建网络
echo ""
echo "===> 创建 Docker 网络..."
docker network inspect shipyard_network >/dev/null 2>&1 || docker network create shipyard_network
echo "✅ 网络 shipyard_network 就绪"

# 创建数据目录
mkdir -p "${PROJECT_ROOT}/data"

# 设置环境变量
export ACCESS_TOKEN="${ACCESS_TOKEN:-secret-token}"
export DATABASE_URL="${DATABASE_URL:-sqlite+aiosqlite:///./data/bay_dev.db}"
export CONTAINER_DRIVER="docker-host"
export DOCKER_IMAGE="ship:latest"
export DOCKER_NETWORK="shipyard_network"
export SHIP_DATA_DIR="${PROJECT_ROOT}/data/shipyard/ship_mnt_data"
# 使用字符串导入方式以支持热重载
export DEBUG="${DEBUG:-false}"

echo ""
echo "============================================"
echo "  配置信息"
echo "============================================"
echo "  Bay API:       http://localhost:8156"
echo "  Dashboard:     http://localhost:3000 (需另开终端启动)"
echo "  Access Token:  ${ACCESS_TOKEN}"
echo "  Driver:        ${CONTAINER_DRIVER}"
echo "  Database:      ${DATABASE_URL}"
echo "============================================"
echo ""
echo "提示: 在另一个终端中启动前端开发服务器:"
echo "  cd ${PROJECT_ROOT}/dashboard && npm run dev"
echo ""
echo "按 Ctrl+C 停止服务器"
echo ""

# 使用 uvicorn 命令行直接启动（支持热重载）
echo "===> 启动 Bay 服务..."
uvicorn app.main:app --host 0.0.0.0 --port 8156 --reload

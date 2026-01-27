#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
PROJECT_ROOT=$(cd "${SCRIPT_DIR}/../.." && pwd)

cd "${PROJECT_ROOT}"

echo "==> [Docker Host] 检查 Docker 服务"
docker info >/dev/null

echo "==> [Docker Host] 构建 Ship 镜像 (ship:latest)"
docker build -t ship:latest "${PROJECT_ROOT}/../ship"

echo "==> [Docker Host] 创建网络 shipyard_network (如不存在)"
docker network inspect shipyard_network >/dev/null 2>&1 || docker network create shipyard_network

mkdir -p "${PROJECT_ROOT}/data"

export ACCESS_TOKEN="secret-token"
export DATABASE_URL="sqlite+aiosqlite:///./data/bay_test.db"
export CONTAINER_DRIVER="docker-host"
export DOCKER_IMAGE="ship:latest"
export DOCKER_NETWORK="shipyard_network"
export SHIP_DATA_DIR="${PROJECT_ROOT}/data/shipyard/ship_mnt_data"

BAY_PID=""
cleanup() {
  if [[ -n "${BAY_PID}" ]] && kill -0 "${BAY_PID}" >/dev/null 2>&1; then
    echo "==> [Docker Host] 停止 Bay (PID=${BAY_PID})"
    kill "${BAY_PID}" || true
  fi
}
trap cleanup EXIT

echo "==> [Docker Host] 启动 Bay (python run.py)"
python run.py &
BAY_PID=$!

echo "==> [Docker Host] 等待健康检查"
for i in {1..30}; do
  if curl -fsS "http://127.0.0.1:8156/health" >/dev/null; then
    echo "==> [Docker Host] Bay 已就绪"
    break
  fi
  sleep 1
  if [[ "$i" -eq 30 ]]; then
    echo "❌ [Docker Host] Bay 启动超时"
    exit 1
  fi
done

echo "==> [Docker Host] 运行单元测试"
python -m pytest tests/unit/ -v

echo "==> [Docker Host] 运行 E2E 测试"
python -m pytest tests/e2e/ -v

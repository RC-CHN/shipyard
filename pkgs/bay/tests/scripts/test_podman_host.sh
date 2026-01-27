#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
PROJECT_ROOT=$(cd "${SCRIPT_DIR}/../.." && pwd)

cd "${PROJECT_ROOT}"

export HTTP_PROXY="http://192.168.44.2:10820"
export HTTPS_PROXY="http://192.168.44.2:10820"
export NO_PROXY="127.0.0.1,localhost"

echo "==> [Podman Host] 检查 Podman 服务"
podman info >/dev/null

echo "==> [Podman Host] 构建 Ship 镜像 (docker.io/soulter/shipyard-ship:latest)"
podman build -t docker.io/soulter/shipyard-ship:latest "${PROJECT_ROOT}/../ship"

echo "==> [Podman Host] 创建网络 bay_shipyard (如不存在)"
podman network exists bay_shipyard || podman network create bay_shipyard

mkdir -p "${PROJECT_ROOT}/data"

export ACCESS_TOKEN="secret-token"
export DATABASE_URL="sqlite+aiosqlite:///./data/bay_test.db"
export CONTAINER_DRIVER="podman-host"
export DOCKER_IMAGE="docker.io/soulter/shipyard-ship:latest"
export DOCKER_NETWORK="bay_shipyard"
export SHIP_DATA_DIR="${PROJECT_ROOT}/data/shipyard/ship_mnt_data"

BAY_PID=""
cleanup() {
  if [[ -n "${BAY_PID}" ]] && kill -0 "${BAY_PID}" >/dev/null 2>&1; then
    echo "==> [Podman Host] 停止 Bay (PID=${BAY_PID})"
    kill "${BAY_PID}" || true
  fi
}
trap cleanup EXIT

echo "==> [Podman Host] 启动 Bay (python run.py)"
python run.py &
BAY_PID=$!

echo "==> [Podman Host] 等待健康检查"
for i in {1..30}; do
  if curl -fsS "http://127.0.0.1:8156/health" >/dev/null; then
    echo "==> [Podman Host] Bay 已就绪"
    break
  fi
  sleep 1
  if [[ "$i" -eq 30 ]]; then
    echo "❌ [Podman Host] Bay 启动超时"
    exit 1
  fi
done

echo "==> [Podman Host] 运行单元测试"
python -m pytest tests/unit/ -v

echo "==> [Podman Host] 运行 E2E 测试"
python -m pytest tests/e2e/ -v

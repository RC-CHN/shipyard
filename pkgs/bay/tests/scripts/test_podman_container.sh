#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
PROJECT_ROOT=$(cd "${SCRIPT_DIR}/../.." && pwd)

cd "${PROJECT_ROOT}"

export HTTP_PROXY="http://192.168.44.2:10820"
export HTTPS_PROXY="http://192.168.44.2:10820"
export NO_PROXY="127.0.0.1,localhost"

echo "==> [Podman Container] 检查 Podman 服务"
podman info >/dev/null

echo "==> [Podman Container] 本地构建 Bay 镜像 (localhost/soulter/shipyard-bay:latest)"
podman build -t localhost/soulter/shipyard-bay:latest "${PROJECT_ROOT}"

echo "==> [Podman Container] 本地构建 Ship 镜像 (docker.io/soulter/shipyard-ship:latest)"
podman build -t docker.io/soulter/shipyard-ship:latest "${PROJECT_ROOT}/../ship"

echo "==> [Podman Container] 创建网络 bay_shipyard (如不存在)"
podman network exists bay_shipyard || podman network create bay_shipyard

HOST_SHIP_DATA_DIR="${PROJECT_ROOT}/data/shipyard/ship_mnt_data"
mkdir -p "${PROJECT_ROOT}/data/shipyard/bay_data" "${HOST_SHIP_DATA_DIR}"

BAY_CONTAINER_NAME="shipyard-bay-podman"

cleanup() {
  if podman ps -a --format "{{.Names}}" | grep -q "^${BAY_CONTAINER_NAME}$"; then
    echo "==> [Podman Container] 清理 Bay 容器"
    podman rm -f "${BAY_CONTAINER_NAME}" || true
  fi
}
trap cleanup EXIT

cleanup

echo "==> [Podman Container] 启动 Bay 容器"
podman run -d --name "${BAY_CONTAINER_NAME}" \
  -p 8156:8156 \
  -e PORT=8156 \
  -e DATABASE_URL=sqlite+aiosqlite:///./data/bay.db \
  -e ACCESS_TOKEN=secret-token \
  -e MAX_SHIP_NUM=10 \
  -e BEHAVIOR_AFTER_MAX_SHIP=reject \
  -e CONTAINER_DRIVER=podman \
  -e DOCKER_IMAGE=docker.io/soulter/shipyard-ship:latest \
  -e DOCKER_NETWORK=bay_shipyard \
  -e SHIP_DATA_DIR="${HOST_SHIP_DATA_DIR}" \
  -v "${PROJECT_ROOT}/data/shipyard/bay_data:/app/data" \
  -v "${HOST_SHIP_DATA_DIR}:${HOST_SHIP_DATA_DIR}" \
  -v "$XDG_RUNTIME_DIR/podman/podman.sock:/var/run/podman/podman.sock" \
  --network bay_shipyard \
  localhost/soulter/shipyard-bay:latest

echo "==> [Podman Container] 等待健康检查"
for i in {1..30}; do
  if curl -fsS "http://127.0.0.1:8156/health" >/dev/null; then
    echo "==> [Podman Container] Bay 已就绪"
    break
  fi
  sleep 1
  if [[ "$i" -eq 30 ]]; then
    echo "❌ [Podman Container] Bay 启动超时"
    podman logs "${BAY_CONTAINER_NAME}" || true
    exit 1
  fi
done

echo "==> [Podman Container] 运行 E2E 测试"
python -m pytest tests/e2e/ -v

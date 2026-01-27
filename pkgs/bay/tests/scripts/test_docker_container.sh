#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
PROJECT_ROOT=$(cd "${SCRIPT_DIR}/../.." && pwd)

cd "${PROJECT_ROOT}"

echo "==> [Docker Container] 检查 Docker 服务"
docker info >/dev/null

echo "==> [Docker Container] 本地构建 Bay 镜像 (soulter/shipyard-bay:latest)"
docker build -t soulter/shipyard-bay:latest "${PROJECT_ROOT}"

echo "==> [Docker Container] 本地构建 Ship 镜像 (soulter/shipyard-ship:latest)"
docker build -t soulter/shipyard-ship:latest "${PROJECT_ROOT}/../ship"

echo "==> [Docker Container] 创建网络 shipyard_network (如不存在)"
docker network inspect shipyard_network >/dev/null 2>&1 || docker network create shipyard_network

mkdir -p "${PROJECT_ROOT}/data/shipyard/bay_data"

export PWD="${PROJECT_ROOT}"

echo "==> [Docker Container] 启动 docker-compose"
docker compose -f docker-compose.yml up -d

echo "==> [Docker Container] 等待健康检查"
for i in {1..30}; do
  if curl -fsS "http://127.0.0.1:8156/health" >/dev/null; then
    echo "==> [Docker Container] Bay 已就绪"
    break
  fi
  sleep 1
  if [[ "$i" -eq 30 ]]; then
    echo "❌ [Docker Container] Bay 启动超时"
    docker compose -f docker-compose.yml logs
    exit 1
  fi
done

echo "==> [Docker Container] 运行单元测试"
uv run python -m pytest tests/unit/ -v

echo "==> [Docker Container] 运行 E2E 测试"
uv run python -m pytest tests/e2e/ -v

echo "==> [Docker Container] 关闭 docker-compose"
docker compose -f docker-compose.yml down

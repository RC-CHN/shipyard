#!/bin/bash
# Shipyard Kubernetes Local Test Script
#
# 此脚本用于在本地 K8s 集群中测试 Kubernetes 驱动
# 支持: Docker Desktop Kubernetes, kind, minikube, k3d
# 使用 pytest tests/e2e/ 进行 API 测试
#
# 使用方法:
#   ./test_kubernetes.sh [命令] [集群类型]
#
# 命令: all, build, deploy, test, cleanup
# 集群类型: docker-desktop (默认), kind, minikube, k3d
#
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
SHIP_DIR="$(cd "$PROJECT_ROOT/../ship" && pwd)"
TESTS_DIR="$PROJECT_ROOT/tests"
K8S_DIR="$TESTS_DIR/k8s"

# 默认参数
COMMAND="${1:-all}"
CLUSTER_TYPE="${2:-docker-desktop}"

# 镜像名称 (本地构建使用 local tag)
BAY_IMAGE="bay:latest"
SHIP_IMAGE="ship:latest"

echo "=========================================="
echo "Shipyard Kubernetes Local Test"
echo "=========================================="
echo "命令: $COMMAND"
echo "集群类型: $CLUSTER_TYPE"
echo "Bay 目录: $PROJECT_ROOT"
echo "Ship 目录: $SHIP_DIR"
echo "K8s 配置目录: $K8S_DIR"
echo "Tests 目录: $TESTS_DIR"
echo ""

# 检查必要工具
check_prerequisites() {
    echo "📋 检查必要工具..."
    
    if ! command -v kubectl &> /dev/null; then
        echo "❌ kubectl 未安装"
        exit 1
    fi
    
    if ! command -v docker &> /dev/null; then
        echo "❌ docker 未安装"
        exit 1
    fi
    
    # 检查 kubectl 是否能连接到集群
    if ! kubectl cluster-info &> /dev/null; then
        echo "❌ 无法连接到 Kubernetes 集群"
        echo "   请确保集群正在运行"
        exit 1
    fi
    
    case "$CLUSTER_TYPE" in
        docker-desktop)
            echo "  使用 Docker Desktop Kubernetes"
            # Docker Desktop 不需要额外检查，镜像自动可用
            ;;
        kind)
            if ! command -v kind &> /dev/null; then
                echo "❌ kind 未安装"
                exit 1
            fi
            ;;
        minikube)
            if ! command -v minikube &> /dev/null; then
                echo "❌ minikube 未安装"
                exit 1
            fi
            ;;
        k3d)
            if ! command -v k3d &> /dev/null; then
                echo "❌ k3d 未安装"
                exit 1
            fi
            ;;
        *)
            echo "❌ 不支持的集群类型: $CLUSTER_TYPE"
            echo "支持的类型: docker-desktop, kind, minikube, k3d"
            exit 1
            ;;
    esac
    
    echo "✅ 所有工具已就绪"
}

# 构建本地镜像
build_images() {
    echo ""
    echo "🔨 构建本地镜像..."
    
    echo "  构建 Bay 镜像..."
    docker build -t "$BAY_IMAGE" "$PROJECT_ROOT"
    
    echo "  构建 Ship 镜像..."
    docker build -t "$SHIP_IMAGE" "$SHIP_DIR"
    
    echo "✅ 镜像构建完成"
}

# 加载镜像到集群
load_images() {
    echo ""
    echo "📦 加载镜像到集群..."
    
    case "$CLUSTER_TYPE" in
        docker-desktop)
            # Docker Desktop 直接使用本地镜像，无需额外加载
            echo "  Docker Desktop 直接使用本地 Docker 镜像"
            ;;
        kind)
            kind load docker-image "$BAY_IMAGE"
            kind load docker-image "$SHIP_IMAGE"
            ;;
        minikube)
            minikube image load "$BAY_IMAGE"
            minikube image load "$SHIP_IMAGE"
            ;;
        k3d)
            k3d image import "$BAY_IMAGE"
            k3d image import "$SHIP_IMAGE"
            ;;
    esac
    
    echo "✅ 镜像加载完成"
}

# 生成使用本地镜像的 YAML
generate_local_yaml() {
    local output_file="$K8S_DIR/k8s-deploy-local.yaml"
    
    sed -e "s|soulter/shipyard-bay:latest|$BAY_IMAGE|g" \
        -e "s|soulter/shipyard-ship:latest|$SHIP_IMAGE|g" \
        -e "s|imagePullPolicy: IfNotPresent|imagePullPolicy: Never|g" \
        "$K8S_DIR/k8s-deploy.yaml" > "$output_file"
    
    echo "$output_file"
}

# 部署到 Kubernetes
deploy() {
    echo ""
    echo "🚀 部署到 Kubernetes..."
    
    # 先创建 StorageClass（如果不存在）
    echo "  创建 StorageClass..."
    kubectl apply -f "$K8S_DIR/storageclass-retain.yaml" || true
    
    # 生成本地 YAML
    local yaml_file
    yaml_file=$(generate_local_yaml)
    
    kubectl apply -f "$yaml_file"
    
    echo "✅ 部署完成"
}

# 等待 Bay 就绪
wait_for_bay() {
    echo ""
    echo "⏳ 等待 Bay 服务就绪..."
    
    # 等待 Pod 创建
    sleep 5
    
    # 等待 Pod Ready
    kubectl wait --for=condition=ready pod \
        -l app=bay \
        -n shipyard \
        --timeout=120s || {
        echo "❌ Bay Pod 未能就绪"
        echo "查看 Pod 状态:"
        kubectl get pods -n shipyard
        echo ""
        echo "查看日志:"
        kubectl logs -n shipyard -l app=bay --tail=50
        exit 1
    }
    
    echo "✅ Bay 服务已就绪"
}

# 运行测试
run_tests() {
    echo ""
    echo "🧪 运行 API 测试..."
    
    # 端口转发
    echo "  启动端口转发..."
    kubectl port-forward svc/bay 8156:8156 -n shipyard &
    PF_PID=$!
    
    # 等待端口就绪
    sleep 3
    for i in {1..10}; do
        if curl -s http://localhost:8156/health > /dev/null 2>&1; then
            echo "  ✅ 端口转发就绪"
            break
        fi
        sleep 1
    done
    
    # 设置环境变量
    export BAY_URL="http://localhost:8156"
    export BAY_ACCESS_TOKEN="test-token"
    
    # 运行测试脚本
    echo ""
    echo "  运行 pytest tests/unit/..."
    cd "$PROJECT_ROOT"
    python -m pytest tests/unit/ -v || true
    
    echo ""
    echo "  运行 pytest tests/e2e/..."
    python -m pytest tests/e2e/ -v || true
    
    # 清理端口转发
    kill $PF_PID 2>/dev/null || true
    
    echo ""
    echo "✅ 测试完成"
}

# 显示状态
show_status() {
    echo ""
    echo "📊 集群状态..."
    echo ""
    echo "=== Pods ==="
    kubectl get pods -n shipyard -o wide
    echo ""
    echo "=== Services ==="
    kubectl get svc -n shipyard
    echo ""
    echo "=== PVCs ==="
    kubectl get pvc -n shipyard
}

# 清理资源
cleanup() {
    echo ""
    echo "🧹 清理资源..."
    
    # 删除 namespace（会删除所有资源）
    kubectl delete namespace shipyard --ignore-not-found=true
    
    # 删除 cluster-wide 资源
    kubectl delete clusterrole shipyard-bay-namespace-reader --ignore-not-found=true
    kubectl delete clusterrolebinding shipyard-bay-namespace-reader --ignore-not-found=true
    
    # 删除生成的本地 YAML
    rm -f "$K8S_DIR/k8s-deploy-local.yaml"
    
    echo "✅ 清理完成"
}

# 显示帮助
show_help() {
    cat << EOF
使用方法: $0 [命令] [集群类型]

命令:
  all       - 执行完整流程：构建、部署、测试 (默认)
  build     - 仅构建镜像
  deploy    - 仅部署到集群 (需要先 build)
  test      - 仅运行测试 (需要先 deploy)
  status    - 显示集群状态
  cleanup   - 清理所有资源
  help      - 显示帮助

集群类型:
  docker-desktop  - Docker Desktop Kubernetes (默认)
  kind            - Kind 集群
  minikube        - Minikube 集群
  k3d             - K3d 集群

示例:
  $0                           # 在 docker-desktop 集群中执行完整测试
  $0 all docker-desktop        # 在 Docker Desktop 中执行完整测试
  $0 all kind                  # 在 kind 集群中执行完整测试
  $0 all minikube              # 在 minikube 中执行完整测试
  $0 build                     # 仅构建镜像
  $0 deploy                    # 仅部署
  $0 test                      # 仅运行测试
  $0 cleanup                   # 清理资源
EOF
}

# 主函数
main() {
    case "$COMMAND" in
        all)
            check_prerequisites
            build_images
            load_images
            deploy
            wait_for_bay
            show_status
            run_tests
            cleanup
            ;;
        build)
            check_prerequisites
            build_images
            ;;
        deploy)
            check_prerequisites
            load_images
            deploy
            wait_for_bay
            show_status
            ;;
        test)
            run_tests
            ;;
        status)
            show_status
            ;;
        cleanup)
            cleanup
            ;;
        help|--help|-h)
            show_help
            ;;
        *)
            echo "未知命令: $COMMAND"
            echo ""
            show_help
            exit 1
            ;;
    esac
}

# 执行
main

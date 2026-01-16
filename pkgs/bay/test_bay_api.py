#!/usr/bin/env python3
"""
Bay API 功能测试脚本

使用方法:
    # 确保 Bay 服务正在运行
    uv run python test_bay_api.py
"""

import requests
import uuid
import time
import sys

# 配置
BAY_URL = "http://localhost:8156"
ACCESS_TOKEN = "secret-token"  # 默认 token
SESSION_ID = str(uuid.uuid4())

headers = {
    "Authorization": f"Bearer {ACCESS_TOKEN}",
    "X-SESSION-ID": SESSION_ID,
    "Content-Type": "application/json",
}


def test_health():
    """测试健康检查端点"""
    print("=" * 50)
    print("测试 1: 健康检查")
    print("=" * 50)
    
    try:
        resp = requests.get(f"{BAY_URL}/health", timeout=5)
        print(f"状态码: {resp.status_code}")
        print(f"响应: {resp.json()}")
        
        if resp.status_code == 200:
            print("✅ 健康检查通过")
            return True
        else:
            print("❌ 健康检查失败")
            return False
    except Exception as e:
        print(f"❌ 请求失败: {e}")
        return False


def test_list_ships():
    """测试列出 ships"""
    print("\n" + "=" * 50)
    print("测试 2: 列出 Ships")
    print("=" * 50)
    
    try:
        resp = requests.get(f"{BAY_URL}/ships", headers=headers, timeout=5)
        print(f"状态码: {resp.status_code}")
        print(f"响应: {resp.json()}")
        
        if resp.status_code == 200:
            print("✅ 列出 ships 成功")
            return True
        else:
            print("❌ 列出 ships 失败")
            return False
    except Exception as e:
        print(f"❌ 请求失败: {e}")
        return False


def test_create_ship():
    """测试创建 ship"""
    print("\n" + "=" * 50)
    print("测试 3: 创建 Ship")
    print("=" * 50)
    
    try:
        payload = {
            "ttl": 300,  # 5 分钟
            "max_session_num": 1,
        }
        
        print(f"请求载荷: {payload}")
        resp = requests.post(
            f"{BAY_URL}/ship", 
            headers=headers, 
            json=payload,
            timeout=120  # 创建容器可能需要时间
        )
        print(f"状态码: {resp.status_code}")
        
        if resp.status_code == 201:
            data = resp.json()
            print(f"响应: {data}")
            print(f"✅ Ship 创建成功! ID: {data.get('id')}")
            return data.get('id')
        else:
            print(f"响应: {resp.text}")
            print("❌ Ship 创建失败")
            return None
    except Exception as e:
        print(f"❌ 请求失败: {e}")
        return None


def test_get_ship(ship_id):
    """测试获取 ship 信息"""
    print("\n" + "=" * 50)
    print(f"测试 4: 获取 Ship 信息 (ID: {ship_id})")
    print("=" * 50)
    
    try:
        resp = requests.get(
            f"{BAY_URL}/ship/{ship_id}", 
            headers=headers, 
            timeout=5
        )
        print(f"状态码: {resp.status_code}")
        print(f"响应: {resp.json()}")
        
        if resp.status_code == 200:
            print("✅ 获取 ship 信息成功")
            return True
        else:
            print("❌ 获取 ship 信息失败")
            return False
    except Exception as e:
        print(f"❌ 请求失败: {e}")
        return False


def test_exec_shell(ship_id):
    """测试在 ship 中执行 shell 命令"""
    print("\n" + "=" * 50)
    print(f"测试 5: 执行 Shell 命令 (Ship ID: {ship_id})")
    print("=" * 50)
    
    try:
        payload = {
            "type": "shell/exec",
            "payload": {
                "command": "echo 'Hello from Bay!'"
            }
        }
        
        print(f"请求载荷: {payload}")
        resp = requests.post(
            f"{BAY_URL}/ship/{ship_id}/exec", 
            headers=headers, 
            json=payload,
            timeout=30
        )
        print(f"状态码: {resp.status_code}")
        
        if resp.status_code == 200:
            data = resp.json()
            print(f"响应: {data}")
            print("✅ Shell 命令执行成功")
            return True
        else:
            print(f"响应: {resp.text}")
            print("❌ Shell 命令执行失败")
            return False
    except Exception as e:
        print(f"❌ 请求失败: {e}")
        return False


def test_delete_ship(ship_id):
    """测试删除 ship"""
    print("\n" + "=" * 50)
    print(f"测试 6: 删除 Ship (ID: {ship_id})")
    print("=" * 50)
    
    try:
        resp = requests.delete(
            f"{BAY_URL}/ship/{ship_id}", 
            headers=headers, 
            timeout=30
        )
        print(f"状态码: {resp.status_code}")
        
        if resp.status_code == 204:
            print("✅ Ship 删除成功")
            return True
        else:
            print(f"响应: {resp.text}")
            print("❌ Ship 删除失败")
            return False
    except Exception as e:
        print(f"❌ 请求失败: {e}")
        return False


def main():
    print("Bay API 功能测试")
    print("=" * 50)
    print(f"服务地址: {BAY_URL}")
    print(f"Session ID: {SESSION_ID}")
    print()
    
    # 测试健康检查
    if not test_health():
        print("\n服务未运行，退出测试")
        sys.exit(1)
    
    # 测试列出 ships
    test_list_ships()
    
    # 测试创建 ship (需要 Docker 和 ship 镜像)
    print("\n" + "-" * 50)
    print("以下测试需要 Docker 和 ship 镜像")
    print("-" * 50)
    
    ship_id = test_create_ship()
    
    if ship_id:
        # 等待一下让 ship 完全启动
        print("\n等待 2 秒让 ship 完全就绪...")
        time.sleep(2)
        
        # 测试获取 ship 信息
        test_get_ship(ship_id)
        
        # 测试执行命令
        test_exec_shell(ship_id)
        
        # 测试删除 ship
        test_delete_ship(ship_id)
    else:
        print("\n跳过需要 Ship 的测试（可能没有 ship 镜像）")
    
    print("\n" + "=" * 50)
    print("测试完成!")
    print("=" * 50)


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""
Bay API 功能测试脚本（更全面）

使用方法:
    # 确保 Bay 服务正在运行
    uv run python test_bay_api.py
"""

from __future__ import annotations

import io
import json
import sys
import time
import uuid
from typing import Any, Dict, Optional

import requests

# 配置
BAY_URL = "http://localhost:8156"
ACCESS_TOKEN = "secret-token"  # 默认 token
SESSION_ID = str(uuid.uuid4())

AUTH_HEADERS = {
    "Authorization": f"Bearer {ACCESS_TOKEN}",
    "X-SESSION-ID": SESSION_ID,
}


def print_section(title: str) -> None:
    print("\n" + "=" * 70)
    print(title)
    print("=" * 70)


def request_json(resp: requests.Response) -> Dict[str, Any] | list[Any] | str:
    try:
        return resp.json()
    except Exception:
        return resp.text


def check_status(
    resp: requests.Response,
    expected: int | list[int],
    success_msg: str,
    fail_msg: str,
) -> bool:
    if isinstance(expected, int):
        expected_list = [expected]
    else:
        expected_list = expected

    ok = resp.status_code in expected_list
    print(f"状态码: {resp.status_code}")
    print(f"响应: {request_json(resp)}")
    if ok:
        print(f"✅ {success_msg}")
    else:
        print(f"❌ {fail_msg}")
    return ok


def test_health() -> bool:
    print_section("测试 1: /health 健康检查")
    try:
        resp = requests.get(f"{BAY_URL}/health", timeout=5)
        return check_status(resp, 200, "健康检查通过", "健康检查失败")
    except Exception as exc:
        print(f"❌ 请求失败: {exc}")
        return False


def test_root() -> bool:
    print_section("测试 2: / 根路由")
    try:
        resp = requests.get(f"{BAY_URL}/", timeout=5)
        return check_status(resp, 200, "根路由可用", "根路由失败")
    except Exception as exc:
        print(f"❌ 请求失败: {exc}")
        return False


def test_stat() -> bool:
    print_section("测试 3: /stat 版本信息")
    try:
        resp = requests.get(f"{BAY_URL}/stat", timeout=5)
        return check_status(resp, 200, "统计信息可用", "统计信息失败")
    except Exception as exc:
        print(f"❌ 请求失败: {exc}")
        return False


def test_auth_required() -> bool:
    print_section("测试 4: 认证校验")
    try:
        resp = requests.get(f"{BAY_URL}/ships", timeout=5)
        ok = check_status(
            resp,
            [401, 403],
            "未授权访问被拒绝",
            "未授权访问未被拒绝",
        )
        if not ok:
            return False
        if resp.status_code == 403:
            detail = ""
            try:
                payload = resp.json()
                detail = payload.get("detail", "") if isinstance(payload, dict) else ""
            except Exception:
                detail = ""
            print(f"提示: 当前未携带 token 时返回 403, detail={detail!r}")
        return True
    except Exception as exc:
        print(f"❌ 请求失败: {exc}")
        return False


def test_list_ships() -> bool:
    print_section("测试 5: /ships 列出 Ships")
    try:
        resp = requests.get(f"{BAY_URL}/ships", headers=AUTH_HEADERS, timeout=5)
        return check_status(resp, 200, "列出 ships 成功", "列出 ships 失败")
    except Exception as exc:
        print(f"❌ 请求失败: {exc}")
        return False


def test_create_ship_invalid_payload() -> bool:
    print_section("测试 6: /ship 创建 Ship（非法参数）")
    try:
        payload = {"ttl": 0, "max_session_num": 0}
        resp = requests.post(
            f"{BAY_URL}/ship",
            headers={**AUTH_HEADERS, "Content-Type": "application/json"},
            json=payload,
            timeout=10,
        )
        return check_status(resp, 422, "非法参数被拒绝", "非法参数未被拒绝")
    except Exception as exc:
        print(f"❌ 请求失败: {exc}")
        return False


def test_create_ship() -> Optional[str]:
    print_section("测试 7: /ship 创建 Ship")
    try:
        payload = {
            "ttl": 300,
            "max_session_num": 2,
            "spec": {"cpus": 0.5, "memory": "512m"},
        }
        print(f"请求载荷: {payload}")
        resp = requests.post(
            f"{BAY_URL}/ship",
            headers={**AUTH_HEADERS, "Content-Type": "application/json"},
            json=payload,
            timeout=120,
        )
        if not check_status(resp, 201, "Ship 创建成功", "Ship 创建失败"):
            return None
        data = resp.json()
        ship_id = data.get("id")
        print(f"Ship ID: {ship_id}")
        return ship_id
    except Exception as exc:
        print(f"❌ 请求失败: {exc}")
        return None


def test_get_ship_not_found() -> bool:
    print_section("测试 8: /ship/{id} 获取不存在 Ship")
    try:
        resp = requests.get(
            f"{BAY_URL}/ship/not-exists-id",
            headers=AUTH_HEADERS,
            timeout=5,
        )
        return check_status(resp, 404, "不存在 ship 返回 404", "不存在 ship 未返回 404")
    except Exception as exc:
        print(f"❌ 请求失败: {exc}")
        return False


def test_get_ship(ship_id: str) -> bool:
    print_section(f"测试 9: /ship/{ship_id} 获取 Ship 信息")
    try:
        resp = requests.get(
            f"{BAY_URL}/ship/{ship_id}", headers=AUTH_HEADERS, timeout=5
        )
        return check_status(resp, 200, "获取 ship 信息成功", "获取 ship 信息失败")
    except Exception as exc:
        print(f"❌ 请求失败: {exc}")
        return False


def test_exec_shell(ship_id: str) -> bool:
    print_section(f"测试 10: /ship/{ship_id}/exec 执行 Shell")
    try:
        payload = {"type": "shell/exec", "payload": {"command": "echo Bay"}}
        resp = requests.post(
            f"{BAY_URL}/ship/{ship_id}/exec",
            headers={**AUTH_HEADERS, "Content-Type": "application/json"},
            json=payload,
            timeout=30,
        )
        return check_status(resp, 200, "Shell 命令执行成功", "Shell 命令执行失败")
    except Exception as exc:
        print(f"❌ 请求失败: {exc}")
        return False


def test_exec_invalid_type(ship_id: str) -> bool:
    print_section(f"测试 11: /ship/{ship_id}/exec 非法操作类型")
    try:
        payload = {"type": "unknown/exec", "payload": {"foo": "bar"}}
        resp = requests.post(
            f"{BAY_URL}/ship/{ship_id}/exec",
            headers={**AUTH_HEADERS, "Content-Type": "application/json"},
            json=payload,
            timeout=30,
        )
        return check_status(resp, 400, "非法操作被拒绝", "非法操作未被拒绝")
    except Exception as exc:
        print(f"❌ 请求失败: {exc}")
        return False


def test_extend_ttl(ship_id: str) -> bool:
    print_section(f"测试 12: /ship/{ship_id}/extend-ttl")
    try:
        payload = {"ttl": 600}
        resp = requests.post(
            f"{BAY_URL}/ship/{ship_id}/extend-ttl",
            headers={**AUTH_HEADERS, "Content-Type": "application/json"},
            json=payload,
            timeout=10,
        )
        return check_status(resp, 200, "TTL 扩展成功", "TTL 扩展失败")
    except Exception as exc:
        print(f"❌ 请求失败: {exc}")
        return False


def test_get_logs(ship_id: str) -> bool:
    print_section(f"测试 13: /ship/logs/{ship_id} 获取日志")
    try:
        resp = requests.get(
            f"{BAY_URL}/ship/logs/{ship_id}", headers=AUTH_HEADERS, timeout=10
        )
        return check_status(resp, 200, "获取日志成功", "获取日志失败")
    except Exception as exc:
        print(f"❌ 请求失败: {exc}")
        return False


def test_upload_download(ship_id: str) -> bool:
    print_section(f"测试 14: /ship/{ship_id}/upload + download")
    try:
        content = b"hello from bay upload"
        file_obj = io.BytesIO(content)
        files = {"file": ("hello.txt", file_obj, "text/plain")}
        session_prefix = SESSION_ID.split("-")[0]
        workspace_path = f"/home/ship_{session_prefix}/workspace/hello.txt"
        data = {"file_path": workspace_path}
        upload_resp = requests.post(
            f"{BAY_URL}/ship/{ship_id}/upload",
            headers=AUTH_HEADERS,
            files=files,
            data=data,
            timeout=30,
        )
        if not check_status(upload_resp, 200, "上传成功", "上传失败"):
            return False

        download_resp = requests.get(
            f"{BAY_URL}/ship/{ship_id}/download",
            headers=AUTH_HEADERS,
            params={"file_path": workspace_path},
            timeout=30,
        )
        if download_resp.status_code != 200:
            print(f"状态码: {download_resp.status_code}")
            print(f"响应: {request_json(download_resp)}")
            print("❌ 下载失败")
            return False

        if download_resp.content != content:
            print("❌ 下载内容不匹配")
            return False

        print("✅ 下载成功且内容匹配")
        return True
    except Exception as exc:
        print(f"❌ 请求失败: {exc}")
        return False


def test_delete_ship(ship_id: str) -> bool:
    print_section(f"测试 15: /ship/{ship_id} 删除 Ship")
    try:
        resp = requests.delete(
            f"{BAY_URL}/ship/{ship_id}", headers=AUTH_HEADERS, timeout=30
        )
        return check_status(resp, 204, "Ship 删除成功", "Ship 删除失败")
    except Exception as exc:
        print(f"❌ 请求失败: {exc}")
        return False


def test_delete_ship_not_found(ship_id: str) -> bool:
    print_section(f"测试 16: /ship/{ship_id} 删除不存在 Ship")
    try:
        resp = requests.delete(
            f"{BAY_URL}/ship/{ship_id}", headers=AUTH_HEADERS, timeout=10
        )
        return check_status(resp, 404, "重复删除返回 404", "重复删除未返回 404")
    except Exception as exc:
        print(f"❌ 请求失败: {exc}")
        return False


def main() -> None:
    print("Bay API 功能测试（全面版）")
    print("=" * 70)
    print(f"服务地址: {BAY_URL}")
    print(f"Session ID: {SESSION_ID}")
    print()

    # 基础健康与信息
    if not test_health():
        print("\n服务未运行，退出测试")
        sys.exit(1)
    test_root()
    test_stat()

    # 认证与列表
    test_auth_required()
    test_list_ships()

    # 非法参数
    test_create_ship_invalid_payload()

    # 需要 Docker 和 ship 镜像
    print("\n" + "-" * 70)
    print("以下测试需要 Docker 和 ship 镜像")
    print("-" * 70)

    test_get_ship_not_found()

    ship_id = test_create_ship()
    if not ship_id:
        print("\n跳过需要 Ship 的测试（可能没有 ship 镜像）")
        return

    # 等待 ship 就绪
    print("\n等待 2 秒让 ship 完全就绪...")
    time.sleep(2)

    test_get_ship(ship_id)
    test_exec_shell(ship_id)
    test_exec_invalid_type(ship_id)
    test_extend_ttl(ship_id)
    test_get_logs(ship_id)
    test_upload_download(ship_id)
    test_delete_ship(ship_id)
    test_delete_ship_not_found(ship_id)

    print("\n" + "=" * 70)
    print("测试完成!")
    print("=" * 70)


if __name__ == "__main__":
    main()

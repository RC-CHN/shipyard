# 测试容器隔离改造方案

## 目标

将 `pkgs/bay/test_bay_api.py` 中的测试改造为：**每个需要容器的测试使用独立的容器**，测试结束后自动清理。

## 当前问题

当前代码在 `main()` 函数中创建一个共享的 Ship 容器，然后多个测试复用这个容器：
- `test_get_ship(ship_id)`
- `test_exec_shell(ship_id)`
- `test_exec_invalid_type(ship_id)`
- `test_extend_ttl(ship_id)`
- `test_get_logs(ship_id)`
- `test_upload_download(ship_id)`
- `test_delete_ship(ship_id)`

这导致测试之间存在隐式依赖，一个测试的副作用可能影响后续测试。

## 改造方案

### 1. 添加辅助基础设施

创建一个上下文管理器 `fresh_ship()` 用于自动创建和清理容器：

```python
from contextlib import contextmanager
from typing import Generator

@contextmanager
def fresh_ship(
    session_id: str | None = None,
    ttl: int = 60,
    cpus: float = 0.5,
    memory: str = "256m",
    disk: str | None = None,
) -> Generator[tuple[str, dict], None, None]:
    """
    创建独立的 Ship 容器用于单个测试，测试结束后自动清理。
    
    Yields:
        tuple[ship_id, headers]: Ship ID 和请求头
    """
    # 生成唯一的 session ID
    test_session_id = session_id or f"test-{uuid.uuid4().hex[:12]}"
    headers = {
        "Authorization": f"Bearer {ACCESS_TOKEN}",
        "X-SESSION-ID": test_session_id,
    }
    
    ship_id = None
    try:
        # 创建 Ship
        spec = {"cpus": cpus, "memory": memory}
        if disk:
            spec["disk"] = disk
        payload = {"ttl": ttl, "max_session_num": 1, "spec": spec}
        
        resp = requests.post(
            f"{BAY_URL}/ship",
            headers={**headers, "Content-Type": "application/json"},
            json=payload,
            timeout=120,
        )
        if resp.status_code != 201:
            raise RuntimeError(f"创建 Ship 失败: {resp.status_code} - {resp.text}")
        
        data = resp.json()
        ship_id = data.get("id")
        
        # 等待容器就绪
        time.sleep(2)
        
        yield ship_id, headers
        
    finally:
        # 清理容器
        if ship_id:
            try:
                requests.delete(
                    f"{BAY_URL}/ship/{ship_id}",
                    headers=headers,
                    timeout=30,
                )
            except Exception:
                pass  # 清理失败不影响测试结果
```

### 2. 测试分类与改造

#### 第一类：不需要容器的测试（无需修改）

| 测试函数 | 说明 |
|---------|------|
| `test_memory_utils()` | 本地单元测试 |
| `test_disk_utils()` | 本地单元测试 |
| `test_health()` | API 测试，无需容器 |
| `test_root()` | API 测试，无需容器 |
| `test_stat()` | API 测试，无需容器 |
| `test_auth_required()` | API 测试，无需容器 |
| `test_list_ships()` | API 测试，无需容器 |
| `test_create_ship_invalid_payload()` | API 测试，无需容器 |
| `test_get_ship_not_found()` | API 测试，无需容器 |

#### 第二类：已经使用独立容器的测试（无需修改）

| 测试函数 | 说明 |
|---------|------|
| `test_create_ship_with_small_memory()` | 已自包含 ✅ |
| `test_create_ship_with_disk()` | 已自包含 ✅ |
| `test_data_persistence()` | 已自包含 ✅ |

#### 第三类：需要改造为独立容器的测试

| 测试函数 | 改造方式 |
|---------|---------|
| `test_create_ship()` | 改为 `test_create_and_get_ship()` - 创建、验证、删除 |
| `test_get_ship()` | 合并到 `test_create_and_get_ship()` |
| `test_exec_shell()` | 改为自包含，使用 `fresh_ship()` |
| `test_exec_invalid_type()` | 改为自包含，使用 `fresh_ship()` |
| `test_extend_ttl()` | 改为自包含，使用 `fresh_ship()` |
| `test_get_logs()` | 改为自包含，使用 `fresh_ship()` |
| `test_upload_download()` | 改为自包含，使用 `fresh_ship()` |
| `test_delete_ship()` | 合并到每个测试的清理逻辑中 |
| `test_delete_ship_not_found()` | 改为独立测试，创建后删除两次 |

### 3. 改造后的测试函数示例

#### test_exec_shell 改造

```python
def test_exec_shell() -> bool:
    print_section("测试: 执行 Shell 命令")
    try:
        with fresh_ship() as (ship_id, headers):
            print(f"使用独立 Ship: {ship_id}")
            payload = {"type": "shell/exec", "payload": {"command": "echo Bay"}}
            resp = requests.post(
                f"{BAY_URL}/ship/{ship_id}/exec",
                headers={**headers, "Content-Type": "application/json"},
                json=payload,
                timeout=30,
            )
            return check_status(resp, 200, "Shell 命令执行成功", "Shell 命令执行失败")
    except Exception as exc:
        print(f"❌ 请求失败: {exc}")
        return False
```

#### test_delete_ship_not_found 改造

```python
def test_delete_ship_not_found() -> bool:
    print_section("测试: 删除不存在的 Ship")
    try:
        with fresh_ship() as (ship_id, headers):
            # 先删除一次
            resp = requests.delete(
                f"{BAY_URL}/ship/{ship_id}",
                headers=headers,
                timeout=30,
            )
            if resp.status_code != 204:
                print(f"❌ 第一次删除失败: {resp.status_code}")
                return False
            
            # 再删除一次，应该返回 404
            resp = requests.delete(
                f"{BAY_URL}/ship/{ship_id}",
                headers=headers,
                timeout=10,
            )
            return check_status(resp, 404, "重复删除返回 404", "重复删除未返回 404")
    except Exception as exc:
        print(f"❌ 请求失败: {exc}")
        return False
```

### 4. 改造后的 main() 函数

```python
def main() -> None:
    print("Bay API 功能测试（容器隔离版）")
    print("=" * 70)
    print(f"服务地址: {BAY_URL}")
    print()

    # ===== 第一阶段：本地单元测试 =====
    print("\n" + "=" * 70)
    print("阶段 1: 本地单元测试")
    print("=" * 70)
    
    if not test_memory_utils():
        print("\n内存单元测试失败，退出测试")
        sys.exit(1)
    if not test_disk_utils():
        print("\n磁盘单元测试失败，退出测试")
        sys.exit(1)

    # ===== 第二阶段：无容器 API 测试 =====
    print("\n" + "=" * 70)
    print("阶段 2: 无容器 API 测试")
    print("=" * 70)
    
    if not test_health():
        print("\n服务未运行，退出测试")
        sys.exit(1)
    test_root()
    test_stat()
    test_auth_required()
    test_list_ships()
    test_create_ship_invalid_payload()
    test_get_ship_not_found()

    # ===== 第三阶段：独立容器测试 =====
    print("\n" + "=" * 70)
    print("阶段 3: 独立容器测试（每个测试使用独立容器）")
    print("=" * 70)
    
    test_create_ship_with_small_memory()
    test_create_ship_with_disk()
    test_create_and_get_ship()
    test_exec_shell()
    test_exec_invalid_type()
    test_extend_ttl()
    test_get_logs()
    test_upload_download()
    test_delete_ship_not_found()

    # ===== 第四阶段：特殊生命周期测试 =====
    print("\n" + "=" * 70)
    print("阶段 4: 特殊生命周期测试")
    print("=" * 70)
    
    test_data_persistence()

    print("\n" + "=" * 70)
    print("测试完成!")
    print("=" * 70)
```

## 实施计划

- [ ] 添加 `fresh_ship()` 上下文管理器
- [ ] 创建 `test_create_and_get_ship()` 合并创建和获取测试
- [ ] 改造 `test_exec_shell()` 使用独立容器
- [ ] 改造 `test_exec_invalid_type()` 使用独立容器
- [ ] 改造 `test_extend_ttl()` 使用独立容器
- [ ] 改造 `test_get_logs()` 使用独立容器
- [ ] 改造 `test_upload_download()` 使用独立容器
- [ ] 改造 `test_delete_ship_not_found()` 使用独立容器
- [ ] 更新 `main()` 函数移除共享容器逻辑
- [ ] 删除不再需要的 `test_create_ship()`, `test_get_ship()`, `test_delete_ship()` 函数

## 优势

1. **完全隔离** - 每个测试使用独立容器，不会相互影响
2. **更健壮** - 单个测试失败不会导致后续测试全部失败
3. **可并行** - 理论上可以并行运行所有独立容器测试
4. **易于调试** - 每个测试的容器状态是确定的

## 潜在问题

1. **运行时间增加** - 每个测试都需要创建和销毁容器，总时间会增加
2. **资源消耗** - 同时运行多个测试时可能消耗更多资源

## 缓解措施

- 可以添加 `--share-container` 参数用于快速开发测试场景
- 容器创建可以使用较小的资源配置（0.5 CPU, 256m 内存）
- TTL 设置较短（60秒）以便快速回收

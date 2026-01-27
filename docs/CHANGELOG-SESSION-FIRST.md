# Shipyard Session-First 重构变更文档

## 概述

本次重构实现了三个核心功能：
1. **1:1 Session-Ship 绑定** - 简化架构，每个会话独占一个容器
2. **Execution History** - 记录执行历史，支持 Agent 技能库构建
3. **MCP Server 集成** - 提供 stdio 传输的 MCP 服务器

## 变更目的

### 1. 1:1 Session-Ship 绑定

**问题背景：**
- 原设计支持多个会话共享一个 Ship（容器），通过 `max_session_num` 控制
- 多会话共享增加了状态管理复杂度和潜在的隔离问题
- Agent 场景下，每个任务需要独立的环境

**解决方案：**
- 移除多会话共享逻辑，每个 Session 绑定一个专属 Ship
- 引入 Warm Pool（预热池）弥补冷启动延迟

### 2. Execution History（执行历史）

**问题背景：**
- 受 VOYAGER 论文启发，Agent 需要记录成功的执行路径来构建技能库
- 技能自我进化需要：代码/命令 + 成功状态 + 执行时间

**解决方案：**
- Bay 侧存储执行历史（对 Ship 透明）
- 记录 Python 和 Shell 执行的完整信息
- 提供查询 API 支持技能库构建

### 3. MCP Server 集成

**问题背景：**
- Claude Desktop、Cursor 等工具支持 MCP 协议
- 需要提供标准化的集成方式

**解决方案：**
- 实现基于 stdio 传输的 MCP 服务器
- 提供 Python 执行、Shell 执行、文件操作等工具

---

## 详细变更

### Bay 服务端

#### 模型变更 (`pkgs/bay/app/models.py`)

**移除字段：**
```python
# Ship 模型
- max_session_num: int = Field(default=1)
- current_session_num: int = Field(default=0)
```

**新增模型：**
```python
class ExecutionHistory(SQLModel, table=True):
    """执行历史记录，用于 Agent 技能库构建"""
    id: str                    # 主键
    session_id: str            # 关联的会话 ID
    ship_id: str               # 执行的 Ship ID
    exec_type: str             # 'python' 或 'shell'
    code: str                  # 执行的代码/命令
    success: bool              # 是否成功
    execution_time_ms: int     # 执行耗时（毫秒）
    output: Optional[str]      # 输出（可选存储）
    error: Optional[str]       # 错误信息
    created_at: datetime       # 创建时间

class ExecutionHistoryEntry(BaseModel):
    """API 响应模型"""
    id: str
    exec_type: str
    code: str
    success: bool
    execution_time_ms: int
    created_at: datetime

class ExecutionHistoryResponse(BaseModel):
    """执行历史查询响应"""
    entries: List[ExecutionHistoryEntry]
    total: int
```

#### 数据库服务 (`pkgs/bay/app/database.py`)

**移除方法：**
- `find_available_ship()` - 查找可用 Ship（多会话共享逻辑）
- `increment_ship_session_count()` - 增加会话计数
- `decrement_ship_session_count()` - 减少会话计数

**新增方法：**
```python
async def find_ship_for_session(session_id: str) -> Optional[Ship]
    """查找会话已绑定的 Ship（1:1 绑定）"""

async def find_warm_pool_ship() -> Optional[Ship]
    """从预热池获取可用 Ship"""

async def count_warm_pool_ships() -> int
    """统计预热池中的 Ship 数量"""

async def create_execution_history(
    session_id: str,
    ship_id: str,
    exec_type: str,
    code: str,
    success: bool,
    execution_time_ms: int,
    output: Optional[str] = None,
    error: Optional[str] = None,
) -> ExecutionHistory
    """创建执行历史记录"""

async def get_execution_history(
    session_id: str,
    exec_type: Optional[str] = None,
    success_only: bool = False,
    limit: int = 100,
    offset: int = 0,
) -> Tuple[List[ExecutionHistory], int]
    """查询执行历史"""
```

#### Ship 服务 (`pkgs/bay/app/services/ship/service.py`)

**简化逻辑：**
- `create_ship()` - 移除多会话分配逻辑，实现 1:1 绑定
- 优先复用会话已绑定的 Ship
- 其次从 Warm Pool 分配
- 最后创建新容器

**新增 Warm Pool 功能：**
```python
async def start_warm_pool()
    """启动预热池后台任务"""

async def stop_warm_pool()
    """停止预热池"""

async def _replenish_warm_pool()
    """补充预热池到目标数量"""

async def _create_warm_pool_ship() -> Ship
    """创建预热池 Ship"""

async def _assign_ship_to_session(ship: Ship, session_id: str, ttl: int)
    """将 Ship 分配给会话"""
```

**执行历史记录：**
- `execute_operation()` 中添加执行历史记录逻辑

#### 配置 (`pkgs/bay/app/config.py`)

**新增配置项：**
```python
warm_pool_enabled: bool = True           # 是否启用预热池
warm_pool_min_size: int = 2              # 最小预热数量
warm_pool_max_size: int = 10             # 最大预热数量
warm_pool_replenish_interval: int = 30   # 补充检查间隔（秒）
```

#### 路由 (`pkgs/bay/app/routes/sessions.py`)

**新增端点：**
```python
@router.get("/sessions/{session_id}/history")
async def get_execution_history(
    session_id: str,
    exec_type: Optional[str] = None,
    success_only: bool = False,
    limit: int = 100,
    offset: int = 0,
) -> ExecutionHistoryResponse
    """获取会话执行历史"""
```

---

### Ship 容器端

#### IPython 组件 (`pkgs/ship/app/components/ipython.py`)

**ExecuteCodeResponse 新增字段：**
```python
code: str              # 执行的代码
execution_time_ms: int # 执行耗时（毫秒）
```

#### Shell 组件 (`pkgs/ship/app/components/shell.py`)

**ExecuteShellResponse 新增字段：**
```python
command: str           # 执行的命令
execution_time_ms: int # 执行耗时（毫秒）
```

#### 用户管理器 (`pkgs/ship/app/components/user_manager.py`)

**ProcessResult 新增字段：**
```python
command: str           # 执行的命令
execution_time_ms: int # 执行耗时（毫秒）
```

---

### Python SDK

#### Client (`shipyard_python_sdk/shipyard/client.py`)

**变更方法：**
```python
async def create_ship(
    ttl: int,
    spec: Optional[Spec] = None,
    max_session_num: int | None = None,  # 已弃用，添加警告
    session_id: Optional[str] = None,
    force_create: bool = False,
) -> SessionShip
```

**新增方法：**
```python
async def get_or_create_session(
    session_id: str,
    ttl: int = 3600,
    spec: Optional[Spec] = None,
) -> SessionShip
    """推荐的 Session-First API"""

def session(
    session_id: str,
    ttl: int = 3600,
    spec: Optional[Spec] = None,
) -> SessionContext
    """上下文管理器方式使用会话"""

async def get_execution_history(
    session_id: str,
    exec_type: Optional[str] = None,
    success_only: bool = False,
    limit: int = 100,
    offset: int = 0,
) -> Dict[str, Any]
    """获取执行历史"""
```

**新增类：**
```python
class SessionContext:
    """会话上下文管理器"""
    async def __aenter__(self) -> SessionShip
    async def __aexit__(self, ...)
```

#### Session (`shipyard_python_sdk/shipyard/session.py`)

**新增方法：**
```python
async def get_execution_history(
    exec_type: Optional[str] = None,
    success_only: bool = False,
    limit: int = 100,
    offset: int = 0,
) -> Dict[str, Any]
    """获取当前会话的执行历史"""

@property
def session_id(self) -> str
    """获取会话 ID"""
```

#### Types (`shipyard_python_sdk/shipyard/types.py`)

**移除属性：**
- `max_session_num`
- `current_session_num`

**新增属性：**
- `expires_at`

#### Utils (`shipyard_python_sdk/shipyard/utils.py`)

**更新函数签名：**
```python
async def create_session_ship(
    ttl: int = 3600,
    spec: Optional[Spec] = None,
    max_session_num: int | None = None,  # 已弃用
    endpoint_url: Optional[str] = None,
    access_token: Optional[str] = None,
    session_id: Optional[str] = None,
    force_create: bool = False,
) -> SessionShip
```

---

### MCP Server（新增）

#### 文件结构
```
pkgs/bay/app/mcp/
├── __init__.py
├── server.py      # MCP 服务器实现
└── run.py         # 入口点
```

#### 提供的工具
```python
@mcp.tool()
async def execute_python(code: str, session_id: Optional[str] = None) -> str
    """执行 Python 代码"""

@mcp.tool()
async def execute_shell(command: str, session_id: Optional[str] = None) -> str
    """执行 Shell 命令"""

@mcp.tool()
async def upload_file(local_path: str, remote_path: str, ...) -> str
    """上传文件到容器"""

@mcp.tool()
async def download_file(remote_path: str, local_path: str, ...) -> str
    """从容器下载文件"""

@mcp.tool()
async def list_sessions() -> str
    """列出所有会话"""

@mcp.tool()
async def get_execution_history(session_id: str, ...) -> str
    """获取执行历史"""
```

#### 使用方式
```bash
# 环境变量
export SHIPYARD_ENDPOINT=http://localhost:8156
export SHIPYARD_TOKEN=secret-token

# 运行
python -m app.mcp.run
```

---

### Dashboard 前端

#### 类型定义 (`types/api.ts`)

**移除字段：**
- `max_session_num`
- `current_session_num`

#### 创建 Ship 表单 (`views/ship-create/useCreateShip.ts`)

- 移除 `maxSessionNum` 表单字段

#### Ship 详情页 (`views/ship-detail/index.vue`)

- 移除会话计数显示

#### Ship 列表页 (`views/ships/index.vue`)

- 移除会话数量列

---

### 单元测试

#### `pkgs/bay/tests/unit/test_ships.py`

**移除测试：**
- `test_create_ship_with_max_session_num`
- `test_find_available_ship`
- `test_session_count_increment_decrement`

**新增测试：**
- `test_execution_history_creation`
- `test_execution_history_query`
- `test_warm_pool_ship_allocation`

---

## SDK 使用示例

### 旧方式（已弃用）
```python
# 不推荐
ship = await client.create_ship(ttl=3600)
result = await ship.python.exec("print('hello')")
```

### 新方式（推荐）

**方式一：get_or_create_session**
```python
session = await client.get_or_create_session(
    session_id="my-task-123",
    ttl=3600
)
result = await session.python.exec("print('hello')")

# 获取执行历史（用于技能库）
history = await session.get_execution_history(success_only=True)
```

**方式二：上下文管理器**
```python
async with client.session("my-task-123") as session:
    result = await session.python.exec("print('hello')")
    # 会话结束后资源由 TTL 管理
```

**方式三：便捷函数**
```python
from shipyard import create_session_ship

session = await create_session_ship(
    session_id="my-task-123",
    ttl=3600
)
```

---

## 技能库构建示例

基于 VOYAGER 论文思想，使用执行历史构建技能库：

```python
# 获取成功的 Python 执行记录
history = await session.get_execution_history(
    exec_type="python",
    success_only=True
)

# 筛选高效代码（执行时间短）
efficient_skills = [
    entry for entry in history["entries"]
    if entry["execution_time_ms"] < 1000
]

# 存入技能库
for skill in efficient_skills:
    skill_library.add(
        code=skill["code"],
        execution_time_ms=skill["execution_time_ms"],
        created_at=skill["created_at"]
    )
```

---

## 迁移指南

### 1. 移除 max_session_num

如果代码中使用了 `max_session_num` 参数：
```python
# 旧代码（会产生弃用警告）
ship = await client.create_ship(ttl=3600, max_session_num=3)

# 新代码
session = await client.get_or_create_session(
    session_id="my-session",
    ttl=3600
)
```

### 2. 使用 Session-First API

```python
# 旧模式：Ship 优先
ship = await client.create_ship(ttl=3600)

# 新模式：Session 优先
session = await client.get_or_create_session("my-session", ttl=3600)
```

### 3. 利用执行历史

```python
# 记录自动进行，无需额外代码
result = await session.python.exec(code)

# 查询历史
history = await session.get_execution_history()
```

---

## 参考文献

1. **VOYAGER** (2023) - "VOYAGER: An Open-Ended Embodied Agent with Large Language Models"
   - 技能库自动构建
   - 代码 + 成功状态 + 执行时间的记录模式

2. **Reflexion** (2023) - "Reflexion: Language Agents with Verbal Reinforcement Learning"
   - 执行反馈用于 Agent 自我改进

3. **LearnAct** (2024) - "LearnAct: Few-Shot Mobile App Testing"
   - 从执行历史中学习可复用技能

# 连接管理

## 概述

`ClickHouseBackend`（同步）和 `AsyncClickHouseBackend`（异步）都维护**单个持久连接**，每个后端实例对应一条底层数据库连接。`ClickHouseConnectionConfig` 通过继承 `ConnectionPoolMixin` 获得的 `pool_*` 配置字段已可正常解析并存储到配置对象中，但**两个后端目前均不会将这些参数传递给底层驱动**——它们作为前向兼容的占位字段保留，计划在未来的连接池实现中启用。

> 💡 **AI 提示词：** "我的 FastAPI 应用使用 `AsyncClickHouseBackend`，如何正确管理数据库连接的生命周期以避免连接泄漏或僵尸连接？"

---

## 当前行为

### 同步后端（`ClickHouseBackend`）

`ClickHouseBackend.connect()` 调用 `clickhouse.connector.connect()`，传入认证信息和超时参数。`pool_name`、`pool_size` 等字段会被静默跳过。

```python
from rhosocial.activerecord.backend.impl.clickhouse import ClickHouseBackend, ClickHouseConnectionConfig

config = ClickHouseConnectionConfig(
    host="localhost",
    port=3306,
    database="myapp",
    username="app",
    password="secret",
    pool_size=10,      # ← 配置类接受，后端忽略
)
backend = ClickHouseBackend(config)
backend.connect()     # 建立一条持久连接
```

### 异步后端（`AsyncClickHouseBackend`）

`AsyncClickHouseBackend.connect()` 调用 `clickhouse.connector.aio.connect()`，同样跳过 `pool_*` 参数，将一个 `ClickHouseConnection` 对象存储在 `self._connection` 中。

```python
import asyncio
from rhosocial.activerecord.backend.impl.clickhouse import (
    AsyncClickHouseBackend, ClickHouseConnectionConfig,
)

config = ClickHouseConnectionConfig(
    host="localhost",
    port=3306,
    database="myapp",
    username="app",
    password="secret",
)

async def main():
    backend = AsyncClickHouseBackend(config)
    await backend.connect()     # 建立一条持久异步连接
    # ... 使用 backend ...
    await backend.disconnect()

asyncio.run(main())
```

---

## 连接生命周期最佳实践

### 每个进程配置一次

在应用启动时统一配置模型（不要在请求处理函数中调用 `configure()`）。每次调用 `Model.configure(config, backend_class)` 都会创建一个新的后端实例及一条新的底层连接。

```python
# 应用启动（以 FastAPI lifespan 为例）
from contextlib import asynccontextmanager
from fastapi import FastAPI
from rhosocial.activerecord.backend.impl.clickhouse import (
    AsyncClickHouseBackend, ClickHouseConnectionConfig,
)
from myapp.models import User, Order

_config = ClickHouseConnectionConfig(
    host="db.prod.internal",
    port=3306,
    database="myapp",
    username="app",
    password="secret",
)

@asynccontextmanager
async def lifespan(app: FastAPI):
    # 启动：配置一次，连接一次
    User.configure(_config, AsyncClickHouseBackend)
    Order.configure(_config, AsyncClickHouseBackend)
    await User.backend().connect()
    await Order.backend().connect()
    yield
    # 关闭：干净断开
    await User.backend().disconnect()
    await Order.backend().disconnect()

app = FastAPI(lifespan=lifespan)
```

### 不要在请求处理函数中调用 configure()

```python
# ❌ 反模式——每次请求都创建新连接
@app.get("/users/{user_id}")
async def get_user(user_id: int):
    User.configure(_config, AsyncClickHouseBackend)   # ← 错误
    await User.backend().connect()
    user = await User.find(user_id)
    await User.backend().disconnect()
    return user

# ✅ 正确——lifespan 已在启动时建立连接
@app.get("/users/{user_id}")
async def get_user(user_id: int):
    return await User.find(user_id)
```

---

## `clickhouse.connector.aio` 的连接池能力

`clickhouse.connector.aio.connect()` 在底层**支持**通过 `pool_name` 和 `pool_size` 参数创建连接池，返回 `PooledClickHouseConnection`，调用 `close()` 时会将连接归还到池而非真正断开。然而，`AsyncClickHouseBackend` 目前**不向驱动传递这些参数**。

**驱动层面的能力（仅供参考）：**

```python
import clickhouse.connector.aio as clickhouse_async

# 驱动支持这样创建连接池（AsyncClickHouseBackend 暂未使用）：
conn = await clickhouse_async.connect(
    host="localhost",
    user="app",
    password="secret",
    database="myapp",
    pool_name="mypool",   # 启用驱动内置连接池
    pool_size=10,
)
# conn 是 PooledClickHouseConnection；调用 conn.close() 会归还到池，而非断开
```

未来版本的 `AsyncClickHouseBackend` 可能会利用此能力。在此之前，`pool_*` 配置字段作为前向兼容的占位符保留。

---

## 连接超时配置

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `connect_timeout` | `int` | `10` | 连接尝试超时时间（秒） |
| `read_timeout` | `int` | `30` | 读操作超时时间（秒） |
| `write_timeout` | `int` | `30` | 写操作超时时间（秒） |

```python
config = ClickHouseConnectionConfig(
    host="localhost",
    port=3306,
    database="myapp",
    username="app",
    password="secret",
    connect_timeout=5,
    read_timeout=20,
    write_timeout=20,
)
```

---

## 预留的连接池配置字段

以下字段由 `ClickHouseConnectionConfig`（通过 `ConnectionPoolMixin`）解析，但**当前不会传递给底层驱动**：

| 字段 | 类型 | 默认值 | 预留用途 |
|------|------|--------|---------|
| `pool_size` | `int` | `5` | 连接池中的连接数 |
| `pool_timeout` | `int` | `30` | 等待空闲连接的超时时间（秒） |
| `pool_name` | `str or None` | `None` | 连接池名称标识符 |
| `pool_reset_session` | `bool` | `True` | 归还时重置会话状态 |
| `pool_pre_ping` | `bool` | `False` | 使用前检测连接健康性 |

---

## 另请参阅

- [连接配置](configuration.md) — `ClickHouseConnectionConfig` 完整选项列表
- [故障排查：连接问题](../troubleshooting/connection.md) — 诊断连接错误
- [异步连接池模式验证脚本](../../../examples/chapter_02_connection_pool/async_connection_pool.py) — 可运行的演示脚本

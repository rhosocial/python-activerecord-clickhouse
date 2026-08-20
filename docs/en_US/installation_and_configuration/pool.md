# Connection Management

## Overview

Both `ClickHouseBackend` (synchronous) and `AsyncClickHouseBackend` (asynchronous) maintain a **single persistent connection** per backend instance. The `pool_*` configuration fields inherited from `ConnectionPoolMixin` are recognised by the config class but are **not yet consumed** by either backend—they are reserved for a future connection-pool implementation.

> 💡 **AI Prompt:** "My FastAPI application uses `AsyncClickHouseBackend`. How should I manage the database connection lifecycle to avoid connection leaks or stale connections?"

---

## Current Behaviour

### Synchronous Backend (`ClickHouseBackend`)

`ClickHouseBackend.connect()` calls `clickhouse.connector.connect()` with credentials and timeout parameters. The `pool_name`, `pool_size`, and related fields are silently skipped.

```python
from rhosocial.activerecord.backend.impl.clickhouse import ClickHouseBackend, ClickHouseConnectionConfig

config = ClickHouseConnectionConfig(
    host="localhost",
    port=3306,
    database="myapp",
    username="app",
    password="secret",
    pool_size=10,      # ← accepted by config, ignored by backend
)
backend = ClickHouseBackend(config)
backend.connect()     # opens one persistent connection
```

### Asynchronous Backend (`AsyncClickHouseBackend`)

`AsyncClickHouseBackend.connect()` calls `clickhouse.connector.aio.connect()` with the same subset of parameters. Pool-related kwargs are also skipped, so a single `ClickHouseConnection` object is stored in `self._connection`.

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
    await backend.connect()     # opens one persistent async connection
    # ... use the backend ...
    await backend.disconnect()

asyncio.run(main())
```

---

## Connection Lifecycle Guidelines

### One Backend Per Process

Configure your models once at application startup (not inside request handlers). Each call to `Model.configure(config, backend_class)` creates a new backend instance and a new underlying connection.

```python
# application startup (e.g., FastAPI lifespan)
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
    # Startup: configure once, connect once
    User.configure(_config, AsyncClickHouseBackend)
    Order.configure(_config, AsyncClickHouseBackend)
    await User.backend().connect()
    await Order.backend().connect()
    yield
    # Shutdown: disconnect cleanly
    await User.backend().disconnect()
    await Order.backend().disconnect()

app = FastAPI(lifespan=lifespan)
```

### Do NOT Configure Inside Request Handlers

```python
# ❌ Anti-pattern — creates a new connection on every request
@app.get("/users/{user_id}")
async def get_user(user_id: int):
    User.configure(_config, AsyncClickHouseBackend)   # ← wrong
    await User.backend().connect()
    user = await User.find(user_id)
    await User.backend().disconnect()
    return user

# ✅ Correct — connection already open from lifespan
@app.get("/users/{user_id}")
async def get_user(user_id: int):
    return await User.find(user_id)
```

---

## Async Pool Capability in `clickhouse.connector.aio`

`clickhouse.connector.aio.connect()` does support creating a connection pool internally when `pool_name` and `pool_size` kwargs are supplied — it returns a `PooledClickHouseConnection` that is checked out from and returned to the pool automatically. However, `AsyncClickHouseBackend` does **not** pass these kwargs today.

**What the driver supports (for reference):**

```python
import clickhouse.connector.aio as clickhouse_async

# The driver CAN create a pool like this (not used by AsyncClickHouseBackend yet):
conn = await clickhouse_async.connect(
    host="localhost",
    user="app",
    password="secret",
    database="myapp",
    pool_name="mypool",   # enables pooling in the driver
    pool_size=10,
)
# conn is a PooledClickHouseConnection; calling conn.close() returns it to the pool
```

Future versions of `AsyncClickHouseBackend` may leverage this capability.  Until then, the `pool_*` configuration fields serve as forward-compatible placeholders.

---

## Connection Timeout Configuration

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `connect_timeout` | `int` | `10` | Seconds before a connection attempt is abandoned |
| `read_timeout` | `int` | `30` | Seconds before a read operation times out |
| `write_timeout` | `int` | `30` | Seconds before a write operation times out |

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

## Reserved Pool Configuration Fields

These fields are parsed by `ClickHouseConnectionConfig` (via `ConnectionPoolMixin`) and stored on the config object, but are currently **not forwarded** to the underlying driver:

| Field | Type | Default | Reserved Purpose |
|-------|------|---------|-----------------|
| `pool_size` | `int` | `5` | Number of connections in the pool |
| `pool_timeout` | `int` | `30` | Seconds to wait for a free connection |
| `pool_name` | `str or None` | `None` | Named pool identifier |
| `pool_reset_session` | `bool` | `True` | Reset session state on checkout |
| `pool_pre_ping` | `bool` | `False` | Test connection health before use |

---

## See Also

- [Connection Configuration](configuration.md) — full list of `ClickHouseConnectionConfig` options
- [Troubleshooting: Connection Issues](../troubleshooting/connection.md) — diagnosing connection errors
- [Async Connection Pool Patterns](../../../examples/chapter_02_connection_pool/async_connection_pool.py) — runnable demonstration script

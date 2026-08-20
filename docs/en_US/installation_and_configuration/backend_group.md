# BackendGroup and BackendManager (ClickHouse)

This document describes how to use `BackendGroup` and `BackendManager` with the ClickHouse backend. For detailed API documentation, refer to the [core library documentation](../../../rhosocial-activerecord/docs/en_US/connection/connection_management.md).

## Quick Example

```python
from rhosocial.activerecord.connection import BackendGroup
from rhosocial.activerecord.backend.impl.clickhouse import ClickHouseBackend, ClickHouseConnectionConfig
from rhosocial.activerecord.model import ActiveRecord


class User(ActiveRecord):
    name: str
    email: str


# Using context manager
with BackendGroup(
    name="main",
    models=[User],
    config=ClickHouseConnectionConfig(
        host="localhost",
        port=3306,
        database="myapp",
        username="app",
        password="secret",
    ),
    backend_class=ClickHouseBackend,
) as group:
    user = User(name="John", email="john@example.com")
    user.save()

# Using with multiple groups via BackendManager
from rhosocial.activerecord.connection import BackendManager

manager = BackendManager()
manager.create_group(
    name="main",
    models=[User],
    config=ClickHouseConnectionConfig(host="localhost", database="main_db"),
    backend_class=ClickHouseBackend,
)
manager.create_group(
    name="stats",
    config=ClickHouseConnectionConfig(host="localhost", database="stats_db"),
    backend_class=ClickHouseBackend,
)

main_backend = manager.get_group("main").get_backend()
stats_backend = manager.get_group("stats").get_backend()
```

## ClickHouse-Specific Features

### Connection Pool Configuration

ClickHouse backend recognizes pool-related config fields (reserved for future implementation):

```python
config = ClickHouseConnectionConfig(
    host="localhost",
    port=3306,
    database="myapp",
    username="app",
    password="secret",
    pool_size=10,          # Reserved for future connection pool
    pool_name="my_pool",   # Reserved for future connection pool
    pool_reset_session=True,
)
```

### SSL/TLS Configuration

```python
config = ClickHouseConnectionConfig(
    host="localhost",
    port=3306,
    database="myapp",
    username="app",
    password="secret",
    ssl_verify_cert=True,
    ssl_ca="/path/to/ca.pem",
)
```

## Example Code

Full example: [chapter_02_connection_pool/async_connection_pool.py](../examples/chapter_02_connection_pool/async_connection_pool.py)

This example demonstrates using backend connection management in a multi-worker FastAPI application.
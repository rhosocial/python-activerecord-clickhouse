# BackendGroup and BackendManager (ClickHouse)

本文档介绍如何在 ClickHouse 后端使用 `BackendGroup` 和 `BackendManager`。详细 API 文档请参考[核心库文档](../../../rhosocial-activerecord/docs/zh_CN/connection/connection_management.md)。

## 快速示例

```python
from rhosocial.activerecord.connection import BackendGroup
from rhosocial.activerecord.backend.impl.clickhouse import ClickHouseBackend, ClickHouseConnectionConfig
from rhosocial.activerecord.model import ActiveRecord


class User(ActiveRecord):
    name: str
    email: str


# 使用上下文管理器
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

# 使用 BackendManager 管理多个数据库
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

## ClickHouse 特有功能

### 连接池配置

ClickHouse 后端识别连接池相关配置字段（为未来连接池实现预留）：

```python
config = ClickHouseConnectionConfig(
    host="localhost",
    port=3306,
    database="myapp",
    username="app",
    password="secret",
    pool_size=10,          # 预留字段
    pool_name="my_pool",   # 预留字段
    pool_reset_session=True,
)
```

### SSL/TLS 配置

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
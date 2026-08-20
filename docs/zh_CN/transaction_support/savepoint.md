# Savepoint 支持

## 概述

Savepoint 允许在事务中创建中间保存点，实现部分回滚。

## 使用 Savepoint

```python
from rhosocial.activerecord.backend.impl.clickhouse import ClickHouseBackend, ClickHouseConnectionConfig


config = ClickHouseConnectionConfig(
    host='localhost',
    database='myapp',
    username='user',
    password='password',
)

backend = ClickHouseBackend(connection_config=config)
backend.connect()

try:
    with backend.get_connection().cursor() as cursor:
        cursor.execute("START TRANSACTION")
        
        # 操作 1
        cursor.execute("INSERT INTO users (name) VALUES ('Alice')")
        
        # 创建保存点
        cursor.execute("SAVEPOINT sp1")
        
        try:
            # 操作 2 (可能会失败)
            cursor.execute("INSERT INTO users (name) VALUES ('Bob')")
            cursor.execute("COMMIT")
        except Exception:
            # 回滚到保存点
            cursor.execute("ROLLBACK TO SAVEPOINT sp1")
            cursor.execute("COMMIT")
            
finally:
    backend.disconnect()
```

## 命名 Savepoint

```python
cursor.execute("SAVEPOINT savepoint_name")
cursor.execute("ROLLBACK TO SAVEPOINT savepoint_name")
```

💡 *AI 提示词：* "什么是数据库 savepoint？它与完全回滚有什么区别？"

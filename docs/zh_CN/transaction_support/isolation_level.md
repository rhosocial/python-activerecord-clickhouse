# 事务隔离级别

## 概述

ClickHouse 支持多种事务隔离级别，不同的隔离级别决定了并发事务之间的可见性。

## 隔离级别说明

| 隔离级别 | 脏读 | 不可重复读 | 幻读 |
|---------|------|-----------|------|
| READ UNCOMMITTED | 可能 | 可能 | 可能 |
| READ COMMITTED | 不可能 | 可能 | 可能 |
| REPEATABLE READ (默认) | 不可能 | 不可能 | 可能 |
| SERIALIZABLE | 不可能 | 不可能 | 不可能 |

## 设置隔离级别

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

# 设置隔离级别
with backend.get_connection().cursor() as cursor:
    cursor.execute("SET TRANSACTION ISOLATION LEVEL READ COMMITTED")
    cursor.execute("START TRANSACTION")
    # 执行事务操作
    cursor.execute("COMMIT")

backend.disconnect()
```

## 各隔离级别详解

### READ COMMITTED

每次读取数据时都读取提交后的数据：

```sql
SET TRANSACTION ISOLATION LEVEL READ COMMITTED;
```

适用于大多数应用场景，平衡了并发性和数据一致性。

### REPEATABLE READ (默认)

在同一事务中多次读取相同数据，结果一致：

```sql
SET TRANSACTION ISOLATION LEVEL REPEATABLE READ;
```

ClickHouse 默认的隔离级别，使用 MVCC 机制实现。

### SERIALIZABLE

最高隔离级别，强制事务顺序执行：

```sql
SET TRANSACTION ISOLATION LEVEL SERIALIZABLE;
```

适用于对数据一致性要求极高的场景，但并发性能较差。

💡 *AI 提示词：* "什么是脏读、不可重复读和幻读？"

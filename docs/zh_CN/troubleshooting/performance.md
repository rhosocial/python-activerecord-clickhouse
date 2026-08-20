# 性能问题

## 概述

本节介绍 ClickHouse 性能问题及优化方法。

## 慢查询分析

### 启用慢查询日志

```sql
-- 查看慢查询配置
SHOW VARIABLES LIKE 'slow_query_log%';

-- 启用慢查询日志
SET GLOBAL slow_query_log = 'ON';
SET GLOBAL long_query_time = 1;
```

### 使用 EXPLAIN 分析查询

```python
backend = ClickHouseBackend(
    host='localhost',
    database='myapp',
    username='user',
    password='password',
)
backend.connect()

with backend.get_connection().cursor() as cursor:
    cursor.execute("EXPLAIN SELECT * FROM users WHERE name = 'Tom'")
    for row in cursor:
        print(row)

backend.disconnect()
```

## 常见性能问题

### 1. 缺少索引

```sql
-- 添加索引
CREATE INDEX idx_name ON users(name);
```

### 2. SELECT *

```python
# 避免 SELECT *，只查询需要的列
users = User.query().select(User.c.id, User.c.name).all()
```

### 3. N+1 查询问题

```python
# 使用预加载避免 N+1
users = User.query().eager_load('posts').all()
```

## 连接超时

```python
config = ClickHouseConnectionConfig(
    connect_timeout=30,
    read_timeout=60,
    write_timeout=60,
)
```

💡 *AI 提示词：* "如何优化 ClickHouse 查询性能？"

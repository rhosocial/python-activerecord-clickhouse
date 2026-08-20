# Performance Issues

## Overview

This section covers ClickHouse performance issues and optimization methods.

## Slow Query Analysis

### Enabling Slow Query Log

```sql
-- View slow query configuration
SHOW VARIABLES LIKE 'slow_query_log%';

-- Enable slow query log
SET GLOBAL slow_query_log = 'ON';
SET GLOBAL long_query_time = 1;
```

### Using EXPLAIN to Analyze Queries

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

## Common Performance Issues

### 1. Missing Index

```sql
-- Add index
CREATE INDEX idx_name ON users(name);
```

### 2. SELECT *

```python
# Avoid SELECT *, only query required columns
users = User.query().select(User.c.id, User.c.name).all()
```

### 3. N+1 Query Problem

```python
# Use eager loading to avoid N+1
users = User.query().eager_load('posts').all()
```

## Connection Timeouts

```python
config = ClickHouseConnectionConfig(
    connect_timeout=30,
    read_timeout=60,
    write_timeout=60,
)
```

💡 *AI Prompt:* "How to optimize ClickHouse query performance?"

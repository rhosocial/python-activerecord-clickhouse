# 索引与性能优化

## 概述

正确的索引设计是 ClickHouse 性能优化的关键。

## 索引类型

### 主键索引

```sql
-- 自动创建主键索引
CREATE TABLE users (
    id INT PRIMARY KEY
);
```

### 唯一索引

```sql
CREATE UNIQUE INDEX idx_email ON users(email);
```

### 普通索引

```sql
CREATE INDEX idx_name ON users(name);
```

### 复合索引

```sql
CREATE INDEX idx_name_status ON users(name, status);
```

## 最佳实践

### 1. 为 WHERE 条件创建索引

```python
# 经常用于查询的字段应建立索引
User.query().where(User.c.email == 'test@example.com')
# 应该在 email 字段上建立索引
```

### 2. 遵循最左前缀原则

```sql
-- 复合索引 (a, b, c) 支持:
-- WHERE a = 1
-- WHERE a = 1 AND b = 2
-- WHERE a = 1 AND b = 2 AND c = 3
-- 不支持: WHERE b = 2
```

### 3. 控制索引数量

索引并非越多越好，每个索引都会增加写操作的开销。

### 4. 使用 EXPLAIN 分析

```sql
EXPLAIN SELECT * FROM users WHERE email = 'test@example.com';
```

💡 *AI 提示词：* "如何设计高效的数据库索引？"

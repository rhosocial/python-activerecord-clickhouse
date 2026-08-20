# Indexing and Performance Optimization

## Overview

Proper index design is key to ClickHouse performance optimization.

## Index Types

### Primary Key Index

```sql
-- Automatically created primary key index
CREATE TABLE users (
    id INT PRIMARY KEY
);
```

### Unique Index

```sql
CREATE UNIQUE INDEX idx_email ON users(email);
```

### Regular Index

```sql
CREATE INDEX idx_name ON users(name);
```

### Composite Index

```sql
CREATE INDEX idx_name_status ON users(name, status);
```

## Best Practices

### 1. Create Indexes for WHERE Conditions

```python
# Fields frequently used in queries should have indexes
User.query().where(User.c.email == 'test@example.com')
# Should have an index on the email field
```

### 2. Follow the Leftmost Prefix Principle

```sql
-- Composite index (a, b, c) supports:
-- WHERE a = 1
-- WHERE a = 1 AND b = 2
-- WHERE a = 1 AND b = 2 AND c = 3
-- Does not support: WHERE b = 2
```

### 3. Control the Number of Indexes

More indexes are not always better. Each index increases overhead for write operations.

### 4. Use EXPLAIN for Analysis

```sql
EXPLAIN SELECT * FROM users WHERE email = 'test@example.com';
```

💡 *AI Prompt:* "How to design efficient database indexes?"

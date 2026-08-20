# Character Set and Collation

## Overview

ClickHouse supports multiple character sets and collations. Correctly configuring character sets is essential for handling multilingual text, emojis, and ensuring sorting behavior meets expectations.

## Common Character Sets

| Character Set | Description | Emoji Support |
|--------------|-------------|---------------|
| utf8 | UTF-8 encoding, up to 3 bytes | ❌ Not supported |
| utf8mb4 | UTF-8 encoding, up to 4 bytes | ✅ Supported |
| latin1 | Western European character set | ❌ Not supported |
| ascii | ASCII character set | ❌ Not supported |

⚠️ **Important**: ClickHouse's `utf8` character set only supports up to 3-byte UTF-8 characters and cannot store emojis (which are 4-byte characters). Use `utf8mb4` if you need emoji support.

## Common Collations

### utf8mb4 Collations

| Collation | Description | Performance |
|-----------|-------------|-------------|
| utf8mb4_general_ci | Fast sorting, but not precise | Fastest |
| utf8mb4_unicode_ci | Unicode standard-based sorting | Medium |
| utf8mb4_0900_ai_ci | ClickHouse 8.0+, more precise Unicode sorting | Fast |
| utf8mb4_zh_0900_as_cs | Chinese pinyin sorting, case-sensitive | Medium |

💡 **Recommendation**: For Chinese applications, use `utf8mb4_zh_0900_as_cs` or `utf8mb4_unicode_ci`.

## Configuration Methods

### 1. Connection-Level Configuration

Specify character set and collation when creating the backend:

```python
from rhosocial.activerecord.backend.impl.clickhouse import ClickHouseBackend

backend = ClickHouseBackend(
    host='localhost',
    port=3306,
    database='myapp',
    username='user',
    password='password',
    charset='utf8mb4',
    collation='utf8mb4_unicode_ci',
)
```

### 2. Database-Level Configuration

```sql
CREATE DATABASE myapp CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
```

### 3. Table-Level Configuration

```sql
CREATE TABLE users (
    id INT PRIMARY KEY AUTO_INCREMENT,
    name VARCHAR(255) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci,
    bio TEXT CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
```

### 4. Column-Level Configuration

```sql
CREATE TABLE posts (
    id INT PRIMARY KEY AUTO_INCREMENT,
    title VARCHAR(255) CHARACTER SET utf8mb4 COLLATE utf8mb4_zh_0900_as_cs,
    content TEXT CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci
);
```

## Collation Suffix Meanings

| Suffix | Meaning |
|--------|---------|
| _ai | Accent Insensitive |
| _as | Accent Sensitive |
| _ci | Case Insensitive |
| _cs | Case Sensitive |
| _ks | Kana Sensitive |

## Best Practices

1. **Unify Character Set**: Use `utf8mb4` consistently across database, tables, and columns to avoid conversion issues

2. **Choose Appropriate Collation**:
   - Need precise sorting → use `_unicode_ci` or `_0900_ai_ci`
   - Need case sensitivity → use `_cs` suffix
   - Chinese applications → recommend `utf8mb4_zh_0900_as_cs`

3. **Note Index Length**: ClickHouse indexes have a 767-byte limit (InnoDB). When using utf8mb4, prefix length for single column indexes should not exceed 191 characters

```sql
-- Correct: limit index length
CREATE INDEX idx_name ON users(name(191));

-- May fail: without index length limit
CREATE INDEX idx_name ON users(name);
```

💡 *AI Prompt:* "What is the difference between utf8mb4 and utf8? Why is utf8mb4 recommended?"

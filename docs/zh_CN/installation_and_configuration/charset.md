# 字符集与排序规则

## 概述

ClickHouse 支持多种字符集（Character Set）和排序规则（Collation），正确配置字符集对于处理多语言文本、表情符号（Emoji）以及确保排序行为符合预期至关重要。

## 常用字符集

| 字符集 | 说明 | 是否支持 Emoji |
|-------|------|---------------|
| utf8 | UTF-8 编码，最多 3 字节 | ❌ 不支持 |
| utf8mb4 | UTF-8 编码，最多 4 字节 | ✅ 支持 |
| latin1 | 西欧字符集 | ❌ 不支持 |
| ascii | ASCII 字符集 | ❌ 不支持 |

⚠️ **重要**：ClickHouse 的 `utf8` 字符集仅支持最多 3 字节的 UTF-8 字符，无法存储表情符号（Emoji）等 4 字节字符。如需支持 Emoji，请使用 `utf8mb4`。

## 常用排序规则

### utf8mb4 排序规则

| 排序规则 | 说明 | 性能 |
|---------|------|------|
| utf8mb4_general_ci | 快速排序，但不精确 | 最快 |
| utf8mb4_unicode_ci | 基于 Unicode 标准的排序 | 中等 |
| utf8mb4_0900_ai_ci | ClickHouse 8.0 新增，更精确的 Unicode 排序 | 较快 |
| utf8mb4_zh_0900_as_cs | 中文拼音排序，区分大小写 | 中等 |

💡 **推荐**：对于中文应用，推荐使用 `utf8mb4_zh_0900_as_cs` 或 `utf8mb4_unicode_ci`。

## 配置方式

### 1. 连接级别配置

在创建后端时指定字符集和排序规则：

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

### 2. 数据库级别配置

```sql
CREATE DATABASE myapp CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
```

### 3. 表级别配置

```sql
CREATE TABLE users (
    id INT PRIMARY KEY AUTO_INCREMENT,
    name VARCHAR(255) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci,
    bio TEXT CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
```

### 4. 字段级别配置

```sql
CREATE TABLE posts (
    id INT PRIMARY KEY AUTO_INCREMENT,
    title VARCHAR(255) CHARACTER SET utf8mb4 COLLATE utf8mb4_zh_0900_as_cs,
    content TEXT CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci
);
```

## 排序规则后缀含义

| 后缀 | 含义 |
|-----|------|
| _ai | 不区分重音（Accent Insensitive） |
| _as | 区分重音（Accent Sensitive） |
| _ci | 不区分大小写（Case Insensitive） |
| _cs | 区分大小写（Case Sensitive） |
| _ks | 区分假名（Kana Sensitive） |

## 最佳实践

1. **统一字符集**：整个数据库、表、字段统一使用 `utf8mb4`，避免字符集混用导致的转换问题

2. **选择合适的排序规则**：
   - 需要精确排序 → 使用 `_unicode_ci` 或 `_0900_ai_ci`
   - 需要区分大小写 → 使用 `_cs` 后缀
   - 中文应用 → 推荐 `utf8mb4_zh_0900_as_cs`

3. **注意索引长度**：ClickHouse 索引有767字节限制（InnoDB），使用 utf8mb4 时，单个字段索引前缀不应超过 191 字符

```sql
-- 正确：限制索引长度
CREATE INDEX idx_name ON users(name(191));

-- 可能出错：未限制索引长度
CREATE INDEX idx_name ON users(name);
```

💡 *AI 提示词：* "utf8mb4 与 utf8 有什么区别？为什么推荐使用 utf8mb4？"

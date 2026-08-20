# ClickHouse 到 Python 类型映射

## 概述

ClickHouse 后端负责将 ClickHouse 数据库中的数据类型转换为 Python 对象，以及将 Python 对象转换回 ClickHouse 可识别的格式。

## 类型映射表

### 数值类型

| ClickHouse 类型 | Python 类型 | 说明 |
|-----------|-------------|------|
| TINYINT | int | 8 位整数 |
| SMALLINT | int | 16 位整数 |
| MEDIUMINT | int | 24 位整数 |
| INT | int | 32 位整数 |
| BIGINT | int | 64 位整数 |
| FLOAT | float | 单精度浮点数 |
| DOUBLE | float | 双精度浮点数 |
| DECIMAL | Decimal | 精确小数 |

### 字符串类型

| ClickHouse 类型 | Python 类型 | 说明 |
|-----------|-------------|------|
| CHAR | str | 固定长度字符串 |
| VARCHAR | str | 可变长度字符串 |
| TINYTEXT | str | 最多 255 字节 |
| TEXT | str | 最多 65535 字节 |
| MEDIUMTEXT | str | 最多 16777215 字节 |
| LONGTEXT | str | 最多 4294967295 字节 |
| JSON | dict/list | JSON 文档 (ClickHouse 5.7+) |

### 日期时间类型

| ClickHouse 类型 | Python 类型 | 说明 |
|-----------|-------------|------|
| DATE | date | 日期 |
| TIME | time | 时间 |
| DATETIME | datetime | 日期时间 |
| TIMESTAMP | datetime | 时间戳 |
| YEAR | int | 年份 |

### 二进制类型

| ClickHouse 类型 | Python 类型 | 说明 |
|-----------|-------------|------|
| BINARY | bytes | 固定长度二进制 |
| VARBINARY | bytes | 可变长度二进制 |
| TINYBLOB | bytes | 最多 255 字节 |
| BLOB | bytes | 最多 65535 字节 |
| MEDIUMBLOB | bytes | 最多 16777215 字节 |
| LONGBLOB | bytes | 最多 4294967295 字节 |

### 特殊类型

| ClickHouse 类型 | Python 类型 | 说明 |
|-----------|-------------|------|
| ENUM | str | 枚举值 |
| SET | str | 集合值 |
| BIT | int | 位字段 |
| BOOLEAN | bool | 布尔值 |

## 使用示例

```python
from rhosocial.activerecord.model import ActiveRecord
from rhosocial.activerecord.base import FieldProxy
from rhosocial.activerecord.field import UUIDMixin, TimestampMixin
from typing import ClassVar
from decimal import Decimal


class Product(UUIDMixin, TimestampMixin, ActiveRecord):
    name: str
    price: Decimal  # 自动映射为 DECIMAL
    description: str  # 自动映射为 TEXT
    metadata: dict  # 自动映射为 JSON (ClickHouse 5.7+)
    
    c: ClassVar[FieldProxy] = FieldProxy()
    
    @classmethod
    def table_name(cls) -> str:
        return 'products'
```

💡 *AI 提示词：* "为什么推荐使用 DECIMAL 而不是 FLOAT 来存储金额？"

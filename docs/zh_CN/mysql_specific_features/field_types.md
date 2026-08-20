# ClickHouse 特定字段类型

## 概述

ClickHouse 提供了多种特定字段类型，本节介绍常用的字段类型及其使用场景。

## 数值类型

| 类型 | 范围 | 说明 |
|-----|------|------|
| TINYINT | -128 ~ 127 | 1 字节整数 |
| SMALLINT | -32768 ~ 32767 | 2 字节整数 |
| MEDIUMINT | -8388608 ~ 8388607 | 3 字节整数 |
| INT | -2147483648 ~ 2147483647 | 4 字节整数 |
| BIGINT | -9223372036854775808 ~ 9223372036854775807 | 8 字节整数 |

## 字符串类型

### VARCHAR vs TEXT

```python
from rhosocial.activerecord.model import ActiveRecord
from rhosocial.activerecord.base import FieldProxy
from rhosocial.activerecord.field import UUIDMixin
from typing import ClassVar
from pydantic import Field


class Article(UUIDMixin, ActiveRecord):
    title: str = Field(max_length=255)  # VARCHAR(255)
    content: str  # TEXT
    
    c: ClassVar[FieldProxy] = FieldProxy()
    
    @classmethod
    def table_name(cls) -> str:
        return 'articles'
```

### JSON 类型 (ClickHouse 5.7+)

```python
from typing import Dict, Any


class Config(UUIDMixin, ActiveRecord):
    name: str
    settings: Dict[str, Any]  # JSON 类型
    
    c: ClassVar[FieldProxy] = FieldProxy()
    
    @classmethod
    def table_name(cls) -> str:
        return 'configs'
```

## SET 和 ENUM

### ENUM

ClickHouse ENUM 是一个字符串对象，其值从允许值列表中选择。内部存储时，ClickHouse 将 ENUM 值存储为整数（1, 2, 3...）以节省空间。

#### 基本用法

```python
from enum import Enum
from rhosocial.activerecord.model import ActiveRecord
from rhosocial.activerecord.field import UUIDMixin


class Status(str, Enum):
    DRAFT = 'draft'
    PUBLISHED = 'published'
    ARCHIVED = 'archived'


class Post(UUIDMixin, ActiveRecord):
    title: str
    status: Status  # ENUM('draft', 'published', 'archived')

    @classmethod
    def table_name(cls) -> str:
        return 'posts'
```

#### 性能优化

为了更好的性能，可以使用 ClickHouse 的内部整数表示：

```python
from rhosocial.activerecord.backend.impl.clickhouse.adapters import ClickHouseEnumAdapter

# 在 backend 初始化后配置
backend.adapter_registry.register(
    ClickHouseEnumAdapter(use_int_storage=True),
    Enum,
    int,
    allow_override=True
)
```

这将：
- 将 ENUM 值存储为整数（1, 2, 3...）而不是字符串
- 将存储从约 N 字节减少到 1-2 字节
- 在 Python 中保持相同的逻辑接口

#### 值验证

可以在发送到数据库之前验证枚举值：

```python
adapter = ClickHouseEnumAdapter()

# 根据允许的值进行验证
adapter.to_database(
    Status.DRAFT, 
    str, 
    {'enum_values': ['draft', 'published']}
)
```

#### 重要说明

1. **值验证**：ClickHouse 自动验证 ENUM 值
2. **大小写敏感**：ENUM 值默认不区分大小写（取决于排序规则）
3. **存储**：< 256 个值使用 1 字节，256-65535 个值使用 2 字节
4. **排序**：ENUM 值按索引顺序排序，而不是按字母顺序

#### ClickHouse 原生 ENUM 类型

适配器可以与 ClickHouse 原生 ENUM 列类型无缝协作：

```sql
CREATE TABLE posts (
    id INT PRIMARY KEY,
    status ENUM('draft', 'published', 'archived')
);
```

```python
from enum import Enum


class Status(str, Enum):
    DRAFT = 'draft'
    PUBLISHED = 'published'
    ARCHIVED = 'archived'


# 插入到 ClickHouse ENUM 列
backend.execute(
    "INSERT INTO posts (id, status) VALUES (%s, %s)",
    (1, Status.PUBLISHED)  # 自动转换为 'published'
)

# 从 ClickHouse ENUM 列查询
result = backend.execute("SELECT status FROM posts WHERE id = %s", (1,))
status = result.data[0]['status']  # 返回 'published'
# 转换回 Python 枚举
py_status = Status(status)  # Status.PUBLISHED
```

**ClickHouse 原生 ENUM 的优势**：
- **存储效率**：无论字符串长度如何，仅使用 1-2 字节
- **数据验证**：ClickHouse 在数据库层面验证值
- **更好的性能**：更快的比较和排序
- **类型安全**：防止插入无效值

**注意**：ClickHouseEnumAdapter 自动处理原生 ENUM 列和常规 VARCHAR/INT 列。

💡 *AI 提示词：* "ClickHouse ENUM 和 VARCHAR 在性能上有什么影响？"

# ClickHouse-Specific Field Types

## Overview

ClickHouse provides various specific field types. This section covers commonly used field types and their use cases.

## Numeric Types

| Type | Range | Description |
|-----|-------|-------------|
| TINYINT | -128 ~ 127 | 1-byte integer |
| SMALLINT | -32768 ~ 32767 | 2-byte integer |
| MEDIUMINT | -8388608 ~ 8388607 | 3-byte integer |
| INT | -2147483648 ~ 2147483647 | 4-byte integer |
| BIGINT | -9223372036854775808 ~ 9223372036854775807 | 8-byte integer |

## String Types

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

### JSON Type (ClickHouse 5.7+)

```python
from typing import Dict, Any


class Config(UUIDMixin, ActiveRecord):
    name: str
    settings: Dict[str, Any]  # JSON type
    
    c: ClassVar[FieldProxy] = FieldProxy()
    
    @classmethod
    def table_name(cls) -> str:
        return 'configs'
```

## SET and ENUM

### ENUM

ClickHouse ENUM is a string object with a value chosen from a list of permitted values. Internally, ClickHouse stores ENUM values as integers (1, 2, 3, ...) for compact storage.

#### Basic Usage

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

#### Performance Optimization

For better performance, you can use ClickHouse's internal integer representation:

```python
from rhosocial.activerecord.backend.impl.clickhouse.adapters import ClickHouseEnumAdapter

# Configure after backend initialization
backend.adapter_registry.register(
    ClickHouseEnumAdapter(use_int_storage=True),
    Enum,
    int,
    allow_override=True
)
```

This will:
- Store ENUM values as integers (1, 2, 3...) instead of strings
- Reduce storage from ~N bytes to 1-2 bytes
- Maintain the same logical interface in Python

#### Value Validation

You can validate enum values before sending to database:

```python
adapter = ClickHouseEnumAdapter()

# Validate against allowed values
adapter.to_database(
    Status.DRAFT, 
    str, 
    {'enum_values': ['draft', 'published']}
)
```

#### Important Notes

1. **Value Validation**: ClickHouse automatically validates ENUM values
2. **Case Sensitivity**: ENUM values are case-insensitive by default (depends on collation)
3. **Storage**: Uses 1 byte for < 256 values, 2 bytes for 256-65535 values
4. **Sorting**: ENUM values sort by index order, not alphabetically

#### ClickHouse Native ENUM Type

The adapter works seamlessly with ClickHouse's native ENUM column type:

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


# Insert into ClickHouse ENUM column
backend.execute(
    "INSERT INTO posts (id, status) VALUES (%s, %s)",
    (1, Status.PUBLISHED)  # Automatically converts to 'published'
)

# Query from ClickHouse ENUM column
result = backend.execute("SELECT status FROM posts WHERE id = %s", (1,))
status = result.data[0]['status']  # Returns 'published'
# Convert back to Python Enum
py_status = Status(status)  # Status.PUBLISHED
```

**Benefits of ClickHouse Native ENUM**:
- **Storage efficiency**: Uses only 1-2 bytes regardless of string length
- **Data validation**: ClickHouse validates values at the database level
- **Better performance**: Faster comparisons and sorting
- **Type safety**: Prevents invalid values from being inserted

**Note**: The ClickHouseEnumAdapter automatically handles both native ENUM columns and regular VARCHAR/INT columns.

💡 *AI Prompt:* "What are the performance implications of ClickHouse ENUM vs VARCHAR?"

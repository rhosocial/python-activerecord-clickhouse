# ClickHouse to Python Type Mapping

## Overview

The ClickHouse backend is responsible for converting ClickHouse database data types to Python objects, and converting Python objects back to ClickHouse-recognized formats.

## Type Mapping Table

### Numeric Types

| ClickHouse Type | Python Type | Description |
|-----------|-------------|-------------|
| TINYINT | int | 8-bit integer |
| SMALLINT | int | 16-bit integer |
| MEDIUMINT | int | 24-bit integer |
| INT | int | 32-bit integer |
| BIGINT | int | 64-bit integer |
| FLOAT | float | Single-precision floating point |
| DOUBLE | float | Double-precision floating point |
| DECIMAL | Decimal | Exact numeric |

### String Types

| ClickHouse Type | Python Type | Description |
|-----------|-------------|-------------|
| CHAR | str | Fixed-length string |
| VARCHAR | str | Variable-length string |
| TINYTEXT | str | Up to 255 bytes |
| TEXT | str | Up to 65535 bytes |
| MEDIUMTEXT | str | Up to 16777215 bytes |
| LONGTEXT | str | Up to 4294967295 bytes |
| JSON | dict/list | JSON document (ClickHouse 5.7+) |

### Date and Time Types

| ClickHouse Type | Python Type | Description |
|-----------|-------------|-------------|
| DATE | date | Date |
| TIME | time | Time |
| DATETIME | datetime | Date and time |
| TIMESTAMP | datetime | Timestamp |
| YEAR | int | Year |

### Binary Types

| ClickHouse Type | Python Type | Description |
|-----------|-------------|-------------|
| BINARY | bytes | Fixed-length binary |
| VARBINARY | bytes | Variable-length binary |
| TINYBLOB | bytes | Up to 255 bytes |
| BLOB | bytes | Up to 65535 bytes |
| MEDIUMBLOB | bytes | Up to 16777215 bytes |
| LONGBLOB | bytes | Up to 4294967295 bytes |

### Special Types

| ClickHouse Type | Python Type | Description |
|-----------|-------------|-------------|
| ENUM | str | Enumeration value |
| SET | str | Set value |
| BIT | int | Bit field |
| BOOLEAN | bool | Boolean value |

## Usage Example

```python
from rhosocial.activerecord.model import ActiveRecord
from rhosocial.activerecord.base import FieldProxy
from rhosocial.activerecord.field import UUIDMixin, TimestampMixin
from typing import ClassVar
from decimal import Decimal


class Product(UUIDMixin, TimestampMixin, ActiveRecord):
    name: str
    price: Decimal  # Automatically maps to DECIMAL
    description: str  # Automatically maps to TEXT
    metadata: dict  # Automatically maps to JSON (ClickHouse 5.7+)
    
    c: ClassVar[FieldProxy] = FieldProxy()
    
    @classmethod
    def table_name(cls) -> str:
        return 'products'
```

💡 *AI Prompt:* "Why is DECIMAL recommended over FLOAT for storing monetary values?"

# Architecture Guide - python-activerecord-clickhouse

> ClickHouse backend implementation for rhosocial-activerecord

## Project Overview

| Item | Value |
|------|-------|
| **Database** | ClickHouse |
| **Python Driver** | clickhouse-connector-python |
| **Python Version** | 3.8+ |
| **Package** | rhosocial-activerecord-clickhouse |

## Directory Structure

```
python-activerecord-clickhouse/
├── src/rhosocial/activerecord/backend/impl/clickhouse/
│   ├── __init__.py           # Backend initialization
│   ├── __main__.py           # CLI entry point
│   ├── backend.py            # Sync backend implementation
│   ├── async_backend.py      # Async backend implementation
│   ├── config.py             # Configuration
│   ├── dialect.py            # ClickHouse dialect
│   ├── protocols.py          # Protocol definitions
│   ├── transaction.py        # Transaction management
│   ├── adapters.py           # Type adapters
│   ├── mixins.py             # ClickHouse-specific mixins
│   ├── types.py              # ClickHouse-specific types
│   ├── cli/                  # CLI commands
│   ├── expression/           # ClickHouse-specific expressions
│   │   ├── json.py           # JSON functions
│   │   ├── match_against.py  # FULLTEXT search
│   │   ├── locking.py        # Locking expressions
│   │   └── spatial.py        # Spatial functions
│   ├── functions/            # ClickHouse-specific functions
│   ├── introspection/        # Schema introspection
│   └── show/                 # SHOW statements
├── tests/
│   └── rhosocial/activerecord_clickhouse_test/
└── pyproject.toml
```

## ClickHouse-Specific Features

- **JSON functions**: JSON_ARRAY, JSON_OBJECT, JSON_CONTAINS, etc.
- **FULLTEXT search**: MATCH AGAINST for full-text queries
- **Spatial types**: GEOMETRY, POINT, POLYGON, etc.
- **Locking**: FOR UPDATE, LOCK IN SHARE MODE
- **INSERT ... ON DUPLICATE KEY UPDATE**: Upsert support

## Expression-Dialect System

All backends use Expression-Dialect separation:
- Expression classes define query structure
- Dialect classes handle SQL generation
- ClickHouse-specific expressions in `expression/` directory

## Namespace Package

Backend implementations use Python namespace packages (no `__init__.py` in impl subdirectories):
- Core: `rhosocial.activerecord`
- Backend: `rhosocial.activerecord.backend.impl.clickhouse`

## Reference

- [Core architecture](../python-activerecord/.claude/architecture.md)
- [Backend development guide](../python-activerecord/.claude/backend_development.md)
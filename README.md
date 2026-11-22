<!-- README.md -->
# rhosocial-activerecord-clickhouse ($\rho_{\mathbf{AR}}$)

[![Python](https://img.shields.io/pypi/pyversions/rhosocial-activerecord-clickhouse.svg)](https://pypi.org/project/rhosocial-activerecord-clickhouse/)
[![Tests](https://github.com/rhosocial/python-activerecord-clickhouse/actions/workflows/test.yml/badge.svg)](https://github.com/rhosocial/python-activerecord-clickhouse/actions)
[![Supported ClickHouse versions](https://img.shields.io/badge/ClickHouse-25.8%7C26.3%7C26.7-blue?logo=clickhouse)](docs/en_US/README.md)
[![Apache 2.0 License](https://img.shields.io/github/license/rhosocial/python-activerecord-clickhouse.svg)](https://github.com/rhosocial/python-activerecord-clickhouse/blob/main/LICENSE)

<div align="center">
    <img src="https://raw.githubusercontent.com/rhosocial/python-activerecord/main/docs/images/logo.svg" alt="rhosocial ActiveRecord Logo" width="200"/>
    <h3>ClickHouse Backend for rhosocial-activerecord</h3>
    <p><b>Columnar types · Capability-gated dialect · Sync only, by design</b></p>
</div>

A [ClickHouse](https://clickhouse.com/) backend for
[rhosocial-activerecord](https://github.com/rhosocial/python-activerecord) —
the ActiveRecord pattern adapted to a columnar, OLAP engine.

> **This package is not on PyPI yet.** The PyPI badges above are aspirational;
> install from source until the first release is published.

**Keywords:** clickhouse, orm, activerecord, pydantic, python, olap, columnar, sync

## Why This Project?

### 1. ClickHouse is a columnar OLAP engine, not a row store

Its native types (`Int64`, `String`, `LowCardinality`, `Nullable`,
`Array`/`Map`/`Tuple`, `JSON`) and `MergeTree` storage model differ fundamentally
from a relational row store. This backend speaks ClickHouse natively —
`ENGINE`, `ORDER BY`, `PARTITION BY`, `TTL` — instead of emulating a generic SQL
database.

### 2. Unsupported features fail fast

ClickHouse has no ACID transactions, foreign keys, unique constraints, or
UPSERT. Rather than silently emulating them, this backend declares them through
support switches and raises `UnsupportedFeatureError` when you cross the
line. You always know what the engine actually guarantees.

### 3. The ActiveRecord pattern stays intact

Define a model as a class, save instances, and query with type-safe expressions
— the same ergonomic API as the core library. Client-side snowflake IDs replace
`AUTO_INCREMENT`, and optional fields map to `Nullable(T)` columns.

## Quick Start

### Installation

```bash
pip install rhosocial-activerecord-clickhouse
```

Requires Python 3.10+, `clickhouse-connect>=1.7.0`, and a running ClickHouse
server. Until the first PyPI release, install from source instead:

```bash
pip install -e .
```

### End-to-End Example

```python
"""Save as demo.py and run with: python demo.py"""
from typing import ClassVar, Optional

from pydantic import Field

from rhosocial.activerecord.backend.impl.clickhouse.backend import ClickHouseBackend
from rhosocial.activerecord.backend.impl.clickhouse.config import ClickHouseConnectionConfig
from rhosocial.activerecord.base.field_proxy import FieldProxy
from rhosocial.activerecord.model import ActiveRecord


class User(ActiveRecord):
    __table_name__ = "users"
    __primary_key__ = "id"
    c: ClassVar[FieldProxy] = FieldProxy()  # enables User.c.<field> expressions

    id: Optional[int] = None                        # client-side snowflake Int64
    username: str = Field(min_length=3, max_length=50)
    email: str
    age: Optional[int] = None                       # Nullable(Int32)


User.configure(
    ClickHouseConnectionConfig(
        host="localhost", port=8123,
        database="test_db", username="default", password="",
    ),
    ClickHouseBackend,
)

# ClickHouse does not auto-create tables — a MergeTree needs ENGINE / ORDER BY.
# The two settings are a prerequisite for UPDATE/DELETE (lightweight mutations).
User.__backend__.execute(
    "CREATE TABLE IF NOT EXISTS users ("
    "id Int64, username String, email String, age Nullable(Int32)"
    ") ENGINE = MergeTree ORDER BY (id, username) "
    "SETTINGS enable_block_number_column = 1, enable_block_offset_column = 1"
)

# Create — the id is generated client-side and backfilled
alice = User(username="alice", email="alice@example.com", age=28)
alice.save()
print(alice.id)  # Int64 snowflake ID

# Query with type-safe expressions
adults = User.query().where(User.c.age >= 18).order_by(User.c.username).all()
print([u.username for u in adults])

# Inspect the generated SQL without executing it
sql, params = User.query().where(User.c.age >= 18).to_sql()
print(sql, params)
```

> **Synchronous only.** `clickhouse-connect` is a sync-only driver, so there is
> no async backend. `AsyncClickHouseBackend` exists only as an import placeholder
> and raises `NotImplementedError` on instantiation — there is no half-working
> async layer.

## Project Architecture

```
Your Code
   ↓
Interface        models, field proxies, mixins, query builders
   ↓
ActiveRecord     lifecycle, persistence
   ↓
Expressions      backend-agnostic declarations → generic statements
   ↓
ClickHouse dialect + capability gates → native ClickHouse SQL
   ↓
clickhouse-connect (HTTP) → ClickHouse
```

For the full picture, start with the [Documentation](docs/en_US/README.md).

**Native ClickHouse dialect.** Expressions describe *what* you want; the
ClickHouse dialect renders native DDL/DML — `MergeTree`, `ORDER BY`,
`PARTITION BY`, `TTL`, `Nullable`, `LowCardinality`. Nothing is sent until an
explicit execute or `.to_sql()` call, so every statement can be previewed.

**Capability-gated.** Features ClickHouse does not provide are switched off at
the dialect level and fail fast with `UnsupportedFeatureError`, rather than
being silently emulated.

**Synchronous, type-first.** Built on Pydantic with typed fields and no `Any`
types in the public API. The driver is sync-only, so there is no async variant;
method names and patterns stay consistent, with no `await` anywhere.

## Backend Support & Progress

This backend ships as a separate distribution from the core
[rhosocial-activerecord](https://github.com/rhosocial/python-activerecord)
library, which documents the ActiveRecord API itself.

- **Server versions:** ClickHouse 25.8, 26.3 and 26.7 are CI-tested (against Python 3.10–3.14).
- **Driver / Python:** `clickhouse-connect>=1.7.0` over HTTP; Python `>=3.10,<3.15`
  — a ceiling inherited from the driver, not chosen here.
- **Synchronous only:** the driver exposes no async surface.

> **⚠️ Development Stage:** This project is under active development. APIs may change, and some features are not yet production-ready.

## Documentation

### Contributing

We welcome contributions! Please see
[CONTRIBUTING.md](https://github.com/rhosocial/python-activerecord/blob/main/CONTRIBUTING.md)
for guidelines.

### License

[Apache License 2.0](LICENSE) — Copyright © 2026 [vistart](https://github.com/vistart)

### Documentation

* **[Documentation Home](docs/en_US/README.md)** — full documentation table of contents
* **[Backend notes](.claude/README.md)** — repository conventions, architecture and guides
* **[ClickHouse specifics](.claude/clickhouse_backend.md)** — dialect and type details
* **[Runnable examples](src/rhosocial/activerecord/backend/impl/clickhouse/examples/)** — one script per feature area
* **[中文文档](docs/zh_CN/)**

---

<div align="center">
    <p><b>Built with ❤️ by the rhosocial team</b></p>
    <p><a href="https://github.com/rhosocial/python-activerecord-clickhouse">GitHub</a> · <a href="docs/en_US/README.md">Documentation</a></p>
</div>

# Relationship with the core library

`rhosocial-activerecord-clickhouse` is a **backend implementation plugin** for the
core library [python-activerecord](https://github.com/rhosocial/python-activerecord).
Understanding the layering helps you tell which capabilities come from the core
and which from this backend.

## Layered architecture

The core library defines four layers:

```
Interface (ActiveRecord model / FieldProxy)
   └── Dialect (SQL dialect, branched by database family)
        └── Expression (serializable SQL expression objects)
             └── Backend (executor: connects, executes, returns results)
```

This backend implements two of them:

- **`ClickHouseDialect`** (`dialect.py`): inherits the core library's generic
  dialect mixins (CTE, window functions, JSON, joins, views, indexes,
  introspection, ...) and stacks ClickHouse-specific mixins on top (table engines,
  `FINAL`/`ARRAY JOIN`, the JSON function family, no-op transactions, fail-fast
  stubs for unsupported features).
- **`ClickHouseBackend`** (`backend.py`): implements the core library's
  `DatabaseBackend` interface, executing SQL via `clickhouse-connect`, managing
  connections, mapping errors, and generating client-side snowflake IDs.

## What this backend provides

| Layer | From core library | From this backend |
|-------|-------------------|-------------------|
| ActiveRecord model, `FieldProxy`, mixins, relations | ✅ | — |
| Generic dialect mixins (CTE/window/JSON/join/view/index/introspection) | ✅ defines protocols | ✅ inherits & overrides per ClickHouse semantics |
| ClickHouse-specific types (`Int*`/`UInt*`/`Decimal*`/`DateTime64`/`Enum*`/`Array`/`Map`/`Tuple`/`Nullable`/`LowCardinality`/`JSON`) | — | ✅ |
| ClickHouse DDL (`ENGINE`/`ORDER BY`/`PARTITION BY`/`TTL`/skip indexes) | — | ✅ |
| `system.*` introspection, `EXPLAIN`/`SHOW` | generic protocols | ✅ ClickHouse implementation |
| Client-side snowflake ID generation | `AutoIncrementSupport` protocol (core dev30+) | ✅ `SnowflakeIDGenerator` |
| Transaction management | protocol | ✅ no-op context manager (fail-fast rollback) |
| Fail-fast stubs for unsupported features | — | ✅ trigger/spatial/vector/set/JSON_TABLE/... |

## Dependency version

This backend depends on the core library `rhosocial-activerecord>=1.0.0.dev30`.
Two dev30-introduced capabilities are **hard dependencies**:

- `BulkInsertOptions.primary_key` field (to propagate client-generated snowflake
  IDs into bulk inserts).
- `AutoIncrementSupport` protocol (the dialect inherits it to express "ClickHouse
  has no server-side AUTO_INCREMENT; the backend generates IDs").

Until the core library `1.0.0.dev30` is officially published to PyPI, this backend
cannot be installed independently via `pip install`; install from source together
with the core library. See [Installation guide](../installation/installation.md).

## Comparison with other backends

The core library ecosystem includes multiple backends (built-in SQLite, MySQL,
PostgreSQL, MariaDB, SQL Server, Oracle). This backend is special in that it is
the only one targeting columnar OLAP:

- **Sync-only**: other backends mostly provide symmetric async implementations;
  this one does not, due to the driver.
- **No transactions**: other backends have real isolation; this backend's
  transactions are no-ops.
- **No server-side auto-increment**: other backends' `AUTO_INCREMENT`/`SERIAL` are
  server-generated; this backend generates `Int64` client-side via the snowflake
  algorithm.
- **Widest fail-fast surface**: this backend has more fail-fast stubs than any
  other, because ClickHouse lacks the most OLTP features.

> 💡 *AI prompt: "If a model is used with both SQLite (tests) and ClickHouse (production), how are the capability differences handled at the code level?"*

## Next steps

- [Supported versions](supported_versions.md)
- [Capability boundaries & fail-fast](capability_boundaries.md)

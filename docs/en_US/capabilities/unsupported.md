# Unsupported features

This backend always fails fast (`UnsupportedFeatureError`) on features ClickHouse does not support, without silent emulation. The tables below are the complete list with alternatives.

## Transactions & constraints

| Feature | Behavior | Alternative |
|------|------|------|
| ACID cross-statement transactions | `transaction()` is a no-op; rollback raises | design per-part atomic mutations |
| `FOREIGN KEY` | not generated in DDL | maintain referential integrity at the application layer |
| `UNIQUE` constraint | not generated in DDL | `ReplacingMergeTree` dedup |
| Triggers | raise | — |
| Sequences | raise | client-side snowflake id |

## DML / Locks

| Feature | Behavior | Alternative |
|------|------|------|
| UPSERT / `ON CONFLICT` / `INSERT IGNORE` / `REPLACE INTO` | raise | `ReplacingMergeTree` + explicit `INSERT` |
| `FOR UPDATE` row lock | raise | OLAP does not do pessimistic locking |
| `FOR SHARE` / `NOWAIT` / `SKIP LOCKED` | raise | same as above |

## Indexes & full-text

| Feature | Behavior | Alternative |
|------|------|------|
| `FULLTEXT` index | raise | skip index `tokenbf_v1` + `hasToken` |
| `MATCH ... AGAINST` | raise | same as above |
| `JSON_TABLE` | raise | `JSONExtract*` / `arrayJoin` |
| SQL-standard spatial indexes | raise | skip indexes |

## Types

| Feature | Behavior | Alternative |
|------|------|------|
| Spatial types (`GEOMETRY`/`POINT`/...) | raise | store WKT as `String` |
| `ST_*` function family | raise | ClickHouse functions |
| MySQL 9.0 `VECTOR` type | raise | `Array(Float32)` |
| `STRING_TO_VECTOR`/`VECTOR_TO_STRING`/`VECTOR_DIM`/`DISTANCE_*` | raise | `L2Distance`/`cosineDistance`/`dotProduct` |
| `SET` type | raise | `Enum16` or `Array(String)` |
| `FIND_IN_SET` | raise | `has()`/`indexOf()` |

## Statements

| Feature | Behavior | Alternative |
|------|------|------|
| Stored procedures / stored functions / `CALL` | raise | ClickHouse SQL UDF (`CREATE FUNCTION ... AS`) |
| `LOAD DATA INFILE` | raise | format parsers / `input()` table function |
| `LOAD XML` | raise | same as above |
| `TABLE` / `VALUES` table-value constructor (MySQL 8.0.19+) | raise | `SELECT ... UNION ALL SELECT ...` |
| Whole-table maintenance (`ANALYZE`/`CHECK`/`CHECKSUM`/`REPAIR TABLE`) | raise | `OPTIMIZE TABLE ... FINAL` or `SYSTEM` commands |
| MySQL optimizer hints (`/*+ SET_VAR */`) | raise | `SETTINGS` clause |
| JSON Relational Duality Views | raise | `JSON` type + `JSONExtract*` |

## Admin commands (MySQL admin set)

`FLUSH`/`RESET`/`CACHE INDEX`/`LOAD INDEX INTO CACHE`/`INSTALL`/`UNINSTALL COMPONENT`/`PLUGIN`/`CLONE`/`RESTART`/`BINLOG`/`HANDLER`/`DO`/`KILL`/`SHUTDOWN`/`HELP`/`CREATE USER`/`DROP USER`/`GRANT`/`REVOKE` — all raise. Use ClickHouse's `SYSTEM` command family instead (`SYSTEM RELOAD`/`SYSTEM KILL`/`SYSTEM FLUSH`/...).

## Async

| Feature | Behavior | Alternative |
|------|------|------|
| Async backend | instantiating `AsyncClickHouseBackend` immediately raises `NotImplementedError` | sync backend + out-of-process concurrency |

`clickhouse-connect` is a purely synchronous library; this backend provides no async implementation.

## How to probe

```python
if dialect.supports_on_conflict_clause():
    ...   # 走 UPSERT
else:
    ...   # 走 INSERT + ReplacingMergeTree
```

Callers should probe explicitly via `supports_*` rather than `try/except UnsupportedFeatureError`, so they can switch across backends (e.g., SQLite for development, ClickHouse for production).

## Next steps

- [Capability boundaries & fail-fast](../introduction/capability_boundaries.md)
- [Mutations (UPDATE/DELETE)](mutations.md)

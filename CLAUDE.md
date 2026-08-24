# Project Overview: rhosocial-activerecord-clickhouse

## Project Name
- **Repository Name**: python-activerecord-clickhouse
- **Python Package Name**: rhosocial-activerecord-clickhouse

## Project Purpose

This project is a ClickHouse backend implementation for the `rhosocial-activerecord` Python package. It provides ClickHouse database support with the elegant ActiveRecord pattern interface.

## Key Design Principles

1. **Backend Implementation**: Extends core ActiveRecord with ClickHouse-specific features
2. **Driver**: Uses `clickhouse-connect` (HTTP interface) for database connectivity
3. **Namespace Package**: Integrates with the rhosocial namespace package architecture
4. **Synchronous only**: clickhouse-connect is a sync-only library; no async backend is provided
5. **Fast-fail semantics**: features ClickHouse does not support (transactions, FK/UNIQUE constraints, triggers, upsert, JSON_TABLE, etc.) raise `UnsupportedFeatureError` instead of being emulated

## Current Status

This project is under active development. Key features implemented:

- Basic CRUD operations (client-side snowflake integer ids; no AUTO_INCREMENT)
- Connection management (clickhouse-connect DB-API, HTTP interface)
- Schema introspection (via ClickHouse `system.*` tables)
- ClickHouse-native data types (Int/UInt, Float, Decimal, String, FixedString, Date/DateTime64, Bool, UUID, IPv4/6, Enum8/16, Array/Map/Tuple, Nullable, LowCardinality, JSON)
- ClickHouse SQL dialect (ENGINE/ORDER BY/PARTITION BY/TTL clauses, set operations with explicit ALL/DISTINCT)
- Capability negotiation via `supports_*` switches

## Backend Behaviour Notes (differs from SQL-standard backends)

- Mutations (`UPDATE`/`DELETE`) run with `mutations_sync=1` and report the
  pre-counted matching-row number as `affected_rows` (ClickHouse cannot
  report mutation row counts itself).
- Optional model fields map to `Nullable(T)` columns; writing NULL into a
  non-nullable String column silently stores an empty string.
- JSON path access renders to native functions (`JSONExtractString` /
  `JSONExtractRaw`, falling back to `JSON_VALUE`), not MySQL arrow operators.

## Not Supported (fail fast)

The following MySQL / SQL-standard features are **not** supported by ClickHouse
and raise `UnsupportedFeatureError` instead of being emulated:

- ACID transactions (`transaction()` degrades to a no-op context manager so
  generic operations keep working; rollback guarantees are absent)
- FOREIGN KEY / UNIQUE constraints
- Triggers, sequences
- UPSERT / ON CONFLICT / INSERT IGNORE / REPLACE INTO
- FOR UPDATE row locking
- SQL-standard FULLTEXT indexes / `MATCH ... AGAINST`
- `JSON_TABLE` (JSON access uses `JSONExtractString` / `JSONExtractRaw` /
  `JSON_VALUE`)
- MySQL-style spatial types (`GEOMETRY`/`POINT`/...) and the `ST_*` function
  family
- MySQL 9.0 `VECTOR` type and `STRING_TO_VECTOR` / `VECTOR_TO_STRING` /
  `VECTOR_DIM` / `DISTANCE_*` functions (use `Array(Float32)` + `L2Distance`)
- MySQL `SET` type and `FIND_IN_SET`
- Stored procedures / stored functions / `CALL`
- `LOAD DATA INFILE` / `LOAD XML`
- MySQL admin commands (`FLUSH` / `RESET` / `KILL` / `INSTALL PLUGIN` /
  `CLONE` / `BINLOG` / `HANDLER` / `GRANT` / `CREATE USER`; use `SYSTEM`
  commands)
- MySQL `TABLE` / `VALUES` table-value constructor (8.0.19+)
- MySQL whole-table maintenance (`ANALYZE` / `CHECK` / `CHECKSUM` / `REPAIR
  TABLE`; use `OPTIMIZE TABLE ... FINAL` or `SYSTEM` commands)
- MySQL optimizer hints (`/*+ SET_VAR(...) */`; use `SETTINGS`)
- JSON Relational Duality Views
- Asynchronous backend (clickhouse-connect is sync-only)

## Python Version Support

- Python `>=3.10,<3.15` (per clickhouse-connect `Requires-Python`)

## Testing

```bash
# Against a local ClickHouse (see tests/config/clickhouse_scenarios.yaml)
export PYTHONPATH=src:tests
.venv3.14-ubuntu26.04/bin/python -m pytest tests/rhosocial/activerecord_clickhouse_test -p no:logging -p no:cacheprovider
```

The shared testsuite feature groups (basic/events/interface/mixins/query/relation)
are bridged under `tests/rhosocial/activerecord_clickhouse_test/feature/`.

## Version Control and Changelog

This project adheres to the same version control, branching, commit message, and changelog management standards as the main `python-activerecord` project.

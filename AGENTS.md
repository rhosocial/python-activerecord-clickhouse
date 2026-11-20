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
5. **Fast-fail semantics**: features ClickHouse does not support (transactions, FK/UNIQUE constraints, triggers, upsert, etc.) raise `UnsupportedFeatureError` instead of being emulated

## Current Status

This project is under active development. Key features implemented:

- Basic CRUD operations
- Connection management (clickhouse-connect DB-API)
- Schema introspection (via ClickHouse `system.*` tables)
- ClickHouse-native data types (Int/UInt, Float, Decimal, String, FixedString, Date/DateTime64, Bool, UUID, IPv4/6, Enum8/16, Array/Map/Tuple, Nullable, LowCardinality, JSON)
- ClickHouse SQL dialect (ENGINE/ORDER BY/PARTITION BY/TTL clauses)
- Capability negotiation via `supports_*` switches

## Not Supported (fail fast)

The following MySQL / SQL-standard features are **not** supported by ClickHouse
and raise `UnsupportedFeatureError` instead of being emulated:

- ACID transactions (no BEGIN/COMMIT/ROLLBACK; `transaction()` degrades to a
  no-op context manager)
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
  `VECTOR_DIM` / `DISTANCE_*` functions — no such API here, by design; ClickHouse's
  own vector type is `QBit`, rendered as `ClickHouseVectorType` →
  `QBit(Float32, n)`, and `Array(Float32)` + `L2Distance` also works
- MySQL `SET` type and `FIND_IN_SET`
- Stored procedures / stored functions / `CALL`
- `LOAD DATA INFILE` / `LOAD XML`
- MySQL admin commands (`FLUSH` / `RESET` / `KILL` / `INSTALL PLUGIN` /
  `CLONE` / `BINLOG` / `HANDLER` / `GRANT` / `CREATE USER`; use `SYSTEM` commands)
- MySQL `TABLE` / `VALUES` table-value constructor (8.0.19+)
- MySQL whole-table maintenance (`ANALYZE` / `CHECK` / `CHECKSUM` / `REPAIR
  TABLE`; use `OPTIMIZE TABLE ... FINAL` or `SYSTEM` commands)
- MySQL optimizer hints (`/*+ SET_VAR(...) */`; use `SETTINGS`)
- JSON Relational Duality Views
- Asynchronous backend (clickhouse-connect is sync-only)

## Backend Behaviour Notes

- Primary keys are generated client-side (snowflake `Int64`) because ClickHouse
  has no AUTO_INCREMENT; requires core `>=1.0.0.dev30` (primary_key propagation).
- A `CREATE TABLE` built from a portable (SQL-standard) declaration is adapted
  by the table renderer, because the declaration cannot express ClickHouse's
  storage model. The renderer appends `ENGINE = MergeTree()` plus
  `ORDER BY (<primary key columns>)` (or `tuple()` with no key) and the
  `enable_block_number_column` / `enable_block_offset_column` settings the
  UPDATE/DELETE path needs. `AUTO_INCREMENT` is not rendered (the id is
  generated client-side), and `UNIQUE` constraints are dropped because no
  ClickHouse engine enforces uniqueness at write time — the strict
  per-constraint formatters still refuse them when called directly. The verbose
  form is still an `UnsupportedFeatureError` when the caller asks for the clause
  itself.
- The same renderer widens a narrower-than-64-bit auto-generated key, and the
  table's other integer columns with it, to `Int64` / `UInt64`: ClickHouse's SQL
  path truncates an overflowing value silently, so a 32-bit key or a 32-bit
  reference to it would store a different value than the model reports.
- A portable column that does not say `NOT NULL` is rendered `Nullable(T)`
  (except for key columns and the Array/Map/Tuple families); ClickHouse's plain
  types coerce `NULL` to a default instead of storing it, so an optional field
  would read back as `''` / `0`.
- Mutations run with `mutations_sync=1`; `affected_rows` for UPDATE/DELETE is a
  pre-count of rows matching the WHERE predicate.
- Optional model fields must map to `Nullable(T)` columns.
- The CLI's `introspect` offers twenty-one types — `tables`, `views`, `columns`,
  `indexes`, `partitions`, `table-engine`, `database`, `functions`,
  `dictionaries`, `clusters`, `quotas`, `users`, `roles`, `unused-indexes`,
  `table-stats`, `runtime`, `index-stats`, `dependencies`, `column-profiles`,
  `value-samples`, `join-coverage` — and each is gated on a dialect
  `supports_*` switch (exit 2 when the connected server answers False).
  Sixteen of the twenty-one answer True here: the seven table-scoped catalogue
  families, the six server-wide catalogue families, and the three row families,
  which read the rows themselves. The other five answer False, because
  ClickHouse has no statistics collector and no dependency graph, so the gate
  refuses them before the introspector is reached. DDL extraction is not offered
  at all, because the backend has no reader for it. `foreign-keys` / `triggers`
  are absent from the vocabulary because
  the engine has neither, which is a different statement from a capability
  switch. The SHOW passthrough (`introspector.show`, 19 methods) is
  library-only and deliberately not wired into `introspect`: SHOW and
  `system.*` are not equivalent, and every introspect type reads `system.*`.

## Python Version Support

- Python `>=3.10,<3.15` (per clickhouse-connect `Requires-Python`)

## Version Control and Changelog

This project adheres to the same version control, branching, commit message, and changelog management standards as the main `python-activerecord` project.

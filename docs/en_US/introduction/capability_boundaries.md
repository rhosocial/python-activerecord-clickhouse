# Capability boundaries & fail-fast

Understanding the capability boundaries is the prerequisite for using this
backend. This backend **does not try to wrap ClickHouse as an OLTP database**.

## Design principle: fail fast, not silent emulation

When a caller requests a capability ClickHouse does not support, this backend
raises `UnsupportedFeatureError`, **instead of**:

- silently ignoring (e.g. making `transaction()` a no-op while claiming it committed);
- degrading into an inefficient emulation (e.g. simulating UPSERT with
  `SELECT + DELETE + INSERT`);
- generating SQL ClickHouse would reject (e.g. `UNIQUE (col)`), or SQL it
      would accept and silently ignore (e.g. an unnamed `FOREIGN KEY (...)` —
      see [FOREIGN KEY is accepted without effect](../capabilities/unsupported.md#foreign-key-is-accepted-without-effect)).

The only exception is `transaction()`: it degrades to a **no-op context manager**
so generic code paths (core library and testsuite transaction-related tests) keep
running without errors; but **rollback semantics do not exist** — mutations are
per-part atomic and cannot be rolled back across statements.

```python
from rhosocial.activerecord.backend.dialect.exceptions import UnsupportedFeatureError

# ClickHouse does not support UPSERT; it fails fast:
try:
    User.query().upsert(...).execute()
except UnsupportedFeatureError as e:
    print(e.suggestion)  # gives a ClickHouse-native alternative
```

> 💡 *AI prompt: "What fields does `UnsupportedFeatureError` carry to help callers do conditional degradation? Why is `transaction()` a no-op instead of raising outright?"*

## Capability quick reference

### Natively supported by ClickHouse (first-class)

- Columnar types: `Int*`/`UInt*`, `Float*`, `Decimal*`, `String`/`FixedString`,
  `Date`/`Date32`/`DateTime`/`DateTime64`, `Bool`, `UUID`, `IPv4`/`IPv6`,
  `Enum8`/`Enum16`, `Array`, `Map`, `Tuple`, `Nullable(T)`, `LowCardinality(T)`, `JSON`,
  and (as of the 26.x line) `Geometry` / `Point`
- DDL: `ENGINE`, `ORDER BY` sorting key, `PARTITION BY`, `TTL`, skip indexes
  (`INDEX name (col) TYPE <type> GRANULARITY n` — the keyword is `TYPE`, not
  MySQL's `USING`)
- Partition maintenance by partition id: `DROP` / `DETACH` / `ATTACH
  PARTITION ID` (ClickHouse's own clause list is at
  <https://clickhouse.com/docs/sql-reference/statements/alter/partition>)
- Querying: CTE (`WITH`), window functions, `QUALIFY`, `ARRAY JOIN`, set
  operations (`UNION`/`INTERSECT`/`EXCEPT`, explicit `ALL`/`DISTINCT`), `EXPLAIN`.
  `FINAL` is a query modifier too, but only for the engines that collapse
  duplicates — a plain `MergeTree` answers `Storage MergeTree doesn't support
  FINAL`, while `ReplacingMergeTree` accepts it.
- JSON: `JSONExtractString`/`JSONExtractRaw`/`JSON_VALUE` (on a `String` column —
  `JSON_VALUE` rejects a `JSON` argument) and the native function family
  (**not** MySQL arrow operators `->`/`->>`)
- Introspection: `system.*` tables (settings/server_settings/metrics/events/
  asynchronous_metrics/replicas/processes/...), `SHOW`
- Access control from SQL: `CREATE USER` / `ALTER USER` / `DROP USER` /
  `GRANT` / `REVOKE` (this backend's expression layer offers no spelling for
  them, so nothing here emits them — but the server has them)
- Client-side snowflake `Int64` IDs (replacing `AUTO_INCREMENT`)
- Lightweight UPDATE/DELETE mutations (`enable_block_number_column`/
  `enable_block_offset_column` settings required — see [Mutations](../capabilities/mutations.md))

### Not supported by ClickHouse (fail-fast)

| Capability | Behavior | Alternative |
|------------|----------|-------------|
| ACID cross-statement transactions | `transaction()` no-op; rollback raises | design per per-part atomic mutations, or use `ReplacingMergeTree` |
| `FOREIGN KEY` / `UNIQUE` constraints | DDL not emitted. `UNIQUE (col)` is a `SYNTAX_ERROR` on the server; an unnamed `FOREIGN KEY (...) REFERENCES ...` is **accepted and silently discarded** — see [FOREIGN KEY is accepted without effect](../capabilities/unsupported.md#foreign-key-is-accepted-without-effect) | dedup via table engine; referential integrity at the application layer |
| Triggers, sequences | raise | — |
| UPSERT / `ON CONFLICT` / `INSERT IGNORE` / `REPLACE INTO` | raise | `ReplacingMergeTree` + explicit `INSERT` |
| `FOR UPDATE` row locking | raise | OLAP does not do pessimistic locking |
| `FULLTEXT` indexes / `MATCH...AGAINST` | raise | the `text` inverted index (GA from 26.2) + `hasAllTokens`/`hasAnyTokens` |
| `JSON_TABLE` | raise | `JSONExtract*` / `arrayJoin` |
| Spatial types (`GEOMETRY`/`POINT`/...) and the OGC `ST_*` functions | raise | ClickHouse's own `Geometry`/`Point` column types and its 7 WKB/MVT `ST_*` codecs; `geoDistance` for distance |
| MySQL 9.0 `VECTOR` type and `STRING_TO_VECTOR`/`VECTOR_DIM`/`DISTANCE_*` | not offered — the API is absent (ClickHouse's own vector type is `QBit`, rendered by `ClickHouseVectorType`) | `QBit(Float32, n)` or `Array(Float32)` + `L2Distance`/`cosineDistance` |
| `SET` type / `FIND_IN_SET` | raise | `Enum16` or `Array(String)` + `has()` |
| Stored procedures / functions / `CALL` | raise | ClickHouse SQL UDFs (`CREATE FUNCTION ... AS`) |
| `LOAD DATA INFILE` / `LOAD XML` | raise | format parsers / `input()` table function |
| MySQL admin commands (`FLUSH`/`RESET`/`KILL`/`INSTALL PLUGIN`/`CLONE`/`BINLOG`/`HANDLER`/`GRANT`/`CREATE USER`) | raise | ClickHouse `SYSTEM` command family |
| `TABLE` / `VALUES` table-value constructor (MySQL 8.0.19+) | raise | `SELECT ... UNION ALL SELECT ...` |
| Whole-table maintenance (`ANALYZE`/`CHECKSUM`/`REPAIR TABLE`) | raise (`CHECK TABLE` is the exception and *does* work) | `OPTIMIZE TABLE ... FINAL` or `SYSTEM` commands |
| MySQL optimizer hints (`/*+ SET_VAR */`) | raise. The refusal is not redundant: ClickHouse **parses the comment and discards its contents**, measured on 26.7.3.19 — `/*+ SET_VAR(max_block_size=7) */` leaves `getSetting('max_block_size')` at `65409`, and a hint naming an invented setting (`SET_VAR(totally_bogus_zzz=1)`) is also accepted, so the name is not validated either | `SETTINGS` clause |
| JSON Relational Duality Views | raise | `JSON` type + `JSONExtract*` |
| `SHOW` statements ClickHouse does not have (`SHOW VARIABLES`/`STATUS`/`TABLE STATUS`/`TRIGGERS`/`CREATE TRIGGER`/`WARNINGS`/`ERRORS`/`CHARACTER SET`/`COLLATION`/`PLUGINS`) | raise | the `system.*` tables each names, via `ClickHouseStatusIntrospector`. `SHOW` accepts no `VARIABLES`, `STATUS`, `TRIGGERS` or `PLUGINS` keyword at all |
| `SHOW` statements ClickHouse **does** have (`SHOW [FULL] COLUMNS`/`INDEX`/`PROCESSLIST`/`ENGINES`/`GRANTS`) | **not refused — these work** and are read via `backend.introspector.show.*()`. Their columns are ClickHouse's, so a parser reading MySQL's names gets `None` fields rather than an error | the `system.*` tables, if you prefer to query them directly. See [The `SHOW` set ClickHouse actually has](../capabilities/unsupported.md#the-show-set-clickhouse-actually-has) |
| Declarative partitioning (`PARTITION BY RANGE/LIST/HASH/KEY` with `PARTITION ... VALUES ...`, subpartitioning, `ADD`/`TRUNCATE`/`REORGANIZE`/`EXCHANGE`/`COALESCE`/`ANALYZE`/`CHECK`/`REBUILD`/`REPAIR PARTITION`) | raise — no such clause exists; see [Partitioning](../capabilities/unsupported.md#partitioning) | `PARTITION BY <expr>` via `storage_options`; maintenance by `DROP`/`DETACH`/`ATTACH PARTITION ID`; introspection via `system.parts` |
| Async backend | there is no async backend to instantiate: `AsyncClickHouseBackend(...)` raises `NotImplementedError` | sync backend + out-of-process concurrency. The two async *introspectors* in this package (`AsyncClickHouseStatusIntrospector`, `AsyncShowIntrospector`) are complete and await real queries — they just have no stock backend to run against. |

For the complete list, see [Unsupported features](../capabilities/unsupported.md).

## How to degrade conditionally in code

Callers should check via `supports_*` capability switches rather than `try/except`:

```python
if not dialect.supports_on_conflict_clause():
    # take the INSERT + ReplacingMergeTree path
    ...
```

This makes capability probing explicit and readable when switching backends (e.g.
SQLite in dev, ClickHouse in production).

## Next steps

- [Installation guide](../installation/installation.md)
- [Quick start](../getting_started/quick_start.md)

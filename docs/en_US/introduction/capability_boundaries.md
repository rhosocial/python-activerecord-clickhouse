# Capability boundaries & fail-fast

Understanding the capability boundaries is the prerequisite for using this
backend. This backend **does not try to wrap ClickHouse as an OLTP database**.

## Design principle: fail fast, not silent emulation

When a caller requests a capability ClickHouse does not support, this backend
raises `UnsupportedFeatureError`, **instead of**:

- silently ignoring (e.g. making `transaction()` a no-op while claiming it committed);
- degrading into an inefficient emulation (e.g. simulating UPSERT with
  `SELECT + DELETE + INSERT`);
- generating SQL ClickHouse would reject (e.g. `FOREIGN KEY`).

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
  `Enum8`/`Enum16`, `Array`, `Map`, `Tuple`, `Nullable(T)`, `LowCardinality(T)`, `JSON`
- DDL: `ENGINE`, `ORDER BY` sorting key, `PARTITION BY`, `TTL`, skip indexes
  (`INDEX ... USING`)
- Querying: CTE (`WITH`), window functions, `QUALIFY`, `FINAL`, `ARRAY JOIN`, set
  operations (`UNION`/`INTERSECT`/`EXCEPT`, explicit `ALL`/`DISTINCT`), `EXPLAIN`
- JSON: `JSONExtractString`/`JSONExtractRaw`/`JSON_VALUE` and the native function
  family (**not** MySQL arrow operators `->`/`->>`)
- Introspection: `system.*` tables (settings/metrics/replicas/processes/...), `SHOW`
- Client-side snowflake `Int64` IDs (replacing `AUTO_INCREMENT`)
- Lightweight UPDATE/DELETE mutations (`enable_block_number_column`/
  `enable_block_offset_column` settings required — see [Mutations](../capabilities/mutations.md))

### Not supported by ClickHouse (fail-fast)

| Capability | Behavior | Alternative |
|------------|----------|-------------|
| ACID cross-statement transactions | `transaction()` no-op; rollback raises | design per per-part atomic mutations, or use `ReplacingMergeTree` |
| `FOREIGN KEY` / `UNIQUE` constraints | DDL not emitted | dedup via table engine |
| Triggers, sequences | raise | — |
| UPSERT / `ON CONFLICT` / `INSERT IGNORE` / `REPLACE INTO` | raise | `ReplacingMergeTree` + explicit `INSERT` |
| `FOR UPDATE` row locking | raise | OLAP does not do pessimistic locking |
| `FULLTEXT` indexes / `MATCH...AGAINST` | raise | skip indexes (`tokenbf_v1` + `hasToken`) |
| `JSON_TABLE` | raise | `JSONExtract*` / `arrayJoin` |
| Spatial types (`GEOMETRY`/`POINT`/...) and `ST_*` functions | raise | store WKT as `String`, compute with ClickHouse functions |
| MySQL 9.0 `VECTOR` type and `STRING_TO_VECTOR`/`VECTOR_DIM`/`DISTANCE_*` | raise | `Array(Float32)` + `L2Distance`/`cosineDistance` |
| `SET` type / `FIND_IN_SET` | raise | `Enum16` or `Array(String)` + `has()` |
| Stored procedures / functions / `CALL` | raise | ClickHouse SQL UDFs (`CREATE FUNCTION ... AS`) |
| `LOAD DATA INFILE` / `LOAD XML` | raise | format parsers / `input()` table function |
| MySQL admin commands (`FLUSH`/`RESET`/`KILL`/`INSTALL PLUGIN`/`CLONE`/`BINLOG`/`HANDLER`/`GRANT`/`CREATE USER`) | raise | ClickHouse `SYSTEM` command family |
| `TABLE` / `VALUES` table-value constructor (MySQL 8.0.19+) | raise | `SELECT ... UNION ALL SELECT ...` |
| Whole-table maintenance (`ANALYZE`/`CHECK`/`CHECKSUM`/`REPAIR TABLE`) | raise | `OPTIMIZE TABLE ... FINAL` or `SYSTEM` commands |
| MySQL optimizer hints (`/*+ SET_VAR */`) | raise | `SETTINGS` clause |
| JSON Relational Duality Views | raise | `JSON` type + `JSONExtract*` |
| Async backend | `AsyncClickHouseBackend` placeholder raises `NotImplementedError` on instantiation | sync backend + out-of-process concurrency |

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

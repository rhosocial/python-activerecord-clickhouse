# Table Engines & Sorting Key

ClickHouse DDL consists of clauses such as `ENGINE`, `ORDER BY`, `PARTITION BY`, `TTL`, `PRIMARY KEY`, `SAMPLE BY`, and `SETTINGS`. This backend supports them natively at the dialect layer and can generate them through the core library's DDL expressions — **full SQL semantic coverage**, no hand-written SQL required.

> 📐 This backend extends the core library's `CreateTableStatement` with its own options node: the clauses are declared as **expression nodes** on `ClickHouseCreateTableOptions(table_storage_options=...)`, and `to_sql()` generates complete native ClickHouse DDL.

## MergeTree Family

| Engine | Dedup/merge semantics | Use case |
|------|--------------|---------|
| `MergeTree` | no dedup | event logs, detail records |
| `ReplacingMergeTree` | dedup by `ORDER BY`, keep last version | substitute for unique constraint (eventually consistent) |
| `CollapsingMergeTree` | collapse by sign | insert/delete/update marked streams |
| `SummingMergeTree` | sum by dimensions | pre-aggregation |
| `AggregatingMergeTree` | aggregate state by dimensions | materialized views |

> ClickHouse does **not** have `FOREIGN KEY`/`UNIQUE` constraints. Dedup is performed by the table engine during merges, not enforced as a write-time constraint. This is the root cause of the backend's `FOREIGN KEY`/`UNIQUE` fail-fast behavior.

## ORDER BY Sorting Key = Primary Key

The backend maps the model's `__primary_key__` to the `ORDER BY` sorting key.

### Sorting key rules

- **Not updatable**: `ORDER BY` columns cannot be modified by UPDATE (raises an error).
- **Fixed at creation**: determined at table creation; later changes require rebuilding the table.
- **Prefix query acceleration**: queries filtering on the sorting-key prefix can skip irrelevant granules.
- **Recommendation**: place the most frequently filtered, monotonically increasing columns (timestamps, ids) at the front of the sorting key.

## DDL Expression vs Raw SQL Comparison

Both approaches produce the **same** ClickHouse DDL, demonstrating that the expressions cover the SQL semantics:

### Raw SQL

```sql
CREATE TABLE IF NOT EXISTS events (
    ts DateTime64(6),
    id Int64,
    url String
) ENGINE = MergeTree
PARTITION BY toYYYYMM(ts)
ORDER BY (ts, id)
TTL ts + INTERVAL 90 DAY DELETE
SETTINGS enable_block_number_column = 1, enable_block_offset_column = 1;
```

### DDL Expression (equivalent)

```python
from rhosocial.activerecord.backend.expression.core import Column, FunctionCall
from rhosocial.activerecord.backend.expression.objects import Table
from rhosocial.activerecord.backend.expression.operators import RawSQL
from rhosocial.activerecord.backend.expression.statements import (
    ColumnDefinition,
    CreateTableStatement,
)
from rhosocial.activerecord.backend.impl.clickhouse.expression import (
    ClickHouseCreateTableOptions,
    ClickHouseDateTime64Type,
    ClickHouseEngineSpec,
    ClickHouseInt64Type,
    ClickHouseSetting,
    ClickHouseStorageOptionKind,
    ClickHouseStringType,
    ClickHouseTableStorageOption,
)

kind = ClickHouseStorageOptionKind

storage = [
    ClickHouseTableStorageOption(
        dialect, kind.ENGINE, value=ClickHouseEngineSpec(dialect, "MergeTree")
    ),
    ClickHouseTableStorageOption(
        dialect,
        kind.PARTITION_BY,
        value=[FunctionCall(dialect, "toYYYYMM", Column(dialect, "ts"))],
    ),
    ClickHouseTableStorageOption(
        dialect, kind.ORDER_BY, value=[Column(dialect, "ts"), Column(dialect, "id")]
    ),
    ClickHouseTableStorageOption(
        dialect, kind.TTL, value=RawSQL(dialect, "ts + INTERVAL 90 DAY DELETE")
    ),
    ClickHouseTableStorageOption(
        dialect,
        kind.SETTINGS,
        value=[
            ClickHouseSetting(dialect, "enable_block_number_column", 1),
            ClickHouseSetting(dialect, "enable_block_offset_column", 1),
        ],
    ),
]

expr = CreateTableStatement(
    dialect,
    Table(dialect, "events"),
    [
        ColumnDefinition(dialect, "ts", ClickHouseDateTime64Type(dialect, precision=6)),
        ColumnDefinition(dialect, "id", ClickHouseInt64Type(dialect)),
        ColumnDefinition(dialect, "url", ClickHouseStringType(dialect)),
    ],
    if_not_exists=True,
    table_options=ClickHouseCreateTableOptions(dialect, table_storage_options=storage),
)
sql, params = expr.to_sql()
dialect.execute(sql, params)
```

Generated SQL (one line; ClickHouse accepts either form):

```sql
CREATE TABLE IF NOT EXISTS `events` (`ts` DateTime64(6), `id` Int64, `url` String)
ENGINE = MergeTree PARTITION BY TOYYYYMM(`ts`) ORDER BY (`ts`, `id`)
TTL ts + INTERVAL 90 DAY DELETE
SETTINGS enable_block_number_column = 1, enable_block_offset_column = 1
```

## Storage Clause Nodes

One clause is one `ClickHouseTableStorageOption`. Which payload shape it takes is decided by its `option` member, and the renderer owns the keyword — the caller never writes SQL text for a clause:

| `option` | `value` | renders as |
|-----|--------|--------|
| `ENGINE` | `ClickHouseEngineSpec` | `ENGINE = MergeTree`, `ENGINE = ReplacingMergeTree(version)` |
| `PRIMARY KEY` | list of expression nodes | `PRIMARY KEY (a, b)` |
| `PARTITION BY` | list of expression nodes | `PARTITION BY toYYYYMM(ts)` |
| `ORDER BY` | list of expression nodes | `ORDER BY (ts, id)` |
| `SAMPLE BY` | one expression node | `SAMPLE BY cityHash64(user_id)` |
| `TTL` | one expression node | `TTL ts + INTERVAL 90 DAY DELETE` |
| `SETTINGS` | list of `ClickHouseSetting` | `SETTINGS index_granularity = 8192` |

Three rules the renderer enforces:

- **Canonical order.** Clauses are emitted in ClickHouse's grammar order (`ENGINE` → `PRIMARY KEY` → `PARTITION BY` → `ORDER BY` → `SAMPLE BY` → `TTL` → `SETTINGS`) regardless of the order you declared them in.
- **One clause, once.** Declaring the same `option` twice raises `ValueError` at construction instead of rendering a statement ClickHouse would reject.
- **A single node needs no parentheses.** `ORDER BY id` and `ORDER BY (ts, id)` are both valid; the renderer parenthesises only when there is more than one expression.

`ON CLUSTER` is not a storage clause: it sits between the table name and the column list, so it is declared on the options node next to the clauses:

```python
table_options=ClickHouseCreateTableOptions(
    dialect,
    on_cluster="analytics_cluster",
    table_storage_options=storage,
)
# CREATE TABLE `events` ON CLUSTER `analytics_cluster` (...) ENGINE = MergeTree ...
```

> ⚠️ The core `CreateTableStatement(storage_options=...)` slot is **refused by name** in this backend: ClickHouse has no generic `WITH (...)` storage-options clause, and accepting the dict would render a statement that silently differs from what the caller wrote. The error names `ClickHouseCreateTableOptions` as the replacement.

> 💡 *AI prompt: "`ReplacingMergeTree` dedup is eventually consistent; how does the caller ensure it reads the latest version when querying? What is the cost of the `FINAL` keyword?"*

## PARTITION BY Partitioning

Partitions are for data lifecycle management (dropping old partitions monthly) and hot/cold tiering, **not** for accelerating point queries (that's the sorting key's job):

```
PARTITION BY toYYYYMM(ts)
```

## TTL Data Expiry

```
TTL ts + INTERVAL 30 DAY DELETE
```

Expired data is automatically deleted; commonly used for log/event tables.

## ALTER TABLE

This backend supports `ALTER TABLE` ADD/DROP COLUMN (including `IF EXISTS`/`IF NOT EXISTS`), MODIFY COLUMN, etc.:

```python
from rhosocial.activerecord.backend.expression.objects import Table
from rhosocial.activerecord.backend.expression.statements import (
    AddColumnAction, AlterTableStatement, ColumnDefinition,
)
from rhosocial.activerecord.backend.impl.clickhouse.expression import ClickHouseStringType

expr = AlterTableStatement(
    dialect,
    Table(dialect, "events"),
    [AddColumnAction(dialect, ColumnDefinition(dialect, "country", ClickHouseStringType(dialect)))],
)
sql, _ = expr.to_sql()
# ALTER TABLE `events` ADD COLUMN `country` String
```

See the DDL comparison in [First CRUD application](../getting_started/first_crud.md), and [Skip indexes](skip_indexes.md) for inline `INDEX` clauses.

## Next steps

- [Skip indexes](skip_indexes.md)
- [Mutations (UPDATE/DELETE)](../capabilities/mutations.md)

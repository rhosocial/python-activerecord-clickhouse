# Table Engines & Sorting Key

ClickHouse DDL consists of clauses such as `ENGINE`, `ORDER BY`, `PARTITION BY`, `TTL`, `PRIMARY KEY`, `SAMPLE BY`, and `SETTINGS`. This backend supports them natively at the dialect layer and can generate them through the core library's DDL expressions — **full SQL semantic coverage**, no hand-written SQL required.

> 📐 This backend inherits and extends the core library's `CreateTableExpression`: declaring ClickHouse clauses through the `storage_options` dictionary, with `to_sql()` generating complete native ClickHouse DDL.

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

Both approaches generate **exactly the same** ClickHouse DDL, demonstrating that the expressions cover all SQL semantics:

### Raw SQL

```sql
CREATE TABLE IF NOT EXISTS events (
    ts DateTime64(6, 'UTC'),
    id Int64,
    url String,
    INDEX idx_url url TYPE bloom_filter GRANULARITY 4
) ENGINE = MergeTree
PARTITION BY toYYYYMM(ts)
ORDER BY (ts, id)
TTL ts + INTERVAL 90 DAY DELETE
SETTINGS enable_block_number_column = 1, enable_block_offset_column = 1;
```

### DDL Expression (equivalent)

```python
from rhosocial.activerecord.backend.expression.statements import (
    CreateTableExpression, ColumnDefinition, IndexDefinition,
)
from rhosocial.activerecord.backend.expression.parts import IndexType
from rhosocial.activerecord.backend.impl.clickhouse.expression import (
    ClickHouseInt64Type, ClickHouseStringType, ClickHouseDateTime64Type,
)

expr = CreateTableExpression(
    dialect=dialect,
    table="events",
    columns=[
        ColumnDefinition(name="ts", data_type=ClickHouseDateTime64Type(6)),
        ColumnDefinition(name="id", data_type=ClickHouseInt64Type()),
        ColumnDefinition(name="url", data_type=ClickHouseStringType()),
    ],
    indexes=[
        IndexDefinition(name="idx_url", columns=["url"], index_type="bloom_filter",
                       dialect_options={"granularity": 4}),
    ],
    storage_options={
        "ENGINE": "MergeTree",
        "PARTITION BY": "toYYYYMM(ts)",
        "ORDER BY": ["ts", "id"],
        "TTL": "ts + INTERVAL 90 DAY DELETE",
        "SETTINGS": "enable_block_number_column = 1, enable_block_offset_column = 1",
    },
    if_not_exists=True,
)
sql, _ = expr.to_sql()      # 与上方原始 SQL 等价
dialect.execute(sql)
```

### Supported `storage_options` keys

`format_table_engine_clauses` accepts (case/underscore insensitive, values inserted as-is):

| key | renders as |
|-----|--------|
| `ENGINE` | `ENGINE = <value>` |
| `ORDER BY` | `ORDER BY (col1, col2)` |
| `PARTITION BY` | `PARTITION BY <expr>` |
| `PRIMARY KEY` | `PRIMARY KEY (...)` |
| `SAMPLE BY` | `SAMPLE BY <expr>` |
| `TTL` | `TTL <expr>` |
| `SETTINGS` | `SETTINGS k = v, ...` |

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
from rhosocial.activerecord.backend.expression.statements import (
    AlterTableExpression, AlterColumn, ColumnAlterOperation,
)
expr = AlterTableExpression(dialect, "users", [
    AlterColumn("col", ColumnAlterOperation.SET_DEFAULT, new_value="ABC"),
])
sql, _ = expr.to_sql()
# ALTER TABLE users ALTER COLUMN col SET DEFAULT 'ABC'
```

See the DDL comparison in [First CRUD application](../getting_started/first_crud.md).

## Next steps

- [Skip indexes](skip_indexes.md)
- [Mutations (UPDATE/DELETE)](../capabilities/mutations.md)

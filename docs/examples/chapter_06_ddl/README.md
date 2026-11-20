# Chapter 6 — DDL

[`ddl.py`](ddl.py) builds a `CREATE TABLE` for an event log entirely from
expression nodes and runs it against the connected server.

The storage clauses are declared through `ClickHouseCreateTableOptions`:

| Clause | Node value |
|--------|------------|
| `ENGINE` | `ClickHouseEngineSpec(dialect, "MergeTree")` |
| `PARTITION BY` | expression list — `toYYYYMM(ts)` |
| `ORDER BY` | expression list — `(ts, id)` (the sorting key) |
| `TTL` | one expression node — raw `ts + INTERVAL 90 DAY DELETE` |
| `SETTINGS` | `ClickHouseSetting` list — the two block-number settings |

`CreateTableStatement.to_sql()` renders them in ClickHouse's grammar order and
returns `(sql, params)`, which are passed straight to `backend.execute()`.

After creation the script calls
`backend.introspector.get_table_engine("example_events")` to read the table's
engine, sorting key and partition key back from `system.tables`, then drops the
table in a `finally` block.

Related docs: [Table engines & sorting key](../../en_US/ddl/table_engine.md),
[Partition maintenance](../../en_US/ddl/partition_maintenance.md),
[Skip indexes](../../en_US/ddl/skip_indexes.md).

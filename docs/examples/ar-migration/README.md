# ActiveRecord-layer migration examples — ClickHouse

Offline (no server) examples of the partition-lifecycle backend suggestions for
the ClickHouse backend. Each script builds a `ClickHouseDialect`, asks for a
`suggest_partition_*` suggestion, and prints `expr.to_sql()[0]` for each
expression node. No connection and no `ctx.apply()` are used.

Run from the repository root with `PYTHONPATH=src`:

```bash
python docs/examples/ar-migration/01_partition_build.py
python docs/examples/ar-migration/02_partition_lifecycle.py
```

| Script | Scenarios |
|---|---|
| `01_partition_build.py` | Build a partitioned table via `PARTITION BY <expr>`; a plan without an expression node is declined (`False`) |
| `02_partition_lifecycle.py` | `table_drop` (`DROP TABLE`); `add` (no-op, `None`); `drop` one partition id; `retention` as an ordered drop chain; conservative `retention` with no ids (`None`); `table_alter` / `split` / `merge` unavailable (`False`) |

## ClickHouse-specific differences

- **No declarative strategy**: a partition is an inline `PARTITION BY <expr>`
  storage clause on `CREATE TABLE`. The `PartitionStrategy` argument is ignored;
  the plan carries a real `Column` expression under `expressions` (alias `keys`).
- **No `ADD PARTITION`**: a partition appears the first time a row lands in it,
  so `suggest_partition_add` answers `None` ("no action needed") rather than a
  DDL statement.
- **Maintenance by partition id**: `DROP PARTITION ID '<id>'` addresses a
  partition by the server-assigned id from `system.parts.partition_id`.
  `retention` takes an explicit, ordered `partition_ids` list; with no ids there
  is no action (`None`), and an id list without a table is declined (`False`).
- **No `REORGANIZE` / `COALESCE` / `REMOVE PARTITIONING`**: `split`, `merge` and
  `table_alter` are explicitly unsupported (`False`); to remove partitioning you
  drop the table (`table_drop`).
- This backend is synchronous only; there is no async suggestion counterpart.

All output comes from `expr.to_sql()`; the `False` / `None` states are printed as
the suggestion's tri-state value. For the shared index and the core SQLite
examples, see the core repository's `docs/examples/ar-migration/README.md`.

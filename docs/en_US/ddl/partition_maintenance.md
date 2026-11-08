# Partition Maintenance

ClickHouse partitions tables one level only. A `MergeTree`-family table declares
its partition key with `PARTITION BY <expr>` in `CREATE TABLE` (see
[Table Engines & Sorting Key](table_engine.md)), and a partition appears the
first time a row lands in it. There is no `SUBPARTITION BY`, no named
`PARTITION ... VALUES LESS THAN` boundary, and therefore no partition tree:
every partition of a table is a sibling, addressed by the id the server derives
from the key expression and reports in `system.parts.partition_id`.

That leaves `ALTER TABLE` with exactly three management verbs:

```sql
ALTER TABLE visits DROP PARTITION ID '202601';
ALTER TABLE visits DETACH PARTITION ID '202601';
ALTER TABLE visits ATTACH PARTITION ID '202601';
```

The backend exposes them through `backend.partition_maintenance`, together with
the read a retention job decides from. The service holds no table names and no
retention policy: which tables to maintain and what to keep belong to the
application.

## Listing Partitions

`list()` returns the introspector's rows — one `ClickHousePartitionInfo` per
partition id, aggregated from active parts only — so the two entry points cannot
disagree:

```python
from rhosocial.activerecord.backend.impl.clickhouse.backend import ClickHouseBackend
from rhosocial.activerecord.backend.impl.clickhouse.config import ClickHouseConnectionConfig

config = ClickHouseConnectionConfig(
    host="localhost", port=8123, database="analytics",
    username="root", password="password",
)
backend = ClickHouseBackend(connection_config=config)
backend.connect()
backend.introspect_and_adapt()

service = backend.partition_maintenance
for partition in service.list("visits"):
    print(partition.partition_id, partition.partition, partition.row_count)
```

`partition_id` is the value the three management helpers take. `partition` is
the readable key value (`'202601'` for `toYYYYMM(created_at)`), and a table
declared without `PARTITION BY` answers its single `'all'` partition. A `database`
argument names the ClickHouse database explicitly; omitting it uses the
connected database.

The listing is cached by the introspector. After a change made outside the
helper — a raw `ALTER TABLE` through `backend.execute`, or another process on
the same server — pass `refresh=True` to read the server again:

```python
service.list("visits", refresh=True)
```

## Dropping, Detaching and Attaching

```python
service.drop("visits", "202601")     # delete the partition and its rows
service.detach("visits", "202601")   # move it aside; the data survives on disk
service.attach("visits", "202601")   # take the detached partition back
```

`drop` is the operation partitioning exists for: the server tags the partition's
parts inactive and removes them in the background, rather than deleting rows one
at a time. `detach` and `attach` are a pair — the second reads the partition from
the table's `detached/` directory and returns its rows to the table. A helper
call is one statement, because ClickHouse has no transactions; the successful
partition change also drops the table's cached introspection, so the next
`list()` describes the server's current state.

A caller that holds the verb as configuration can dispatch by name:

```python
service.execute("detach", "visits", "202601")
```

## What ClickHouse Does Not Have

The verbs above are the complete inventory. `ADD PARTITION` does not exist
because a partition materialises with its first row; `TRUNCATE PARTITION` is
spelled `ALTER TABLE ... DELETE IN PARTITION ID ... WHERE ...`; and there is no
`REORGANIZE`, `EXCHANGE`, `COALESCE`, `REMOVE PARTITIONING` or `SUBPARTITION BY`.
`execute()` raises `UnsupportedFeatureError` for any other verb, and the
dialect's capability switches agree: `supports_subpartitioning()`,
`supports_range_table_partitioning()`, `supports_list_table_partitioning()` and
`supports_hash_table_partitioning()` all answer `False`, while
`supports_drop_partition()`, `supports_detach_partition()` and
`supports_attach_partition()` answer `True`. Nothing is emulated and no
statement the server would reject is rendered.

> ⚠️ Partition ids are assigned by the server. The helpers act on partitions
> that already exist; ClickHouse has no way to pre-create an empty one. A row
> written under a key value that has no partition yet simply starts that
> partition, so there is no `ensure()` step to call before writing.

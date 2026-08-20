# ClickHouse DDL Operations

The ClickHouse backend supports the same type-safe DDL expressions as the core library.

## Supported Operations

| Operation | ClickHouse Support | Notes |
|----------|--------------|-------|
| `CreateTableExpression` | ✅ Full | PRIMARY KEY, NOT NULL, UNIQUE, etc. |
| `DropTableExpression` | ✅ Full | IF EXISTS support |
| `AlterTableExpression` | ✅ Full | ADD/DROP COLUMN |
| `CreateIndexExpression` | ✅ Full | Index types (BTREE, HASH) |
| `DropIndexExpression` | ✅ Full | |
| `CreateViewExpression` | ✅ Full | ClickHouse ALGORITHM options |
| `DropViewExpression` | ✅ Full | |
| `CreateTableExpression` | ✅ Full | Partition support (RANGE, LIST, HASH, KEY) |
| `PartitionByRange` | ✅ Full | RANGE and RANGE COLUMNS partitioning |
| `PartitionByList` | ✅ Full | LIST and LIST COLUMNS partitioning |
| `PartitionByHash` | ✅ Full | HASH and LINEAR HASH partitioning |
| `PartitionByKey` | ✅ Full | KEY and LINEAR KEY partitioning |

## ClickHouse-Specific Features

### Partition Support

ClickHouse supports rich table partitioning strategies. See [Partition Documentation](../clickhouse_specific_features/partition.md).

```python
from rhosocial.activerecord.backend.impl.clickhouse.expression.partition import (
    ClickHousePartitionByRange, ClickHousePartitionDefinition, ClickHousePartitionValue,
)

partition = ClickHousePartitionByRange(
    dialect,
    keys=["created_at"],
    partitions=[
        ClickHousePartitionDefinition("p1", less_than=ClickHousePartitionValue("2024-01-01")),
        ClickHousePartitionDefinition("p2", less_than=ClickHousePartitionMaxValue()),
    ],
)

create_table = CreateTableExpression(
    dialect,
    table_name="orders",
    columns=[...],
    partition_clause=partition,
)
```

### ALGORITHM Option

ClickHouse views support ALGORITHM to control execution:

```python
from rhosocial.activerecord.backend.expression import ViewOptions, ViewAlgorithm

create_view = CreateViewExpression(
    dialect,
    view_name="optimized_view",
    query=query,
    options=ViewOptions(algorithm=ViewAlgorithm.MERGE)
)
```

### Storage Engine

ClickHouse supports specifying storage engine:

```python
create_table = CreateTableExpression(
    dialect,
    table_name="users",
    columns=columns,
    dialect_options={"engine": "InnoDB"}
)
```

## Running the Example

```bash
cd python-activerecord-clickhouse
source .venv3.8/bin/activate
PYTHONPATH=src python docs/examples/chapter_04_ddl/ddl.py
```

The example tests:
1. Create table with constraints
2. Create table with IF NOT EXISTS
3. Alter table - add column
4. Alter table - drop column
5. Drop table with IF EXISTS
6. Introspection to verify schema changes

> **Note**: ClickHouse has different ALTER TABLE support than SQLite. For full ClickHouse DDL capabilities, refer to [ClickHouse 9.6 Documentation](https://dev.clickhouse.com/doc/refman/9.6/en/sql-statements.html).
# ClickHouse Partitioning

ClickHouse supports table partitioning to improve management and query performance for large tables.

## Partitioning Strategies

| Strategy | Expression Class | Description |
|----------|-----------------|-------------|
| RANGE | `ClickHousePartitionByRange` | Range-based partitioning, e.g. `PARTITION BY RANGE (id)` |
| RANGE COLUMNS | `ClickHousePartitionByRangeColumns` | Multi-column range partitioning |
| LIST | `ClickHousePartitionByList` | Value list partitioning |
| LIST COLUMNS | `ClickHousePartitionByListColumns` | Multi-column value list partitioning |
| HASH | `ClickHousePartitionByHash` | Hash partitioning, supports LINEAR |
| KEY | `ClickHousePartitionByKey` | Like HASH, uses ClickHouse built-in hash function |

### Creating a Partitioned Table

```python
from rhosocial.activerecord.backend.impl.clickhouse.expression.partition import (
    ClickHousePartitionByRange, ClickHousePartitionDefinition, ClickHousePartitionValue,
    ClickHousePartitionMaxValue,
)

partition_by = ClickHousePartitionByRange(
    dialect,
    keys=["created_at"],
    partitions=[
        ClickHousePartitionDefinition("p_old", less_than=ClickHousePartitionValue("2024-01-01")),
        ClickHousePartitionDefinition("p_current", less_than=ClickHousePartitionMaxValue()),
    ]
)
# sql: 'PARTITION BY RANGE (created_at) (PARTITION p_old VALUES LESS THAN ("2024-01-01"), PARTITION p_current VALUES LESS THAN MAXVALUE)'
```

## Partition Lifecycle Management

### ADD PARTITION

```python
add_part = ClickHouseAddPartitionExpression(
    dialect, table="orders",
    partitions=[ClickHousePartitionDefinition("p_new", less_than=ClickHousePartitionValue("2025-01-01"))],
)
```

### DROP PARTITION

```python
drop_part = ClickHouseDropPartitionExpression(dialect, table="orders", partitions=["p_old"])
```

### EXCHANGE PARTITION

```python
exchange = ClickHouseExchangePartitionExpression(
    dialect, table="orders", partition="p_current",
    exchange_table="orders_staging", with_validation=True,
)
```

## Dialect Feature Detection

```python
if dialect.supports_table_partitioning():
    pass
if dialect.supports_exchange_partition():
    pass
```

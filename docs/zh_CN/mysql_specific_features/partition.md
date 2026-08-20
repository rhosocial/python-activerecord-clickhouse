# ClickHouse 分区

ClickHouse 支持表分区以改善大表的管理和查询性能。

## 分区策略

ClickHouse 支持以下分区策略：

| 策略 | 表达式类 | 说明 |
|------|---------|------|
| RANGE | `ClickHousePartitionByRange` | 按范围分区，如 `PARTITION BY RANGE (id)` |
| RANGE COLUMNS | `ClickHousePartitionByRangeColumns` | 按多列范围分区 |
| LIST | `ClickHousePartitionByList` | 按值列表分区 |
| LIST COLUMNS | `ClickHousePartitionByListColumns` | 按多列值列表分区 |
| HASH | `ClickHousePartitionByHash` | 哈希分区，支持 LINEAR |
| KEY | `ClickHousePartitionByKey` | 类似 HASH，使用 ClickHouse 内置哈希函数 |

### 创建分区表

```python
from rhosocial.activerecord.backend.impl.clickhouse.expression.partition import (
    ClickHousePartitionByRange, ClickHousePartitionDefinition, ClickHousePartitionValue,
    ClickHousePartitionMaxValue,
)

# RANGE 分区
partition_by = ClickHousePartitionByRange(
    dialect,
    keys=["created_at"],
    partitions=[
        ClickHousePartitionDefinition("p_old", less_than=ClickHousePartitionValue("2024-01-01")),
        ClickHousePartitionDefinition("p_current", less_than=ClickHousePartitionMaxValue()),
    ]
)

# 在 CREATE TABLE 中使用
# sql: 'PARTITION BY RANGE (created_at) (PARTITION p_old VALUES LESS THAN ("2024-01-01"), PARTITION p_current VALUES LESS THAN MAXVALUE)'
```

## 分区生命周期管理

### ADD PARTITION

```python
from rhosocial.activerecord.backend.impl.clickhouse.expression.partition import (
    ClickHouseAddPartitionExpression,
)

add_part = ClickHouseAddPartitionExpression(
    dialect,
    table="orders",
    partitions=[
        ClickHousePartitionDefinition("p_new", less_than=ClickHousePartitionValue("2025-01-01")),
    ]
)
# sql: 'ALTER TABLE orders ADD PARTITION (PARTITION p_new VALUES LESS THAN ("2025-01-01"))'
```

### DROP PARTITION

```python
from rhosocial.activerecord.backend.impl.clickhouse.expression.partition import ClickHouseDropPartitionExpression

drop_part = ClickHouseDropPartitionExpression(dialect, table="orders", partitions=["p_old"])
# sql: 'ALTER TABLE orders DROP PARTITION p_old'
```

### EXCHANGE PARTITION

```python
from rhosocial.activerecord.backend.impl.clickhouse.expression.partition import ClickHouseExchangePartitionExpression

exchange = ClickHouseExchangePartitionExpression(
    dialect, table="orders", partition="p_current",
    exchange_table="orders_staging", with_validation=True
)
# sql: 'ALTER TABLE orders EXCHANGE PARTITION p_current WITH TABLE orders_staging WITH VALIDATION'
```

## 辅助工具

```python
from rhosocial.activerecord.backend.impl.clickhouse.expression.partition_lifecycle import (
    ClickHouseAddPartitionHelper, ClickHouseDropOldestPartitionHelper,
)

# 批量添加分区（自动命名）
helper = ClickHouseAddPartitionHelper(dialect, "orders", [less_than_value1, less_than_value2])
for expr in helper:
    # 执行每个 ADD PARTITION
    pass

# 删除最旧分区
helper = ClickHouseDropOldestPartitionHelper(dialect, "orders")
for expr in helper:
    pass
```

## 分区维护

| 操作 | 表达式 | 说明 |
|------|--------|------|
| 分析 | `ClickHouseAnalyzePartitionExpression` | 更新索引统计 |
| 检查 | `ClickHouseCheckPartitionExpression` | 检查数据一致性 |
| 优化 | `ClickHouseOptimizePartitionExpression` | 回收空间 |
| 重建 | `ClickHouseRebuildPartitionExpression` | 重建分区 |
| 修复 | `ClickHouseRepairPartitionExpression` | 修复损坏 |

## 方言检查

```python
if dialect.supports_table_partitioning():
    # 支持表分区

if dialect.supports_range_columns_partitioning():
    # 支持 RANGE COLUMNS 分区

if dialect.supports_exchange_partition():
    # 支持 EXCHANGE PARTITION
```

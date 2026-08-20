# ClickHouse DDL 操作

ClickHouse 后端支持与核心库相同的类型安全 DDL 表达式。

## 支持的操作

| 操作 | ClickHouse 支持 | 备注 |
|----------|--------------|-------|
| `CreateTableExpression` | ✅ 完整 | PRIMARY KEY, NOT NULL, UNIQUE 等 |
| `DropTableExpression` | ✅ 完整 | IF EXISTS 支持 |
| `AlterTableExpression` | ✅ 完整 | ADD/DROP COLUMN |
| `CreateIndexExpression` | ✅ 完整 | 索引类型 (BTREE, HASH) |
| `DropIndexExpression` | ✅ 完整 | |
| `CreateViewExpression` | ✅ 完整 | ClickHouse ALGORITHM 选项 |
| `DropViewExpression` | ✅ 完整 | |
| `CreateTableExpression` | ✅ 完整 | 分区支持（RANGE, LIST, HASH, KEY） |
| `PartitionByRange` | ✅ 完整 | RANGE 和 RANGE COLUMNS 分区 |
| `PartitionByList` | ✅ 完整 | LIST 和 LIST COLUMNS 分区 |
| `PartitionByHash` | ✅ 完整 | HASH 和 LINEAR HASH 分区 |
| `PartitionByKey` | ✅ 完整 | KEY 和 LINEAR KEY 分区 |

## ClickHouse 特性

### 分区支持

ClickHouse 支持丰富的表分区策略。详见 [分区文档](../clickhouse_specific_features/partition.md)。

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
    ]
)

create_table = CreateTableExpression(
    dialect,
    table_name="orders",
    columns=[...],
    partition_clause=partition,
)
```

### ALGORITHM 选项

ClickHouse 视图支持 ALGORITHM 来控制执行方式：

```python
from rhosocial.activerecord.backend.expression import ViewOptions, ViewAlgorithm

create_view = CreateViewExpression(
    dialect,
    view_name="optimized_view",
    query=query,
    options=ViewOptions(algorithm=ViewAlgorithm.MERGE)
)
```

### 存储引擎

ClickHouse 支持指定存储引擎：

```python
create_table = CreateTableExpression(
    dialect,
    table_name="users",
    columns=columns,
    dialect_options={"engine": "InnoDB"}
)
```

## 运行示例

```bash
cd python-activerecord-clickhouse
source .venv3.8/bin/activate
PYTHONPATH=src python docs/examples/chapter_04_ddl/ddl.py
```

示例测试：
1. 创建带约束的表
2. 使用 IF NOT EXISTS 创建表
3. ALTER TABLE - 添加列
4. ALTER TABLE - 删除列
5. 使用 IF EXISTS 删除表
6. 内省验证架构变化

> **注意**：ClickHouse 具有与 SQLite 不同的 ALTER TABLE 支持。完整的 ClickHouse DDL 功能请参考 [ClickHouse 9.6 文档](https://dev.clickhouse.com/doc/refman/9.6/en/sql-statements.html)。
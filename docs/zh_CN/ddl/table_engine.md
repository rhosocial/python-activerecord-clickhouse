# 表引擎与排序键

ClickHouse 的 DDL 由 `ENGINE`、`ORDER BY`、`PARTITION BY`、`TTL`、`PRIMARY KEY`、`SAMPLE BY`、`SETTINGS` 等子句组成。本后端在方言层原生支持，且能通过核心库的 DDL 表达式生成——**SQL 语义全覆盖**，无需手写 SQL。

> 📐 本后端继承并扩展了核心库的 `CreateTableExpression`：通过 `storage_options` 字典声明 ClickHouse 子句，`to_sql()` 生成完整 ClickHouse 原生 DDL。

## MergeTree 家族

| 引擎 | 去重/合并语义 | 适用场景 |
|------|--------------|---------|
| `MergeTree` | 不去重 | 事件日志、明细 |
| `ReplacingMergeTree` | 按 `ORDER BY` 去重保留最后版本 | 替代唯一约束（最终一致）|
| `CollapsingMergeTree` | 按 sign 折叠 | 增删改标记流 |
| `SummingMergeTree` | 按维度求和 | 预聚合 |
| `AggregatingMergeTree` | 按维度聚合状态 | 物化视图 |

> ClickHouse **没有** `FOREIGN KEY`/`UNIQUE` 约束。去重由表引擎在合并时完成，不是写入时强约束。这是本后端 `FOREIGN KEY`/`UNIQUE` fail-fast 的根因。

## ORDER BY 排序键 = 主键

后端把模型的 `__primary_key__` 映射到 `ORDER BY` 排序键。

### 排序键规则

- **不可更新**：`ORDER BY` 列不能被 UPDATE 修改（会抛错）。
- **建表即定**：建表时确定，后续修改需重建表。
- **前缀查询加速**：按排序键前缀过滤的查询能跳过无关 granule。
- **建议**：把过滤最频繁、基数递增的列（时间戳、id）放排序键前部。

## DDL 表达式 vs 原始 SQL 对照

两种方式生成**完全相同**的 ClickHouse DDL，证明表达式覆盖全部 SQL 语义：

### 原始 SQL

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

### DDL 表达式（等价）

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

### `storage_options` 支持的 key

`format_table_engine_clauses` 接受（大小写/下划线不敏感，值原样插入）：

| key | 渲染为 |
|-----|--------|
| `ENGINE` | `ENGINE = <value>` |
| `ORDER BY` | `ORDER BY (col1, col2)` |
| `PARTITION BY` | `PARTITION BY <expr>` |
| `PRIMARY KEY` | `PRIMARY KEY (...)` |
| `SAMPLE BY` | `SAMPLE BY <expr>` |
| `TTL` | `TTL <expr>` |
| `SETTINGS` | `SETTINGS k = v, ...` |

> 💡 *AI 提示词："`ReplacingMergeTree` 的去重是最终一致的，调用方查询时如何确保拿到最新版本？`FINAL` 关键字有什么代价？"*

## PARTITION BY 分区

分区用于数据生命周期管理（按月删除旧分区）与冷热分层，**不是为了** 加速点查（那是排序键的事）：

```
PARTITION BY toYYYYMM(ts)
```

## TTL 数据过期

```
TTL ts + INTERVAL 30 DAY DELETE
```

到期数据自动删除，常用于日志/事件表。

## ALTER TABLE

本后端支持 `ALTER TABLE` 的 ADD/DROP COLUMN（含 `IF EXISTS`/`IF NOT EXISTS`）、MODIFY COLUMN 等：

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

详见 [第一个 CRUD 应用](../getting_started/first_crud.md) 的 DDL 对照。

## 下一步

- [跳数索引](skip_indexes.md)
- [变更（UPDATE/DELETE）](../capabilities/mutations.md)

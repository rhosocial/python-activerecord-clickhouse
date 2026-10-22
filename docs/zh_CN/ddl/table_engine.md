# 表引擎与排序键

ClickHouse 的 DDL 由 `ENGINE`、`ORDER BY`、`PARTITION BY`、`TTL`、`PRIMARY KEY`、`SAMPLE BY`、`SETTINGS` 等子句组成。本后端在方言层原生支持，且能通过核心库的 DDL 表达式生成——**SQL 语义全覆盖**，无需手写 SQL。

> 📐 本后端扩展了核心库的 `CreateTableStatement`，并提供了自己的选项节点：子句以**表达式节点**的形式声明在 `ClickHouseCreateTableOptions(table_storage_options=...)` 上，`to_sql()` 生成完整 ClickHouse 原生 DDL。

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

两种方式生成**相同**的 ClickHouse DDL，证明表达式覆盖了这些 SQL 语义：

### 原始 SQL

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

### DDL 表达式（等价）

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

生成的 SQL（单行；ClickHouse 两种形式都接受）：

```sql
CREATE TABLE IF NOT EXISTS `events` (`ts` DateTime64(6), `id` Int64, `url` String)
ENGINE = MergeTree PARTITION BY TOYYYYMM(`ts`) ORDER BY (`ts`, `id`)
TTL ts + INTERVAL 90 DAY DELETE
SETTINGS enable_block_number_column = 1, enable_block_offset_column = 1
```

## 存储子句节点

一个子句对应一个 `ClickHouseTableStorageOption`。它取哪种载荷由 `option` 成员决定，而关键字由渲染器负责——调用方从不自己拼子句的 SQL 文本：

| `option` | `value` | 渲染为 |
|-----|--------|--------|
| `ENGINE` | `ClickHouseEngineSpec` | `ENGINE = MergeTree`、`ENGINE = ReplacingMergeTree(version)` |
| `PRIMARY KEY` | 表达式节点列表 | `PRIMARY KEY (a, b)` |
| `PARTITION BY` | 表达式节点列表 | `PARTITION BY toYYYYMM(ts)` |
| `ORDER BY` | 表达式节点列表 | `ORDER BY (ts, id)` |
| `SAMPLE BY` | 单个表达式节点 | `SAMPLE BY cityHash64(user_id)` |
| `TTL` | 单个表达式节点 | `TTL ts + INTERVAL 90 DAY DELETE` |
| `SETTINGS` | `ClickHouseSetting` 列表 | `SETTINGS index_granularity = 8192` |

渲染器强制三条规则：

- **规范顺序**：无论声明顺序如何，子句一律按 ClickHouse 语法顺序输出（`ENGINE` → `PRIMARY KEY` → `PARTITION BY` → `ORDER BY` → `SAMPLE BY` → `TTL` → `SETTINGS`）。
- **一个子句只出现一次**：同一个 `option` 声明两次会在构造时抛 `ValueError`，而不是渲染出一条 ClickHouse 会拒绝的语句。
- **单个表达式不加括号**：`ORDER BY id` 与 `ORDER BY (ts, id)` 都合法；只有多于一个表达式时才加括号。

`ON CLUSTER` 不是存储子句：它位于表名与列清单之间，因此与子句一样声明在选项节点上：

```python
table_options=ClickHouseCreateTableOptions(
    dialect,
    on_cluster="analytics_cluster",
    table_storage_options=storage,
)
# CREATE TABLE `events` ON CLUSTER `analytics_cluster` (...) ENGINE = MergeTree ...
```

> ⚠️ 核心 `CreateTableStatement(storage_options=...)` 槽位在本后端被**按名拒绝**：ClickHouse 没有通用的 `WITH (...)` 存储选项子句，接受字典只会渲染出一条与调用方所写内容悄悄不同的语句。错误信息会直接指出替代方案 `ClickHouseCreateTableOptions`。

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

详见 [第一个 CRUD 应用](../getting_started/first_crud.md) 的 DDL 对照，以及[跳数索引](skip_indexes.md)中的内联 `INDEX` 子句。

## 下一步

- [跳数索引](skip_indexes.md)
- [变更（UPDATE/DELETE）](../capabilities/mutations.md)

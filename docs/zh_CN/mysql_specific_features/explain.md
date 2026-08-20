# EXPLAIN 支持

## 概述

ClickHouse 后端提供对 `EXPLAIN` 语句的完整支持，可用于分析查询性能并查看执行计划。该功能通过统一的 API 与 ActiveRecord 查询构建器集成，同时暴露 ClickHouse 特有的行为。

主要能力：
- 基础 `EXPLAIN`，用于查看执行计划
- `EXPLAIN ANALYZE`，返回实际运行时统计数据（需要 ClickHouse 8.0.18+）
- 多种输出格式：`TEXT`、`JSON`（5.6.5+）、`TREE`（8.0.16+）
- 结构化结果解析，通过 `ClickHouseExplainResult` 访问
- 索引使用分析辅助方法
- 同步与异步双模式支持

## 基本用法

### 通过查询构建器使用 EXPLAIN

```python
from rhosocial.activerecord.backend.expression.statements import ExplainFormat

# 简单 EXPLAIN — 返回 ClickHouseExplainResult
result = User.query().explain().all()

# 查看生成的 SQL 前缀
print(result.sql)  # EXPLAIN SELECT ...

# 打印执行耗时（秒）
print(result.duration)
```

### 读取结果行

```python
result = User.query().explain().all()

for row in result.rows:
    print(row.id, row.select_type, row.table, row.type)
    print("  key:", row.key, "rows:", row.rows, "extra:", row.extra)
```

每行是一个 `ClickHouseExplainRow`，对应 ClickHouse 12 列固定格式输出：

| 字段 | 类型 | 说明 |
|---|---|---|
| `id` | `Optional[int]` | 查询块标识符 |
| `select_type` | `Optional[str]` | 查询类型（`SIMPLE`、`PRIMARY`、`SUBQUERY` 等） |
| `table` | `Optional[str]` | 表名 |
| `partitions` | `Optional[str]` | 匹配的分区 |
| `type` | `Optional[str]` | 连接类型（`ALL`、`index`、`ref`、`eq_ref`、`const` 等） |
| `possible_keys` | `Optional[str]` | 候选索引 |
| `key` | `Optional[str]` | 实际选用的索引 |
| `key_len` | `Optional[str]` | 所选索引的长度 |
| `ref` | `Optional[str]` | 与索引进行比较的列 |
| `rows` | `Optional[int]` | 预估检查的行数 |
| `filtered` | `Optional[float]` | 表条件过滤后剩余行的百分比 |
| `extra` | `Optional[str]` | 附加信息（字段别名为 `Extra`） |

## 输出格式

### TEXT 格式（默认）

```python
# 默认情况下不生成 FORMAT 子句
result = User.query().explain().all()
# 生成: EXPLAIN SELECT ...
```

### JSON 格式（ClickHouse 5.6.5+）

```python
result = User.query().explain(format=ExplainFormat.JSON).all()
# 生成: EXPLAIN FORMAT=JSON SELECT ...
```

### TREE 格式（ClickHouse 8.0.16+）

```python
result = User.query().explain(format=ExplainFormat.TREE).all()
# 生成: EXPLAIN FORMAT=TREE SELECT ...
```

**重要说明：**
- 在低版本 ClickHouse 上请求不支持的格式时，服务器将返回错误。
- 使用前可通过 `backend.dialect.supports_explain_format("TREE")` 检查可用性。

## EXPLAIN ANALYZE（ClickHouse 8.0.18+）

`EXPLAIN ANALYZE` 会实际执行查询，并在代价估算的基础上同时返回真实的运行时统计数据，可用于对比预估行数与实际行数及耗时。

```python
# 基础 ANALYZE
result = User.query().explain(analyze=True).all()
# 生成: EXPLAIN ANALYZE SELECT ...

# 带 JSON 格式的 ANALYZE（ClickHouse 8.0.21+）
result = User.query().explain(analyze=True, format=ExplainFormat.JSON).all()
# 生成: EXPLAIN ANALYZE FORMAT=JSON SELECT ...
```

**重要说明：**
- `EXPLAIN ANALYZE` **会真正执行查询**。在生产环境中对写操作使用时请谨慎评估副作用。
- 需要 ClickHouse 8.0.18+，在低版本上服务器将返回错误。

## 生成的 SQL 语法

ClickHouse 使用平铺式（无括号）选项语法，与 PostgreSQL 的括号式语法不同：

```
EXPLAIN [ANALYZE] [FORMAT=TEXT|JSON|TREE] <语句>
```

`ANALYZE` 关键字始终在 `FORMAT` 之前：

```python
# 仅 analyze=True
# → EXPLAIN ANALYZE SELECT ...

# 仅指定 format
# → EXPLAIN FORMAT=JSON SELECT ...

# 同时指定两者
# → EXPLAIN ANALYZE FORMAT=JSON SELECT ...
```

## 索引使用分析

`ClickHouseExplainResult` 提供基于启发式规则的索引使用快速评估，规则依赖 `type` 列、`key` 列及 `extra` 字段文本：

```python
result = User.query().where(User.c.email == "alice@example.com").explain().all()

usage = result.analyze_index_usage()
print(usage)  # "full_scan" | "index_with_lookup" | "covering_index"

# 便捷属性
if result.is_full_scan:
    print("警告：检测到全表扫描")

if result.is_covering_index:
    print("最优：正在使用覆盖索引")

if result.is_index_used:
    print("索引已被使用")
```

### 索引使用判断规则

| 条件 | `analyze_index_usage()` 返回值 |
|---|---|
| `type == "ALL"` | `"full_scan"` |
| `key` 为 `None`（非 ALL） | `"full_scan"` |
| `key` 不为 `None` 且 `extra` 含 `"Using index"` | `"covering_index"` |
| `key` 不为 `None`，无覆盖索引标志 | `"index_with_lookup"` |

## 异步 API

异步后端提供相同接口，在终止方法处使用 `await`：

```python
async def analyze_queries():
    # 简单异步 EXPLAIN
    result = await User.query().explain().all_async()

    # 带 JSON 格式的 ANALYZE
    result = await User.query().explain(
        analyze=True,
        format=ExplainFormat.JSON
    ).all_async()

    for row in result.rows:
        print(row.table, row.type, row.key)
```

## 运行时检查格式支持

使用 `dialect` 方法在调用前检查版本相关选项：

```python
dialect = backend.dialect

# 检查 ANALYZE 支持
if dialect.supports_explain_analyze():
    result = User.query().explain(analyze=True).all()

# 检查特定格式
if dialect.supports_explain_format("TREE"):
    result = User.query().explain(format=ExplainFormat.TREE).all()
else:
    result = User.query().explain(format=ExplainFormat.TEXT).all()
```

## 与复杂查询组合使用

EXPLAIN 可与完整的查询构建器链式调用配合：

```python
# JOIN 查询
result = (
    User.query()
    .join(Order, User.c.id == Order.c.user_id)
    .where(User.c.status == "active")
    .explain(format=ExplainFormat.JSON)
    .all()
)

# GROUP BY / 聚合
result = (
    Order.query()
    .group_by(Order.c.user_id)
    .explain(analyze=True)
    .count(Order.c.id)
)

# 子查询
result = (
    User.query()
    .where(User.c.id.in_(Order.query().select(Order.c.user_id)))
    .explain()
    .all()
)
```

## 版本兼容性

| 功能 | 最低 ClickHouse 版本 |
|---|---|
| 基础 `EXPLAIN` | 所有支持版本 |
| `EXPLAIN FORMAT=JSON` | 5.6.5 |
| `EXPLAIN FORMAT=TREE` | 8.0.16 |
| `EXPLAIN ANALYZE` | 8.0.18 |
| `EXPLAIN ANALYZE FORMAT=JSON` | 8.0.21 |

## API 参考

### ClickHouse 使用的 `ExplainOptions` 字段

| 字段 | 类型 | 默认值 | 说明 |
|---|---|---|---|
| `analyze` | `bool` | `False` | 生成 `ANALYZE` 关键字（需要 8.0.18+） |
| `format` | `Optional[ExplainFormat]` | `None` | 输出格式（`TEXT`/`JSON`/`TREE`） |

其他 `ExplainOptions` 字段（如 `verbose`、`buffers`、`timing`）会被接受，但 ClickHouse 方言不会将其写入生成的 SQL。

### `ClickHouseExplainResult` 方法

| 方法 / 属性 | 说明 |
|---|---|
| `rows` | `List[ClickHouseExplainRow]`，解析后的结果行 |
| `sql` | 被 EXPLAIN 的完整 SQL 字符串 |
| `duration` | 查询执行耗时（秒） |
| `raw_rows` | 驱动返回的原始行数据 |
| `analyze_index_usage()` | 返回 `"full_scan"`、`"index_with_lookup"` 或 `"covering_index"` |
| `is_full_scan` | `analyze_index_usage() == "full_scan"` 时为 `True` |
| `is_index_used` | 有任意索引被使用时为 `True` |
| `is_covering_index` | 使用了覆盖索引时为 `True` |

### `ClickHouseDialect` 方法

| 方法 | 返回值 | 说明 |
|---|---|---|
| `supports_explain_analyze()` | `bool` | 服务器版本 ≥ 8.0.18 时为 `True` |
| `supports_explain_format(fmt)` | `bool` | 指定格式字符串受支持时为 `True` |
| `format_explain_statement(expr)` | `str` | 构建 `EXPLAIN [ANALYZE] [FORMAT=X]` 前缀 |

## 最佳实践

- **程序化分析推荐使用 JSON 格式。** `FORMAT=JSON` 提供结构化的计划树，比纯文本更易解析。
- **`EXPLAIN ANALYZE` 仅用于开发阶段。** 该语句会真正执行查询，仅在需要实际行数和耗时数据时使用。
- **混合版本环境中使用前检查格式支持。** 在多版本 ClickHouse 环境下，始终调用 `dialect.supports_explain_format()` 进行检查。
- **结合索引分析。** 在集成测试中使用 `result.is_full_scan` 作为快速冒烟测试，及时发现意外的全表扫描。

💡 *AI 提示词：说明如何在 rhosocial-activerecord 中使用 ClickHouse 8.0 的 EXPLAIN ANALYZE FORMAT=JSON 诊断慢查询。*

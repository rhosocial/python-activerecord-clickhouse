# 两个时刻之间的带符号秒数

`seconds_between` 只回答一个问题：从 `start` 到 `end` 经过了多少秒，符号表示方向，小数被保留。它是 `date_diff` 的小数版本（`date_diff("second", ...)` 仍按整秒计算；需要整秒的调用方自行取整）。

```python
from rhosocial.activerecord.backend.expression import Column, seconds_between

elapsed = seconds_between(
    dialect,
    Column(dialect, "queued_at"),
    Column(dialect, "started_at"),
).as_("queue_seconds")
sql, params = elapsed.to_sql()
# sql: "dateDiff('millisecond', `queued_at`, `started_at`) / 1000.0 AS `queue_seconds`"
# params: ()
```

也可以从列这一侧发起；接收者必须是时间戳列（`TimestampColumn`，或通过 `Model.c.<field>` 取得的 `datetime` 字段）：

```python
queue_seconds = queued_at.seconds_between(started_at)
```

## ClickHouse 的拼写

```sql
dateDiff('millisecond', start, end) / 1000.0
```

`dateDiff` 只按整单位计数，因此本后端向它索取 ClickHouse 能给出的最细单位——毫秒——再除以 `1000.0`。除法把整数计数变成 `Float64`，这正是小数得以保留的原因；若直接用 `dateDiff(..., 'second', ...)`，亚秒级跨度会被舍入为 `0`。

符号不需要特殊处理。`dateDiff(unit, start, end)` 就是 `end - start`，所以 `end` 早于 `start` 时同样这段 SQL 会减出负数：

| 情形 | 结果 |
|------|------|
| `end` 晚于 `start` | 正数 |
| `end` 早于 `start` | 负数 |
| 同一时刻 | `0` |
| 任一侧带小数 | 保留到毫秒（见下） |

`DateTime` 或 `Date` 列没有小数部分，结果是整秒。`DateTime64(3)` 保留毫秒，结果也带毫秒。`DateTime64(6)` 存储微秒，但这里的 `dateDiff` 只按毫秒计数：微秒被截断而不是四舍五入。需要高于毫秒的精度时，应在该精度上计算差值（`dateDiff('microsecond', ...) / 1000000.0`），而不是指望这个节点越过拼写所指定的最细单位。

## 绑定参数

SQL 先写 `start` 再写 `end`，所以绑定参数也按这个顺序收集：

```python
expr = seconds_between(
    dialect,
    Literal(dialect, "2026-01-01 00:00:00"),
    Literal(dialect, "2026-01-02 00:00:00"),
)
sql, params = expr.to_sql()
# sql: "dateDiff('millisecond', %s, %s) / 1000.0"
# params: ("2026-01-01 00:00:00", "2026-01-02 00:00:00")
```

`end` 在结果中是较晚的值，却是 SQL 里的第二个占位符；参数顺序跟随语句文本，而不是节点的角色名称。

## 参见

- 核心库的 `docs/en_US/backend/expression/functions.md`，其中说明 `seconds_between` 节点与后端 formatter 契约。
- [查询概览](README.md)，了解 ClickHouse 专属的查询能力。

# Nullable 与可选字段

ClickHouse 与传统 OLTP 数据库在 NULL 处理上有重要差异，理解它们能避免数据被静默改写。

## 可选字段映射到 `Nullable(T)`

模型上的 `Optional[T]` 字段会映射到 ClickHouse 的 `Nullable(T)` 列：

```python
class User(ActiveRecord):
    age: Optional[int] = None      # -> Nullable(Int32)
    bio: Optional[str] = None      # -> Nullable(String)
```

对应 DDL：

```sql
CREATE TABLE users (
    age Nullable(Int32),
    bio Nullable(String)
) ENGINE = MergeTree ORDER BY ...
```

## ⚠️ NULL 写入非 Nullable 列会变成空值

这是 ClickHouse 的语义，**不是** 后端 bug：往一个非 `Nullable` 的 `String` 列写 `None`，ClickHouse 会存成空字符串 `''`；往非 `Nullable` 的数值列写 `None`，会存成 `0`。

```python
class User(ActiveRecord):
    username: str          # 非 Optional -> String（非 Nullable）

User(username=None).save()   # ClickHouse 存成 ''，不会报错！
```

如果你需要区分"空"与"未提供"，必须把列声明为 `Nullable`（即模型字段用 `Optional`）。

## 为什么排序键不应 Nullable

`ORDER BY` 排序键列**不建议** 用 `Nullable(T)`：

- `Nullable` 列在排序时 NULL 会排在特定位置，行为与预期不同；
- `Nullable` 会拖慢 MergeTree 合并；
- 排序键本身是不可更新的，主键列更应是非空稳定值。

建模建议：把主键（`id`）与排序键列设为非空 `Int64`/`String`，仅把次要数据列设为 `Nullable`。

## `LowCardinality(T)` 与 `Nullable(T)` 的取舍

对于枚举式低基数字符串（如状态码、类别），优先用 `LowCardinality(String)` 而非 `Nullable(String)`：

- `LowCardinality` 去重存储，查询更快；
- 不需要"未提供"语义时，不要加 `Nullable`；
- 二者可叠加：`LowCardinality(Nullable(String))`，但通常无必要。

## 默认值与 `Optional` 的区别

Pydantic 的 `Field(default=...)` 与 `Optional` 是正交的：

```python
class User(ActiveRecord):
    age: Optional[int] = None          # 列 Nullable(Int32)，默认 NULL
    score: int = 0                     # 列 Int32，默认 0（非 NULL）
    status: str = "active"             # 列 String，默认 'active'
```

`Optional` 决定列是否 `Nullable`，`default` 决定未提供时的写入值。

## 下一步

- [字段类型映射](field_types.md)
- [变更（UPDATE/DELETE）](../capabilities/mutations.md)

# 数组、Map、Tuple 查询

ClickHouse 的列式复合类型（`Array`/`Map`/`Tuple`）是其 OLAP 强项，本后端在查询中直接渲染 ClickHouse 原生函数。

## Array 数组

```python
class Event(ActiveRecord):
    tags: list[str]   # Array(String)

# 查询包含某标签的行
rows = Event.query().where(
    FunctionCall(dialect, "has", Column(dialect, "tags"), Literal(dialect, "clickhouse"))
).all()
```

常用数组函数：

| 函数 | 用途 |
|------|------|
| `has(arr, x)` | 数组是否含 x |
| `hasAll(arr, [x, y])` | 是否含全部 |
| `indexOf(arr, x)` | x 的下标 |
| `arrayJoin(arr)` | 将数组元素展开为多行（配合 `FROM ... ARRAY JOIN`）|
| `length(arr)` | 数组长度 |
| `arrayConcat(a, b)` | 拼接 |

### ARRAY JOIN

把数组展开为多行：

```sql
SELECT tag FROM events ARRAY JOIN tags AS tag
```

后端 dialect 提供 `ARRAY JOIN` 子句渲染。

## Map 映射

```python
class Counter(ActiveRecord):
    counts: dict[str, int]   # Map(String, Int32)

# 取某 key 的值
rows = Counter.query().select(
    Column(dialect, "counts")[Literal(dialect, "clicks")]   # map[key]
).all()
```

ClickHouse Map 用 `[]` 或 `mapKeys`/`mapValues`：

| 函数 | 用途 |
|------|------|
| `map[key]` | 取值 |
| `mapKeys(m)` | 键数组 |
| `mapValues(m)` | 值数组 |
| `mapContains(m, key)` | 是否含 key |

## Tuple 元组

```python
class Point(ActiveRecord):
    coord: tuple   # Tuple(Float64, Float64)

# 按下标取
rows = Point.query().select(
    Column(dialect, "coord")[1]   # 元组第 1 个元素
).all()
```

Tuple 用 `tupleElement(t, n)` 或 `t.n` 访问。

## 嵌入向量（替代 MySQL VECTOR）

ClickHouse 没有 MySQL 9.0 的 `VECTOR` 类型。把嵌入存为 `Array(Float32)`，用原生距离函数：

| 计算 | ClickHouse 函数 |
|------|----------------|
| 欧氏距离 | `L2Distance(a, b)` |
| 余弦距离 | `cosineDistance(a, b)` |
| 点积 | `dotProduct(a, b)` |

```sql
SELECT id, L2Distance(embedding, [0.1, 0.2, ...]) AS dist
FROM items ORDER BY dist LIMIT 10
```

配合 skip index（如 `vector_similarity`）可做近似最近邻。

## 下一步

- [JSON 查询](json.md)
- [表引擎与排序键](../ddl/table_engine.md)

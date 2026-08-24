# Arrays, Maps, Tuples

ClickHouse's columnar composite types (`Array`/`Map`/`Tuple`) are its OLAP
strength; this backend renders them as native ClickHouse functions in queries.

## Array

```python
class Event(ActiveRecord):
    tags: list[str]   # Array(String)

# query rows containing a tag
rows = Event.query().where(
    FunctionCall(dialect, "has", Column(dialect, "tags"), Literal(dialect, "clickhouse"))
).all()
```

Common array functions:

| Function | Purpose |
|----------|---------|
| `has(arr, x)` | array contains x |
| `hasAll(arr, [x, y])` | contains all |
| `indexOf(arr, x)` | index of x |
| `arrayJoin(arr)` | expand array elements into rows (with `FROM ... ARRAY JOIN`) |
| `length(arr)` | array length |
| `arrayConcat(a, b)` | concatenate |

### ARRAY JOIN

Expand an array into rows:

```sql
SELECT tag FROM events ARRAY JOIN tags AS tag
```

The backend dialect supports the `ARRAY JOIN` clause rendering.

## Map

```python
class Counter(ActiveRecord):
    counts: dict[str, int]   # Map(String, Int32)

# get a key's value
rows = Counter.query().select(
    Column(dialect, "counts")[Literal(dialect, "clicks")]   # map[key]
).all()
```

ClickHouse Map uses `[]` or `mapKeys`/`mapValues`:

| Function | Purpose |
|----------|---------|
| `map[key]` | get value |
| `mapKeys(m)` | keys array |
| `mapValues(m)` | values array |
| `mapContains(m, key)` | contains key |

## Tuple

```python
class Point(ActiveRecord):
    coord: tuple   # Tuple(Float64, Float64)

# access by index
rows = Point.query().select(
    Column(dialect, "coord")[1]   # 1st element of tuple
).all()
```

Tuple is accessed via `tupleElement(t, n)` or `t.n`.

## Embedding vectors (replacing MySQL VECTOR)

ClickHouse has no MySQL 9.0 `VECTOR` type. Store embeddings as `Array(Float32)`
and use native distance functions:

| Compute | ClickHouse function |
|---------|--------------------|
| Euclidean distance | `L2Distance(a, b)` |
| Cosine distance | `cosineDistance(a, b)` |
| Dot product | `dotProduct(a, b)` |

```sql
SELECT id, L2Distance(embedding, [0.1, 0.2, ...]) AS dist
FROM items ORDER BY dist LIMIT 10
```

Pair with a skip index (e.g. `vector_similarity`) for approximate nearest neighbor.

## Next steps

- [JSON queries](json.md)
- [Table engines & sorting key](../ddl/table_engine.md)

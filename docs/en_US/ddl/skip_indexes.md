# Skip Indexes

ClickHouse's skip index is not an OLTP B-tree index; it is "skip" metadata on MergeTree granules, used to accelerate filtering.

## Basic syntax

```sql
CREATE TABLE events (
    ts DateTime,
    url String,
    INDEX idx_url url TYPE bloom_filter GRANULARITY 4,
    INDEX idx_ts ts TYPE minmax GRANULARITY 4
) ENGINE = MergeTree ORDER BY (ts)
```

`INDEX ... USING type` is supported at this backend's dialect layer.

## Common skip index types

| Type | Purpose | Suitable columns |
|------|------|--------|
| `minmax` | stores granule min/max values, skip ranges during filtering | numeric/time |
| `set(max_rows)` | stores the set of distinct granule values | low cardinality |
| `bloom_filter` | Bloom filter, judge possible existence | any equality |
| `bloom_filter(bf)` | parameterized Bloom | same as above |
| `tokenbf_v1` | tokenizing Bloom | text token search |
| `ngrambf_v1(n, sz, b, f)` | n-gram Bloom | substring search |

## Substitute for FULLTEXT

ClickHouse does **not** support MySQL's `FULLTEXT` index and `MATCH...AGAINST` (this backend fails fast). Use `tokenbf_v1` + `hasToken` for text search:

```sql
CREATE TABLE docs (
    body String,
    INDEX idx_body body TYPE tokenbf_v1(3, 256, 2, 0) GRANULARITY 4
) ENGINE = MergeTree ORDER BY id;

SELECT * FROM docs WHERE hasToken(body, 'clickhouse');
```

## Vector approximate nearest neighbor (substitute for MySQL VECTOR index)

Use a `vector_similarity` skip index (with an `Array(Float32)` column) for ANN search, instead of MySQL's `VECTOR` type and `DISTANCE_*` functions.

## Cost of skip indexes

- Not exact indexes; may produce false positives (requires table lookups for filtering);
- Maintaining metadata on write has overhead;
- Suitable for scenarios where "most granules are filtered out"; not suitable for high selectivity queries.

## Next steps

- [Table engines & sorting key](table_engine.md)
- [Arrays, Maps, Tuples](../querying/arrays_maps.md)

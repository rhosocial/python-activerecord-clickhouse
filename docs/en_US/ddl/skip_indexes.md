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

The index-type keyword is `TYPE`, not MySQL's `USING`: `INDEX i (s) TYPE minmax GRANULARITY 4` is accepted, while `INDEX i (s) USING minmax` is a `SYNTAX_ERROR` on 26.7.3.19.

## Common skip index types

| Type | Purpose | Suitable columns |
|------|------|--------|
| `minmax` | stores granule min/max values, skip ranges during filtering | numeric/time |
| `set(max_rows)` | stores the set of distinct granule values | low cardinality |
| `bloom_filter` | Bloom filter, judge possible existence | any equality |
| `bloom_filter(bf)` | parameterized Bloom | same as above |
| `text(tokenizer = ...)` | inverted index over tokenized text | full-text search |
| `ngrambf_v1(n, sz, b, f)` | n-gram Bloom (deprecated for full text from 26.2) | substring search |
| `tokenbf_v1(sz, f, seed)` | tokenizing Bloom (deprecated for full text from 26.2) | word search |

The server's own list of what it accepts is in the error text: declaring an
unknown type answers ``Unknown Index type 'fulltext'. Available index types:
hypothesis, text, vector_similarity, bloom_filter, sparse_grams, tokenbf_v1,
ngrambf_v1, set, minmax``.

## Substitute for FULLTEXT

ClickHouse does **not** support MySQL's `FULLTEXT` index and `MATCH...AGAINST`
(this backend fails fast). Its full-text facility is the `text` inverted index,
GA from 26.2:

```sql
CREATE TABLE docs (
    body String,
    INDEX idx_body body TYPE text(tokenizer = splitByNonAlpha) GRANULARITY 4
) ENGINE = MergeTree ORDER BY tuple();

SELECT * FROM docs WHERE hasAllTokens(body, ['clickhouse', 'index']);
SELECT * FROM docs WHERE hasAnyTokens(body, ['index', 'inverted']);
```

`GRANULARITY` is accepted but ignored for a text index — the index is built for
the whole part and `SHOW CREATE TABLE` reports `GRANULARITY 100000000`.

`tokenbf_v1` + `hasToken` still works on 26.7.3.19 (`CREATE TABLE ... TYPE
tokenbf_v1(32768, 3, 0)` is accepted and `hasToken(body, 'beta')` matches), but
ClickHouse's own documentation records `tokenbf_v1` and `ngrambf_v1` as
deprecated for full-text search from 26.2 in favour of `text`, so prefer `text`
for new tables. See
<https://clickhouse.com/docs/reference/engines/table-engines/mergetree-family/textindexes>.

`splitByNonAlpha` is case-sensitive: add `preprocessor = lower(body)` to the
index for case-insensitive matching.

## Vector approximate nearest neighbor (substitute for MySQL VECTOR index)

Use a `vector_similarity` skip index (with an `Array(Float32)` column) for ANN search, instead of MySQL's `VECTOR` type and `DISTANCE_*` functions.

## Cost of skip indexes

- Not exact indexes; may produce false positives (requires table lookups for filtering);
- Maintaining metadata on write has overhead;
- Suitable for scenarios where "most granules are filtered out"; not suitable for high selectivity queries.

## Next steps

- [Table engines & sorting key](table_engine.md)
- [Arrays, Maps, Tuples](../querying/arrays_maps.md)

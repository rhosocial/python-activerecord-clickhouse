# 跳数索引（Skip Indexes）

ClickHouse 的 skip index 不是 OLTP 的 B-tree 索引，而是在 MergeTree granule 上的"跳过"元数据，用于加速过滤。

## 基本语法

```sql
CREATE TABLE events (
    ts DateTime,
    url String,
    INDEX idx_url url TYPE bloom_filter GRANULARITY 4,
    INDEX idx_ts ts TYPE minmax GRANULARITY 4
) ENGINE = MergeTree ORDER BY (ts)
```

索引类型的关键字是 `TYPE`，不是 MySQL 的 `USING`：`INDEX i (s) TYPE minmax GRANULARITY 4` 会被接受，而 `INDEX i (s) USING minmax` 在 26.7.3.19 上是 `SYNTAX_ERROR`。

## 常用 skip index 类型

| 类型 | 用途 | 适用列 |
|------|------|--------|
| `minmax` | 存储 granule 最小最大值，过滤跳过区间 | 数值/时间 |
| `set(max_rows)` | 存储 granule 去重值集合 | 低基数 |
| `bloom_filter` | 布隆过滤器判断可能存在 | 任意等值 |
| `bloom_filter(bf)` | 带参数布隆 | 同上 |
| `text(tokenizer = ...)` | 分词后的倒排索引 | 全文检索 |
| `ngrambf_v1(n, sz, b, f)` | n-gram 布隆（自 26.2 起全文用途废弃） | 子串检索 |
| `tokenbf_v1(sz, f, seed)` | token 分词布隆（自 26.2 起全文用途废弃） | 单词检索 |

服务端自己接受的清单就写在报错文本里：声明未知类型会得到
``Unknown Index type 'fulltext'. Available index types: hypothesis, text,
vector_similarity, bloom_filter, sparse_grams, tokenbf_v1, ngrambf_v1, set,
minmax``。

## 替代 FULLTEXT

ClickHouse **不支持** MySQL 的 `FULLTEXT` 索引与 `MATCH...AGAINST`（本后端 fail-fast）。
它的全文设施是 `text` 倒排索引，26.2 起 GA：

```sql
CREATE TABLE docs (
    body String,
    INDEX idx_body body TYPE text(tokenizer = splitByNonAlpha) GRANULARITY 4
) ENGINE = MergeTree ORDER BY tuple();

SELECT * FROM docs WHERE hasAllTokens(body, ['clickhouse', 'index']);
SELECT * FROM docs WHERE hasAnyTokens(body, ['index', 'inverted']);
```

`text` 索引接受 `GRANULARITY` 但会忽略它——索引按整个 part 构建，
`SHOW CREATE TABLE` 里显示的是 `GRANULARITY 100000000`。

`tokenbf_v1` + `hasToken` 在 26.7.3.19 上仍然可用（`CREATE TABLE ... TYPE
tokenbf_v1(32768, 3, 0)` 被接受，`hasToken(body, 'beta')` 也能命中），但
ClickHouse 自己的文档记录了 `tokenbf_v1` 与 `ngrambf_v1` 自 26.2 起在全文检索用途上
已废弃、应由 `text` 取代，因此新表请优先用 `text`。参见
<https://clickhouse.com/docs/reference/engines/table-engines/mergetree-family/textindexes>。

`splitByNonAlpha` 区分大小写：需要忽略大小写时在索引上加
`preprocessor = lower(body)`。

## 向量近似最近邻（替代 MySQL VECTOR index）

用 `vector_similarity` skip index（配合 `Array(Float32)` 列）做 ANN 检索，而非 MySQL 的 `VECTOR` 类型与 `DISTANCE_*` 函数。

## skip index 的代价

- 不是精确索引，可能产生假阳性（需回表过滤）；
- 写入时维护元数据有开销；
- 适合"过滤掉大部分 granule"的场景，不适合高选择率查询。

## 下一步

- [表引擎与排序键](table_engine.md)
- [数组、Map、Tuple 查询](../querying/arrays_maps.md)

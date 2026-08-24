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

`INDEX ... USING type` 在本后端方言层支持。

## 常用 skip index 类型

| 类型 | 用途 | 适用列 |
|------|------|--------|
| `minmax` | 存储 granule 最小最大值，过滤跳过区间 | 数值/时间 |
| `set(max_rows)` | 存储 granule 去重值集合 | 低基数 |
| `bloom_filter` | 布隆过滤器判断可能存在 | 任意等值 |
| `bloom_filter(bf)` | 带参数布隆 | 同上 |
| `tokenbf_v1` | token 分词布隆 | 文本 token 检索 |
| `ngrambf_v1(n, sz, b, f)` | n-gram 布隆 | 子串检索 |

## 替代 FULLTEXT

ClickHouse **不支持** MySQL 的 `FULLTEXT` 索引与 `MATCH...AGAINST`（本后端 fail-fast）。用 `tokenbf_v1` + `hasToken` 做文本检索：

```sql
CREATE TABLE docs (
    body String,
    INDEX idx_body body TYPE tokenbf_v1(3, 256, 2, 0) GRANULARITY 4
) ENGINE = MergeTree ORDER BY id;

SELECT * FROM docs WHERE hasToken(body, 'clickhouse');
```

## 向量近似最近邻（替代 MySQL VECTOR index）

用 `vector_similarity` skip index（配合 `Array(Float32)` 列）做 ANN 检索，而非 MySQL 的 `VECTOR` 类型与 `DISTANCE_*` 函数。

## skip index 的代价

- 不是精确索引，可能产生假阳性（需回表过滤）；
- 写入时维护元数据有开销；
- 适合"过滤掉大部分 granule"的场景，不适合高选择率查询。

## 下一步

- [表引擎与排序键](table_engine.md)
- [数组、Map、Tuple 查询](../querying/arrays_maps.md)

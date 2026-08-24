# 不支持的功能

本后端对 ClickHouse 不支持的功能一律快速失败（`UnsupportedFeatureError`），不静默模拟。下表是完整清单与替代方案。

## 事务与约束

| 功能 | 行为 | 替代 |
|------|------|------|
| ACID 跨语句事务 | `transaction()` 空操作；rollback 抛异常 | 按 per-part 原子变更设计 |
| `FOREIGN KEY` | DDL 不生成 | 应用层维护引用完整性 |
| `UNIQUE` 约束 | DDL 不生成 | `ReplacingMergeTree` 去重 |
| 触发器 | raise | — |
| 序列 | raise | 客户端雪花 id |

## DML / 锁

| 功能 | 行为 | 替代 |
|------|------|------|
| UPSERT / `ON CONFLICT` / `INSERT IGNORE` / `REPLACE INTO` | raise | `ReplacingMergeTree` + 显式 `INSERT` |
| `FOR UPDATE` 行锁 | raise | OLAP 不做悲观锁 |
| `FOR SHARE` / `NOWAIT` / `SKIP LOCKED` | raise | 同上 |

## 索引与全文

| 功能 | 行为 | 替代 |
|------|------|------|
| `FULLTEXT` 索引 | raise | skip index `tokenbf_v1` + `hasToken` |
| `MATCH ... AGAINST` | raise | 同上 |
| `JSON_TABLE` | raise | `JSONExtract*` / `arrayJoin` |
| SQL 标准空间索引 | raise | skip indexes |

## 类型

| 功能 | 行为 | 替代 |
|------|------|------|
| 空间类型（`GEOMETRY`/`POINT`/...）| raise | 存 WKT 为 `String` |
| `ST_*` 函数族 | raise | ClickHouse 函数 |
| MySQL 9.0 `VECTOR` 类型 | raise | `Array(Float32)` |
| `STRING_TO_VECTOR`/`VECTOR_TO_STRING`/`VECTOR_DIM`/`DISTANCE_*` | raise | `L2Distance`/`cosineDistance`/`dotProduct` |
| `SET` 类型 | raise | `Enum16` 或 `Array(String)` |
| `FIND_IN_SET` | raise | `has()`/`indexOf()` |

## 语句

| 功能 | 行为 | 替代 |
|------|------|------|
| 存储过程 / 存储函数 / `CALL` | raise | ClickHouse SQL UDF（`CREATE FUNCTION ... AS`）|
| `LOAD DATA INFILE` | raise | 格式解析器 / `input()` 表函数 |
| `LOAD XML` | raise | 同上 |
| `TABLE` / `VALUES` 表值构造（MySQL 8.0.19+）| raise | `SELECT ... UNION ALL SELECT ...` |
| 整表维护（`ANALYZE`/`CHECK`/`CHECKSUM`/`REPAIR TABLE`）| raise | `OPTIMIZE TABLE ... FINAL` 或 `SYSTEM` 命令 |
| MySQL optimizer hints（`/*+ SET_VAR */`）| raise | `SETTINGS` 子句 |
| JSON Relational Duality Views | raise | `JSON` 类型 + `JSONExtract*` |

## 管理命令（MySQL admin set）

`FLUSH`/`RESET`/`CACHE INDEX`/`LOAD INDEX INTO CACHE`/`INSTALL`/`UNINSTALL COMPONENT`/`PLUGIN`/`CLONE`/`RESTART`/`BINLOG`/`HANDLER`/`DO`/`KILL`/`SHUTDOWN`/`HELP`/`CREATE USER`/`DROP USER`/`GRANT`/`REVOKE`——全部 raise。改用 ClickHouse 的 `SYSTEM` 命令族（`SYSTEM RELOAD`/`SYSTEM KILL`/`SYSTEM FLUSH`/...）。

## 异步

| 功能 | 行为 | 替代 |
|------|------|------|
| 异步后端 | `AsyncClickHouseBackend` 实例化即抛 `NotImplementedError` | 同步后端 + 进程外并发 |

`clickhouse-connect` 是纯同步库，本后端不提供 async 实现。

## 如何探测

```python
if dialect.supports_on_conflict_clause():
    ...   # 走 UPSERT
else:
    ...   # 走 INSERT + ReplacingMergeTree
```

调用方应通过 `supports_*` 显式探测，而非 `try/except UnsupportedFeatureError`，以便跨后端（如 SQLite 开发、ClickHouse 生产）切换。

## 下一步

- [能力边界与快速失败](../introduction/capability_boundaries.md)
- [变更（UPDATE/DELETE）](mutations.md)

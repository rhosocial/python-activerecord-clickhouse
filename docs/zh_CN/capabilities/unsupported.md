# 不支持的功能

本后端对 ClickHouse 不支持的功能一律快速失败（`UnsupportedFeatureError`），不静默模拟。下表是完整清单与替代方案。

## 事务与约束

| 功能 | 行为 | 替代 |
|------|------|------|
| ACID 跨语句事务 | `transaction()` 空操作；rollback 抛异常 | 按 per-part 原子变更设计 |
| `FOREIGN KEY` | DDL 不生成——**注意：其中一种写法服务器会接受但不生效，详见下文** | 应用层维护引用完整性 |
| `UNIQUE` 约束 | DDL 不生成，且服务器直接拒绝 | `ReplacingMergeTree` 去重 |
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
| `FULLTEXT` 索引 | raise | `text` 倒排索引 + `hasAllTokens`/`hasAnyTokens` |
| `MATCH ... AGAINST` | raise | 同上 |
| `JSON_TABLE` | raise | `JSONExtract*` / `arrayJoin` |
| SQL 标准空间索引 | raise | skip indexes |

ClickHouse 自己的全文设施是 `text` 倒排索引（26.2 起 GA）。它也是一种 skip
index，因此和其他 skip index 一样通过 `storage_options` 声明：

```sql
CREATE TABLE docs (
    body String,
    INDEX idx_body body TYPE text(tokenizer = splitByNonAlpha) GRANULARITY 4
) ENGINE = MergeTree ORDER BY tuple();

SELECT * FROM docs WHERE hasAllTokens(body, ['clickhouse', 'index']);
```

两个细节，均在 26.7.3.19 上实测，且都记录在
<https://clickhouse.com/docs/reference/engines/table-engines/mergetree-family/textindexes>：

- `tokenbf_v1` 与 `ngrambf_v1` 自 **26.2** 起在全文检索用途上**已废弃**。服务端
  仍然接受它们——`CREATE TABLE ... INDEX i body TYPE tokenbf_v1(32768, 3, 0)`
  成功，`hasToken(body, 'beta')` 也仍然命中——所以既有表继续可用，但新工作应改用
  `text`。
- `splitByNonAlpha` 区分大小写。需要忽略大小写时加上 `preprocessor = lower(<col>)`，
  否则 `hasAnyTokens(body, ['fox'])` 会漏掉 `'Fox'`。

## 类型

| 功能 | 行为 | 替代 |
|------|------|------|
| 空间类型（`GEOMETRY`/`POINT`/...）| raise | `Geometry` / `Point` 列类型，或把 WKT 存为 `String` |
| `ST_*` 函数族 | raise | ClickHouse 实际有的 7 个 `ST_*`（WKB/MVT 编解码）+ `geoDistance` |
| MySQL 9.0 `VECTOR` 类型 | 不提供——该 API 已移除 | `ClickHouseVectorType` → `QBit(Float32, n)`，或 `Array(Float32)` |
| `STRING_TO_VECTOR`/`VECTOR_TO_STRING`/`VECTOR_DIM`/`DISTANCE_*` | 不提供——该 API 已移除 | `L2Distance`/`cosineDistance`/`dotProduct` |
| `SET` 类型 | raise | `Enum16` 或 `Array(String)` |
| `FIND_IN_SET` | raise | `has()`/`indexOf()` |

关于这两行空间类型，在 26.7.3.19 上实测：ClickHouse **确实**有 `Geometry` 与
`Point` 列类型（`CREATE TABLE t (g Geometry) ENGINE = MergeTree` 会被接受），
也**确实**有且仅有 7 个 `ST_*` 函数——`ST_AsMVT`、`ST_AsMVTGeom`、
`ST_LineFromWKB`、`ST_MLineFromWKB`、`ST_PolyFromWKB`、`ST_MPolyFromWKB`、
`ST_PointFromWKB`——全部是 WKB / MVT 编解码。缺的是本后端 `ST_*` mixin 会生成的
OGC 函数面：`ST_Distance`/`ST_AsText` 返回 `UNKNOWN_FUNCTION`，`Geometry` 类型也
不接受 WKT 文本（`Cannot parse text value of type Geometry here: POINT(1 2)`）。
真正存在的距离函数是 `geoDistance(lon1, lat1, lon2, lat2)`。

## 语句

| 功能 | 行为 | 替代 |
|------|------|------|
| 存储过程 / 存储函数 / `CALL` | raise | ClickHouse SQL UDF（`CREATE FUNCTION ... AS`）|
| `LOAD DATA INFILE` | raise | 格式解析器 / `input()` 表函数 |
| `LOAD XML` | raise | 同上 |
| `TABLE` / `VALUES` 表值构造（MySQL 8.0.19+）| raise | `SELECT ... UNION ALL SELECT ...` |
| 整表维护（`ANALYZE`/`CHECKSUM`/`REPAIR TABLE`）| raise。`CHECK TABLE` 是例外，它确实可用——见下文 | `OPTIMIZE TABLE ... FINAL` 或 `SYSTEM` 命令 |
| MySQL optimizer hints（`/*+ SET_VAR */`）| raise，且这个拒绝并非多余：服务器**会解析该注释但忽略其内容** | `SETTINGS` 子句 |
| JSON Relational Duality Views | raise | `JSON` 类型 + `JSONExtract*` |
| `SHOW TABLE STATUS` / `SHOW TRIGGERS` / `SHOW CREATE TRIGGER` / `SHOW WARNINGS` / `SHOW ERRORS` / `SHOW VARIABLES` / `SHOW STATUS` / `SHOW CHARACTER SET` / `SHOW COLLATION` / `SHOW PLUGINS` | raise | 各自的 `system.*` 表，经 `ClickHouseStatusIntrospector` 读取 |
| `SHOW [FULL] COLUMNS` / `SHOW INDEX` / `SHOW PROCESSLIST` / `SHOW ENGINES` / `SHOW GRANTS` | **不再拒绝——这几条确实可用**，经 `backend.introspector.show.*()` 读取 | 若想直接查系统表：`DESCRIBE TABLE` / `system.columns`、`system.tables` + `system.data_skipping_indices`、`system.processes`、`system.table_engines`、`system.grants` |

### ClickHouse 实际具备的 `SHOW` 集合

MySQL `SHOW` 集合中有五条语句本后端过去拒绝，但服务器上其实可用，现已渲染并解析。
每条都按服务器真实返回的列名读取，而这些列名与 MySQL 的差异是**静默失败**
而非报错——按 MySQL 的列名去找只会拿到 `None`，不会抛异常：

| 语句 | ClickHouse 列名 | 与 MySQL 的差异 |
|------|-----------------|------------------|
| `SHOW [FULL] COLUMNS FROM db.t` | `field`、`type`、`null`、`key`、`default`、`extra`（`FULL` 下另有 `collation`、`comment`、`privileges`）| `key` 取值是 `PRI SOR` / `PRI` / `''`，不是 `PRI`/`UNI`/`MUL`；`default` 同时承载 `ALIAS`、`DEFAULT` **与** `MATERIALIZED` 的表达式；行按**列名**排序，不是声明顺序 |
| `SHOW INDEX FROM db.t` | `table`、`non_unique`、`key_name`、`seq_in_index`、`pk_col`、`collation`、`cardinality`、`sub_part`、`packed`、`null`、`index_type`、`comment`、`index_comment`、`visible`、`expression` | 被索引的列叫 `pk_col`，不是 `Column_name`；`index_type` 是 `PRIMARY`/`MINMAX`/`BLOOM_FILTER`/…，不是 `BTREE` |
| `SHOW PROCESSLIST` | `system.processes` 的全部 43 列 | 全小写；没有每进程的 `Command` 或 `State`，因此结果里这两个字段恒为 `None`；且**没有 `FULL` 变体**（`SHOW FULL PROCESSLIST` 是 `SYNTAX_ERROR`）|
| `SHOW ENGINES` | `name`、八个 `supports_*` 标志、`description`、`syntax`、`examples`、`introduced_in`、`related` | MySQL 的 `Support`/`Transactions`/`XA`/`Savepoints` 一个都没有 |
| `SHOW GRANTS [FOR user]` | **只有一列，列名是语句文本加上输出格式**——`GRANTS`、`GRANTS FORMAT JSONEachRow`、`GRANTS FORMAT Native`、`GRANTS FOR root`——绝不是 MySQL 的 `Grants for` | 因此读的是该列的**值**而非具名键。`FOR user@host` 也不是 ClickHouse 的写法：访问实体是角色名，`SHOW GRANTS FOR root@localhost` 报 `UNKNOWN_ROLE` |

仍有两条保持拒绝，因为服务器确实没有：`SHOW VARIABLES` 与 `SHOW STATUS`——
`SHOW` 之后的语法里根本没有这两个关键字；配置在 `system.settings` /
`system.server_settings`，运行时计数器在 `system.metrics`、`system.events`、
`system.asynchronous_metrics`，都由 `ClickHouseStatusIntrospector` 读取。
`SHOW TABLE STATUS`、`SHOW TRIGGERS`、`SHOW CREATE TRIGGER`、`SHOW WARNINGS`、
`SHOW ERRORS`、`SHOW CHARACTER SET`、`SHOW COLLATION`、`SHOW PLUGINS` 同理。

证明这些"不存在"的依据是服务器自己的语法。26.7.3.19 上 `SHOW` 接受的关键字全集是
`CREATE`、`FULL`、`DATABASES`、`CLUSTERS`、`MERGES`、`FILESYSTEM CACHES`、
`CLUSTER`、`CHANGED`、`SETTINGS`、`TEMPORARY`、`TABLES`、`DICTIONARIES`、
`EXTENDED`、`COLUMNS`、`FIELDS`、`ENGINES`、`FUNCTIONS`、`INDEX`、`INDEXES`、
`INDICES`、`KEYS`、`SETTING`、`DATABASE`、`VIEW`、`PROCESSLIST`、`ACCESS`、
`USERS`、`ROLES`、`PROFILES`、`POLICIES`、`QUOTAS`、`MASKING POLICIES`、
`CURRENT ROLES`、`ENABLED ROLES`、`CURRENT QUOTA`、`QUOTA`、`GRANTS`、
`PRIVILEGES`——没有 `VARIABLES`、没有 `STATUS`、没有 `TRIGGERS`、没有
`PLUGINS`。另见 <https://clickhouse.com/docs/reference/statements/show>。

### FOREIGN KEY 会被接受但不生效

`FOREIGN KEY` 值得单独说明，因为服务器**并非**简单拒绝它。四种写法中有三种直接
被拒，第四种——也是通用 SQL 生成器最可能产出的那种——**被接受、静默丢弃、
完全没有效果**。以下均在 26.7.3.19 上实测：

| 写法 | 结果 |
|------|------|
| `CREATE TABLE c (id UInt32, pid UInt32, FOREIGN KEY (pid) REFERENCES p(id)) ENGINE = MergeTree ORDER BY id` | **成功。**`SHOW CREATE TABLE c` 里没有外键，`system.tables.create_table_query` 不含 `FOREIGN` 字符串，孤儿行可以写入并正常读回 |
| `CREATE TABLE c (id UInt32, CONSTRAINT fk FOREIGN KEY (id) REFERENCES p(id)) ...` | `Code: 62. Syntax error: failed at position 57 (FOREIGN) ... Expected one of: CHECK, ASSUME. (SYNTAX_ERROR)` |
| `CREATE TABLE c (id UInt32 REFERENCES p(id)) ...`（列内联引用）| `Code: 62. Syntax error: failed at position 43 (REFERENCES) ...` |
| `CREATE TABLE c (id UInt32) ENGINE = MergeTree ORDER BY id FOREIGN KEY (id) REFERENCES p(id)`（写在存储子句之后）| `Code: 62. Syntax error: failed at position 75 (FOREIGN) ...` |

删掉被引用的父表同样成功，孤儿行依旧可读——所以这个子句也不是延迟检查，它是被
彻底忽略了。

对本后端有两个后果：

* **生成它会是三种结果里最糟的一种。**它不会报错，于是缺陷会在日后以"引用完整性
  缺失"的形式出现在生产数据里，而服务器元数据中没有任何线索可以解释。这正是本后端
  [设计原则](../introduction/capability_boundaries.md)要避免的"静默模拟"，也是
  `format_table_constraint` 对 `FOREIGN KEY` 抛异常、而不是渲染那个恰好能解析的
  子句的原因。
* **"DDL 不生成"与"服务器会拒绝它"不是同一个断言。**若读者把后者当作前提，就会
  自己去 `CREATE TABLE` 里粘一个 `FOREIGN KEY` 试一下，然后对未命名的那种写法得出
  "服务器支持外键"的结论。

作为对照，ClickHouse *真正*支持的约束形式是 `CHECK` 与 `ASSUME`（均见
<https://clickhouse.com/docs/reference/statements/create/table#constraints>），
且 `CHECK` 会被强制执行——越界的 `UInt32` 被按补码回绕存储而未被拒绝，仅仅是因为
比较是在存储值上做的。而 `UNIQUE (col)` 则被直接拒绝：`Code: 62. Syntax error:
failed at position 50 ((): (col)) ... Expected one of: NULL, NOT, DEFAULT,
MATERIALIZED, EPHEMERAL, ALIAS, AUTO_INCREMENT, TTL, PRIMARY KEY, data type,
identifier. (SYNTAX_ERROR)`。

### CHECK TABLE 可用

`CHECK TABLE` 是 ClickHouse 的真实语句，本后端现在会生成它；它不在上面的快速失败
清单里。它按表引擎分派，因此校验内容取决于引擎。

## 分区

ClickHouse **确实**支持分区，但方式与 MySQL 不同：在 `MergeTree` 表上以
`PARTITION BY <expr>` 声明，没有策略关键字，没有 `VALUES LESS THAN` /
`VALUES IN` / `MAXVALUE` 边界，也没有子分区。该子句通过 `storage_options` 声明；
维护按 partition id 进行（`DROP` / `DETACH` / `ATTACH PARTITION ID`）；
自省走 `system.parts`。下表中的 MySQL 语句在 ClickHouse 没有对应写法，
因此是**彻底移除**而不是逐条关掉开关——证明其缺失的清单见
<https://clickhouse.com/docs/sql-reference/statements/alter/partition>。

| 功能 | 行为 | 替代 |
|------|------|------|
| 声明式 `PARTITION BY RANGE/LIST/HASH/KEY` + `PARTITION ... VALUES ...` | raise | `storage_options` 中的 `PARTITION BY <expr>` |
| `ADD PARTITION` | raise | 分区在有数据落入时自然产生 |
| `TRUNCATE PARTITION` | raise | `ALTER TABLE ... DELETE IN PARTITION ... WHERE ...`，或 `TRUNCATE TABLE` |
| `REORGANIZE` / `EXCHANGE` / `COALESCE PARTITION`、`REMOVE PARTITIONING` | raise | `REPLACE PARTITION` / `MOVE PARTITION TO TABLE` |
| `ANALYZE`/`CHECK`/`OPTIMIZE`/`REBUILD`/`REPAIR PARTITION` | raise | `SYSTEM RESTART`/`SYSTEM RELOAD`、`OPTIMIZE TABLE ... PARTITION` |
| `SUBPARTITION BY` | raise | 元组分区键（`PARTITION BY (a, b)`）|
| `MAXVALUE` 分区边界 | raise | 分区键取值本身 |
| `information_schema.PARTITIONS` | raise | `system.parts` |

## 管理命令（MySQL admin set）

`FLUSH`/`RESET`/`CACHE INDEX`/`LOAD INDEX INTO CACHE`/`INSTALL`/`UNINSTALL COMPONENT`/`PLUGIN`/`CLONE`/`RESTART`/`BINLOG`/`HANDLER`/`DO`/`KILL`/`SHUTDOWN`/`HELP`——全部 raise。改用 ClickHouse 的 `SYSTEM` 命令族（`SYSTEM RELOAD`/`SYSTEM KILL`/`SYSTEM FLUSH`/...）。`KILL` 也不是 MySQL 那种单条语句：ClickHouse 的是 `KILL QUERY|MUTATION|PART_MOVE_TO_SHARD|TRANSACTION ...`，`KILL 1` 会得到 "Expected one of: QUERY, MUTATION, PART_MOVE_TO_SHARD, TRANSACTION"。

这份清单此前还列了 `CREATE USER`/`DROP USER`/`GRANT`/`REVOKE`，那几条并非 MySQL 专属：
`CREATE USER`、`ALTER USER`、`DROP USER`、`GRANT`、`REVOKE` 都是 ClickHouse 自己的
访问控制语句，在 26.7.3.19 上全部执行成功——本后端只是没有可生成它们的核心 API，
因此不会把 `CREATE USER` 路由到服务端。从 SQL 控制台做访问管理并没有被禁止，
被禁止的只是本后端表达式层没有对应写法。

## 异步

| 功能 | 行为 | 替代 |
|------|------|------|
| `AsyncClickHouseBackend` | 实例化即抛 `NotImplementedError` | 同步的 `ClickHouseBackend` + 进程外并发 |

窄口径的说法是准确的：**没有任何 async 后端类可以建立连接。**
`AsyncClickHouseBackend(connection_config=...)` 在 `__init__` 里抛
`NotImplementedError`，因为 `clickhouse-connect` 是纯同步驱动；
`AsyncClickHouseTransactionManager` 同样如此。

但"本包不提供 async 实现"是不对的。本包提供了两个完整的 async 自省器——
`AsyncClickHouseStatusIntrospector` 与 `AsyncShowIntrospector`——它们各自实现了
core 的 async status / SHOW 契约中的每个方法，都是真正 `await` 的查询，
没有一个方法抛 `NotImplementedError`。任何能自行提供 async 后端对象的调用方
（自带的异步 ClickHouse 驱动，或一层包装）都能用到它们；只有随包提供的
`AsyncClickHouseBackend` 拒绝实例化。异步测试 fixture 跳过也正是同一个原因：
它们拿不到一个可实例化的后端。

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

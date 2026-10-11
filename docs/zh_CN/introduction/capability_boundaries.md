# 能力边界与快速失败

理解能力边界是使用本后端的前提。本后端**不试图把 ClickHouse 包装成 OLTP 数据库**。

## 设计原则：快速失败，而非静默模拟

当调用方请求一个 ClickHouse 不支持的能力时，本后端的处理方式是抛出 `UnsupportedFeatureError`，**而不是**：

- 静默忽略（如把 `transaction()` 变成空操作但对外声称已提交）；
- 退化成低效模拟（如用 `SELECT + DELETE + INSERT` 模拟 UPSERT）；
- 生成 ClickHouse 会拒绝的 SQL（如 `UNIQUE (col)`），或生成它会接受却静默忽略的
  SQL（如未命名的 `FOREIGN KEY (...)`——见
  [FOREIGN KEY 会被接受但不生效](../capabilities/unsupported.md#foreign-key-会被接受但不生效)）。

唯一例外是 `transaction()`：它降级为**空操作上下文管理器**，仅为让通用代码路径（核心库与 testsuite 的事务相关测试）能继续运行而不报错；但 **rollback 语义不存在**——mutations 是 per-part 原子的，无法跨语句回滚。

```python
from rhosocial.activerecord.backend.dialect.exceptions import UnsupportedFeatureError

# ClickHouse 不支持 UPSERT，会快速失败：
try:
    User.query().upsert(...).execute()
except UnsupportedFeatureError as e:
    print(e.suggestion)  # 给出 ClickHouse 原生替代建议
```

> 💡 *AI 提示词："`UnsupportedFeatureError` 携带了哪些字段帮助调用方做条件降级？为什么 `transaction()` 是空操作而不是直接抛异常？"*

## 能力分类速查

### ClickHouse 原生支持（一等公民）

- 列式类型：`Int*`/`UInt*`、`Float*`、`Decimal*`、`String`/`FixedString`、`Date`/`Date32`/`DateTime`/`DateTime64`、`Bool`、`UUID`、`IPv4`/`IPv6`、`Enum8`/`Enum16`、`Array`、`Map`、`Tuple`、`Nullable(T)`、`LowCardinality(T)`、`JSON`，以及 26.x 起的 `Geometry`/`Point`
- DDL：`ENGINE`、`ORDER BY` 排序键、`PARTITION BY`、`TTL`、skip indexes（`INDEX name (col) TYPE <type> GRANULARITY n`——关键字是 `TYPE`，不是 MySQL 的 `USING`）
- 按 partition id 维护分区：`DROP` / `DETACH` / `ATTACH PARTITION ID`（ClickHouse 自己的子句清单见 <https://clickhouse.com/docs/sql-reference/statements/alter/partition>）
- 查询：CTE（`WITH`）、窗口函数、`QUALIFY`、`ARRAY JOIN`、集合操作（`UNION`/`INTERSECT`/`EXCEPT`，显式 `ALL`/`DISTINCT`）、`EXPLAIN`。`FINAL` 也是查询修饰符，但只对会合并重复行的引擎有效——普通 `MergeTree` 会返回 `Storage MergeTree doesn't support FINAL`，`ReplacingMergeTree` 则接受
- JSON：`JSONExtractString`/`JSONExtractRaw`/`JSON_VALUE`（`JSON_VALUE` 只接受 `String` 列，传 `JSON` 类型会报 `JSONPath functions require first argument to be JSON of string`）等原生函数（**非** MySQL arrow 运算符 `->`/`->>`）
- 自省：`system.*` 表（settings/server_settings/metrics/events/asynchronous_metrics/replicas/processes/...）、`SHOW` 命令
- SQL 层访问控制：`CREATE USER` / `ALTER USER` / `DROP USER` / `GRANT` / `REVOKE`（本后端表达式层没有可生成它们的写法，因此这里不会发出这些语句——但服务端有）
- 客户端雪花 `Int64` id（替代 `AUTO_INCREMENT`）
- 轻量级 UPDATE/DELETE（`UPDATE ... WHERE` / `DELETE ... WHERE`；需表设置 `enable_block_number_column`/`enable_block_offset_column`，详见 [变更](../capabilities/mutations.md)）

### ClickHouse 不支持（快速失败）

| 能力 | 行为 | 替代方案 |
|------|------|---------|
| ACID 跨语句事务 | `transaction()` 空操作；rollback 抛异常 | 按 per-part 原子变更设计，或用 `ReplacingMergeTree` |
| `FOREIGN KEY` / `UNIQUE` 约束 | DDL 不生成。`UNIQUE (col)` 在服务器上是 `SYNTAX_ERROR`；未命名的 `FOREIGN KEY (...) REFERENCES ...` 则**会被接受并静默丢弃**——见 [FOREIGN KEY 会被接受但不生效](../capabilities/unsupported.md#foreign-key-会被接受但不生效) | 由表引擎去重；引用完整性在应用层维护 |
| 触发器、序列 | raise | — |
| UPSERT / `ON CONFLICT` / `INSERT IGNORE` / `REPLACE INTO` | raise | `ReplacingMergeTree` + 显式 `INSERT` |
| `FOR UPDATE` 行锁 | raise | OLAP 不做悲观锁 |
| `FULLTEXT` 索引 / `MATCH...AGAINST` | raise | `text` 倒排索引（26.2 起 GA）+ `hasAllTokens`/`hasAnyTokens` |
| `JSON_TABLE` | raise | `JSONExtract*` / `arrayJoin` |
| 空间类型（`GEOMETRY`/`POINT`/...）与 OGC `ST_*` 函数 | raise | ClickHouse 自己的 `Geometry`/`Point` 列类型与 7 个 WKB/MVT `ST_*` 编解码函数；距离用 `geoDistance` |
| MySQL 9.0 `VECTOR` 类型与 `STRING_TO_VECTOR`/`VECTOR_DIM`/`DISTANCE_*` | 不提供——该 API 已移除（ClickHouse 自己的向量类型是 `QBit`，由 `ClickHouseVectorType` 渲染） | `QBit(Float32, n)` 或 `Array(Float32)` + `L2Distance`/`cosineDistance` |
| `SET` 类型 / `FIND_IN_SET` | raise | `Enum16` 或 `Array(String)` + `has()` |
| 存储过程 / 存储函数 / `CALL` | raise | ClickHouse SQL UDF（`CREATE FUNCTION ... AS`）|
| `LOAD DATA INFILE` / `LOAD XML` | raise | 格式解析器 / `input()` 表函数 |
| MySQL 管理命令（`FLUSH`/`RESET`/`KILL`/`INSTALL PLUGIN`/`CLONE`/`BINLOG`/`HANDLER`） | raise | ClickHouse `SYSTEM` 命令族 |
| `TABLE` / `VALUES` 表值构造（MySQL 8.0.19+） | raise | `SELECT ... UNION ALL SELECT ...` |
| 整表维护（`ANALYZE`/`CHECKSUM`/`REPAIR TABLE`） | raise（`CHECK TABLE` 是例外，它确实可用） | `OPTIMIZE TABLE ... FINAL` 或 `SYSTEM` 命令 |
| MySQL optimizer hints（`/*+ SET_VAR */`） | raise。这个拒绝并非多余：ClickHouse **会解析该注释但丢弃其内容**，26.7.3.19 上实测——`/*+ SET_VAR(max_block_size=7) */` 之后 `getSetting('max_block_size')` 仍是 `65409`；而 `SET_VAR(totally_bogus_zzz=1)` 这种根本不存在的设置名同样被接受，说明连设置名都不校验 | `SETTINGS` 子句 |
| JSON Relational Duality Views | raise | `JSON` 类型 + `JSONExtract*` |
| ClickHouse 没有的 `SHOW` 语句（`SHOW VARIABLES`/`STATUS`/`TABLE STATUS`/`TRIGGERS`/`CREATE TRIGGER`/`WARNINGS`/`ERRORS`/`CHARACTER SET`/`COLLATION`/`PLUGINS`） | raise | 各自的 `system.*` 表，经 `ClickHouseStatusIntrospector` 读取。`SHOW` 之后根本没有 `VARIABLES`、`STATUS`、`TRIGGERS`、`PLUGINS` 这些关键字 |
| ClickHouse **确实**有的 `SHOW` 语句（`SHOW [FULL] COLUMNS`/`INDEX`/`PROCESSLIST`/`ENGINES`/`GRANTS`） | **不再拒绝——这几条可用**，经 `backend.introspector.show.*()` 读取。它们的列名是 ClickHouse 的，按 MySQL 的列名去解析只会拿到 `None` 而不是报错 | 若想直接查系统表就用对应的 `system.*` 表。见 [ClickHouse 实际具备的 `SHOW` 集合](../capabilities/unsupported.md#clickhouse-实际具备的-show-集合) |
| 声明式分区（`PARTITION BY RANGE/LIST/HASH/KEY` + `PARTITION ... VALUES ...`、子分区、`ADD`/`TRUNCATE`/`REORGANIZE`/`EXCHANGE`/`COALESCE`/`ANALYZE`/`CHECK`/`REBUILD`/`REPAIR PARTITION`） | raise——ClickHouse 没有这些子句，见 [分区](../capabilities/unsupported.md) | `storage_options` 中的 `PARTITION BY <expr>`；维护用 `DROP`/`DETACH`/`ATTACH PARTITION ID`；自省用 `system.parts` |
| 异步后端 | 没有可实例化的异步后端：`AsyncClickHouseBackend(...)` 直接抛 `NotImplementedError` | 用同步后端 + 进程外并发。本包内的两个异步*自省器*（`AsyncClickHouseStatusIntrospector`、`AsyncShowIntrospector`）是完整的、会真正 `await` 查询——只是没有随包后端可供它们运行 |

完整清单见 [不支持的功能](../capabilities/unsupported.md)。

## 如何在代码中做条件降级

调用方应通过 `supports_*` 能力开关检查，而非 `try/except`：

```python
if not dialect.supports_on_conflict_clause():
    # 走 INSERT + ReplacingMergeTree 路径
    ...
```

这样在切换后端（如开发用 SQLite、生产用 ClickHouse）时，能力探测是显式且可读的。

## 下一步

- [安装指南](../installation/installation.md)
- [快速开始](../getting_started/quick_start.md)

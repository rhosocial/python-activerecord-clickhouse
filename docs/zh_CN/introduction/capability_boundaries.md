# 能力边界与快速失败

理解能力边界是使用本后端的前提。本后端**不试图把 ClickHouse 包装成 OLTP 数据库**。

## 设计原则：快速失败，而非静默模拟

当调用方请求一个 ClickHouse 不支持的能力时，本后端的处理方式是抛出 `UnsupportedFeatureError`，**而不是**：

- 静默忽略（如把 `transaction()` 变成空操作但对外声称已提交）；
- 退化成低效模拟（如用 `SELECT + DELETE + INSERT` 模拟 UPSERT）；
- 生成 ClickHouse 会拒绝的 SQL（如 `FOREIGN KEY`）。

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

- 列式类型：`Int*`/`UInt*`、`Float*`、`Decimal*`、`String`/`FixedString`、`Date`/`Date32`/`DateTime`/`DateTime64`、`Bool`、`UUID`、`IPv4`/`IPv6`、`Enum8`/`Enum16`、`Array`、`Map`、`Tuple`、`Nullable(T)`、`LowCardinality(T)`、`JSON`
- DDL：`ENGINE`、`ORDER BY` 排序键、`PARTITION BY`、`TTL`、skip indexes（`INDEX ... USING`）
- 查询：CTE（`WITH`）、窗口函数、`QUALIFY`、`FINAL`、`ARRAY JOIN`、集合操作（`UNION`/`INTERSECT`/`EXCEPT`，显式 `ALL`/`DISTINCT`）、`EXPLAIN`
- JSON：`JSONExtractString`/`JSONExtractRaw`/`JSON_VALUE` 等原生函数（**非** MySQL arrow 运算符 `->`/`->>`）
- 自省：`system.*` 表（settings/metrics/replicas/processes/...）、`SHOW` 命令
- 客户端雪花 `Int64` id（替代 `AUTO_INCREMENT`）
- 轻量级 UPDATE/DELETE（`UPDATE ... WHERE` / `DELETE ... WHERE`；需表设置 `enable_block_number_column`/`enable_block_offset_column`，详见 [变更](../capabilities/mutations.md)）

### ClickHouse 不支持（快速失败）

| 能力 | 行为 | 替代方案 |
|------|------|---------|
| ACID 跨语句事务 | `transaction()` 空操作；rollback 抛异常 | 按 per-part 原子变更设计，或用 `ReplacingMergeTree` |
| `FOREIGN KEY` / `UNIQUE` 约束 | DDL 不生成 | 由表引擎去重 |
| 触发器、序列 | raise | — |
| UPSERT / `ON CONFLICT` / `INSERT IGNORE` / `REPLACE INTO` | raise | `ReplacingMergeTree` + 显式 `INSERT` |
| `FOR UPDATE` 行锁 | raise | OLAP 不做悲观锁 |
| `FULLTEXT` 索引 / `MATCH...AGAINST` | raise | skip indexes（`tokenbf_v1` + `hasToken`） |
| `JSON_TABLE` | raise | `JSONExtract*` / `arrayJoin` |
| 空间类型（`GEOMETRY`/`POINT`/...）与 `ST_*` 函数 | raise | 存 WKT 为 `String`，用 ClickHouse 函数算 |
| MySQL 9.0 `VECTOR` 类型与 `STRING_TO_VECTOR`/`VECTOR_DIM`/`DISTANCE_*` | raise | `Array(Float32)` + `L2Distance`/`cosineDistance` |
| `SET` 类型 / `FIND_IN_SET` | raise | `Enum16` 或 `Array(String)` + `has()` |
| 存储过程 / 存储函数 / `CALL` | raise | ClickHouse SQL UDF（`CREATE FUNCTION ... AS`）|
| `LOAD DATA INFILE` / `LOAD XML` | raise | 格式解析器 / `input()` 表函数 |
| MySQL 管理命令（`FLUSH`/`RESET`/`KILL`/`INSTALL PLUGIN`/`CLONE`/`BINLOG`/`HANDLER`/`GRANT`/`CREATE USER`） | raise | ClickHouse `SYSTEM` 命令族 |
| `TABLE` / `VALUES` 表值构造（MySQL 8.0.19+） | raise | `SELECT ... UNION ALL SELECT ...` |
| 整表维护（`ANALYZE`/`CHECK`/`CHECKSUM`/`REPAIR TABLE`） | raise | `OPTIMIZE TABLE ... FINAL` 或 `SYSTEM` 命令 |
| MySQL optimizer hints（`/*+ SET_VAR */`） | raise | `SETTINGS` 子句 |
| JSON Relational Duality Views | raise | `JSON` 类型 + `JSONExtract*` |
| 异步后端 | `AsyncClickHouseBackend` 占位类实例化即抛 `NotImplementedError` | 用同步后端 + 进程外并发 |

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

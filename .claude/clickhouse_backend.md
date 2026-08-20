# ClickHouse Backend Knowledge Base for RhoSocial ActiveRecord

## ClickHouse 与传统关系型数据库的核心差异

| 维度 | MySQL / PostgreSQL | ClickHouse |
|---|---|---|
| 存储模型 | 行式存储，面向 OLTP | 列式存储，面向 OLAP，数据按 Part 组织 |
| 主键语义 | 唯一性约束 + B-Tree | 稀疏索引（每个 granule 8192 行一条索引），不强制唯一 |
| 外键 | 支持并强制引用完整性 | **不支持 FOREIGN KEY** |
| UNIQUE | 强制唯一 | 无强制唯一；可用 `ReplacingMergeTree` 语义模拟 |
| CHECK | 支持 | 支持，插入时校验 |
| 事务 | 完整 ACID | 单次 INSERT 近似 ACID；多语句/多表事务为实验特性（需 ClickHouse Keeper），Cloud 不支持 |
| UPDATE/DELETE | 同步、行级锁 | 25.7+ 标准 UPDATE；Lightweight DELETE（异步标记）；传统 mutation 重写 Part |
| 自增主键 | 原生支持 | 无原生自增，建议用 UUID（项目已有 `UUIDMixin`）或 `generateSnowflakeID()` |
| JOIN | 优化器成熟 | 完整 JOIN（hash/direct/full sorting merge/grace hash），24.12+ 自动优化两表顺序，25.9+ 扩展到多表 |
| 并发/锁 | 行级锁 + MVCC | 无行锁，写入以 Part 为单位追加，MVCC 快照隔离 |
| 表引擎 | 单一引擎（InnoDB/heap） | 引擎家族（MergeTree / ReplacingMergeTree / CollapsingMergeTree / AggregatingMergeTree / Log / Memory / Distributed）

## 对 ActiveRecord 层面的建议

1. `ForeignKeyConstraint` 在 ClickHouse Dialect 中需做降级处理（静默忽略或警告），DDL 无 `FOREIGN KEY` 关键字。
2. `PRIMARY_KEY` 映射为 `ORDER BY`（排序键），非传统主键语义。需引入 ClickHouse 专属引擎字段（如 `ENGINE = MergeTree` 或 `ReplacingMergeTree`）。
3. 自增 ID 直接复用 `UUIDMixin`，或引入 `SnowflakeIDMixin`（ClickHouse 有 `generateSnowflakeID()`）。
4. `with_transaction()` 跨表原子提交在生产环境基本不可用，应明确边界（实验特性、非 Cloud、非复制 MergeTree、Keeper 就绪时才开放，或直接抛 `NotSupportedError`）。
5. Async backend 可规划 `AsyncClickHouseBackend`，生态已有 `clickhouse-connect` / `asynch` 异步驱动。
6. `SoftDeleteMixin` 比直接依赖 DELETE 更适合 ClickHouse 默认模式（`deleted_at` 字段 + TTL 自动清理）。

结论：ClickHouse 能支持基础 CRUD（插入、查询、条件更新/删除、JOIN 预加载），但唯一性约束、外键引用完整性、跨表事务这三项在 ClickHouse 上要么不存在，要么只是实验特性。做这个 backend 的关键不是把 ClickHouse 硬套进现有 RDBMS 语义，而是在 Dialect 层清楚地"降级"或"重新映射"那些原生不支持的关系型保证，并在文档里明确告诉使用者：这是"能查能写"的 ActiveRecord 接口，而非"数据库替你保证一致性"的传统 RDBMS 接口。

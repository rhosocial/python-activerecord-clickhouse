# 概述

## 为什么需要 ClickHouse 后端

ClickHouse 是面向列式存储的 OLAP 数据库，在实时分析、海量数据聚合场景下表现卓越。但它的世界观与 OLTP 行存数据库截然不同：没有事务、没有外键、没有唯一约束、变更（UPDATE/DELETE）是异步的"突变"（mutations）。

传统的 ORM 在接入 ClickHouse 时通常有两种做法：

1. **假装它是 OLTP**：用模拟事务、模拟外键、生成 ClickHouse 无法执行的 SQL，最终在运行时崩溃或产生语义错误的数据。
2. **只当查询网关**：只做 SELECT 透传，放弃 ActiveRecord 模式的建模能力。

`rhosocial-activerecord-clickhouse` 选择第三条路——**诚实对待语义**：

- ClickHouse 原生支持的能力（列式类型、`ENGINE`、`ORDER BY` 排序键、`PARTITION BY`、TTL、`JSONExtract*`、数组/Map/Tuple、`system.*` 自省）以一等公民暴露，生成 ClickHouse 原生 SQL。
- ClickHouse 不支持的能力（ACID 事务、外键/唯一约束、触发器、UPSERT、FOR UPDATE、FULLTEXT、JSON_TABLE、空间/向量类型、存储过程、MySQL 管理命令等）通过 `supports_*` 能力开关声明为 `False`，调用对应的 `format_*` 方法会快速抛出 `UnsupportedFeatureError`，**绝不静默模拟**。

> 💡 *AI 提示词："为什么这个后端选择快速失败而不是模拟事务？这对调用方代码有什么影响？"*

## 核心设计原则

1. **后端实现**：扩展核心 ActiveRecord 的 Expression-Dialect-Backend 分层，提供 ClickHouse 专属类型与方言。
2. **驱动**：使用 `clickhouse-connect`（HTTP 接口）作为数据库连接层。
3. **命名空间包**：以 `rhosocial.activerecord.backend.impl.clickhouse` 接入核心库的命名空间包架构。
4. **仅同步**：`clickhouse-connect` 是纯同步库，本后端**不提供异步后端**。`AsyncClickHouseBackend` 是一个会快速失败的占位类，方便通用导入路径继续加载，但任何实例化都会抛出 `NotImplementedError`。
5. **快速失败语义**：不支持的功能抛 `UnsupportedFeatureError`，而不是退化成静默的空操作或模拟实现。

## 适用场景

- 在 ClickHouse 之上做带类型安全的建模（Pydantic V2 深度集成）。
- 写实时分析应用，需要 ActiveRecord 风格的查询构建器生成 ClickHouse 原生 SQL。
- 复用核心库的 Mixin（Timestamp、乐观锁、软删除等）与关系（has_one/has_many/has_many_through）。
- 通过 CLI 与 `system.*` 自省做运维与数据探查。

## 不适用场景

- 需要 ACID 跨语句事务保证的业务（ClickHouse 的 mutations 是 per-part 原子，无跨语句隔离）。
- 依赖唯一约束做去重的写入（应由表引擎 `ReplacingMergeTree`/`CollapsingMergeTree` 承担）。
- 需要异步 I/O 的高并发服务（驱动是同步的；如有此需求，应在进程外用连接池 + 工作线程）。

## 下一步

- [与核心库的关系](relationship.md)：理解分层架构与本后端的位置。
- [支持版本](supported_versions.md)：确认你的 ClickHouse 与 Python 版本。
- [能力边界与快速失败](capability_boundaries.md)：在写代码前先知道什么能做什么不能做。

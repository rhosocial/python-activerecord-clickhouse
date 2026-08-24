# 与核心库的关系

`rhosocial-activerecord-clickhouse` 是核心库 [python-activerecord](https://github.com/rhosocial/python-activerecord) 的**后端实现插件**。理解二者的分层关系，有助于你知道哪些能力来自核心、哪些来自本后端。

## 分层架构

核心库定义了四层抽象：

```
Interface (ActiveRecord 模型 / FieldProxy)
   └── Dialect (SQL 方言，按数据库族分支)
        └── Expression (可序列化的 SQL 表达式对象)
             └── Backend (执行器，连库、执行、返回结果)
```

本后端实现其中两层：

- **`ClickHouseDialect`**（`dialect.py`）：继承核心库的通用方言 mixin（CTE、窗口函数、JSON、连接、视图、索引、自省……），并叠加 ClickHouse 专属 mixin（表引擎、`FINAL`/`ARRAY JOIN`、JSON 函数族、事务空操作、各类不支持特性的 fail-fast stub）。
- **`ClickHouseBackend`**（`backend.py`）：实现核心库的 `DatabaseBackend` 接口，负责通过 `clickhouse-connect` 执行 SQL、管理连接、映射错误、生成客户端雪花 id。

## 本后端提供什么

| 层 | 来自核心库 | 来自本后端 |
|----|-----------|-----------|
| ActiveRecord 模型、`FieldProxy`、Mixin、关系 | ✅ | — |
| 通用 Dialect mixin（CTE/窗口/JSON/连接/视图/索引/自省） | ✅ 定义协议 | ✅ 继承并按 ClickHouse 语义覆盖 |
| ClickHouse 专属类型（`Int*`/`UInt*`/`Decimal*`/`DateTime64`/`Enum*`/`Array`/`Map`/`Tuple`/`Nullable`/`LowCardinality`/`JSON`） | — | ✅ |
| ClickHouse DDL（`ENGINE`/`ORDER BY`/`PARTITION BY`/`TTL`/skip indexes） | — | ✅ |
| `system.*` 自省、`EXPLAIN`/`SHOW` | 通用协议 | ✅ ClickHouse 实现 |
| 客户端雪花 id 生成 | `AutoIncrementSupport` 协议（核心 dev30+） | ✅ `SnowflakeIDGenerator` |
| 事务管理 | 协议 | ✅ 空操作上下文管理器（fail-fast rollback） |
| 不支持特性的 fail-fast stub | — | ✅ trigger/spatial/vector/set/JSON_TABLE/... |

## 依赖版本

本后端依赖核心库 `rhosocial-activerecord>=1.0.0.dev30`。两个 dev30 引入的关键能力本后端**硬依赖**：

- `BulkInsertOptions.primary_key` 字段（用于把客户端生成的雪花 id 传播进批量插入）。
- `AutoIncrementSupport` 协议（dialect 继承它，表达"ClickHouse 无服务端 AUTO_INCREMENT，由后端生成 id"）。

在核心库 `1.0.0.dev30` 正式发布到 PyPI 之前，本后端无法独立 `pip install`，需从源码与核心库一并安装。详见 [安装指南](../installation/installation.md)。

## 与其他后端的对比

核心库生态包含多个后端（SQLite 内置、MySQL、PostgreSQL、MariaDB、SQL Server、Oracle）。本后端的特殊之处在于它是唯一面向列式 OLAP 的后端：

- **同步专属**：其他后端大多提供对称的 async 实现，本后端因驱动限制不提供。
- **无事务**：其他后端的事务是真实隔离的，本后端的事务是空操作。
- **无服务端自增**：其他后端的 `AUTO_INCREMENT`/`SERIAL` 由数据库生成，本后端由客户端雪花算法生成 `Int64`。
- **快速失败覆盖面最广**：本后端的 fail-fast stub 数量远多于其他后端，因为 ClickHouse 缺失的 OLTP 特性最多。

> 💡 *AI 提示词："如果一个模型同时用于 SQLite（测试）和 ClickHouse（生产），能力差异如何在代码层处理？"*

## 下一步

- [支持版本](supported_versions.md)
- [能力边界与快速失败](capability_boundaries.md)

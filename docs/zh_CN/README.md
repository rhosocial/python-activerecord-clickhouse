# rhosocial-activerecord ClickHouse 后端文档

> 🤖 **AI 学习助手**：本文档中关键概念旁标有 💡 AI 提示词标记。遇到不理解的概念时，可以直接向 AI 助手提问。
>
> **示例：** "ClickHouse 后端为什么把事务降级为空操作？与 SQLite/MySQL 后端有什么区别？"
>
> 📖 **详细用法请参考**：[AI 辅助开发指南](https://github.com/rhosocial/python-activerecord/tree/docs/docs/zh_CN/introduction/ai_assistance.md)

ClickHouse 后端是 [rhosocial-activerecord](https://github.com/rhosocial/python-activerecord) 的 ClickHouse 数据库后端实现。它使用 `clickhouse-connect`（HTTP 接口）驱动，将 ActiveRecord 模式带入 ClickHouse 列式、OLAP 世界，同时**诚实对待 ClickHouse 的语义边界**——ClickHouse 不支持的能力（事务、外键/唯一约束、触发器、UPSERT、FOR UPDATE、FULLTEXT、JSON_TABLE、空间/向量类型、存储过程、MySQL 管理命令等）会以 `UnsupportedFeatureError` 快速失败，而非静默模拟。

## 目录 (Table of Contents)

1. **[简介 (Introduction)](introduction/README.md)**
    * **[概述](introduction/README.md)**：为什么选择 ClickHouse 后端
    * **[与核心库的关系](introduction/relationship.md)**：后端如何集成进 rhosocial-activerecord
    * **[支持版本](introduction/supported_versions.md)**：ClickHouse 25.8/26.3/26.7、Python 3.10–3.14
    * **[能力边界与快速失败](introduction/capability_boundaries.md)**：支持什么、不支持什么、为什么不模拟

2. **[安装 (Installation)](installation/README.md)**
    * **[安装指南](installation/installation.md)**：pip 安装与环境要求
    * **[连接配置](installation/configuration.md)**：host/port/database/username/password

3. **[快速入门 (Getting Started)](getting_started/README.md)**
    * **[快速开始](getting_started/quick_start.md)**：最小可运行示例
    * **[第一个 CRUD 应用](getting_started/first_crud.md)**：建表、插入、查询、更新、删除

4. **[模型定义 (Modeling)](modeling/README.md)**
    * **[字段类型映射](modeling/field_types.md)**：Python 类型 ↔ ClickHouse 列类型（Int/UInt/Float/Decimal/String/Date/DateTime64/Bool/UUID/IPv4/6/Enum/Array/Map/Tuple/Nullable/LowCardinality/JSON）
    * **[Nullable 与可选字段](modeling/nullable.md)**：可选模型字段映射到 `Nullable(T)`

5. **[查询 (Querying)](querying/README.md)**
    * **[JSON 查询](querying/json.md)**：`JSONExtract*` 函数族
    * **[数组、Map、Tuple](querying/arrays_maps.md)**：列式复合类型查询

6. **[DDL](ddl/README.md)**
    * **[表引擎与排序键](ddl/table_engine.md)**：`ENGINE`、`ORDER BY`、`PARTITION BY`、`TTL`
    * **[跳数索引](ddl/skip_indexes.md)**：`INDEX ... USING` skip indexes

7. **[能力特性 (Capabilities)](capabilities/README.md)**
    * **[客户端雪花 ID](capabilities/snowflake_ids.md)**：ClickHouse 无 AUTO_INCREMENT，id 客户端生成
    * **[变更（UPDATE/DELETE）](capabilities/mutations.md)**：`mutations_sync=1` 与 `affected_rows` 语义
    * **[不支持的功能](capabilities/unsupported.md)**：完整 fail-fast 清单与替代方案

8. **[命令行 (CLI)](cli/README.md)**
    * **[CLI 用法](cli/README.md)**：`python -m rhosocial.activerecord.backend.impl.clickhouse`

9. **[测试 (Testing)](testing/README.md)**
    * **[测试配置](testing/README.md)**：场景配置与 CI 矩阵

---

> ⚠️ **依赖说明**：本后端依赖核心库 `rhosocial-activerecord>=1.0.0.dev30`（`primary_key` 在批量插入选项中传播、`AutoIncrementSupport` 协议）。在核心库 `1.0.0.dev30` 正式发布到 PyPI 之前，本后端无法独立 `pip install`，请从源码与核心库一并安装。

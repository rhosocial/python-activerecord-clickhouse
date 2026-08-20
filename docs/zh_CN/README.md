# rhosocial-activerecord ClickHouse 后端文档

> 🤖 **AI 学习助手**：本文档中关键概念旁标有 💡 AI 提示词标记。遇到不理解的概念时，可以直接向 AI 助手提问。

> **示例：** "ClickHouse 后端如何处理事务？与 SQLite 有什么区别？"

> 📖 **详细用法请参考**：[AI 辅助开发指南](introduction/ai_assistance.md)

## 目录 (Table of Contents)

1. **[简介 (Introduction)](introduction/README.md)**
    *   **[ClickHouse 后端概述](introduction/README.md)**: 为什么选择 ClickHouse 后端
    *   **[与核心库的关系](introduction/relationship.md)**: rhosocial-activerecord 与 ClickHouse 后端的集成
    *   **[支持版本](introduction/supported_versions.md)**: ClickHouse 5.6~9.6, Python 3.8+ 支持情况

2. **[安装与配置 (Installation & Configuration)](installation_and_configuration/README.md)**
    *   **[安装指南](installation_and_configuration/installation.md)**: pip 安装与环境要求
    *   **[连接配置](installation_and_configuration/configuration.md)**: host, port, database, username, password 等配置项
    *   **[SSL/TLS 配置](installation_and_configuration/ssl.md)**: 安全连接设置
    *   **[连接管理](installation_and_configuration/pool.md)**: 随用随连模式（暂不支持连接池）
    *   **[字符集与排序规则](installation_and_configuration/charset.md)**: utf8mb4 配置

3. **[ClickHouse 特性 (ClickHouse Specific Features)](clickhouse_specific_features/README.md)**
    *   **[ClickHouse 特定字段类型](clickhouse_specific_features/field_types.md)**: SET, ENUM, JSON, TEXT vs VARCHAR
    *   **[ClickHouse Dialect 表达式](clickhouse_specific_features/dialect.md)**: ClickHouse 特定的 SQL 方言
    *   **[存储引擎](clickhouse_specific_features/storage_engine.md)**: InnoDB, MyISAM 选择
    *   **[索引与性能优化](clickhouse_specific_features/indexing.md)**: 索引设计原则

4. **[DDL 操作 (DDL Operations)](ddl/README.md)**
    *   **[ClickHouse DDL 概览](ddl/README.md)**: CREATE TABLE, ALTER TABLE, DROP TABLE
    *   **[示例代码](../examples/chapter_04_ddl/ddl.py)**: DDL 示例

5. **[事务支持 (Transaction Support)](transaction_support/README.md)**
    *   **[事务隔离级别](transaction_support/isolation_level.md)**: READ COMMITTED, REPEATABLE READ 等
    *   **[Savepoint 支持](transaction_support/savepoint.md)**: 嵌套事务
    *   **[自动重试与死锁处理](transaction_support/deadlock.md)**: 失败重试机制

6. **[类型适配器 (Type Adapters)](type_adapters/README.md)**
    *   **[ClickHouse 到 Python 类型映射](type_adapters/mapping.md)**: 类型转换规则
    *   **[自定义类型适配器](type_adapters/custom.md)**: 扩展类型支持
    *   **[时区处理](type_adapters/timezone.md)**: UTC 与本地时区

7. **[测试 (Testing)](testing/README.md)**
    *   **[测试配置](testing/configuration.md)**: 测试环境设置
    *   **[使用 testsuite 进行测试](testing/testsuite.md)**: 测试套件使用
    *   **[本地 ClickHouse 测试](testing/local.md)**: 本地数据库测试

8. **[故障排除 (Troubleshooting)](troubleshooting/README.md)**
    *   **[常见连接错误](troubleshooting/connection.md)**: 连接问题诊断
    *   **[性能问题](troubleshooting/performance.md)**: 性能瓶颈分析
    *   **[字符集问题](troubleshooting/charset.md)**: 编码问题处理

9. **[场景实战 (Scenarios)](scenarios/README.md)**
    *   **[并行 Worker 处理](scenarios/parallel_workers.md)**: 多进程/异步并发场景的正确用法

10. **[Worker 隔离实验](examples/chapter_05_worker_isolation/README.md)**
    *   **[Worker 连接隔离实验](examples/chapter_05_worker_isolation/README.md)**: Worker 进程隔离实验

> 📖 **核心库文档**：要了解 ActiveRecord 框架的完整功能，请参考 [rhosocial-activerecord 文档](https://github.com/Rhosocial/python-activerecord/tree/main/docs/zh_CN)。

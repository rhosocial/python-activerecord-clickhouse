# rhosocial-activerecord ClickHouse Backend Documentation

> 🤖 **AI Learning Assistant**: Key concepts in this documentation are marked with 💡 AI Prompt. When you encounter concepts you don't understand, you can ask the AI assistant directly.

> **Example:** "How does the ClickHouse backend handle transactions? How does it differ from SQLite?"

> 📖 **For detailed usage, please refer to**: [AI-Assisted Development Guide](introduction/ai_assistance.md)

## Table of Contents

1. **[Introduction](introduction/README.md)**
    *   **[ClickHouse Backend Overview](introduction/README.md)**: Why choose ClickHouse backend
    *   **[Relationship with Core Library](introduction/relationship.md)**: Integration of rhosocial-activerecord and ClickHouse backend
    *   **[Supported Versions](introduction/supported_versions.md)**: ClickHouse 5.6~9.6, Python 3.8+ support

2. **[Installation & Configuration](installation_and_configuration/README.md)**
    *   **[Installation Guide](installation_and_configuration/installation.md)**: pip installation and environment requirements
    *   **[Connection Configuration](installation_and_configuration/configuration.md)**: host, port, database, username, password and other configuration options
    *   **[SSL/TLS Configuration](installation_and_configuration/ssl.md)**: secure connection settings
    *   **[Connection Management](installation_and_configuration/pool.md)**: connect-on-use pattern (connection pool not supported)
    *   **[Character Set and Collation](installation_and_configuration/charset.md)**: utf8mb4 configuration

3. **[ClickHouse Specific Features](clickhouse_specific_features/README.md)**
    *   **[ClickHouse-Specific Field Types](clickhouse_specific_features/field_types.md)**: SET, ENUM, JSON, TEXT vs VARCHAR
    *   **[ClickHouse Dialect Expressions](clickhouse_specific_features/dialect.md)**: ClickHouse-specific SQL dialect
    *   **[Storage Engines](clickhouse_specific_features/storage_engine.md)**: InnoDB, MyISAM selection
    *   **[Indexing and Performance Optimization](clickhouse_specific_features/indexing.md)**: index design principles

4. **[DDL Operations](ddl/README.md)**
    *   **[ClickHouse DDL Overview](ddl/README.md)**: CREATE TABLE, ALTER TABLE, DROP TABLE
    *   **[Example Code](../examples/chapter_04_ddl/ddl.py)**: DDL example

5. **[Transaction Support](transaction_support/README.md)**
    *   **[Transaction Isolation Levels](transaction_support/isolation_level.md)**: READ COMMITTED, REPEATABLE READ, etc.
    *   **[Savepoint Support](transaction_support/savepoint.md)**: nested transactions
    *   **[Auto-Retry and Deadlock Handling](transaction_support/deadlock.md)**: failure retry mechanism

6. **[Type Adapters](type_adapters/README.md)**
    *   **[ClickHouse to Python Type Mapping](type_adapters/mapping.md)**: type conversion rules
    *   **[Custom Type Adapters](type_adapters/custom.md)**: extending type support
    *   **[Timezone Handling](type_adapters/timezone.md)**: UTC and local timezone

7. **[Testing](testing/README.md)**
    *   **[Test Configuration](testing/configuration.md)**: test environment setup
    *   **[Using testsuite for Testing](testing/testsuite.md)**: test suite usage
    *   **[Local ClickHouse Testing](testing/local.md)**: local database testing

8. **[Troubleshooting](troubleshooting/README.md)**
    *   **[Common Connection Errors](troubleshooting/connection.md)**: connection issue diagnosis
    *   **[Performance Issues](troubleshooting/performance.md)**: performance bottleneck analysis
    *   **[Character Set Issues](troubleshooting/charset.md)**: encoding problem handling

9. **[Scenarios](scenarios/README.md)**
    *   **[Parallel Worker Processing](scenarios/parallel_workers.md)**: correct usage in multi-process/async concurrent scenarios

10. **[Worker Isolation Experiment](examples/chapter_05_worker_isolation/README.md)**
    *   **[Worker Connection Isolation](examples/chapter_05_worker_isolation/README.md)**: worker process isolation experiment

> 📖 **Core Library Documentation**: To learn about the complete functionality of the ActiveRecord framework, please refer to [rhosocial-activerecord documentation](https://github.com/Rhosocial/python-activerecord/tree/main/docs/en_US).

# Runnable examples

Small, self-contained scripts that put the concepts from the
[documentation](../en_US/README.md) into code. Every example targets this
ClickHouse backend and is synchronous — the driver behind the backend
(`clickhouse-connect`) is sync-only.

All examples read their connection settings from the same environment variables
used by the test suite:

```bash
export CLICKHOUSE_HOST=localhost
export CLICKHOUSE_PORT=8123
export CLICKHOUSE_DATABASE=test_db
export CLICKHOUSE_USER=root
export CLICKHOUSE_PASSWORD=password
```

A running ClickHouse server is required; the scripts explain how to start one
and exit non-zero rather than fabricate results when they cannot connect.

| Chapter | Example | What it shows |
|---------|---------|---------------|
| 03 | [Connection](chapter_03_connection/README.md) | Configuration, connect, and a first query |
| 04 | [Modeling](chapter_04_modeling/README.md) | Declarative models, `UseSqlType`, mixins, `FieldProxy`, `table_name()` |
| 06 | [DDL](chapter_06_ddl/README.md) | `CreateTableStatement` with a `MergeTree` engine via expression nodes |
| 08 | [Introspection](chapter_08_introspection/README.md) | Catalogue queries and the backend's own table-engine read |
| — | [Migrations](migration/README.md) | Non-transactional DDL, compensating DOWN, function-style and named-migration demos |

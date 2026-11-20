# Migration examples (ClickHouse backend)

Synchronous, runnable examples for the backend-specific migration concerns described in the
[Migrations chapter](../../en_US/migration/README.md). The migration system itself is documented in
the core library's [Migration chapter](https://github.com/rhosocial/python-activerecord/blob/main/docs/en_US/migration/README.md).

All examples use `ClickHouseBackend` + `ClickHouseConnectionConfig`, read the connection settings
from the usual `CLICKHOUSE_*` environment variables, and require a running ClickHouse server;
they exit non-zero with a clear message when they cannot connect. Do **not** pass `--async` —
`AsyncClickHouseBackend` is only a placeholder that raises `NotImplementedError`.

Run them from the repository root with `PYTHONPATH=src`:

```bash
python docs/examples/migration/01_function_migration.py
python docs/examples/migration/02_named_migration.py
```

| Script | Demonstrates |
|--------|--------------|
| `01_function_migration.py` | `@migration` + `run_migration_group`: `dry_run=True` → UP → DOWN, with a `JSONFileMigrationRecordStore` |
| `02_named_migration.py` | `NamedMigration` + `MigrationRunner` and the equivalent `named-migration` CLI wiring |
| `migration_support.py` | importable model, function-style migration, and class-style `NamedMigration` used by both scripts (FQN resolution) |

> ClickHouse DDL is non-transactional and many ALTER / MUTATION statements are asynchronous:
> a version record means the statements were *accepted*, not that the schema has settled. DOWN
> is an explicit compensating statement, never a rollback. See the chapter for the full caveats.

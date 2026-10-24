# `introspect` — ClickHouse metadata, from the command line

The `introspect` subcommand asks a live ClickHouse server what it holds, and
prints the answer. Every question runs through the backend's introspector, so
what the CLI reports is what the library sees — the same objects, the same
types, the same parsing — rather than a second implementation that can drift
from it.

```bash
python -m rhosocial.activerecord.backend.impl.clickhouse introspect <TYPE> [NAME] [OPTIONS]
```

## What it can ask about

| Type | Reads | Notes |
| :--- | :--- | :--- |
| `tables` | `system.tables` | Tables, with the storage engine in the `table_type` position. `--include-system` adds the engine's own tables. |
| `views` | `system.tables` | Views, with their definitions. |
| `table` | several | One table by name, with its columns, indexes and foreign keys filled in. |
| `columns` | `system.columns` | One table's columns: name, type, nullability, ordinal position, default. |
| `indexes` | `system.data_skipping_indices` | One table's data-skipping indices — ClickHouse's nearest analogue to an index. |
| `foreign-keys` | — | The engine neither declares nor enforces foreign keys, so this answers with the capability missing rather than an empty list that looks like "none declared". |
| `triggers` | — | Likewise: ClickHouse has no triggers. Asking reports the capability as unsupported, not a silent empty answer. |
| `partitions` | `system.parts` | One table's partitions and subpartitions, in the engine's own order, aggregated from the parts currently active. |
| `table-engine` | `system.tables` | The engine of one table, with its sorting, primary and sampling keys, plus row and byte totals. |
| `database` | `system.build_options`, `system.databases` | Server version and the databases visible to this role. |

`NAME` is required for `table`, `columns`, `indexes`, `foreign-keys`,
`partitions` and `table-engine`. The list types take no name.

## Options

| Option | Default | Description |
| :--- | :--- | :--- |
| `-o, --output` | `table` | `table` (rich), `json`, `csv`, `tsv`. |
| `--schema` | the connected database | The database to read. ClickHouse's namespace level is a *database*, and the CLI says so rather than calling it a schema. |
| `--include-system` | off | Include system tables. |
| `--host`, `--port`, `--database`, `--user`, `--password` | env or defaults | Connection. `CLICKHOUSE_*` env vars are honoured, and arguments override them. |
| `--ssl` | off | Use SSL for the connection. |
| `--async` | off | Drive the asynchronous backend. |
| `--named-connection` | _None_ | A connection saved by the `named-connection` subcommand. |
| `--conn-param` | _None_ | Extra `key=value` connection parameters; repeatable. |
| `--rich-ascii` | off | ASCII characters for table borders. |

## Notes

*   **Read-only.** `introspect` never writes. It does not create, drop, or
    alter anything, so it is safe to run against a server whose schema
    matters.
*   **`partitions` reads `system.parts`, not `system.partitions`.** The parts
    view is what is live; a partition with no active parts has nothing to
    report, which is why the answer is aggregated rather than listed.
*   **`table_type` carries the engine.** For ClickHouse that is the more
    useful of the two facts MySQL's same-shaped view would report.
*   **`triggers` and `foreign-keys` are refused, not empty.** ClickHouse has
    neither, so the backend reports the capability as unsupported. An empty
    list would read as "none declared", which is a different and wrong
    answer — the same command against a MySQL database returns a real list.
*   **One question per invocation.** A CLI process is one connection that
    opens, answers, and closes — there is no cache carried between runs.

## Examples

```bash
# The two ClickHouse-specific families
python -m rhosocial.activerecord.backend.impl.clickhouse introspect partitions events
python -m rhosocial.activerecord.backend.impl.clickhouse introspect table-engine events -o json

# One table in full
python -m rhosocial.activerecord.backend.impl.clickhouse introspect table events

# Another database, including its system tables
python -m rhosocial.activerecord.backend.impl.clickhouse introspect tables --schema reports --include-system
```

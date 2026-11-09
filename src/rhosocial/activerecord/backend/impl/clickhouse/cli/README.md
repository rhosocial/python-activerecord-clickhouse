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

Twenty-one types, in the order `--help` prints them. Sixteen answer True for
this dialect — the seven table-scoped catalogue families, the six server-wide
catalogue families, and the three that read the rows — and the remaining five
are offered and gated on a switch that answers False here, so a run is refused
(exit 2) rather than reached and answered with an empty list. DDL extraction is
not offered at all: the dialect carries no reader for it.

| Type | Reads | `NAME` | Notes |
| :--- | :--- | :--- | :--- |
| `tables` | `system.tables` | refused | Tables, with the relation kind in `table_type` (`BASE_TABLE` / `VIEW` / `MATERIALIZED_VIEW` / `SYSTEM_TABLE`) and the storage engine in `extra`. `--include-system` adds the engine's own tables. |
| `views` | `system.tables` | view, optional | Views, with their definitions; a name describes one view. |
| `columns` | `system.columns` | table, required | One table's columns: name, type, nullability, ordinal position, default. |
| `indexes` | `system.data_skipping_indices` | table, required | One table's data-skipping indices — ClickHouse's nearest analogue to an index. |
| `partitions` | `system.parts` | table, required | One table's partitions and subpartitions, in the engine's own order, aggregated from the parts currently active. |
| `table-engine` | `system.tables` | table, required | The engine of one table, with its sorting, primary and sampling keys, plus row and byte totals. |
| `database` | `system.build_options`, `system.databases` | refused | Server version and the databases visible to this role. |
| `functions` | `system.functions` | name, optional | Built-in and user-defined functions in one catalogue; `origin` distinguishes `System` from the user-defined flavours. A name narrows the listing (and can match an alias row). |
| `dictionaries` | `system.dictionaries` | name, optional | Loaded dictionaries with their status, type, key/attribute names and types, sizes and lifetimes. `database` is `''` for configuration-file dictionaries. |
| `clusters` | `system.clusters` | cluster, optional | One record per shard/replica member; a cluster name narrows the listing to its members rather than to one server. |
| `quotas` | `system.quotas` | name, optional | Quotas with their sharing keys, durations and apply-to lists. |
| `users` | `system.users` | name, optional | Accounts with authentication *types*, default roles, host restrictions and grantee limits. Credential parameters are not projected. |
| `roles` | `system.roles` | name, optional | Roles with their id and access-control storage path. |
| `unused-indexes` | refused here | — | Offered and gated: `supports_unused_indexes_detection` answers False here, so the run is refused rather than answered empty. |
| `table-stats` | refused here | — | Offered and gated on `supports_table_stats`, which answers False here. |
| `runtime` | refused here | — | Offered and gated on `supports_runtime_stats`, which answers False here. |
| `index-stats` | refused here | — | Offered and gated on `supports_index_stats`, which answers False here. |
| `dependencies` | refused here | object, optional | Offered and gated on `supports_object_dependencies` (False here); a name narrows the graph to that object's edges. |
| `column-profiles` | the rows themselves | table, required | Answers True here: the profile is one aggregate over the rows, so every figure is exact and paid for with a full scan per column. |
| `value-samples` | the rows themselves | table, required | Answers True here, read from the rows; `--column` names the column and `--limit` caps the count (default 100). |
| `join-coverage` | the rows themselves | left table, required | Answers True here: how much two columns' value domains overlap. `--column`, `--right-table` and `--right-column` are required. |

`NAME` is a table name for `columns`, `indexes`, `partitions`,
`table-engine`, `column-profiles`, `value-samples` and `join-coverage`, and the
view itself for `views`. The six server-wide catalogue
families — `functions`, `dictionaries`, `clusters`, `quotas`, `users` and
`roles` — take an optional member name that narrows their listing; for
`clusters` that means one cluster's member rows, and for `functions` it means
the rows carrying one name, which can include an alias. `tables` and `database`
answer for the whole database, so they **refuse** a name rather than drop it: a
run that accepted one and printed the full listing would read as though it had
been narrowed. The four operational families — `unused-indexes`, `table-stats`,
`runtime` and `index-stats` — describe the server rather than one object, so a
name is refused there for the same reason. `dependencies` is the exception: a
name narrows the graph to the edges that object carries, which is a real
answer. The two exit codes say which kind of refusal happened:

*   **1** — the request was well formed but did not succeed: the connection
    failed, a query failed, or a named view does not exist.
*   **2** — the request cannot be answered here: `NAME` is used where the type
    takes none, or the connected server's capabilities do not include the type.


## Options

| Option | Default | Description |
| :--- | :--- | :--- |
| `-o, --output` | `table` | `table` (rich), `json`, `csv`, `tsv`. |
| `--database` | required (env: `CLICKHOUSE_DATABASE`) | The database to connect to **and** the database to read. ClickHouse's namespace level is a *database* and the flag says so. |
| `--include-system` | off | Include system tables. |
| `--column` | _None_ | The column a `value-samples` or `join-coverage` question is about. |
| `--right-table`, `--right-column` | _None_ | The right-hand side of a `join-coverage` question. |
| `--limit` | `100` | How many values `value-samples` lists when not given. |
| `--host`, `--port`, `--database`, `--user`, `--password` | env or defaults | Connection. `CLICKHOUSE_*` env vars are honoured, and arguments override them. |
| `--ssl` | off | Use SSL for the connection. |
| `--async` | off | **Not available**: ClickHouse is a synchronous-only backend, so this path cannot serve a request. |
| `--named-connection` | _None_ | A connection saved by the `named-connection` subcommand. |
| `--conn-param` | _None_ | Extra `key=value` connection parameters; repeatable. |
| `--rich-ascii` | off | ASCII characters for table borders. |

## Notes

*   **Read-only.** `introspect` never writes. It does not create, drop, or
    alter anything, so it is safe to run against a server whose schema
    matters.
*   **There is no namespace flag, and that is deliberate.** ClickHouse's one
    namespace level is a *database* and `--database` names it, so the flag says
    the engine's word rather than a generic one. No `--schema`, and no alias for
    it, so a caller cannot name a level that does not exist here.
*   **`partitions` reads `system.parts`, not `system.partitions`.** The parts
    view is what is live; a partition with no active parts has nothing to
    report, which is why the answer is aggregated rather than listed.
*   **`table_type` is the relation kind; the engine is in `extra`.** ClickHouse
    answers the storage engine, not a standard table type, so the kind is
    derived from the declared view-engine set (`View` and friends are views,
    `MaterializedView` its own kind, `system`-database rows system tables) and
    the engine string accompanies it instead of standing in for it.
*   **No `triggers`, no `foreign-keys`, no `constraints`, no `tablespaces`.**
    ClickHouse has neither triggers nor foreign keys, its CHECK constraints are
    DDL-declared clauses with no `system.*` catalogue table, and its storage is
    disks/parts plus storage policies rather than SQL tablespaces. So the CLI
    does not offer those types at all — they are missing from `TYPE` instead of
    accepted and then refused. An empty list from a type that was offered would
    read as "none declared", which is a different and wrong answer; the same
    command against a MySQL database returns a real list. This is a statement
    about the *engine*, and it is not the same as a capability switch: a
    `supports_*` switch that answers False says "this server cannot answer",
    while a type that is absent from the vocabulary says "this backend never
    asks". Every type that *is* offered carries a switch, and a server that
    answers False for it is refused with exit 2 and
    `Error: <type> introspection is not supported by this server`.
*   **`show.*` is not reachable from `introspect`, and that is a boundary, not
    a gap.** The backend's SHOW passthrough (`introspector.show`, 19 methods
    shared with MySQL and MariaDB) stays where it is: ClickHouse's `SHOW`
    statements and `system.tables` / `system.parts` / `system.columns` are not
    equivalent, and every type here reads `system.*`. Offering both would give
    one question two readings, one of which depends on session context.
*   **One question per invocation.** A CLI process is one connection that
    opens, answers, and closes — there is no cache carried between runs.
*   **The five gated families say "this server cannot answer", not "none".**
    `unused-indexes`, `table-stats`, `runtime`, `index-stats` and
    `dependencies` are offered rather than omitted, and each is refused by its
    switch before the introspector is reached. An offered-but-unanswered type
    is a contract the CLI keeps by refusing; printing an empty list instead
    would read as an answer of zero. DDL extraction is not offered at all,
    because ClickHouse has no `SHOW CREATE` equivalent this backend reads, so
    the CLI does not advertise a type whose capability is permanently False.

## Examples

```bash
# The two ClickHouse-specific families
python -m rhosocial.activerecord.backend.impl.clickhouse introspect partitions events
python -m rhosocial.activerecord.backend.impl.clickhouse introspect table-engine events -o json

# One view, by name
python -m rhosocial.activerecord.backend.impl.clickhouse introspect views daily_totals
python -m rhosocial.activerecord.backend.impl.clickhouse introspect views nope   # exit 1: no such view

# A name a whole-database type cannot use
python -m rhosocial.activerecord.backend.impl.clickhouse introspect tables events  # exit 2

# Another database, including its system tables
python -m rhosocial.activerecord.backend.impl.clickhouse introspect tables --database reports --include-system

# What the rows hold, not what the columns declare -- read from the rows, so exact and paid for
python -m rhosocial.activerecord.backend.impl.clickhouse introspect column-profiles events
python -m rhosocial.activerecord.backend.impl.clickhouse introspect value-samples events --column status --limit 50
python -m rhosocial.activerecord.backend.impl.clickhouse introspect join-coverage events --column user_id --right-table users --right-column id

# The server-wide catalogue families, whole or narrowed by a member name
python -m rhosocial.activerecord.backend.impl.clickhouse introspect functions -o json
python -m rhosocial.activerecord.backend.impl.clickhouse introspect functions cityHash64
python -m rhosocial.activerecord.backend.impl.clickhouse introspect dictionaries
python -m rhosocial.activerecord.backend.impl.clickhouse introspect clusters
python -m rhosocial.activerecord.backend.impl.clickhouse introspect quotas
python -m rhosocial.activerecord.backend.impl.clickhouse introspect users
python -m rhosocial.activerecord.backend.impl.clickhouse introspect roles

# Questions this dialect declines -- exit 2, "not supported by this server", not an empty list
python -m rhosocial.activerecord.backend.impl.clickhouse introspect unused-indexes
python -m rhosocial.activerecord.backend.impl.clickhouse introspect dependencies

# Object families this engine does not expose are absent from TYPE entirely
python -m rhosocial.activerecord.backend.impl.clickhouse introspect constraints    # argparse refuses
```

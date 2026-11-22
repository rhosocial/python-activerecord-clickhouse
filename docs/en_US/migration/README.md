# Migrations on the ClickHouse backend

> **Scope**: this chapter covers **only** what is specific to running ActiveRecord migrations on
> the ClickHouse backend. The migration system itself — decorators, runners, version records,
> dry runs, dependency validation, the `migrate` and `named-migration` CLIs — is documented in the
> core library's [Migration chapter](https://github.com/rhosocial/python-activerecord/blob/main/docs/en_US/migration/README.md).
> Read that chapter first; this one assumes it. Runnable scripts live in
> [`docs/examples/migration/`](../../examples/migration/README.md).

## 1. Sync only — no async migrations

`clickhouse-connect` is a synchronous-only driver. `ClickHouseBackend` is the real backend;
`AsyncClickHouseBackend` is a placeholder that raises `NotImplementedError` on instantiation.
Consequently:

- Use `run_migration_group`, `MigrationRunner`, and `BatchMigrationRunner`. Do **not** use
  `run_migration_group_async` or `AsyncMigrationRunner`.
- Do not set `@migration(async_variant=...)` — a sync function has no async partner here.
- Do not pass `--async` to the `named-migration` CLI; it will try to build the placeholder
  backend and fail fast.
- `transaction_mode` has no effect on rollback (see the next two sections).

## 2. Configuring the backend for migrations

```python
import os
from rhosocial.activerecord.backend.impl.clickhouse.backend import ClickHouseBackend
from rhosocial.activerecord.backend.impl.clickhouse.config import ClickHouseConnectionConfig

config = ClickHouseConnectionConfig(
    host=os.getenv("CLICKHOUSE_HOST", "localhost"),
    port=int(os.getenv("CLICKHOUSE_PORT", "8123")),
    database=os.getenv("CLICKHOUSE_DATABASE", "test_db"),
    username=os.getenv("CLICKHOUSE_USER", "root"),
    password=os.getenv("CLICKHOUSE_PASSWORD", "password"),
)
backend = ClickHouseBackend(connection_config=config)
backend.connect()
backend.introspect_and_adapt()  # negotiate server version and support switches
```

`ClickHouseConnectionConfig` also carries `settings`, `compress`, `connect_timeout`,
`send_receive_timeout`, and SSL/pool/charset/timezone options. `settings` is where you place
server knobs such as `mutations_sync` / `alter_sync` when your DDL relies on them. A connection
may also come from a named connection or a model's `configure(config, ClickHouseBackend)`; both
CLIs accept the usual `--host/--port/--database/--user/--password` arguments.

## 3. DDL is non-transactional and auto-applies

ClickHouse has no ACID transactions: `backend.transaction()` degrades to a no-op context
manager. There is no BEGIN/COMMIT/ROLLBACK wrapped around a migration group.

- Every statement takes effect as soon as the server accepts it; there is no pending batch to
  abort.
- If the third function of a group fails, the first two have already changed the schema. The
  runner writes no version record for the failing version — but that does not undo anything.
  You must reconcile the live schema by hand.
- Version records are bookkeeping only; editing them never reverts DDL.
- Practical consequence: always preview with `dry_run=True` first (§6).

## 4. Many ALTER / MUTATION statements are asynchronous

`CREATE` and `DROP` are effectively immediate, but `ALTER TABLE ...` and data-changing
MUTATION statements are queued by ClickHouse. The server may acknowledge them before the
change is fully applied across all parts and replicas. The backend's own UPDATE/DELETE path
forces `mutations_sync=1`, but that setting does not automatically cover arbitrary DDL emitted
by a migration function.

A "successful" migration (a version record written, `result.applied == ["v..."]`) therefore
means **"the statements were accepted"**, not **"the schema or data has settled"**. If a later
step depends on the new column or partition being present everywhere:

- set the relevant sync settings in `ClickHouseConnectionConfig.settings` (e.g.
  `mutations_sync`, `alter_sync`), or wait explicitly with a `SYSTEM` command, and
- verify through `system.*` introspection before continuing.

Keep such follow-up checks inside the same migration function so they are part of the recorded
step, and compose SQL with expression nodes rather than string concatenation (see the
[DDL chapter](../ddl/README.md)).

## 5. No rollback — DOWN is a compensating statement

Because DDL cannot be rolled back, `DOWN` is not an undo; it is a new forward action that
restores the previous shape. When authoring migrations:

- Every UP needs an explicit inverse: `CREATE TABLE` ↔ `DROP TABLE IF EXISTS`,
  `ADD COLUMN` ↔ `DROP COLUMN IF EXISTS`, `CREATE VIEW` ↔ `DROP VIEW`.
- Prefer `if_not_exists` on UP and `if_exists` on DOWN, so a partially applied group can be
  re-run after a manual repair.
- DOWN still runs in reverse group order (core behavior); keep that order consistent with your
  compensating statements.
- Do not rely on `single_transaction=True` for safety — with ClickHouse it cannot roll back
  DDL that has already been applied.

## 6. Version records and dry run (ClickHouse specifics)

- The only built-in record store is `JSONFileMigrationRecordStore`: a local file, not a
  ClickHouse table. Back it up and share it carefully — it is the sole source of truth for
  what has been applied.
- Dry run renders statements without touching the server. On a non-transactional backend it is
  the only safe preview of a DDL batch: call `run_migration_group(..., dry_run=True)` and read
  `preview.dry_run_sql` before the real run.
- With the class-style `MigrationRunner`, prefer `ctx.execute()` of named expressions so
  `--dry-run` renders correctly (see the legacy-runner caveat in the core chapter).

## 7. Version-gated features

The dialect probes the connected server's version and sets `supports_*` switches accordingly —
some settings and functions exist only on newer releases (CI covers 25.8, 26.3, and 26.7). If a
migration uses a newer ClickHouse feature:

- gate it with `backend.dialect.supports_<capability>()`, skipping or choosing an alternative on
  older servers;
- if a dialect refuses DDL (`ProtocolNotImplementedError` / `UnsupportedFeatureError`), the
  runner surfaces it as `MigrationDialectError`;
- do not hard-code release numbers — ClickHouse uses calendar versioning (`YY.M.patch`).

## 8. Two authoring styles (sync)

Both styles are documented in full in the core chapter; only their ClickHouse wiring is shown
here.

Function style (primary API):

```python
from rhosocial.activerecord.backend.migration import migration, MigrationDirection, run_migration_group

@migration("f001_create_events")
def create_events(ctx):
    if ctx.direction == MigrationDirection.UP:
        ctx.apply(MigrationEvent.create_table_statement(backend=ctx.backend))
    else:
        ctx.apply(MigrationEvent.drop_table_statement(if_exists=True, backend=ctx.backend))

preview = run_migration_group(backend, ["migration_support:create_events"], dry_run=True)
```

Class style (legacy-compatible):

```python
from rhosocial.activerecord.backend.migration import NamedMigration, MigrationContext

class CreateEventsTable(NamedMigration):
    version = "c001_create_events"

    def up(self, ctx: MigrationContext) -> None:
        ctx.apply(MigrationEvent.create_table_statement(backend=ctx.backend))

    def down(self, ctx: MigrationContext) -> None:
        ctx.apply(MigrationEvent.drop_table_statement(if_exists=True, backend=ctx.backend))
```

CLI wiring:

```bash
python -m rhosocial.activerecord.backend.impl.clickhouse named-migration \
    myapp.migrations.CreateEventsTable --host localhost --database test_db \
    --record-store ./migrations.json --dry-run
```

> Do not pass `--async`: this backend has no async implementation.

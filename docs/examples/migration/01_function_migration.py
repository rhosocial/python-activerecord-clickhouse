# docs/examples/migration/01_function_migration.py
"""Function-style migration on the ClickHouse backend: dry run -> UP -> DOWN.

Shows the pieces that are specific to ClickHouse (see docs/en_US/migration/README.md):

* configure ``ClickHouseBackend`` with ``ClickHouseConnectionConfig`` and call
  ``introspect_and_adapt()``;
* preview a non-transactional DDL batch with ``run_migration_group(..., dry_run=True)``;
* DOWN is an explicit compensating DROP — ClickHouse DDL cannot be rolled back.

Requires a running ClickHouse server; connection settings come from the usual
CLICKHOUSE_* environment variables. Run from the repository root with
``PYTHONPATH=src``:

    python docs/examples/migration/01_function_migration.py
"""

import os
import sys
import tempfile
from pathlib import Path

# Make the sibling support module importable by fully qualified name.
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from rhosocial.activerecord.backend.impl.clickhouse.backend import ClickHouseBackend
from rhosocial.activerecord.backend.impl.clickhouse.config import ClickHouseConnectionConfig
from rhosocial.activerecord.backend.migration import MigrationDirection, run_migration_group
from rhosocial.activerecord.backend.migration.record import JSONFileMigrationRecordStore

from migration_support import create_events

# module:function — the form used by run_migration_group and the `migrate` CLI.
FQN = "migration_support:create_events"


def build_config() -> ClickHouseConnectionConfig:
    return ClickHouseConnectionConfig(
        host=os.getenv("CLICKHOUSE_HOST", "localhost"),
        port=int(os.getenv("CLICKHOUSE_PORT", "8123")),
        database=os.getenv("CLICKHOUSE_DATABASE", "test_db"),
        username=os.getenv("CLICKHOUSE_USER", "root"),
        password=os.getenv("CLICKHOUSE_PASSWORD", "password"),
    )


def main() -> None:
    config = build_config()
    backend = ClickHouseBackend(connection_config=config)
    try:
        backend.connect()
    except Exception as error:  # noqa: BLE001 - any connection failure gives the same guidance
        print(f"Could not connect to ClickHouse at {config.host}:{config.port}: {error}", file=sys.stderr)
        sys.exit(1)

    store_path = Path(tempfile.gettempdir()) / "ch_migration_function_records.json"
    store = JSONFileMigrationRecordStore(store_path)
    try:
        backend.introspect_and_adapt()

        # 1) dry run — nothing is written. On a non-transactional backend this is
        #    the only safe way to preview the DDL batch before it auto-applies.
        preview = run_migration_group(backend, [create_events], dry_run=True)
        print("== dry run (no DDL written) ==")
        print("  statements:", preview.dry_run_total)
        for label, sql, params in preview.dry_run_sql:
            print(f"  [{label}] {sql}  params={params}")
        print("  records written:", preview.records_written)

        # 2) real UP — the CREATE TABLE is accepted and immediately takes effect.
        up = run_migration_group(backend, [FQN], record_store=store)
        print("\n== UP ==")
        print("  applied:", up.applied, "versions:", up.versions)
        print("  applied versions:", [record.version for record in store.get_applied()])

        # 3) DOWN — not a rollback: a compensating DROP TABLE IF EXISTS.
        down = run_migration_group(
            backend, [FQN], direction=MigrationDirection.DOWN, record_store=store
        )
        print("\n== DOWN (compensating DDL) ==")
        print("  rolled back:", down.rolled_back)
        print("  applied versions after DOWN:", [record.version for record in store.get_applied()])
    finally:
        backend.disconnect()
        if store_path.exists():
            store_path.unlink()


if __name__ == "__main__":
    main()

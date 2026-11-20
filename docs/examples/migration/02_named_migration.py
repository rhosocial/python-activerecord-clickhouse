# docs/examples/migration/02_named_migration.py
"""Class-style (named-migration) demo on the ClickHouse backend.

Drives the ``NamedMigration`` in ``migration_support.py`` through ``MigrationRunner``
and shows the equivalent ``named-migration`` CLI invocation. As everywhere on this
backend, the flow is synchronous: DOWN is an explicit compensating statement and
ClickHouse DDL is applied immediately, not inside a transaction.

Requires a running ClickHouse server. Run from the repository root with
``PYTHONPATH=src``:

    python docs/examples/migration/02_named_migration.py

Equivalent CLI (module.Class is resolved from the current working directory):

    python -m rhosocial.activerecord.backend.impl.clickhouse named-migration \
        migration_support.CreateEventsTable \
        --host localhost --database test_db --dry-run
"""

import os
import sys
import tempfile
from pathlib import Path

# Make the sibling support module importable by fully qualified name.
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from rhosocial.activerecord.backend.impl.clickhouse.backend import ClickHouseBackend
from rhosocial.activerecord.backend.impl.clickhouse.config import ClickHouseConnectionConfig
from rhosocial.activerecord.backend.migration import MigrationDirection, MigrationRunner
from rhosocial.activerecord.backend.migration.record import JSONFileMigrationRecordStore

# module.Class — the form used by `named-migration` and MigrationRunner.
FQN = "migration_support.CreateEventsTable"


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

    store_path = Path(tempfile.gettempdir()) / "ch_migration_class_records.json"
    store = JSONFileMigrationRecordStore(store_path)
    try:
        backend.introspect_and_adapt()
        runner = MigrationRunner(FQN)

        print("== dry run (UP) ==")
        result = runner.run(backend, MigrationDirection.UP, dry_run=True)
        print("  version:", result.version, "success:", result.success)

        print("\n== UP ==")
        result = runner.run(backend, MigrationDirection.UP, record_store=store)
        print("  version:", result.version, "success:", result.success)
        print("  applied:", [record.version for record in store.get_applied()])

        print("\n== DOWN (compensating DDL, reverse order) ==")
        result = runner.run(backend, MigrationDirection.DOWN, record_store=store)
        print("  version:", result.version, "success:", result.success)
        print("  applied after DOWN:", [record.version for record in store.get_applied()])
    finally:
        backend.disconnect()
        if store_path.exists():
            store_path.unlink()


if __name__ == "__main__":
    main()

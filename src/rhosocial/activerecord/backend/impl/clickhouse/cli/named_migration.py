# src/rhosocial/activerecord/backend/impl/clickhouse/cli/named_migration.py
"""named-migration subcommand — ClickHouse adapter for the shared CLI helper."""

from __future__ import annotations

from rhosocial.activerecord.backend.impl.clickhouse import ClickHouseBackend, AsyncClickHouseBackend

from .connection import create_connection_parent_parser, resolve_connection_config_from_args
from .output import create_provider


def create_parser(subparsers):
    """Create the named-migration subcommand parser.

    Provides connection and output arguments via a parent parser.
    """
    from rhosocial.activerecord.backend.migration.cli import create_named_migration_parser

    local_parent = create_connection_parent_parser()
    nm_epilog = """Examples:
  # Apply a migration
  %(prog)s myapp.migrations.v001.CreateUsersTable --host localhost --database mydb --direction up

  # Rollback
  %(prog)s myapp.migrations.v001.CreateUsersTable --host localhost --database mydb --direction down

  # Apply with record store
  %(prog)s myapp.migrations.v001.CreateUsersTable --database mydb --record-store ./migrations.json

  # Dry-run
  %(prog)s myapp.migrations.v001.CreateUsersTable --database mydb --direction up --dry-run

  # Apply asynchronously
  %(prog)s myapp.migrations.v001.CreateUsersTable --database mydb --direction up --async

  # Pass parameters to the migration
  %(prog)s myapp.migrations.v001.CreateUsersTable --param table_name=custom_table

  # List available migrations
  %(prog)s myapp.migrations --list

  # Describe a migration
  %(prog)s myapp.migrations.v001.CreateUsersTable --describe

  # Batch: apply all pending migrations in a module
  %(prog)s myapp.migrations --all --record-store ./migrations.json

  # Batch: dry-run all pending migrations
  %(prog)s myapp.migrations --all --record-store ./migrations.json --dry-run

  # Batch: rollback all applied migrations
  %(prog)s myapp.migrations --all --record-store ./migrations.json --direction down

  # Batch: wrap all migrations in a single transaction
  %(prog)s myapp.migrations --all --record-store ./migrations.json --single-transaction

End-to-end demo scripts with UP/DOWN round-trip verification:
  https://github.com/rhosocial/python-activerecord-clickhouse/tree/main/src/rhosocial/activerecord/backend/impl/clickhouse/examples/named_migrations
  PYTHONPATH=src bash demo_basic.sh
  PYTHONPATH=src bash demo_chain.sh
  PYTHONPATH=src bash demo_all.sh
"""
    return create_named_migration_parser(subparsers, local_parent, epilog=nm_epilog)


def handle(args):
    """Handle the named-migration subcommand."""
    from rhosocial.activerecord.backend.migration.cli import handle_named_migration as handle_nm

    provider = create_provider(args.output, ascii_borders=args.rich_ascii)

    backend = None

    def backend_factory():
        nonlocal backend
        config = resolve_connection_config_from_args(args)
        backend = ClickHouseBackend(connection_config=config)
        backend.connect()
        backend.introspect_and_adapt()
        return backend

    def disconnect():
        if backend and getattr(backend, "_connection", None):
            backend.disconnect()

    is_async = getattr(args, "is_async", False)
    if is_async:
        async_backend = None

        def backend_async_factory():
            nonlocal async_backend
            config = resolve_connection_config_from_args(args)
            async_backend = AsyncClickHouseBackend(connection_config=config)
            return async_backend

        async def disconnect_async():
            if async_backend and getattr(async_backend, "_connection", None):
                await async_backend.disconnect()

        handle_nm(
            args,
            provider,
            backend_factory=backend_factory,
            disconnect=disconnect,
            backend_async_factory=backend_async_factory,
            disconnect_async=disconnect_async,
        )
        return

    handle_nm(
        args,
        provider,
        backend_factory=backend_factory,
        disconnect=disconnect,
    )
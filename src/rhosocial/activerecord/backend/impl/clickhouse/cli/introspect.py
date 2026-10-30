# src/rhosocial/activerecord/backend/impl/clickhouse/cli/introspect.py
"""introspect subcommand - Database introspection.

There is no namespace flag here, and that is deliberate. ClickHouse has
exactly one namespace level and calls it a *database* -- there is no
schema under it. So ``--database``, which the connection already takes, is
the whole answer: the run connects to a database and asks about that
database. An earlier version accepted ``--schema`` and had to explain in
its help text that the value named a database anyway; the flag is gone
rather than aliased.
"""

import argparse
import asyncio
import sys
from dataclasses import asdict, is_dataclass
from enum import Enum
from typing import Any

from rhosocial.activerecord.backend.errors import ConnectionError, QueryError

from rhosocial.activerecord.backend.impl.clickhouse.backend import ClickHouseBackend
from rhosocial.activerecord.backend.impl.clickhouse.backend.async_backend import (
    AsyncClickHouseBackend,
)

from .connection import add_connection_args, resolve_connection_config_from_args
from .output import create_provider

OUTPUT_CHOICES = ["table", "json", "csv", "tsv"]

#: The single place a type name maps to the dialect capability that decides
#: whether this backend can answer it. ``INTROSPECT_TYPES`` is derived from it,
#: so a family cannot be offered without a switch saying it may be -- and the
#: order below is the order the parser and ``--help`` print.
#:
#: ``foreign-keys`` and ``triggers`` are **not** here, and their absence says
#: something different from a switch that answers False. This engine neither
#: declares nor enforces foreign keys and has no triggers at all, so the
#: question is not part of this backend's vocabulary: argparse refuses the word
#: and the answer is "this backend does not ask" rather than "this server
#: cannot answer". A capability switch is for the second case -- a family the
#: dialect knows and a particular server version may lack. Mixing the two is
#: what made an earlier attempt to arbitrate types in core unworkable.
_TYPE_CAPABILITIES = {
    "tables": "supports_table_introspection",
    "views": "supports_view_introspection",
    "columns": "supports_column_introspection",
    "indexes": "supports_index_introspection",
    "partitions": "supports_partition_introspection",
    "table-engine": "supports_table_engine_introspection",
    "database": "supports_database_info",
}

INTROSPECT_TYPES = list(_TYPE_CAPABILITIES)

#: What the optional NAME positional means for each type.
#:
#: ``required`` -- the type asks about one table and cannot be answered without
#: it. ``optional`` -- a catalogue family that can also answer for one member,
#: so a given name narrows it (and a name that matches nothing is an error, not
#: an empty list). ``forbidden`` -- the family has no single-member question
#: here. ``tables`` must stay one: answering for one table would fill in its
#: columns and indexes, which is the aggregate this command deliberately
#: dropped.
_NAME_RULE = {
    "tables": "forbidden",
    "views": "optional",
    "columns": "required",
    "indexes": "required",
    "partitions": "required",
    "table-engine": "required",
    "database": "forbidden",
}


def _require_capability(args, backend) -> None:
    """Refuse a type the connected server cannot answer.

    The dialect is adapted before this runs, so the switch answers for the
    server in front of us rather than for the newest release this backend
    knows. A stub standing in for the backend (the offline CLI tests) may carry
    no dialect at all; a real one always does.
    """
    switch = _TYPE_CAPABILITIES.get(args.type)
    if switch is None:
        return
    dialect = getattr(backend, "dialect", None)
    if dialect is None:
        return
    supported = getattr(dialect, switch, None)
    if supported is None or supported():
        return
    print(
        f"Error: {args.type} introspection is not supported by this server",
        file=sys.stderr,
    )
    sys.exit(2)


def _validate_name(args) -> None:
    """Refuse a NAME the type cannot use, before anything connects.

    A silently ignored argument is the worst of the three outcomes: the run
    succeeds, prints a full listing, and reads as though it had been narrowed.
    Only ``forbidden`` is decided here; a ``required`` name that is missing is
    still reported by the branch that needs it, with the exit code it always
    had.
    """
    if _NAME_RULE.get(args.type) == "forbidden" and args.name:
        print(
            f"Error: '{args.type}' introspection answers for the whole database "
            f"and takes no name",
            file=sys.stderr,
        )
        sys.exit(2)


def create_parser(subparsers):
    """Create the introspect subcommand parser."""
    parser = subparsers.add_parser(
        "introspect",
        help="Database introspection",
        epilog="""Examples:
  # List all tables in database
  %(prog)s tables --database mydb

  # List all views
  %(prog)s views --database mydb

  # Describe one view
  %(prog)s views v1 --database mydb

  # Get detailed table info (columns and indexes)
  %(prog)s table users --database mydb

  # Get column details for a table
  %(prog)s columns users --database mydb

  # List a table's partitions (from system.parts, grouped by partition_id)
  %(prog)s partitions events --database mydb

  # Show a table's engine and key expressions (from system.tables)
  %(prog)s table-engine events --database mydb

  # Output as JSON
  %(prog)s tables --database mydb -o json

  # Using environment variables for connection
  export CLICKHOUSE_HOST=localhost CLICKHOUSE_DATABASE=mydb CLICKHOUSE_USER=root CLICKHOUSE_PASSWORD=secret
  %(prog)s tables
""",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    # Output format
    parser.add_argument(
        "-o",
        "--output",
        choices=OUTPUT_CHOICES,
        default="table",
        help="Output format (default: table)",
    )

    # Connection arguments
    add_connection_args(parser)

    # Rich display options
    parser.add_argument(
        "--rich-ascii",
        action="store_true",
        help="Use ASCII characters for rich table borders.",
    )

    # introspect-specific arguments
    # The list above is this backend's own answer, written here because only
    # ClickHouse can say which families it has. `foreign-keys` and `triggers`
    # are absent on purpose: the engine neither declares nor enforces foreign
    # keys and has no triggers, so offering those questions would advertise an
    # error rather than an answer.
    parser.add_argument(
        "type",
        choices=INTROSPECT_TYPES,
        help="Introspection type: " + ", ".join(INTROSPECT_TYPES),
    )
    parser.add_argument(
        "name",
        nargs="?",
        default=None,
        help="Table/view name (required for some types)",
    )
    parser.add_argument(
        "--include-system",
        action="store_true",
        help="Include system tables in output",
    )

    return parser


def handle(args):
    """Handle the introspect subcommand."""
    provider = create_provider(args.output, ascii_borders=args.rich_ascii)

    _validate_name(args)

    named_conn = getattr(args, "named_connection", None)
    if not named_conn and not args.database:
        print("Error: --database is required for introspection", file=sys.stderr)
        sys.exit(1)

    config = resolve_connection_config_from_args(args)

    if args.is_async:
        backend = AsyncClickHouseBackend(connection_config=config)
        asyncio.run(_handle_introspect_async(args, backend, provider))
    else:
        backend = ClickHouseBackend(connection_config=config)
        _handle_introspect_sync(args, backend, provider)


# ---------------------------------------------------------------------------
# Internal helper functions
# ---------------------------------------------------------------------------


def _serialize_for_output(obj: Any) -> Any:
    """Serialize object for JSON output, handling non-serializable types."""
    if obj is None:
        return None
    if hasattr(obj, "model_dump"):
        try:
            result = obj.model_dump(mode="json")
            return _serialize_for_output(result)
        except TypeError:
            result = obj.model_dump()
            return _serialize_for_output(result)
    if is_dataclass(obj) and not isinstance(obj, type):
        return {k: _serialize_for_output(v) for k, v in asdict(obj).items()}
    if isinstance(obj, Enum):
        return obj.value
    if isinstance(obj, dict):
        return {k: _serialize_for_output(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_serialize_for_output(item) for item in obj]
    if isinstance(obj, (str, int, float, bool)):
        return obj
    return str(obj)


def _handle_introspect_sync(args, backend: ClickHouseBackend, provider):
    """Handle introspect subcommand synchronously."""
    try:
        backend.connect()
        # Ask the server which version it is before any query is formatted:
        # every capability gate reads the adapted dialect, and the parsers
        # report the version through the same adaptation.
        backend.introspect_and_adapt()
        _require_capability(args, backend)

        introspector = backend.introspector

        if args.type == "tables":
            tables = introspector.list_tables(schema=None, include_system=args.include_system)
            data = _serialize_for_output(tables)
            provider.display_results(data, title="Tables")

        elif args.type == "views":
            if args.name:
                # The core method calls its namespace parameter ``schema``;
                # ClickHouse's one namespace level is its database, and
                # ``None`` means the database this run connected to. The name
                # above is not translated: it is the view name ``system.tables``
                # lists.
                view = introspector.get_view_info(args.name, schema=None)
                if view is None:
                    print(f"Error: View '{args.name}' not found", file=sys.stderr)
                    sys.exit(1)
                provider.display_results(_serialize_for_output([view]), title=f"View {args.name}")
            else:
                views = introspector.list_views(schema=None)
                data = _serialize_for_output(views)
                provider.display_results(data, title="Views")

        elif args.type == "columns":
            if not args.name:
                print("Error: Table name is required for 'columns' introspection", file=sys.stderr)
                sys.exit(1)
            columns = introspector.list_columns(args.name, schema=None)
            data = _serialize_for_output(columns)
            provider.display_results(data, title=f"Columns of {args.name}")

        elif args.type == "indexes":
            if not args.name:
                print("Error: Table name is required for 'indexes' introspection", file=sys.stderr)
                sys.exit(1)
            indexes = introspector.list_indexes(args.name, schema=None)
            data = _serialize_for_output(indexes)
            provider.display_results(data, title=f"Indexes of {args.name}")

        elif args.type == "partitions":
            if not args.name:
                print(
                    "Error: Table name is required for 'partitions' introspection", file=sys.stderr
                )
                sys.exit(1)
            # This backend has no schema layer, so the method's parameter is
            # named ``database`` and ``None`` means the connected database.
            partitions = introspector.list_partitions(args.name, database=None)
            data = _serialize_for_output(partitions)
            provider.display_results(data, title=f"Partitions of {args.name}")

        elif args.type == "table-engine":
            if not args.name:
                print(
                    "Error: Table name is required for 'table-engine' introspection",
                    file=sys.stderr,
                )
                sys.exit(1)
            engine = introspector.get_table_engine(args.name, database=None)
            if engine is None:
                print(f"Error: Table '{args.name}' not found", file=sys.stderr)
                sys.exit(1)
            provider.display_results(
                [_serialize_for_output(engine)], title=f"Engine of {args.name}"
            )

        elif args.type == "database":
            info = introspector.get_database_info()
            data = _serialize_for_output(info)
            provider.display_results([data], title="Database Info")

    except ConnectionError as e:
        provider.display_connection_error(e)
        sys.exit(1)
    except QueryError as e:
        provider.display_query_error(e)
        sys.exit(1)
    except Exception as e:
        print(f"Error during introspection: {e}", file=sys.stderr)
        sys.exit(1)
    finally:
        if backend._connection:  # type: ignore
            backend.disconnect()


async def _handle_introspect_async(args, backend: AsyncClickHouseBackend, provider):
    """Handle introspect subcommand asynchronously."""
    try:
        await backend.connect()
        await backend.introspect_and_adapt()
        _require_capability(args, backend)

        introspector = backend.introspector

        if args.type == "tables":
            tables = await introspector.list_tables(schema=None, include_system=args.include_system)
            data = _serialize_for_output(tables)
            provider.display_results(data, title="Tables")

        elif args.type == "views":
            if args.name:
                # Same rule as the synchronous handler: ``schema`` is
                # ClickHouse's database in the core method's vocabulary, and
                # ``None`` is the connected one.
                view = await introspector.get_view_info(args.name, schema=None)
                if view is None:
                    print(f"Error: View '{args.name}' not found", file=sys.stderr)
                    sys.exit(1)
                provider.display_results(_serialize_for_output([view]), title=f"View {args.name}")
            else:
                views = await introspector.list_views(schema=None)
                data = _serialize_for_output(views)
                provider.display_results(data, title="Views")

        elif args.type == "columns":
            if not args.name:
                print("Error: Table name is required for 'columns' introspection", file=sys.stderr)
                sys.exit(1)
            columns = await introspector.list_columns(args.name, schema=None)
            data = _serialize_for_output(columns)
            provider.display_results(data, title=f"Columns of {args.name}")

        elif args.type == "indexes":
            if not args.name:
                print("Error: Table name is required for 'indexes' introspection", file=sys.stderr)
                sys.exit(1)
            indexes = await introspector.list_indexes(args.name, schema=None)
            data = _serialize_for_output(indexes)
            provider.display_results(data, title=f"Indexes of {args.name}")

        elif args.type == "partitions":
            if not args.name:
                print(
                    "Error: Table name is required for 'partitions' introspection", file=sys.stderr
                )
                sys.exit(1)
            # This backend has no schema layer, so the method's parameter is
            # named ``database`` and ``None`` means the connected database.
            partitions = await introspector.list_partitions(args.name, database=None)
            data = _serialize_for_output(partitions)
            provider.display_results(data, title=f"Partitions of {args.name}")

        elif args.type == "table-engine":
            if not args.name:
                print(
                    "Error: Table name is required for 'table-engine' introspection",
                    file=sys.stderr,
                )
                sys.exit(1)
            engine = await introspector.get_table_engine(args.name, database=None)
            if engine is None:
                print(f"Error: Table '{args.name}' not found", file=sys.stderr)
                sys.exit(1)
            provider.display_results(
                [_serialize_for_output(engine)], title=f"Engine of {args.name}"
            )

        elif args.type == "database":
            info = await introspector.get_database_info()
            data = _serialize_for_output(info)
            provider.display_results([data], title="Database Info")

    except ConnectionError as e:
        provider.display_connection_error(e)
        sys.exit(1)
    except QueryError as e:
        provider.display_query_error(e)
        sys.exit(1)
    except Exception as e:
        print(f"Error during introspection: {e}", file=sys.stderr)
        sys.exit(1)
    finally:
        if backend._connection:  # type: ignore
            await backend.disconnect()

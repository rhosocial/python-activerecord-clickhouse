# src/rhosocial/activerecord/backend/impl/clickhouse/cli/introspect.py
"""introspect subcommand - Database introspection.

There is no namespace flag here, and that is deliberate. ClickHouse has
exactly one namespace level and calls it a *database* -- there is no
schema under it. So ``--database``, which the connection already takes, is
the whole answer: the run connects to a database and asks about that
database. An earlier version accepted ``--schema`` and had to explain in
its help text that the value named a database anyway; the flag is gone
rather than aliased.

The twenty-one families ``_TYPE_CAPABILITIES`` names are the ones this dialect
answers or declares it does not, and the advertised list is derived from the
mapping rather than written a second time -- so a family cannot be offered
without saying which switch decides whether the connected server can answer
it. Five of the twenty-one answer ``False`` here, because ClickHouse has no
statistics collector and no dependency graph: the gate refuses those before
the introspector is reached, which is what keeps "this server cannot report
it" apart from "this database has none". The sixteen that answer answer the
question; the nine catalogue families read ``system.*``, the three data
families read the rows, and this backend's introspection genuinely ends
there. DDL extraction is not part of the vocabulary: the dialect carries no
reader for it, so the CLI does not offer the type.

The six server-wide catalogue families -- ``functions``, ``dictionaries``,
``clusters``, ``quotas``, ``users`` and ``roles`` -- are not scoped to a
database. Each takes an optional NAME that narrows the listing to one member;
``clusters`` narrows to one cluster's member rows rather than to a single
server, and ``functions`` narrows to the rows carrying one name, which can
include an alias beside the function it names.

``runtime_types`` is the one cell no other engine in this family can fill, so
it belongs to the profile row and not to a shared column: the CLI prints the
row the introspector returns with the field on it, because dropping a
backend's own fact would be a quieter kind of wrong than not having it.

``NAME`` is required, optional or refused per type, and the rule for each
lives in ``_NAME_RULE`` rather than inside the question that needs it:
``_validate_name`` reads the table once, so a name a type has no question
for is refused with exit 2 rather than parsed and dropped, and a type added
without a rule is a type nobody has decided for.
"""

import argparse
import asyncio
import sys
from dataclasses import asdict, is_dataclass
from enum import Enum
from typing import Any, Dict

from rhosocial.activerecord.backend.errors import ConnectionError, QueryError

from rhosocial.activerecord.backend.impl.clickhouse.backend import ClickHouseBackend
from rhosocial.activerecord.backend.impl.clickhouse.backend.async_backend import (
    AsyncClickHouseBackend,
)

from .connection import add_connection_args, resolve_connection_config_from_args
from .output import OUTPUT_CHOICES, create_provider

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
    # ---- the server-wide catalogue families ----
    # None of these is scoped to one database: functions, clusters, quotas,
    # users and roles are server-wide relations, and dictionaries carries its
    # own database field (the empty string for configuration-file entries).
    # Each accepts an optional NAME that narrows the listing rather than
    # selecting a single row.
    "functions": "supports_function_introspection",
    "dictionaries": "supports_dictionary_introspection",
    "clusters": "supports_cluster_introspection",
    "quotas": "supports_quota_introspection",
    "users": "supports_user_introspection",
    "roles": "supports_role_introspection",
    # ---- the operational families ----
    # Each is a listing over the connection's scope, so none takes a NAME
    # except ``dependencies``, which one name narrows to the edges that
    # object carries. These read a statistics collector or a catalogue rather
    # than the schema structure, which is why they are separate types and not
    # columns on ``tables``. The dialect answers False for every one of them,
    # and the gate is what the run meets.
    "unused-indexes": "supports_unused_indexes_detection",
    "table-stats": "supports_table_stats",
    "runtime": "supports_runtime_stats",
    "index-stats": "supports_index_stats",
    "dependencies": "supports_object_dependencies",
    # ---- the one-object families ----
    # The profiles of one table and the samples of one of its columns. Both
    # read the rows themselves, so every figure is exact and paid for in time.
    "column-profiles": "supports_column_data_profile",
    "value-samples": "supports_column_value_sample",
    "join-coverage": "supports_join_coverage",
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
#:
#: The order is the order ``_TYPE_CAPABILITIES`` declares and the parser and
#: ``--help`` print, and the two tables cover the same keys: a type offered
#: without a rule is a type whose NAME decision nobody has made. The tests
#: assert both halfs of that -- the set, and the table's contents.
_NAME_RULE = {
    "tables": "forbidden",
    "views": "optional",
    "columns": "required",
    "indexes": "required",
    "partitions": "required",
    "table-engine": "required",
    # The server-wide catalogue families all take an optional NAME: a name
    # narrows the listing to that member. ``clusters`` narrows to one cluster's
    # member rows, and ``functions`` narrows to the rows carrying one name
    # (which can include an alias beside the function it names).
    "functions": "optional",
    "dictionaries": "optional",
    "clusters": "optional",
    "quotas": "optional",
    "users": "optional",
    "roles": "optional",
    # The four operational families answer for the whole database. A NAME
    # would read as a narrowing the question has no way to express.
    "unused-indexes": "forbidden",
    "table-stats": "forbidden",
    "runtime": "forbidden",
    "index-stats": "forbidden",
    # A name narrows the graph to the edges that object carries -- "what
    # breaks if I drop this" -- so it is optional here the way a view's is.
    "dependencies": "optional",
    # The one-object families: the name is the table, and the column is
    # named on its own flag. ``join-coverage`` asks about two tables; the
    # left one is NAME and the right one is a flag.
    "column-profiles": "required",
    "value-samples": "required",
    "join-coverage": "required",
    "database": "forbidden",
}

#: Options whose meaning depends on the type, and whether they must be given.
#:
#: ``--column`` is read by ``value-samples`` (which column to sample) and by
#: ``join-coverage`` (the left column); the two join flags are read only by
#: ``join-coverage``. A flag supplied to a type that does not read it is
#: refused rather than ignored, for the same reason a NAME nothing reads is:
#: a silently dropped argument produces a successful run that looks like it
#: answered a narrower question.
_TYPE_OPTIONS = {
    "value-samples": (
        ("column", "--column", True),
        ("limit", "--limit", False),
    ),
    "join-coverage": (
        ("column", "--column", True),
        ("right_table", "--right-table", True),
        ("right_column", "--right-column", True),
    ),
}

#: Every option in ``_TYPE_OPTIONS``, by attribute, for the stray-flag check.
_TYPE_OPTION_FLAGS = {
    attribute: flag
    for options in _TYPE_OPTIONS.values()
    for attribute, flag, _required in options
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
    A ``required`` name that is missing is the other half of the rule: the
    question cannot be asked at all, so it is an incomplete invocation rather
    than a bug report from the branch that needed it.
    """
    rule = _NAME_RULE.get(args.type)
    if rule == "required" and not args.name:
        # The same code a missing ``--database`` gets: an incomplete
        # invocation, not a request this backend refuses. 2 is reserved for
        # the two things the CLI newly declines to do -- answer for a family
        # the server cannot, and accept a NAME the type has no use for.
        print(
            f"Error: Table name is required for '{args.type}' introspection",
            file=sys.stderr,
        )
        sys.exit(1)
    if rule == "forbidden" and args.name:
        print(
            f"Error: '{args.type}' introspection answers for the whole database "
            f"and takes no name",
            file=sys.stderr,
        )
        sys.exit(2)


def _validate_options(args) -> None:
    """Refuse a flag the type does not read, or a missing one it needs.

    NAME has a rule table for the same reason: an option accepted by the
    parser and ignored by the branch yields a run that succeeds and reads as
    though it had answered the narrowed question. A missing required option is
    an incomplete invocation (exit 1); an option the type has no use for is a
    request this command declines (exit 2), like a NAME it cannot use.
    """
    options = _TYPE_OPTIONS.get(args.type, ())
    accepted = {attribute for attribute, _flag, _required in options}

    missing = [
        flag
        for attribute, flag, required in options
        if required and not getattr(args, attribute, None)
    ]
    if missing:
        print(
            f"Error: {', '.join(missing)} is required for "
            f"'{args.type}' introspection",
            file=sys.stderr,
        )
        sys.exit(1)

    for attribute, flag in _TYPE_OPTION_FLAGS.items():
        if attribute in accepted:
            continue
        if getattr(args, attribute, None) not in (None, ""):
            print(
                f"Error: '{args.type}' introspection takes no {flag}",
                file=sys.stderr,
            )
            sys.exit(2)


def _value_sample_arguments(args) -> Dict[str, int]:
    """The optional arguments ``value-samples`` sends, given the parsed argument.

    ``limit`` is forwarded only when the caller supplied ``--limit``. When the
    flag is absent the introspector's signature answers with its own default,
    so a forwarder that filled in ``100`` would be a second place writing a
    number the signature already owns -- and a place no test could keep in
    step with it.
    """
    limit = getattr(args, "limit", None)
    return {} if limit is None else {"limit": limit}


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

  # Get column details for a table
  %(prog)s columns users --database mydb

  # List a table's partitions (from system.parts, grouped by partition_id)
  %(prog)s partitions events --database mydb

  # Show a table's engine and key expressions (from system.tables)
  %(prog)s table-engine events --database mydb

  # The server-wide catalogue families: built-in and user-defined functions,
  # dictionaries, cluster members, quotas, accounts and roles. A NAME narrows
  # each listing; no NAME lists the whole catalogue.
  %(prog)s functions --database mydb
  %(prog)s functions myFunction --database mydb
  %(prog)s dictionaries --database mydb
  %(prog)s clusters --database mydb
  %(prog)s quotas --database mydb
  %(prog)s users --database mydb
  %(prog)s roles --database mydb

  # Operational readings over the whole database: indexes with no recorded
  # use, per-table and per-index counters, live runtime facts, and the
  # dependency graph (which a NAME narrows to one object's edges)
  %(prog)s unused-indexes --database mydb
  %(prog)s table-stats --database mydb
  %(prog)s index-stats --database mydb
  %(prog)s runtime --database mydb
  %(prog)s dependencies --database mydb
  %(prog)s dependencies events --database mydb

  # The exact per-column profiles and the values one column holds. Both
  # read every row, so they are paid for.
  %(prog)s column-profiles events --database mydb
  %(prog)s value-samples events --column code --limit 20 --database mydb

  # How much two columns' value domains overlap
  %(prog)s join-coverage events --column code --right-table cities \\
      --right-column id --database mydb

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
        help=(
            "Object name: a table for columns/indexes/partitions/table-engine/"
            "column-profiles/value-samples/join-coverage (required), the "
            "object itself for views, dependencies and the server-wide catalogue "
            "families (optional); refused for tables, database, unused-indexes, "
            "table-stats, index-stats and runtime"
        ),
    )
    # The three families that ask about a column or a second table carry the
    # names the probe needs. They stay flags rather than more positionals
    # because ``name`` already means "the table" everywhere else, and
    # ``value-samples events.code`` would read as a dotted object name.
    parser.add_argument(
        "--column",
        default=None,
        help=(
            "Column name: the column to sample for value-samples, and the "
            "left column for join-coverage"
        ),
    )
    parser.add_argument(
        "--right-table",
        dest="right_table",
        default=None,
        help="Right-hand table for join-coverage",
    )
    parser.add_argument(
        "--right-column",
        dest="right_column",
        default=None,
        help="Right-hand column for join-coverage",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help=(
            "Maximum values to list for value-samples "
            "(default: the introspector's own limit)."
        ),
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
    _validate_options(args)

    named_conn = getattr(args, "named_connection", None)
    if not named_conn and not args.database:
        print("Error: --database is required for introspection", file=sys.stderr)
        sys.exit(1)

    config = resolve_connection_config_from_args(args)

    if args.is_async:
        # ``AsyncClickHouseBackend`` is a fail-fast placeholder: its constructor
        # raises. Catching that here keeps the refusal readable -- the same
        # sentence ``query`` uses -- instead of a traceback out of the
        # constructor, which is what an unguarded call produced.
        try:
            backend = AsyncClickHouseBackend(connection_config=config)
        except NotImplementedError:
            print(
                "Error: --async is not supported by the ClickHouse backend. "
                "clickhouse-connect is a synchronous-only library.",
                file=sys.stderr,
            )
            sys.exit(1)
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
            # ``_validate_name`` has already refused a run without a name:
            # every figure below is that table's own.
            columns = introspector.list_columns(args.name, schema=None)
            data = _serialize_for_output(columns)
            provider.display_results(data, title=f"Columns of {args.name}")

        elif args.type == "indexes":
            indexes = introspector.list_indexes(args.name, schema=None)
            data = _serialize_for_output(indexes)
            provider.display_results(data, title=f"Indexes of {args.name}")

        elif args.type == "partitions":
            # This backend has no schema layer, so the method's parameter is
            # named ``database`` and ``None`` means the connected database.
            partitions = introspector.list_partitions(args.name, database=None)
            data = _serialize_for_output(partitions)
            provider.display_results(data, title=f"Partitions of {args.name}")

        elif args.type == "table-engine":
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

        # ---- the server-wide catalogue families ----------------------------
        # None is scoped to one database; each takes an optional NAME that
        # narrows the listing to that member (a cluster name narrows to that
        # cluster's members, and a function name to the rows carrying it).

        elif args.type == "functions":
            functions = introspector.list_functions(name=args.name)
            data = _serialize_for_output(functions)
            title = f"Function {args.name}" if args.name else "Functions"
            provider.display_results(data, title=title)

        elif args.type == "dictionaries":
            dictionaries = introspector.list_dictionaries(name=args.name)
            data = _serialize_for_output(dictionaries)
            title = f"Dictionary {args.name}" if args.name else "Dictionaries"
            provider.display_results(data, title=title)

        elif args.type == "clusters":
            clusters = introspector.list_clusters(name=args.name)
            data = _serialize_for_output(clusters)
            title = f"Cluster {args.name}" if args.name else "Clusters"
            provider.display_results(data, title=title)

        elif args.type == "quotas":
            quotas = introspector.list_quotas(name=args.name)
            data = _serialize_for_output(quotas)
            title = f"Quota {args.name}" if args.name else "Quotas"
            provider.display_results(data, title=title)

        elif args.type == "users":
            users = introspector.list_users(name=args.name)
            data = _serialize_for_output(users)
            title = f"User {args.name}" if args.name else "Users"
            provider.display_results(data, title=title)

        elif args.type == "roles":
            roles = introspector.list_roles(name=args.name)
            data = _serialize_for_output(roles)
            title = f"Role {args.name}" if args.name else "Roles"
            provider.display_results(data, title=title)

        # ---- the operational families -------------------------------------
        # These read a statistics collector or a catalogue rather than the
        # schema structure: each one is a listing of the whole database's
        # scope, so none takes a name (the dependency graph may be narrowed
        # to one object, and answers the whole graph without it).

        elif args.type == "unused-indexes":
            indexes = introspector.list_unused_indexes(schema=None)
            data = _serialize_for_output(indexes)
            provider.display_results(data, title="Unused Indexes")

        elif args.type == "table-stats":
            stats = introspector.list_table_usage_stats(schema=None)
            data = _serialize_for_output(stats)
            provider.display_results(data, title="Table Usage Stats")

        elif args.type == "runtime":
            metrics = introspector.list_runtime_metrics(schema=None)
            data = _serialize_for_output(metrics)
            provider.display_results(data, title="Runtime Metrics")

        elif args.type == "index-stats":
            stats = introspector.list_index_usage_stats(schema=None)
            data = _serialize_for_output(stats)
            provider.display_results(data, title="Index Usage Stats")

        elif args.type == "dependencies":
            # A name narrows the graph to the edges that object carries --
            # "what breaks if I drop this" -- rather than asking a different
            # family, so it is optional here the way a view's name is.
            dependencies = introspector.list_object_dependencies(
                object_name=args.name, schema=None
            )
            data = _serialize_for_output(dependencies)
            title = f"Dependencies of {args.name}" if args.name else "Object Dependencies"
            provider.display_results(data, title=title)

        # ---- the one-object families --------------------------------------
        # The profiles of one table or one column of it: the name is the table
        # and the column is named on its own flag.

        elif args.type == "column-profiles":
            # The note goes to stderr so the machine formats stay parseable,
            # and each row carries ``source='aggregate'`` itself.
            print(
                "Note: column profiles are aggregated from the rows themselves "
                "(source='aggregate') -- exact, and paid for with a full scan per column.",
                file=sys.stderr,
            )
            profiles = introspector.list_column_data_profiles(args.name, schema=None)
            data = _serialize_for_output(profiles)
            provider.display_results(data, title=f"Column profiles of {args.name}")

        elif args.type == "value-samples":
            samples = introspector.sample_column_values(
                args.name,
                args.column,
                schema=None,
                **_value_sample_arguments(args),
            )
            data = _serialize_for_output(samples)
            provider.display_results(data, title=f"Values of {args.name}.{args.column}")

        elif args.type == "join-coverage":
            coverage = introspector.estimate_join_coverage(
                args.name,
                args.column,
                args.right_table,
                args.right_column,
                schema=None,
            )
            if coverage is None:
                # A column with nothing to match answers "no measurement",
                # which is not zero overlap; printing a row of nulls would
                # read as a measured zero.
                print(
                    f"Error: no coverage could be measured for {args.name}.{args.column} "
                    f"and {args.right_table}.{args.right_column}",
                    file=sys.stderr,
                )
                sys.exit(1)
            data = _serialize_for_output([coverage])
            provider.display_results(data, title="Join Coverage")

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
    """Handle introspect subcommand asynchronously.

    Kept correct even though the CLI refuses ``--async``: the backend it would
    run against is a fail-fast placeholder, so the day a real async backend
    exists the question is "connect it", not "write it". Before that, these
    call sites named five methods no introspector class has.
    """
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
            # The same rule as the synchronous handler: ``_validate_name``
            # has already refused a run without a name.
            columns = await introspector.list_columns(args.name, schema=None)
            data = _serialize_for_output(columns)
            provider.display_results(data, title=f"Columns of {args.name}")

        elif args.type == "indexes":
            indexes = await introspector.list_indexes(args.name, schema=None)
            data = _serialize_for_output(indexes)
            provider.display_results(data, title=f"Indexes of {args.name}")

        elif args.type == "partitions":
            # This backend has no schema layer, so the method's parameter is
            # named ``database`` and ``None`` means the connected database.
            partitions = await introspector.list_partitions(args.name, database=None)
            data = _serialize_for_output(partitions)
            provider.display_results(data, title=f"Partitions of {args.name}")

        elif args.type == "table-engine":
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

        elif args.type == "functions":
            functions = await introspector.list_functions(name=args.name)
            data = _serialize_for_output(functions)
            title = f"Function {args.name}" if args.name else "Functions"
            provider.display_results(data, title=title)

        elif args.type == "dictionaries":
            dictionaries = await introspector.list_dictionaries(name=args.name)
            data = _serialize_for_output(dictionaries)
            title = f"Dictionary {args.name}" if args.name else "Dictionaries"
            provider.display_results(data, title=title)

        elif args.type == "clusters":
            clusters = await introspector.list_clusters(name=args.name)
            data = _serialize_for_output(clusters)
            title = f"Cluster {args.name}" if args.name else "Clusters"
            provider.display_results(data, title=title)

        elif args.type == "quotas":
            quotas = await introspector.list_quotas(name=args.name)
            data = _serialize_for_output(quotas)
            title = f"Quota {args.name}" if args.name else "Quotas"
            provider.display_results(data, title=title)

        elif args.type == "users":
            users = await introspector.list_users(name=args.name)
            data = _serialize_for_output(users)
            title = f"User {args.name}" if args.name else "Users"
            provider.display_results(data, title=title)

        elif args.type == "roles":
            roles = await introspector.list_roles(name=args.name)
            data = _serialize_for_output(roles)
            title = f"Role {args.name}" if args.name else "Roles"
            provider.display_results(data, title=title)

        # The async twins of the nine branches above: same method, same
        # argument and same title, awaited. They are written out rather than
        # shared with the sync chain because the executor is the only thing
        # that differs, and a shared body would have to carry an ``await``
        # flag that reads worse than the duplicate.

        elif args.type == "unused-indexes":
            indexes = await introspector.list_unused_indexes(schema=None)
            data = _serialize_for_output(indexes)
            provider.display_results(data, title="Unused Indexes")

        elif args.type == "table-stats":
            stats = await introspector.list_table_usage_stats(schema=None)
            data = _serialize_for_output(stats)
            provider.display_results(data, title="Table Usage Stats")

        elif args.type == "runtime":
            metrics = await introspector.list_runtime_metrics(schema=None)
            data = _serialize_for_output(metrics)
            provider.display_results(data, title="Runtime Metrics")

        elif args.type == "index-stats":
            stats = await introspector.list_index_usage_stats(schema=None)
            data = _serialize_for_output(stats)
            provider.display_results(data, title="Index Usage Stats")

        elif args.type == "dependencies":
            dependencies = await introspector.list_object_dependencies(
                object_name=args.name, schema=None
            )
            data = _serialize_for_output(dependencies)
            title = f"Dependencies of {args.name}" if args.name else "Object Dependencies"
            provider.display_results(data, title=title)

        elif args.type == "column-profiles":
            print(
                "Note: column profiles are aggregated from the rows themselves "
                "(source='aggregate') -- exact, and paid for with a full scan per column.",
                file=sys.stderr,
            )
            profiles = await introspector.list_column_data_profiles(
                args.name, schema=None
            )
            data = _serialize_for_output(profiles)
            provider.display_results(data, title=f"Column profiles of {args.name}")

        elif args.type == "value-samples":
            samples = await introspector.sample_column_values(
                args.name,
                args.column,
                schema=None,
                **_value_sample_arguments(args),
            )
            data = _serialize_for_output(samples)
            provider.display_results(data, title=f"Values of {args.name}.{args.column}")

        elif args.type == "join-coverage":
            coverage = await introspector.estimate_join_coverage(
                args.name,
                args.column,
                args.right_table,
                args.right_column,
                schema=None,
            )
            if coverage is None:
                print(
                    f"Error: no coverage could be measured for {args.name}.{args.column} "
                    f"and {args.right_table}.{args.right_column}",
                    file=sys.stderr,
                )
                sys.exit(1)
            data = _serialize_for_output([coverage])
            provider.display_results(data, title="Join Coverage")

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

# src/rhosocial/activerecord/backend/impl/clickhouse/cli/connection.py
"""Connection argument parsing and backend creation for ClickHouse CLI."""

import os


def add_connection_args(parser):
    """Add ClickHouse connection arguments to a subcommand parser.

    Each subcommand that needs a database connection calls this.
    """
    parser.add_argument(
        "--host",
        default=os.getenv("CLICKHOUSE_HOST", "localhost"),
        help="Database host (env: CLICKHOUSE_HOST, default: localhost)",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=int(os.getenv("CLICKHOUSE_PORT", "8123")),
        help="Database port (env: CLICKHOUSE_PORT, default: 8123)",
    )
    parser.add_argument(
        "--database",
        default=os.getenv("CLICKHOUSE_DATABASE"),
        help="Database name (env: CLICKHOUSE_DATABASE, optional for some operations)",
    )
    parser.add_argument(
        "--user",
        default=os.getenv("CLICKHOUSE_USER", "root"),
        help="Database user (env: CLICKHOUSE_USER, default: root)",
    )
    parser.add_argument(
        "--password",
        default=os.getenv("CLICKHOUSE_PASSWORD", ""),
        help="Database password (env: CLICKHOUSE_PASSWORD)",
    )
    parser.add_argument(
        "--ssl",
        choices=["auto", "require", "verify-ca", "verify-full", "disabled"],
        default="auto",
        help="SSL mode (env: CLICKHOUSE_SSL, default: auto)",
    )
    parser.add_argument(
        "--async",
        action="store_true",
        dest="is_async",
        help="Use asynchronous backend",
    )
    parser.add_argument(
        "--named-connection",
        dest="named_connection",
        metavar="QUALIFIED_NAME",
        help="Named connection from Python module (e.g., myapp.connections.prod_db).",
    )
    parser.add_argument(
        "--conn-param",
        action="append",
        metavar="KEY=VALUE",
        default=[],
        dest="connection_params",
        help="Connection parameter override for named connection. Can be specified multiple times.",
    )


def add_version_arg(parser):
    """Add --version argument (used only by info subcommand)."""
    parser.add_argument(
        "--version",
        type=str,
        default=None,
        help='ClickHouse version to simulate (e.g., "26.7.1", "25.8"). Defaults to server-reported version.',
    )


def create_connection_parent_parser():
    """Create a parent parser with connection and output arguments.

    Used by shared CLI helpers (named-expression, named-procedure) that
    require a parent_parser containing connection parameters.
    """
    import argparse

    parent = argparse.ArgumentParser(add_help=False)
    add_connection_args(parent)
    # Output parameters
    parent.add_argument(
        "-o",
        "--output",
        choices=["table", "json", "csv", "tsv"],
        default="table",
        help='Output format. Defaults to "table" if rich is installed.',
    )
    parent.add_argument(
        "--rich-ascii",
        action="store_true",
        help="Use ASCII characters for rich table borders.",
    )
    return parent


def resolve_connection_config_from_args(args):
    """Resolve ClickHouse connection config from parsed args.

    Priority order:
        1. --named-connection + --conn-param
        2. Explicit connection parameters (--host, --port, etc.)
        3. Default values
    """
    from rhosocial.activerecord.backend.impl.clickhouse.config import ClickHouseConnectionConfig
    from rhosocial.activerecord.backend.named_connection.cli import parse_params
    from rhosocial.activerecord.backend.named_connection import NamedConnectionResolver

    named_conn = getattr(args, "named_connection", None)
    conn_params = getattr(args, "connection_params", [])

    if conn_params:
        conn_params = parse_params(conn_params)
    else:
        conn_params = {}

    if named_conn:
        resolver = NamedConnectionResolver(named_conn).load()
        if conn_params:
            return resolver.resolve(conn_params)
        return resolver.resolve({})

    # Fallback to explicit connection parameters.
    # ClickHouse HTTP is plain by default; SSL is enabled via --ssl with an
    # explicit mode (require / verify-ca / verify-full). The backend maps
    # ssl_mode + ssl_verify_cert onto clickhouse-connect's secure/verify.
    config_kwargs = {
        "host": args.host or "localhost",
        "port": args.port or 8123,
        "database": args.database,
        "username": args.user,
        "password": args.password,
    }
    ssl_mode = getattr(args, "ssl", None)
    if ssl_mode and ssl_mode not in ("disabled", "auto", None):
        config_kwargs["ssl_mode"] = ssl_mode
        # require  -> HTTPS, no cert validation
        # verify-ca -> HTTPS + validate server cert (clickhouse-connect also
        #              validates hostname; connect via the cert's hostname
        #              to avoid mismatch)
        # verify-full -> HTTPS + validate cert + hostname
        if ssl_mode in ("verify-ca", "verify-full"):
            config_kwargs["ssl_verify_cert"] = True
        if ssl_mode == "verify-full":
            config_kwargs["ssl_verify_identity"] = True

    return ClickHouseConnectionConfig(**config_kwargs)


def create_backend(args):
    """Create, connect, and introspect a ClickHouse backend from parsed args."""
    from rhosocial.activerecord.backend.impl.clickhouse import ClickHouseBackend

    config = resolve_connection_config_from_args(args)
    backend = ClickHouseBackend(connection_config=config)
    backend.connect()
    backend.introspect_and_adapt()
    return backend

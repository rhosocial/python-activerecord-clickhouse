# docs/examples/chapter_03_connection/connect.py
"""Chapter 3: connect to ClickHouse and run a first query.

This is the smallest complete program for this backend:

1. build a :class:`ClickHouseConnectionConfig` (the HTTP port is 8123),
2. pass it to :class:`ClickHouseBackend`,
3. connect, run two read-only statements with ``backend.execute``,
4. disconnect in a ``finally`` block.

Connection settings are read from the environment variables the test suite
uses, so the same command works locally and in CI. With no server reachable the
script prints how to start one and exits non-zero — it never invents a result.
"""

import os
import sys

from rhosocial.activerecord.backend.impl.clickhouse.backend import ClickHouseBackend
from rhosocial.activerecord.backend.impl.clickhouse.config import ClickHouseConnectionConfig


def build_config() -> ClickHouseConnectionConfig:
    """Build a connection config from the environment."""
    return ClickHouseConnectionConfig(
        host=os.getenv("CLICKHOUSE_HOST", "localhost"),
        port=int(os.getenv("CLICKHOUSE_PORT", "8123")),
        database=os.getenv("CLICKHOUSE_DATABASE", "test_db"),
        username=os.getenv("CLICKHOUSE_USER", "root"),
        password=os.getenv("CLICKHOUSE_PASSWORD", "password"),
    )


def connect(config: ClickHouseConnectionConfig) -> ClickHouseBackend:
    """Connect, or explain how to reach a server and exit non-zero."""
    backend = ClickHouseBackend(connection_config=config)
    try:
        backend.connect()
    except Exception as error:  # noqa: BLE001 - any connection failure is the same answer here
        print(f"Could not connect to ClickHouse at {config.host}:{config.port}: {error}", file=sys.stderr)
        print("", file=sys.stderr)
        print("Start a server and set the environment variables the tests use:", file=sys.stderr)
        print("  CLICKHOUSE_HOST=127.0.0.1", file=sys.stderr)
        print("  CLICKHOUSE_PORT=8123", file=sys.stderr)
        print("  CLICKHOUSE_DATABASE=test_db", file=sys.stderr)
        print("  CLICKHOUSE_USER=root", file=sys.stderr)
        print("  CLICKHOUSE_PASSWORD=password", file=sys.stderr)
        sys.exit(1)
    return backend


def main() -> None:
    config = build_config()
    backend = connect(config)
    try:
        print(f"Connected to {config.host}:{config.port}, database {config.database}")

        # The dialect negotiates the server version during connect().
        print("Server version:", backend.dialect.get_server_version())

        # A scalar read: result.data is a list of row mappings.
        version = backend.execute("SELECT version() AS version").data[0]
        print("SELECT version():", version["version"])

        # A small set of rows from a system table.
        rows = backend.execute("SELECT number FROM system.numbers LIMIT 5").data
        print("First five numbers:", [row["number"] for row in rows or []])
    finally:
        backend.disconnect()


if __name__ == "__main__":
    main()

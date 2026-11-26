# docs/examples/chapter_08_introspection/introspect.py
"""Chapter 8: introspect the connected ClickHouse server.

``backend.introspector`` answers questions from ``system.*`` catalogues. This
example walks the layers documented on the Introspection page:

1. capability probes on the dialect (what this server can answer),
2. the database row from ``system.databases``,
3. table and column listings from ``system.tables`` / ``system.columns``,
4. this backend's own partition and table-engine reads,
5. a server-wide catalogue read — the function list from ``system.functions``.

A small demo table is created so the table-scoped reads have something to find,
and dropped again in a ``finally`` block.
"""

import os
import sys

from rhosocial.activerecord.backend.impl.clickhouse.backend import ClickHouseBackend
from rhosocial.activerecord.backend.impl.clickhouse.config import ClickHouseConnectionConfig

DEMO_TABLE = "example_introspection_events"


def build_config() -> ClickHouseConnectionConfig:
    return ClickHouseConnectionConfig(
        host=os.getenv("CLICKHOUSE_HOST", "localhost"),
        port=int(os.getenv("CLICKHOUSE_PORT", "8123")),
        database=os.getenv("CLICKHOUSE_DATABASE", "test_db"),
        username=os.getenv("CLICKHOUSE_USER", "root"),
        password=os.getenv("CLICKHOUSE_PASSWORD", "password"),
    )


def connect(config: ClickHouseConnectionConfig) -> ClickHouseBackend:
    backend = ClickHouseBackend(connection_config=config)
    try:
        backend.connect()
    except Exception as error:  # noqa: BLE001 - any connection failure is the same answer here
        print(f"Could not connect to ClickHouse at {config.host}:{config.port}: {error}", file=sys.stderr)
        print("Set CLICKHOUSE_HOST / CLICKHOUSE_PORT / CLICKHOUSE_DATABASE /", file=sys.stderr)
        print("CLICKHOUSE_USER / CLICKHOUSE_PASSWORD to reach a running server.", file=sys.stderr)
        sys.exit(1)
    return backend


def ensure_demo_table(backend: ClickHouseBackend) -> None:
    """Create a monthly-partitioned demo table with rows in two partitions."""
    backend.execute(
        f"""
        CREATE TABLE IF NOT EXISTS {DEMO_TABLE} (
            id         Int64,
            event_date Date,
            status     LowCardinality(String)
        ) ENGINE = MergeTree
        PARTITION BY toYYYYMM(event_date)
        ORDER BY id
        """
    )
    count = backend.execute(f"SELECT count() AS n FROM {DEMO_TABLE}").data[0]["n"]
    if count:
        return
    backend.execute(
        f"""
        INSERT INTO {DEMO_TABLE} (id, event_date, status) VALUES
            (1, toDate('2026-01-05'), 'ok'),
            (2, toDate('2026-01-19'), 'error'),
            (3, toDate('2026-02-02'), 'ok')
        """
    )


def main() -> None:
    config = build_config()
    backend = connect(config)
    try:
        # Adapt the dialect to the connected server before asking the probes.
        backend.introspect_and_adapt()
        dialect = backend.dialect
        introspector = backend.introspector

        print("Capability probes (the gates the CLI reads):")
        for label, supported in (
            ("tables", dialect.supports_table_introspection()),
            ("columns", dialect.supports_column_introspection()),
            ("partitions", dialect.supports_partition_metadata_introspection()),
            ("table-engine", dialect.supports_table_engine_introspection()),
            ("functions", dialect.supports_function_introspection()),
            ("table-stats", dialect.supports_table_stats()),
        ):
            print(f"  {label:<14} {'yes' if supported else 'no'}")

        database = introspector.get_database_info()
        print("\nDatabase:", database.name)

        ensure_demo_table(backend)

        tables = introspector.list_tables()
        print("Tables in this database:", [table.name for table in tables])

        table_info = introspector.get_table_info(DEMO_TABLE)
        print("Columns of", DEMO_TABLE, ":", [column.name for column in table_info.columns])

        # Backend-specific families: ClickHouse calls the namespace a database,
        # so these reads take database= (not the core API's schema=).
        print("\nPartitions of", DEMO_TABLE, ":")
        state = introspector.get_partition_state(DEMO_TABLE, include_stats=True)
        print("  scheme        :", state.scheme)
        print("  key_expression:", state.key_expression)
        for bound in state.bounds:
            print(
                f"  {bound.name}: {bound.raw['active_part_count']} part(s), "
                f"{bound.row_count} row(s), {bound.size_bytes} bytes"
            )

        engine = introspector.get_table_engine(DEMO_TABLE)
        print("\nTable engine:")
        print("  engine        :", engine.engine)
        print("  sorting_key   :", engine.sorting_key)
        print("  partition_key :", engine.partition_key)
        print("  total_rows    :", engine.total_rows)
        print("  total_bytes   :", engine.total_bytes)

        # Server-wide catalogue: a name narrows the listing rather than
        # selecting a single row, since one name can also have alias rows.
        functions = introspector.list_functions("toYYYYMM")
        print("\nFunctions named toYYYYMM:", [function.name for function in functions])
    finally:
        backend.execute(f"DROP TABLE IF EXISTS {DEMO_TABLE}")
        backend.disconnect()


if __name__ == "__main__":
    main()

"""ClickHouse-specific introspection: partitions and table engine.

This example uses the two reads this backend adds to the standard introspection
API:

    backend.introspector.list_partitions(table, database=None)
    backend.introspector.get_table_engine(table, database=None)

``list_partitions`` aggregates the table's active parts from ``system.parts``
per ``partition_id``: rows, bytes on disk, part count, the modification-time
range and the engine. ``get_table_engine`` reads the storage definition from
``system.tables``: engine, ``ORDER BY`` / ``PRIMARY KEY`` / ``PARTITION BY`` /
``SAMPLE BY`` expressions, totals and comment.

Naming: ClickHouse's top-level namespace is a *database*, and it has no schema
layer. That is why both methods take ``database=`` rather than the core
introspection API's ``schema=``; the value is the same namespace either way, and
nothing is translated. Passing ``None`` uses the connected database.

The second half of the example counts the statements the introspector sends and
times both calls, cold (cache empty) and warm (cache filled), to show that the
cache actually removes the round trips rather than merely being present.

Run it with a ClickHouse server reachable through the same environment
variables the test suite uses:

    CLICKHOUSE_HOST=127.0.0.1 CLICKHOUSE_PORT=8123 CLICKHOUSE_DATABASE=test_db
    CLICKHOUSE_USER=root CLICKHOUSE_PASSWORD=password
    python introspection_partitions.py

With no server, the script prints these instructions and exits non-zero. It does
not invent partitions or an engine for a server it could not reach.
"""

import os
import sys
import time

from rhosocial.activerecord.backend.impl.clickhouse.backend import ClickHouseBackend
from rhosocial.activerecord.backend.impl.clickhouse.config import ClickHouseConnectionConfig

DEMO_TABLE = "introspection_partitions_demo"


def build_config() -> ClickHouseConnectionConfig:
    """Connection settings from the environment variables the tests use."""
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


def ensure_demo_table(backend: ClickHouseBackend) -> None:
    """Create the demo table if needed and give it two partitions' worth of rows.

    The rows are inserted only when the table is empty, so running the example
    twice does not keep growing it. Two different months are used because the
    table is partitioned by month: one partition per month makes the grouped
    read visible.
    """
    backend.execute(
        f"""
        CREATE TABLE IF NOT EXISTS {DEMO_TABLE} (
            id UInt32,
            event_date Date,
            label String
        ) ENGINE = MergeTree()
        PARTITION BY toYYYYMM(event_date)
        ORDER BY id
        """
    )
    row = backend.execute(f"SELECT count() AS row_count FROM {DEMO_TABLE}").data[0]
    if row["row_count"]:
        print(f"Table {DEMO_TABLE} already holds {row['row_count']} rows; leaving them as they are.")
        return
    backend.execute(
        f"""
        INSERT INTO {DEMO_TABLE} (id, event_date, label) VALUES
            (1, toDate('2026-01-05'), 'alpha'),
            (2, toDate('2026-01-19'), 'beta'),
            (3, toDate('2026-02-02'), 'gamma')
        """
    )
    print(f"Created {DEMO_TABLE} and inserted 3 rows across two monthly partitions.")


class QuestionCounter:
    """Executor stand-in that counts the statements it is asked to run.

    The introspector talks to the server through its executor, so counting here
    counts exactly the questions introspection sends -- no logging, no
    server-side metric that other queries could disturb.
    """

    def __init__(self, inner):
        self._inner = inner
        self.questions = 0

    def execute(self, sql, params=()):
        self.questions += 1
        return self._inner.execute(sql, params)


def timed(read):
    """Run *read* and return ``(value, seconds)``."""
    started = time.perf_counter()
    value = read()
    return value, time.perf_counter() - started


def print_partitions(partitions) -> None:
    print("")
    print(f"  {'partition_id':<14} {'partition':<12} {'parts':>6} {'rows':>6} {'bytes':>10}  engine")
    for item in partitions:
        print(
            f"  {item.partition_id:<14} {str(item.partition):<12} "
            f"{item.active_part_count:>6} {item.row_count:>6} {item.bytes_on_disk:>10}  {item.engine}"
        )
        print(
            f"  {'':<14} modified {item.min_modification_time} .. {item.max_modification_time}"
        )


def print_engine(info) -> None:
    print("")
    print(f"  engine        : {info.engine}")
    print(f"  sorting_key   : {info.sorting_key!r}")
    print(f"  primary_key   : {info.primary_key!r}")
    print(f"  partition_key : {info.partition_key!r}")
    print(f"  sampling_key  : {info.sampling_key!r}")
    print(f"  total_rows    : {info.total_rows}")
    print(f"  total_bytes   : {info.total_bytes}")
    print(f"  comment       : {info.comment!r}")


def main() -> None:
    config = build_config()
    backend = connect(config)
    try:
        print(f"Connected to {config.host}:{config.port}, database {config.database}")
        ensure_demo_table(backend)

        introspector = backend.introspector
        counter = QuestionCounter(introspector._executor)
        introspector._executor = counter

        # --- cold: the cache is empty, so both reads must ask the server ---
        introspector.clear_cache()
        cold_start = counter.questions
        partitions, partitions_cold_seconds = timed(lambda: introspector.list_partitions(DEMO_TABLE))
        engine, engine_cold_seconds = timed(lambda: introspector.get_table_engine(DEMO_TABLE))
        cold_questions = counter.questions - cold_start

        print("")
        print("Partitions (cold read):")
        print_partitions(partitions)
        print("")
        print("Table engine (cold read):")
        print_engine(engine)

        # --- warm: same two calls, answered from the cache ---
        warm_start = counter.questions
        warm_partitions, partitions_warm_seconds = timed(lambda: introspector.list_partitions(DEMO_TABLE))
        warm_engine, engine_warm_seconds = timed(lambda: introspector.get_table_engine(DEMO_TABLE))
        warm_questions = counter.questions - warm_start

        # The cached answers are the same objects, not re-parsed copies.
        assert warm_partitions is partitions
        assert warm_engine is engine

        print("")
        print("Cache:")
        print(
            f"  cold : {cold_questions} question(s) to the server, "
            f"{partitions_cold_seconds + engine_cold_seconds:.4f}s total"
        )
        print(f"         list_partitions {partitions_cold_seconds:.4f}s, "
              f"get_table_engine {engine_cold_seconds:.4f}s")
        print(
            f"  warm : {warm_questions} question(s) to the server, "
            f"{partitions_warm_seconds + engine_warm_seconds:.4f}s total"
        )
        print(f"         list_partitions {partitions_warm_seconds:.4f}s, "
              f"get_table_engine {engine_warm_seconds:.4f}s")
        print("")
        print("The warm reads send nothing because each answer was cached under")
        print("IntrospectionScope.TABLE with extra='partition' / extra='engine'.")
    finally:
        backend.execute(f"DROP TABLE IF EXISTS {DEMO_TABLE}")
        backend.disconnect()


if __name__ == "__main__":
    main()

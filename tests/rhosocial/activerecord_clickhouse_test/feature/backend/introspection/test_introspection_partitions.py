# tests/rhosocial/activerecord_clickhouse_test/feature/backend/introspection/test_introspection_partitions.py
"""Partitions and table-engine introspection, against a live ClickHouse server.

What is pinned here:

* ``list_partitions`` really groups ``system.parts`` by ``partition_id`` and the
  aggregate means what it says -- row counts add up across the parts of a
  partition, and only active parts are read;
* ``get_table_engine`` reports the definition the table was created with;
* both reads are cached under the table scope with an ``extra`` namespace, so a
  warm call sends **no** statement to the server;
* the CLI reaches the same methods through ``introspect partitions`` /
  ``introspect table-engine`` and renders them through the output provider;
* the result types are frozen, so a cached answer cannot be mutated by one
  caller and handed to the next.

The live tests skip themselves when no server is reachable. The scenario is the
one the rest of the backend tests use (``tests/config/clickhouse_scenarios.yaml``
or ``CLICKHOUSE_SCENARIOS_CONFIG_PATH``), read through ``providers.scenarios`` so
this file cannot drift to its own connection settings.
"""

import io
import json
import socket
from contextlib import redirect_stderr, redirect_stdout
from dataclasses import FrozenInstanceError

import pytest

from rhosocial.activerecord.backend.impl.clickhouse.__main__ import main
from rhosocial.activerecord.backend.impl.clickhouse.cli.introspect import (
    INTROSPECT_TYPES,
)
from rhosocial.activerecord.backend.impl.clickhouse.dialect import ClickHouseDialect
from rhosocial.activerecord.backend.impl.clickhouse.expression.introspection import (
    ClickHouseTableEngineQuery,
    ClickHouseTablePartitionsQuery,
)
from rhosocial.activerecord.backend.impl.clickhouse.introspection.types import (
    ClickHousePartitionInfo,
    ClickHouseTableEngineInfo,
)

TABLE = "test_intro_partitions_ch"


# --------------------------------------------------------------------------- #
# Skip mechanism: a live scenario is required, and its absence is a skip
# --------------------------------------------------------------------------- #


@pytest.fixture(scope="module")
def live_server():
    """Skip the whole live group when the configured server is not there."""
    from providers.scenarios import get_enabled_scenarios

    scenarios = get_enabled_scenarios()
    if not scenarios:
        pytest.skip("No ClickHouse scenarios configured")
    config = next(iter(scenarios.values()))
    try:
        with socket.create_connection((config["host"], int(config["port"])), timeout=2):
            pass
    except OSError as error:
        pytest.skip(f"ClickHouse unreachable at {config['host']}:{config['port']}: {error}")
    return config


@pytest.fixture
def partitioned_table(live_server, clickhouse_backend):
    """A MergeTree table with two monthly partitions and three rows."""
    backend = clickhouse_backend
    backend.execute(f"DROP TABLE IF EXISTS {TABLE}")
    backend.execute(
        f"""
        CREATE TABLE {TABLE} (
            id UInt32,
            event_date Date,
            label String
        ) ENGINE = MergeTree()
        PARTITION BY toYYYYMM(event_date)
        ORDER BY id
        """
    )
    backend.execute(
        f"""
        INSERT INTO {TABLE} (id, event_date, label) VALUES
            (1, toDate('2026-01-05'), 'alpha'),
            (2, toDate('2026-01-19'), 'beta'),
            (3, toDate('2026-02-02'), 'gamma')
        """
    )
    backend.introspector.clear_cache()
    yield backend
    backend.execute(f"DROP TABLE IF EXISTS {TABLE}")


class QuestionCounter:
    """Delegating executor that counts the statements introspection sends."""

    def __init__(self, inner):
        self._inner = inner
        self.questions = 0

    def execute(self, sql, params=()):
        self.questions += 1
        return self._inner.execute(sql, params)


# --------------------------------------------------------------------------- #
# SQL nodes (no server needed)
# --------------------------------------------------------------------------- #


@pytest.fixture(scope="module")
def dialect():
    return ClickHouseDialect(version=(26, 7, 3))


class TestQueryNodes:
    def test_partitions_query_groups_active_parts(self, dialect):
        sql, params = ClickHouseTablePartitionsQuery(dialect, "test_db", "events").to_sql()
        assert "FROM `system`.`parts`" in sql
        assert "COUNT(*) AS `active_part_count`" in sql
        assert "SUM(`rows`) AS `row_count`" in sql
        assert "SUM(`bytes_on_disk`) AS `bytes_on_disk`" in sql
        assert "MIN(`modification_time`) AS `min_modification_time`" in sql
        assert "MAX(`modification_time`) AS `max_modification_time`" in sql
        assert "GROUP BY `partition_id`" in sql
        assert "ORDER BY `partition_id`" in sql
        # Only active parts are aggregated: inactive parts are replaced data.
        assert "`active` = %s" in sql
        assert params == ("test_db", "events", 1)

    def test_engine_query_projects_the_definition(self, dialect):
        sql, params = ClickHouseTableEngineQuery(dialect, "test_db", "events").to_sql()
        assert "FROM `system`.`tables`" in sql
        for column in (
            "`engine`",
            "`sorting_key`",
            "`primary_key`",
            "`partition_key`",
            "`sampling_key`",
            "`total_rows`",
            "`total_bytes`",
            "`comment`",
        ):
            assert column in sql
        assert "`database` = %s AND `name` = %s" in sql
        assert params == ("test_db", "events")


# --------------------------------------------------------------------------- #
# Result types (no server needed)
# --------------------------------------------------------------------------- #


class TestResultTypes:
    def test_partition_info_is_frozen(self):
        item = ClickHousePartitionInfo(
            partition_id="202601",
            table_name="events",
            database="test_db",
            engine="MergeTree",
        )
        with pytest.raises(FrozenInstanceError):
            item.row_count = 1

    def test_table_engine_info_is_frozen(self):
        item = ClickHouseTableEngineInfo(
            table_name="events",
            database="test_db",
            engine="MergeTree",
        )
        with pytest.raises(FrozenInstanceError):
            item.engine = "Log"

    def test_cli_declares_the_new_introspection_types(self):
        assert "partitions" in INTROSPECT_TYPES
        assert "table-engine" in INTROSPECT_TYPES


# --------------------------------------------------------------------------- #
# Live results
# --------------------------------------------------------------------------- #


class TestPartitions:
    def test_partitions_are_grouped_by_partition_id(self, partitioned_table):
        partitions = partitioned_table.introspector.list_partitions(TABLE)

        assert [p.partition_id for p in partitions] == ["202601", "202602"]
        assert [p.partition for p in partitions] == ["202601", "202602"]
        assert {p.partition_id: p.row_count for p in partitions} == {
            "202601": 2,
            "202602": 1,
        }
        for item in partitions:
            assert item.table_name == TABLE
            assert item.database == partitioned_table.config.database
            assert item.engine == "MergeTree"
            assert item.bytes_on_disk > 0
            assert item.active_part_count >= 1
            assert item.min_modification_time is not None
            assert item.max_modification_time >= item.min_modification_time

    def test_rows_add_up_to_the_table_total(self, partitioned_table):
        partitions = partitioned_table.introspector.list_partitions(TABLE)
        assert sum(p.row_count for p in partitions) == 3
        assert sum(p.bytes_on_disk for p in partitions) > 0

    def test_table_without_parts_returns_an_empty_list(self, partitioned_table):
        empty_table = f"{TABLE}_empty"
        partitioned_table.execute(f"DROP TABLE IF EXISTS {empty_table}")
        partitioned_table.execute(
            f"CREATE TABLE {empty_table} (id UInt32) ENGINE = MergeTree() ORDER BY id"
        )
        try:
            assert partitioned_table.introspector.list_partitions(empty_table) == []
        finally:
            partitioned_table.execute(f"DROP TABLE IF EXISTS {empty_table}")

    def test_missing_table_returns_an_empty_list(self, partitioned_table):
        assert partitioned_table.introspector.list_partitions("no_such_table_xyz") == []


class TestTableEngine:
    def test_engine_and_key_expressions(self, partitioned_table):
        info = partitioned_table.introspector.get_table_engine(TABLE)

        assert info is not None
        assert info.table_name == TABLE
        assert info.database == partitioned_table.config.database
        assert info.engine == "MergeTree"
        assert info.sorting_key == "id"
        assert info.primary_key == "id"
        assert info.partition_key == "toYYYYMM(event_date)"
        assert info.sampling_key == ""
        assert info.total_rows == 3
        assert info.total_bytes > 0
        assert info.comment == ""

    def test_missing_table_returns_none(self, partitioned_table):
        assert partitioned_table.introspector.get_table_engine("no_such_table_xyz") is None

    def test_database_argument_names_the_clickhouse_database(self, partitioned_table):
        database = partitioned_table.config.database
        info = partitioned_table.introspector.get_table_engine(TABLE, database=database)
        assert info is not None
        assert info.database == database
        # Same answer whether the database is implicit or named.
        assert info == partitioned_table.introspector.get_table_engine(TABLE)


class TestCache:
    def test_warm_reads_send_no_questions(self, partitioned_table):
        introspector = partitioned_table.introspector
        counter = QuestionCounter(introspector._executor)
        introspector._executor = counter
        try:
            introspector.clear_cache()

            cold_start = counter.questions
            partitions = introspector.list_partitions(TABLE)
            engine = introspector.get_table_engine(TABLE)
            cold_questions = counter.questions - cold_start

            warm_start = counter.questions
            warm_partitions = introspector.list_partitions(TABLE)
            warm_engine = introspector.get_table_engine(TABLE)
            warm_questions = counter.questions - warm_start

            assert cold_questions == 2
            assert warm_questions == 0
            assert warm_partitions is partitions
            assert warm_engine is engine
        finally:
            introspector._executor = counter._inner

    def test_table_scope_invalidation_drops_both_families(self, partitioned_table):
        introspector = partitioned_table.introspector
        introspector.clear_cache()
        introspector.list_partitions(TABLE)
        introspector.get_table_engine(TABLE)
        before = len(introspector.cache)

        introspector.invalidate_cache(scope=None, name=TABLE)

        assert len(introspector.cache) < before


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #


def run_cli(argv):
    out, err = io.StringIO(), io.StringIO()
    exit_code = None
    with redirect_stdout(out), redirect_stderr(err):
        try:
            main(argv)
        except SystemExit as exc:
            exit_code = exc.code
    return out.getvalue(), err.getvalue(), exit_code


@pytest.fixture
def cli_env(live_server):
    """A backend and CLI args on the scenario's own connection settings.

    The table is created through the same connection the CLI will use, so the
    CLI cannot be pointed at a different database than the fixture populated.
    """
    from providers.scenarios import get_scenario_raw

    backend_class, config = get_scenario_raw("clickhouse_http")
    backend = backend_class(connection_config=config)
    backend.connect()
    backend.execute(f"DROP TABLE IF EXISTS {TABLE}")
    backend.execute(
        f"""
        CREATE TABLE {TABLE} (
            id UInt32,
            event_date Date,
            label String
        ) ENGINE = MergeTree()
        PARTITION BY toYYYYMM(event_date)
        ORDER BY id
        """
    )
    backend.execute(
        f"""
        INSERT INTO {TABLE} (id, event_date, label) VALUES
            (1, toDate('2026-01-05'), 'alpha'),
            (2, toDate('2026-01-19'), 'beta'),
            (3, toDate('2026-02-02'), 'gamma')
        """
    )
    conn_args = [
        "--host", config.host,
        "--port", str(config.port),
        "--database", config.database,
        "--user", config.username,
        "--password", config.password,
    ]
    try:
        yield conn_args
    finally:
        backend.execute(f"DROP TABLE IF EXISTS {TABLE}")
        backend.disconnect()


class TestCli:
    def test_partitions_json(self, cli_env):
        out, err, exit_code = run_cli(
            ["introspect", "partitions", TABLE] + cli_env + ["-o", "json"]
        )

        assert exit_code is None, f"stderr: {err}\nstdout: {out}"
        data = json.loads(out)
        assert [row["partition_id"] for row in data] == ["202601", "202602"]
        assert {row["partition_id"]: row["row_count"] for row in data} == {
            "202601": 2,
            "202602": 1,
        }
        assert all(row["engine"] == "MergeTree" for row in data)

    def test_table_engine_json(self, cli_env):
        out, err, exit_code = run_cli(
            ["introspect", "table-engine", TABLE] + cli_env + ["-o", "json"]
        )

        assert exit_code is None, f"stderr: {err}\nstdout: {out}"
        data = json.loads(out)
        assert len(data) == 1
        assert data[0]["engine"] == "MergeTree"
        assert data[0]["partition_key"] == "toYYYYMM(event_date)"
        assert data[0]["sorting_key"] == "id"
        assert data[0]["total_rows"] == 3

    def test_partitions_require_a_table_name(self, cli_env):
        out, err, exit_code = run_cli(["introspect", "partitions"] + cli_env)

        assert exit_code == 1
        assert "Table name is required" in err

    def test_table_engine_requires_the_table_to_exist(self, cli_env):
        out, err, exit_code = run_cli(
            ["introspect", "table-engine", "no_such_table_xyz"] + cli_env
        )

        assert exit_code == 1
        assert "not found" in err

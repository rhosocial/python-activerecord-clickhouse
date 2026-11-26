# tests/rhosocial/activerecord_clickhouse_test/feature/backend/execute/introspection/test_introspection_partitions.py
"""Partition state and table-engine introspection, against a live ClickHouse server.

What is pinned here:

* ``get_partition_state`` reads the scheme from the table engine's
  ``partition_key`` and the bounds from ``system.parts`` grouped by
  ``partition_id``; the aggregate means what it says (row counts add up across
  the parts of a partition, and only active parts are read);
* an **unpartitioned** table whose parts list is not empty still answers
  ``scheme is None``: ``system.parts`` reports a single ``'all'`` partition for
  a written MergeTree table, so a non-empty parts list is not evidence of
  partitioning;
* ``include_stats=False`` carries no per-partition row count or byte size;
* ``list_partitions`` is gone, with no compatibility alias;
* ``get_table_engine`` reports the definition the table was created with, and
  the neutral table state carries the engine, keys and TTL;
* the reads are cached under the table scope with an ``extra`` namespace, so a
  warm call sends **no** statement to the server;
* the CLI reaches the neutral method through ``introspect partitions`` and
  renders the neutral shape;
* the result types are frozen, so a cached answer cannot be mutated by one
  caller and handed to the next.

The live tests skip themselves when no server is reachable. The scenario is the
one the rest of the backend tests use (``tests/config/clickhouse_scenarios.yaml``
or ``CLICKHOUSE_SCENARIOS_CONFIG_PATH``), read through ``support.clickhouse`` so
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
from rhosocial.activerecord.backend.introspection.types import PartitionScheme

TABLE = "test_intro_partitions_ch"


# --------------------------------------------------------------------------- #
# Skip mechanism: a live scenario is required, and its absence is a skip
# --------------------------------------------------------------------------- #


@pytest.fixture(scope="module")
def live_server():
    """Skip the whole live group when the configured server is not there."""
    from support.clickhouse import get_enabled_scenarios

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

    def test_partitions_query_without_stats_skips_the_aggregate(self, dialect):
        sql, params = ClickHouseTablePartitionsQuery(
            dialect, "test_db", "events", include_stats=False
        ).to_sql()
        assert "FROM `system`.`parts`" in sql
        assert "GROUP BY `partition_id`" in sql
        assert "COUNT(*) AS `active_part_count`" not in sql
        assert "SUM(`rows`)" not in sql
        assert "SUM(`bytes_on_disk`)" not in sql
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
            "`engine_full`",
            "`is_temporary`",
            "`storage_policy`",
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

    def test_cli_declares_the_introspection_types(self):
        assert "partitions" in INTROSPECT_TYPES
        assert "table-engine" in INTROSPECT_TYPES


# --------------------------------------------------------------------------- #
# Live results
# --------------------------------------------------------------------------- #


class TestPartitionState:
    def test_scheme_comes_from_the_partition_key(self, partitioned_table):
        state = partitioned_table.introspector.get_partition_state(
            TABLE, include_stats=True
        )

        assert state is not None
        assert state.scheme is PartitionScheme.EXPRESSION
        assert state.key_expression == "toYYYYMM(event_date)"
        assert state.key_columns == ()
        assert [bound.name for bound in state.bounds] == ["202601", "202602"]
        assert [bound.upper for bound in state.bounds] == ["202601", "202602"]
        assert {bound.name: bound.row_count for bound in state.bounds} == {
            "202601": 2,
            "202602": 1,
        }
        assert all(bound.size_bytes > 0 for bound in state.bounds)
        assert state.raw["engine"] == "MergeTree"
        for bound in state.bounds:
            assert bound.is_default is False
            assert bound.is_maxvalue is False
            assert bound.subpartition_count == 0

    def test_bounds_add_up_to_the_table_total(self, partitioned_table):
        state = partitioned_table.introspector.get_partition_state(
            TABLE, include_stats=True
        )
        assert state is not None
        assert sum(bound.row_count for bound in state.bounds) == 3
        assert sum(bound.size_bytes for bound in state.bounds) > 0

    def test_without_stats_no_measurement_is_carried(self, partitioned_table):
        state = partitioned_table.introspector.get_partition_state(TABLE)
        assert state is not None
        assert [bound.name for bound in state.bounds] == ["202601", "202602"]
        assert all(bound.row_count is None for bound in state.bounds)
        assert all(bound.size_bytes is None for bound in state.bounds)

    def test_unpartitioned_table_has_no_scheme_despite_non_empty_parts(
        self, partitioned_table
    ):
        """``system.parts`` always has a row once an unpartitioned table is written."""
        unpartitioned = f"{TABLE}_unpartitioned"
        partitioned_table.execute(f"DROP TABLE IF EXISTS {unpartitioned}")
        partitioned_table.execute(
            f"CREATE TABLE {unpartitioned} (id UInt32) ENGINE = MergeTree() ORDER BY id"
        )
        partitioned_table.execute(f"INSERT INTO {unpartitioned} (id) VALUES (1), (2)")
        try:
            parts = partitioned_table.fetch_all(
                f"SELECT partition_id FROM system.parts "
                f"WHERE table = '{unpartitioned}' AND active"
            )
            # The trap this test exists for: the parts view is non-empty even
            # though the table declares no partition key.
            assert [row["partition_id"] for row in parts] == ["all"]

            partitioned_table.introspector.clear_cache()
            state = partitioned_table.introspector.get_partition_state(unpartitioned)

            assert state is not None
            assert state.scheme is None
            assert state.key_expression == ""
            assert state.bounds == ()
        finally:
            partitioned_table.execute(f"DROP TABLE IF EXISTS {unpartitioned}")

    def test_partitioned_but_empty_table_has_a_scheme_and_no_bounds(
        self, partitioned_table
    ):
        empty = f"{TABLE}_empty_partitioned"
        partitioned_table.execute(f"DROP TABLE IF EXISTS {empty}")
        partitioned_table.execute(
            f"CREATE TABLE {empty} (id UInt32, event_date Date) "
            "ENGINE = MergeTree() PARTITION BY toYYYYMM(event_date) ORDER BY id"
        )
        try:
            partitioned_table.introspector.clear_cache()
            state = partitioned_table.introspector.get_partition_state(empty)
            assert state is not None
            assert state.scheme is PartitionScheme.EXPRESSION
            assert state.key_expression == "toYYYYMM(event_date)"
            assert state.bounds == ()
        finally:
            partitioned_table.execute(f"DROP TABLE IF EXISTS {empty}")

    def test_missing_table_returns_none(self, partitioned_table):
        assert partitioned_table.introspector.get_partition_state("no_such_table_xyz") is None

    def test_list_partitions_is_gone(self, partitioned_table):
        """The old family was folded into ``get_partition_state``, with no alias."""
        assert not hasattr(partitioned_table.introspector, "list_partitions")

    def test_include_stats_changes_the_cache_key(self, partitioned_table):
        introspector = partitioned_table.introspector
        with_stats = introspector.get_partition_state(TABLE, include_stats=True)
        without_stats = introspector.get_partition_state(TABLE, include_stats=False)
        assert with_stats is not without_stats
        assert with_stats.bounds[0].row_count == 2
        assert without_stats.bounds[0].row_count is None


class TestTableState:
    def test_kind_storage_and_partitioning(self, partitioned_table):
        state = partitioned_table.introspector.get_table_state(TABLE)

        assert state.name == TABLE
        assert state.schema == partitioned_table.config.database
        assert state.kind == "regular"
        assert state.storage.engine == "MergeTree"
        assert state.storage.raw["sorting_key"] == "id"
        assert state.storage.raw["partition_key"] == "toYYYYMM(event_date)"
        assert state.raw["partition_key"] == "toYYYYMM(event_date)"
        assert state.raw["total_rows"] == 3
        assert state.partitioning is not None
        assert state.partitioning.scheme is PartitionScheme.EXPRESSION

    def test_ttl_is_read_from_the_engine_clause(self, partitioned_table):
        ttl_table = f"{TABLE}_ttl"
        partitioned_table.execute(f"DROP TABLE IF EXISTS {ttl_table}")
        partitioned_table.execute(
            f"CREATE TABLE {ttl_table} (id UInt32, d Date) "
            "ENGINE = MergeTree() ORDER BY id TTL d + INTERVAL 1 YEAR"
        )
        try:
            info = partitioned_table.introspector.get_table_engine(ttl_table)
            assert info is not None
            assert info.engine_full is not None
            assert "TTL" in info.engine_full
            assert info.ttl == "d + toIntervalYear(1)"

            state = partitioned_table.introspector.get_table_state(ttl_table)
            assert state.raw["ttl"] == "d + toIntervalYear(1)"
            assert state.storage.raw["ttl"] == "d + toIntervalYear(1)"
        finally:
            partitioned_table.execute(f"DROP TABLE IF EXISTS {ttl_table}")

    def test_missing_table_raises(self, partitioned_table):
        with pytest.raises(LookupError):
            partitioned_table.introspector.get_table_state("no_such_table_xyz")


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
        assert info.engine_full is not None
        assert info.is_temporary is False

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
            state = introspector.get_partition_state(TABLE, include_stats=True)
            engine = introspector.get_table_engine(TABLE)
            cold_questions = counter.questions - cold_start

            warm_start = counter.questions
            warm_state = introspector.get_partition_state(TABLE, include_stats=True)
            warm_engine = introspector.get_table_engine(TABLE)
            warm_questions = counter.questions - warm_start

            # The engine read and the parts read; the named engine read is a
            # cache hit after ``get_partition_state``.
            assert cold_questions == 2
            assert warm_questions == 0
            assert warm_state is state
            assert warm_engine is engine
        finally:
            introspector._executor = counter._inner

    def test_table_scope_invalidation_drops_both_families(self, partitioned_table):
        introspector = partitioned_table.introspector
        introspector.clear_cache()
        introspector.get_partition_state(TABLE, include_stats=True)
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
    from support.clickhouse import get_scenario_raw

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
    def test_partitions_json_renders_the_neutral_state(self, cli_env):
        out, err, exit_code = run_cli(
            ["introspect", "partitions", TABLE] + cli_env + ["-o", "json"]
        )

        assert exit_code is None, f"stderr: {err}\nstdout: {out}"
        data = json.loads(out)
        assert len(data) == 1
        state = data[0]
        assert state["scheme"] == "expression"
        assert state["key_expression"] == "toYYYYMM(event_date)"
        assert [bound["name"] for bound in state["bounds"]] == ["202601", "202602"]
        assert [bound["upper"] for bound in state["bounds"]] == ["202601", "202602"]
        assert {bound["name"]: bound["row_count"] for bound in state["bounds"]} == {
            "202601": 2,
            "202602": 1,
        }

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

    def test_partitions_of_a_missing_table_exit_1(self, cli_env):
        out, err, exit_code = run_cli(
            ["introspect", "partitions", "no_such_table_xyz"] + cli_env
        )

        assert exit_code == 1
        assert "not found" in err

    def test_table_engine_requires_the_table_to_exist(self, cli_env):
        out, err, exit_code = run_cli(
            ["introspect", "table-engine", "no_such_table_xyz"] + cli_env
        )

        assert exit_code == 1
        assert "not found" in err

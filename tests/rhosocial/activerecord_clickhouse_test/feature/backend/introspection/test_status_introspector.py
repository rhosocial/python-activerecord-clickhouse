# tests/rhosocial/activerecord_clickhouse_test/feature/backend/introspection/test_status_introspector.py
"""
The status inventories report the server, they do not recite a list.

Before this file the two inventories were MySQL's: of 45 ``CLICKHOUSE_CONFIG_
VARIABLES`` exactly one (``connect_timeout``) was a ``system.settings`` row, and
of 31 ``CLICKHOUSE_STATUS_VARIABLES`` none was a ``system.metrics`` row. The
consequence was not an exception — it was ``list_performance_metrics()``
returning ``[]`` on every call, forever.

So the live half of this file is the point. It checks the inventories against
the table each name is supposed to come from, in **both** directions:

* nothing is returned that the server does not have — the failure mode that
  made the MySQL inventories return nothing and, once they had been padded
  with placeholder rows, would have made them return fiction;
* nothing the server *does* have is dropped, so the inventories are not quietly
  emptying themselves.

The two directions are separate because neither implies the other, and an
assertion of the form "every shipped name exists" cannot be satisfied at all:
the five tables differ between ClickHouse versions, and ``system.events``
additionally grows only as events fire. Measured on 25.8.33.6, 26.3.28.5 and
26.7.3.19, and on a freshly started 26.7.21.2 — a server that has run nothing —
the shipped/missing split is 59/2 settings, 9/4 server settings, 56/6 gauges,
33/16 events and 32/5 async metrics. A pristine 26.7 is *worse* off than the
used 26.7.3.19 it was measured on. That is the whole reason the inventories are
requests rather than claims; see the module docstring of ``status_introspector``.

Four claims are pinned specifically because they were false before:

* ``max_connections`` is **not** a ``system.settings`` row (0 rows on
  26.7.3.19). It is a ``config.xml`` value, so it is read from
  ``system.server_settings`` where the server reports it as 4096.
* there is no ``clickhouse.user`` database (26.7.3.19 answers
  ``UNKNOWN_DATABASE``), so ``list_users()`` used to return ``[]`` always. It
  reads ``system.users`` now and finds the server's own account.
* ``system.processes`` spells the current database ``current_database``;
  ``currentDatabase`` is MySQL's name and is not a column here.
* ``system.settings`` carries the description, default, unit and read-only flag
  for each row, so none of those are hand-written in the inventory any more.
"""
import inspect
import re

import pytest

from rhosocial.activerecord.backend.errors import DatabaseError
from rhosocial.activerecord.backend.impl.clickhouse.introspection.status_introspector import (
    ClickHouseStatusIntrospectorMixin,
    SyncClickHouseStatusIntrospector,
    AsyncClickHouseStatusIntrospector,
    CLICKHOUSE_CONFIG_SETTINGS,
    CLICKHOUSE_SERVER_SETTINGS,
    CLICKHOUSE_GAUGE_METRICS,
    CLICKHOUSE_COUNTER_EVENTS,
    CLICKHOUSE_ASYNC_METRICS,
    OPEN_CONNECTION_METRICS,
)
from rhosocial.activerecord.backend.introspection.status import StatusCategory

# (constant, system table, name column)
INVENTORIES = [
    (CLICKHOUSE_CONFIG_SETTINGS, "system.settings", "name"),
    (CLICKHOUSE_SERVER_SETTINGS, "system.server_settings", "name"),
    (CLICKHOUSE_GAUGE_METRICS, "system.metrics", "metric"),
    (CLICKHOUSE_COUNTER_EVENTS, "system.events", "event"),
    (CLICKHOUSE_ASYNC_METRICS, "system.asynchronous_metrics", "metric"),
]

# Names that used to be declared and never returned.
MYSQL_NAMES = [
    "innodb_buffer_pool_size",
    "innodb_log_file_size",
    "key_buffer_size",
    "query_cache_size",
    "query_cache_type",
    "sql_mode",
    "secure_file_priv",
    "log_bin",
    "binlog_format",
    "gtid_mode",
    "super_read_only",
    "version_comment",
    "basedir",
    "tmpdir",
    "character_set_server",
    "collation_server",
    "skip_networking",
    "skip_name_resolve",
    "Threads_connected",
    "Threads_running",
    "Qcache_hits",
    "Qcache_inserts",
    "Qcache_lowmem_prunes",
    "Com_select",
    "Com_insert",
    "Com_update",
    "Com_delete",
    "Com_replace",
    "Com_load",
    "Bytes_received",
    "Bytes_sent",
    "Max_used_connections",
    "Innodb_buffer_pool_read_requests",
    "Innodb_buffer_pool_reads",
    "Innodb_buffer_pool_wait_free",
    "Innodb_data_reads",
    "Innodb_data_writes",
    "Innodb_data_read",
    "Innodb_data_written",
    "Innodb_row_lock_waits",
    "Innodb_row_lock_time",
    "Innodb_rows_read",
    "Innodb_rows_inserted",
    "Innodb_rows_updated",
    "Innodb_rows_deleted",
]


@pytest.fixture
def status(clickhouse_backend_single):
    return clickhouse_backend_single.introspector.status


def _names_inventory(server_rows, column):
    return {row.get(column) for row in server_rows}


class TestNothingIsReportedThatTheServerLacks:
    """The half that cannot be fudged: no reported name may be fictional.

    This is the direction that matters. A name the server does not publish can
    only reach a caller if the module made it up or if the row was fabricated,
    and either would be a claim about the server that the server never made.
    """

    @pytest.mark.parametrize(
        "table,column,method",
        [
            ("system.settings", "name", "list_configuration"),
            ("system.server_settings", "name", "list_configuration"),
            ("system.metrics", "metric", "list_performance_metrics"),
            ("system.events", "event", "list_performance_metrics"),
            ("system.asynchronous_metrics", "metric", "list_performance_metrics"),
        ],
    )
    def test_every_reported_name_is_a_row_of_the_table_it_names(
        self, status, clickhouse_backend_single, table, column, method
    ):
        have = _names_inventory(
            clickhouse_backend_single.execute(f"SELECT {column} FROM {table}").data, column
        )
        reported = {i.name for i in getattr(status, method)() if i.extra["source"] == table}
        fabricated = sorted(reported - have)
        assert not fabricated, (
            f"{table} does not have these rows, but they were reported anyway: {fabricated}"
        )

    def test_reported_names_come_from_the_shipped_inventories_not_a_wider_sweep(self, status):
        """The inventories must stay the *whole* of what is reported.

        Both accessors build their list by walking the inventory and looking
        each name up in the rows, so the shortlist is enforced in Python and
        not by the ``WHERE name IN (...)`` clause. Replacing that clause with
        an unfiltered read was measured and changes nothing — which is why this
        test does not police the SQL and instead pins the outcome: nothing is
        reported that the inventories did not ask for. That is the difference
        between "this backend's shortlist" and "whatever the table holds", and
        it is what keeps ``StatusCategory`` meaningful.
        """
        shipped = {n for inventory, _, _ in INVENTORIES for n, _ in inventory}
        shipped.update(OPEN_CONNECTION_METRICS)
        reported = {i.name for i in status.list_configuration()}
        reported.update(i.name for i in status.list_performance_metrics())
        assert reported <= shipped, sorted(reported - shipped)

    def test_every_category_stays_reachable_on_this_server(self, status):
        """Category filtering must not collapse to empty on any version.

        The inventories are hand-categorised, so a name that vanishes on an
        older release could in principle empty a whole category. Measured on
        25.8.33.6, 26.3.28.5, 26.7.3.19 and a pristine 26.7.21.2: all six
        categories keep at least one item, so the filter stays usable.
        """
        reported = list(status.list_configuration()) + list(status.list_performance_metrics())
        used = {item.category for item in reported}
        assert used == set(StatusCategory), sorted(
            c.value for c in set(StatusCategory) - used
        )


class TestNothingTheServerHasIsDropped:
    """The other direction: an inventory must not empty itself silently.

    Sourcing every value from the row (the module's stated design) is only
    useful if the row is actually used. An entry that asks for a name the
    server has and then fails to report it is a bug in the assembly, not a fact
    about the server — and this is the check that catches it, because the
    other direction cannot see it.
    """

    @pytest.mark.parametrize(
        "constant,table,column,method",
        [
            (CLICKHOUSE_CONFIG_SETTINGS, "system.settings", "name", "list_configuration"),
            (CLICKHOUSE_SERVER_SETTINGS, "system.server_settings", "name", "list_configuration"),
            (CLICKHOUSE_GAUGE_METRICS, "system.metrics", "metric", "list_performance_metrics"),
            (CLICKHOUSE_COUNTER_EVENTS, "system.events", "event", "list_performance_metrics"),
            (CLICKHOUSE_ASYNC_METRICS, "system.asynchronous_metrics", "metric", "list_performance_metrics"),
        ],
    )
    def test_every_shipped_name_the_server_has_is_reported(
        self, status, clickhouse_backend_single, constant, table, column, method
    ):
        have = _names_inventory(
            clickhouse_backend_single.execute(f"SELECT {column} FROM {table}").data, column
        )
        expected = {n for n, _ in constant if n in have}
        assert expected, (
            f"this server shares no name at all with the {table} inventory; "
            "the shortlist has drifted away from ClickHouse entirely"
        )
        reported = {i.name for i in getattr(status, method)() if i.extra["source"] == table}
        dropped = sorted(expected - reported)
        assert not dropped, (
            f"{table} has these rows and the inventory asks for them, but they "
            f"were not reported: {dropped}"
        )

    def test_no_inventory_repeats_a_name(self):
        for inventory, table, _ in INVENTORIES:
            names = [n for n, _ in inventory]
            assert len(names) == len(set(names)), f"{table} inventory has duplicates"

    def test_open_connection_gauges_are_all_published(self, clickhouse_backend_single):
        """These five are summed into ``active_count``, so all five are needed.

        Unlike the curated inventories this set is not a shortlist — dropping a
        name would silently under-count — so it is held to the stronger rule
        that all of them exist. Measured present on 25.8.33.6, 26.3.28.5 and
        26.7.3.19.
        """
        rows = clickhouse_backend_single.execute(
            "SELECT metric FROM system.metrics WHERE metric IN (%s)"
            % ", ".join(["%s"] * len(OPEN_CONNECTION_METRICS)),
            OPEN_CONNECTION_METRICS,
        ).data
        have = _names_inventory(rows, "metric")
        missing = [n for n in OPEN_CONNECTION_METRICS if n not in have]
        assert not missing, f"not in system.metrics: {missing}"

    def test_async_inventory_has_no_device_suffixed_names(self):
        """Per-CPU / per-disk / per-interface names are generated per host."""
        generated = ("_nbd", "_ram", "_sda", "_sr", "_eth", "_CPU", "_loopback", "_docker", "_veth")
        for name, _ in CLICKHOUSE_ASYNC_METRICS:
            assert not any(name.endswith(suffix) for suffix in generated), (
                f"{name} carries a per-host device/CPU suffix"
            )


class TestNoMysqlNamesAreShipped:
    """The names that used to make both inventories return nothing."""

    def test_none_of_them_is_in_any_inventory(self):
        shipped = {n for inventory, _, _ in INVENTORIES for n, _ in inventory}
        shipped.update(OPEN_CONNECTION_METRICS)
        assert not shipped & set(MYSQL_NAMES)

    @pytest.mark.parametrize("name", MYSQL_NAMES)
    def test_mysql_name_is_absent_from_system_tables(self, clickhouse_backend_single, name):
        """A MySQL name must not appear in any ClickHouse system table."""
        for table, column in (
            ("system.settings", "name"),
            ("system.server_settings", "name"),
            ("system.metrics", "metric"),
            ("system.events", "event"),
        ):
            row = clickhouse_backend_single.execute(
                f"SELECT count() AS n FROM {table} WHERE {column} = %s", (name,)
            ).data
            assert row and row[0]["n"] == 0, f"{name!r} unexpectedly exists in {table}"


class TestListPerformanceMetrics:
    """The function that used to return ``[]`` on every call."""

    def test_returns_a_non_empty_list(self, status):
        items = status.list_performance_metrics()
        assert len(items) > 0

    def test_covers_all_three_metric_tables(self, status):
        sources = {item.extra["source"] for item in status.list_performance_metrics()}
        assert sources == {
            "system.metrics",
            "system.events",
            "system.asynchronous_metrics",
        }

    def test_every_item_has_a_value_and_the_servers_description(self, status):
        for item in status.list_performance_metrics():
            assert item.value is not None, item.name
            assert item.description, f"{item.name} arrived without a description"

    def test_descriptions_come_from_the_server_not_from_the_module(self, status):
        """``Query`` is described by ClickHouse, not by this repository."""
        item = next(i for i in status.list_performance_metrics() if i.name == "Query")
        assert item.description == "Number of executing queries"

    def test_inventory_names_are_all_returned(self, status, clickhouse_backend_single):
        """Every shipped name this server publishes is returned, per source.

        Qualified by the table, because two of the five inventories can both
        contain ``Merge``-shaped names and a bare set comparison would let one
        table's row stand in for another's.
        """
        for inventory, table, column in INVENTORIES[2:]:
            have = _names_inventory(
                clickhouse_backend_single.execute(f"SELECT {column} FROM {table}").data, column
            )
            returned = {
                item.name for item in status.list_performance_metrics()
                if item.extra["source"] == table
            }
            expected = {name for name, _ in inventory if name in have}
            missing = sorted(expected - returned)
            assert not missing, (
                f"{table} publishes these and the inventory asks for them: {missing}"
            )

    def test_category_filter_is_applied(self, status):
        items = status.list_performance_metrics(StatusCategory.STORAGE)
        assert items
        assert all(item.category == StatusCategory.STORAGE for item in items)

    def test_async_signature_matches_sync(self):
        import inspect

        sync_names = {
            n for n, _ in inspect.getmembers(SyncClickHouseStatusIntrospector, inspect.isfunction)
        }
        async_names = {
            n for n, _ in inspect.getmembers(AsyncClickHouseStatusIntrospector, inspect.isfunction)
        }
        assert sync_names == async_names


class TestSyncAsyncParity:
    """The project's parity rule: same names, same parameters, only await differs."""

    def _public_methods(self, cls):
        return {
            name: fn
            for name, fn in vars(cls).items()
            if not name.startswith("_") and inspect.isfunction(fn)
        }

    def test_same_method_names(self):
        assert set(self._public_methods(SyncClickHouseStatusIntrospector)) == set(
            self._public_methods(AsyncClickHouseStatusIntrospector)
        )

    @pytest.mark.parametrize(
        "name",
        sorted(
            name
            for name, fn in vars(SyncClickHouseStatusIntrospector).items()
            if not name.startswith("_") and inspect.isfunction(fn)
        ),
    )
    def test_same_parameters(self, name):
        sync = getattr(SyncClickHouseStatusIntrospector, name)
        asyn = getattr(AsyncClickHouseStatusIntrospector, name)
        assert inspect.iscoroutinefunction(asyn), f"{name} is not a coroutine"
        assert not inspect.iscoroutinefunction(sync), f"{name} is unexpectedly a coroutine"
        assert list(inspect.signature(sync).parameters) == list(inspect.signature(asyn).parameters)

    def test_the_two_inventories_are_shared_not_duplicated(self):
        """Both classes read the same module-level constants."""
        for attr in (
            "list_configuration",
            "list_performance_metrics",
            "get_connection_info",
            "get_storage_info",
            "list_databases",
            "list_users",
            "get_session_info",
            "list_processes",
        ):
            sync = inspect.getsource(getattr(SyncClickHouseStatusIntrospector, attr))
            asyn = inspect.getsource(getattr(AsyncClickHouseStatusIntrospector, attr))
            for const in (
                "CLICKHOUSE_CONFIG_SETTINGS",
                "CLICKHOUSE_SERVER_SETTINGS",
                "CLICKHOUSE_GAUGE_METRICS",
                "CLICKHOUSE_COUNTER_EVENTS",
                "CLICKHOUSE_ASYNC_METRICS",
                "OPEN_CONNECTION_METRICS",
            ):
                assert (const in sync) == (const in asyn), f"{attr} differs on {const}"


class TestListConfiguration:
    def test_reads_both_configuration_tables(self, status):
        items = status.list_configuration()
        sources = {item.extra["source"] for item in items}
        assert sources == {"system.settings", "system.server_settings"}

    def test_every_inventory_name_is_returned(self, status, clickhouse_backend_single):
        """Both halves of the split configuration, scoped to their own table.

        ``max_connections`` is the case that makes the scoping necessary: it is
        a ``system.server_settings`` row and not a ``system.settings`` row at
        all, so a single unqualified name set would pass even if the two queries
        were reading the wrong tables.
        """
        for inventory, table, column in INVENTORIES[:2]:
            have = _names_inventory(
                clickhouse_backend_single.execute(f"SELECT {column} FROM {table}").data, column
            )
            returned = {
                item.name for item in status.list_configuration()
                if item.extra["source"] == table
            }
            expected = {name for name, _ in inventory if name in have}
            assert expected, f"the {table} inventory shares no name with this server"
            missing = sorted(expected - returned)
            assert not missing, (
                f"{table} publishes these and the inventory asks for them: {missing}"
            )

    def test_description_default_and_unit_come_from_the_row(self, status, clickhouse_backend_single):
        """``max_threads`` reports whatever the server says, not a fixed string.

        Its default is ``auto(N)`` where N is the number of hardware threads
        available to the server — measured ``auto(16)`` on a 16-core host and
        ``auto(4)`` on the same 26.3 build pinned to four CPUs with
        ``docker run --cpuset-cpus=0-3``. A CI runner has a different core count
        again, so the number is not assertable; the *shape* is, and 25.8/26.3
        additionally quote it (``'auto(16)'``, ten characters) where 26.7 does
        not. What is pinned here is that all of it came from the row.
        """
        row = clickhouse_backend_single.execute(
            "SELECT value, default, description, type FROM system.settings WHERE name = %s",
            ("max_threads",),
        ).data[0]
        item = next(i for i in status.list_configuration() if i.name == "max_threads")
        assert item.value is not None
        assert item.default_value == row["default"]
        assert item.extra["type"] == row["type"] == "MaxThreads"
        assert re.fullmatch(r"'?auto\(\d+\)'?", item.default_value), item.default_value
        assert "query processing threads" in item.description

    def test_time_units_come_from_the_declared_type(self, status):
        """``max_execution_time`` is a ``Seconds`` setting on the server."""
        item = next(i for i in status.list_configuration() if i.name == "max_execution_time")
        assert item.unit == "Seconds"

    def test_byte_settings_stay_unitless(self, status):
        """``UInt64`` does not say bytes, so no unit is claimed for it."""
        item = next(
            i for i in status.list_configuration() if i.name == "query_cache_max_size_in_bytes"
        )
        assert item.unit is None

    def test_read_only_flag_comes_from_the_server(self, status):
        item = next(i for i in status.list_configuration() if i.name == "max_connections")
        # config.xml values are fixed unless the server says otherwise.
        assert item.is_readonly is True
        assert item.is_dynamic is False

    def test_changed_flag_is_recorded(self, status):
        for item in status.list_configuration():
            assert isinstance(item.extra["changed"], bool)


class TestConnectionInfo:
    def test_max_connections_comes_from_server_settings(self, status):
        info = status.get_connection_info()
        assert info.max_connections is not None
        assert info.max_connections > 0

    def test_max_connections_is_not_a_system_settings_row(self, clickhouse_backend_single):
        """Why the lookup had to move: the setting is not in ``system.settings``.

        ``max_connections`` is a genuine ClickHouse name — the old code happened
        to have the right word and the wrong table, so the query succeeded and
        returned nothing.
        """
        absent = clickhouse_backend_single.execute(
            "SELECT count() AS n FROM system.settings WHERE name = %s", ("max_connections",)
        ).data
        assert absent[0]["n"] == 0

        present = clickhouse_backend_single.execute(
            "SELECT value FROM system.server_settings WHERE name = %s", ("max_connections",)
        ).data
        assert present and int(present[0]["value"]) > 0

    def test_active_count_sums_the_open_listener_gauges(self, status):
        info = status.get_connection_info()
        parts = [
            info.extra["http_connections"],
            info.extra["tcp_connections"],
            info.extra["interserver_connections"],
            info.extra["mysql_connections"],
            info.extra["postgresql_connections"],
        ]
        assert all(isinstance(p, int) for p in parts)
        assert info.active_count == sum(parts)
        assert info.active_count >= 1

    def test_idle_count_is_none_and_says_why(self, status):
        info = status.get_connection_info()
        assert info.idle_count is None
        assert "Threads_connected" in info.extra["note"]


class TestListUsers:
    def test_reads_system_users(self, status, clickhouse_backend_single):
        expected = {
            row["name"]
            for row in clickhouse_backend_single.execute("SELECT name FROM system.users").data
        }
        assert {u.name for u in status.list_users()} == expected
        assert expected, "the scenario server reports no users at all"

    def test_the_clickhouse_user_database_does_not_exist(self, clickhouse_backend_single):
        """The source the old implementation used, and why it always returned []."""
        with pytest.raises(DatabaseError):
            clickhouse_backend_single.execute("SELECT User, Host FROM clickhouse.user")

    def test_superuser_is_derived_from_grants(self, status):
        for user in status.list_users():
            types = set(user.extra["access_types"])
            expected = all(t in types for t in user.extra["superuser_test"])
            assert user.is_superuser is expected
            assert user.extra["superuser_test"], "the superuser test set must be recorded"

    def test_auth_types_are_reported(self, status):
        assert any(u.extra["auth_type"] for u in status.list_users())


class TestListProcesses:
    def test_database_column_is_read_from_current_database(self, status):
        procs = status.list_processes()
        assert procs, "system.processes always has at least the querying session"
        assert procs[0].database is not None

    def test_currentDatabase_is_not_a_column(self, clickhouse_backend_single):
        """``system.processes`` names it ``current_database``.

        Note the trap: ``SELECT currentDatabase FROM system.processes`` does *not*
        fail, because ClickHouse resolves the bare word to its ``currentDatabase()``
        function and returns that instead. The column list is the only thing that
        settles it.
        """
        columns = {
            row["name"]
            for row in clickhouse_backend_single.execute(
                "SELECT name FROM system.columns WHERE database = 'system' AND table = 'processes'"
            ).data
        }
        assert "current_database" in columns
        assert "currentDatabase" not in columns


class TestStorageInfo:
    def test_free_space_is_populated_from_system_disks(self, status):
        info = status.get_storage_info()
        assert info.free_space_bytes is not None
        assert info.free_space_bytes > 0

    def test_all_disks_are_reported(self, status):
        info = status.get_storage_info()
        assert info.extra["disks"]
        for disk in info.extra["disks"]:
            assert disk["name"] and disk["path"]

    def test_total_size_is_the_configured_database(self, status, clickhouse_backend_single):
        expected = clickhouse_backend_single.execute(
            "SELECT sum(total_bytes) AS n FROM system.tables WHERE database = %s",
            (clickhouse_backend_single.config.database,),
        ).data[0]["n"]
        assert status.get_storage_info().total_size_bytes == expected


class TestOverview:
    def test_overview_is_populated(self, status):
        ov = status.get_overview()
        assert ov.server_vendor == "ClickHouse"
        assert ov.server_version
        assert ov.configuration
        assert ov.performance
        assert ov.databases
        assert ov.users
        assert ov.processes
        assert ov.connections.max_connections

    def test_mysql_only_slots_are_left_at_their_default(self, status):
        """``innodb`` / ``binary_log`` / ``slow_query`` are core fields this
        backend never fills; they must be ``None``, not fabricated."""
        ov = status.get_overview()
        assert ov.innodb is None
        assert ov.binary_log is None
        assert ov.slow_query is None

    def test_the_mixin_no_longer_imports_an_innodb_type(self):
        import rhosocial.activerecord.backend.impl.clickhouse.introspection.status_introspector as mod

        source_names = [n for n in dir(mod) if "InnoDB" in n or "BinaryLog" in n or "SlowQuery" in n]
        assert source_names == []
        assert "innodb" not in mod.ClickHouseStatusIntrospectorMixin._build_server_overview.__code__.co_varnames

    def test_to_dict_is_json_ready(self, status):
        import json

        payload = status.get_overview().to_dict()
        json.dumps(payload)  # must not raise
        assert payload["innodb"] is None
        # to_dict() already unwraps the enum to its value.
        assert payload["performance"][0]["category"] in {
            "configuration",
            "performance",
            "connection",
            "storage",
            "security",
            "replication",
        }


class TestDatabaseTableCounts:
    """The counts are ``information_schema``'s, so an empty database says zero.

    A fresh ClickHouse container has no tables anywhere except ``system`` and
    ``information_schema``; the scenario creates ``test_db`` but nothing puts a
    table *in* it before this runs. Measured on 25.8.33.6, 26.3.28.5 and
    26.7.3.19: ``default`` holds 0 tables on all three.
    """

    def test_the_database_list_is_the_servers_own(self, status, clickhouse_backend_single):
        """``list_databases()`` names what the server has, with a real count each.

        Compared against ``system.databases`` rather than a literal, so a server
        that has an extra database still passes — and so the assertion still
        fails if a name comes back ``None`` or a count comes back missing, which
        is what the MySQL-shaped parsers used to produce.
        """
        expected = {
            row["name"]
            for row in clickhouse_backend_single.execute("SELECT name FROM system.databases").data
        }
        dbs = {db.name: db for db in status.list_databases()}
        assert set(dbs) == expected
        assert "default" in dbs
        assert all(isinstance(db.table_count, int) and db.table_count >= 0 for db in dbs.values())

    def test_counts_match_information_schema_for_a_known_database(
        self, status, clickhouse_backend_single
    ):
        """Pinned against a database whose contents this test controls.

        Asserting against ``information_schema`` itself rather than a literal
        number is what makes the check meaningful on a server whose tables come
        and go: it still fails if the count is read from the wrong column or the
        wrong table, and it cannot fail merely because a database is empty.
        """
        database = clickhouse_backend_single.config.database
        row = clickhouse_backend_single.execute(
            "SELECT count() AS n FROM information_schema.TABLES "
            "WHERE table_schema = %s AND table_type = 'BASE TABLE'",
            (database,),
        ).data[0]
        dbs = {db.name: db for db in status.list_databases()}
        assert database in dbs, f"{database} is the configured database and must be listed"
        assert dbs[database].table_count == row["n"]

    def test_view_count_is_not_zero_for_information_schema(self, status):
        """``information_schema`` really does have views, so this is not a zero."""
        dbs = {db.name: db for db in status.list_databases()}
        assert dbs["information_schema"].view_count > 0


class TestUnitDerivation:
    """``_setting_unit`` is pure, so it is pinned without a server."""

    @pytest.mark.parametrize(
        "declared,expected",
        [
            ("Seconds", "Seconds"),
            ("Milliseconds", "Milliseconds"),
            ("Microseconds", "Microseconds"),
            ("Nanoseconds", "Nanoseconds"),
            ("UInt64", None),
            ("NonZeroUInt64", None),
            ("Bool", None),
            ("MaxThreads", None),
            ("Float", None),
            (None, None),
        ],
    )
    def test_only_time_types_become_units(self, declared, expected):
        assert ClickHouseStatusIntrospectorMixin._setting_unit(declared) == expected
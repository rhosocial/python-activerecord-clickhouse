# tests/.../feature/backend/execute/introspection/test_status_introspector_async_offline.py
"""Offline unit tests for ``AsyncClickHouseStatusIntrospector``.

The live ``test_status_introspector.py`` pins the inventory contract against a
real server, but it exercises the async class only through signature/parity
checks.  ClickHouse's async path (native async driver) must be covered on its
own, without a server: every read below goes through an ``AsyncMock`` on the
backend's ``execute`` seam, and ``_render`` is replaced with a deterministic
node-name tag so a response map can drive each query independently.

No socket, no driver, no ClickHouse server is involved in this module.
"""

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from rhosocial.activerecord.backend.introspection.status import StatusCategory

from rhosocial.activerecord.backend.impl.clickhouse.dialect import ClickHouseDialect
from rhosocial.activerecord.backend.impl.clickhouse.introspection.status_introspector import (
    _SUPERUSER_ACCESS_TYPES,
    OPEN_CONNECTION_METRICS,
    AsyncClickHouseStatusIntrospector,
    ClickHouseStatusIntrospector,
)


class _Result:
    """Minimal stand-in for the backend execution result (only ``.data`` is read).

    It is made awaitable on purpose: the async methods ``await`` the execute
    seam, while the shared ``_build_server_overview`` mixin calls it
    synchronously.  Returning an awaitable result object lets one mock serve
    both call styles without touching the source under test.
    """

    def __init__(self, data=None):
        self.data = data if data is not None else []

    def __await__(self):
        async def _yield_self():
            return self

        return _yield_self().__await__()


def _make_introspector(responses=None, *, database="default", password=None, version_attr=None, databases=None):
    """Build an async introspector over a fully mocked backend.

    ``responses`` maps a query node's class name to the rows (or an exception)
    that ``backend.execute`` should yield for it.  ``databases`` is the list of
    ``SimpleNamespace(name=...)`` objects returned by ``show.databases()``.
    """
    responses = dict(responses or {})
    backend = MagicMock()
    # Query nodes validate that their dialect is a real SQLDialectBase instance;
    # SQL rendering itself is bypassed by the _render override below.
    backend.dialect = ClickHouseDialect(version=(26, 7, 3))
    backend.config = SimpleNamespace(database=database, password=password)
    backend._version = version_attr

    def fake_execute(sql, params=()):
        value = responses.get(sql, [])
        if isinstance(value, Exception):
            raise value
        return _Result(value)

    backend.execute = MagicMock(side_effect=fake_execute)
    backend.introspector = SimpleNamespace(
        show=SimpleNamespace(databases=AsyncMock(return_value=list(databases or [])))
    )

    introspector = AsyncClickHouseStatusIntrospector(backend)

    # Rendering is a dialect concern covered elsewhere; tag by node type so the
    # response map above can dispatch without depending on generated SQL text.
    def fake_render(node):
        return type(node).__name__, ()

    introspector._render = fake_render
    return introspector, backend


# --------------------------------------------------------------------------- #
# Pure helpers (inherited mixin logic, exercised on the async instance)
# --------------------------------------------------------------------------- #


class TestAsyncValueAndVersionHelpers:
    def setup_method(self):
        self.status, _ = _make_introspector()

    @pytest.mark.parametrize(
        "raw,expected",
        [
            (None, None),
            (42, 42),
            ("42", 42),
            ("not-a-number", "not-a-number"),
            (3.5, 3.5),
        ],
    )
    def test_parse_variable_value(self, raw, expected):
        assert self.status.parse_variable_value(raw) == expected

    @pytest.mark.parametrize(
        "raw,expected",
        [
            ("26.7.3.19", (26, 7, 3)),
            ("25.8.4.13", (25, 8, 4)),
            ("26.3.1.1-alpine", (26, 3, 1)),
            ("garbage", (0, 0, 0)),
            ("", (0, 0, 0)),
        ],
    )
    def test_parse_version_string(self, raw, expected):
        assert self.status.parse_version_string(raw) == expected

    @pytest.mark.parametrize(
        "version,major,minor,expected",
        [
            ("26.7.3", 26, 7, True),
            ("26.7.3", 26, 1, True),
            ("25.8.1", 26, 1, False),
            ("garbage", 26, 7, False),
        ],
    )
    def test_is_clickhouse_version_at_least(self, version, major, minor, expected):
        assert self.status._is_clickhouse_version_at_least(version, major, minor) is expected

    @pytest.mark.parametrize(
        "declared,expected",
        [
            ("Seconds", "Seconds"),
            ("Milliseconds", "Milliseconds"),
            ("Microseconds", "Microseconds"),
            ("Nanoseconds", "Nanoseconds"),
            ("UInt64", None),
            ("Bool", None),
            ("MaxThreads", None),
            (None, None),
        ],
    )
    def test_setting_unit(self, declared, expected):
        assert self.status._setting_unit(declared) == expected

    def test_vendor_name(self):
        assert self.status._get_vendor_name() == "ClickHouse"


# --------------------------------------------------------------------------- #
# list_configuration
# --------------------------------------------------------------------------- #

_SETTING_ROWS = [
    {
        "name": "max_threads",
        "value": "8",
        "description": "Max query threads",
        "default": "auto(8)",
        "readonly": 0,
        "type": "MaxThreads",
        "changed": 1,
    },
    {
        "name": "max_execution_time",
        "value": "30",
        "description": "Query timeout",
        "default": "0",
        "readonly": 0,
        "type": "Seconds",
        "changed": 0,
    },
    {"name": "not_in_inventory", "value": "x", "description": "extra"},
]

_SERVER_SETTING_ROWS = [
    {
        "name": "max_connections",
        "value": "100",
        "description": "Max connections",
        "default": "100",
        "changeable_without_restart": "No",
        "type": "UInt64",
        "changed": 0,
    },
    {
        "name": "path",
        "value": "/var/lib/clickhouse/",
        "description": "Data path",
        "default": "/var/lib/clickhouse/",
        "changeable_without_restart": "Yes",
        "type": "String",
        "changed": 0,
    },
]


def _config_responses():
    return {
        "ClickHouseSettingsQuery": _SETTING_ROWS,
        "ClickHouseServerSettingsQuery": _SERVER_SETTING_ROWS,
    }


class TestAsyncListConfiguration:
    async def test_reads_both_configuration_tables(self):
        status, _ = _make_introspector(_config_responses())
        items = await status.list_configuration()
        assert {i.extra["source"] for i in items} == {"system.settings", "system.server_settings"}
        assert [i.name for i in items] == ["max_threads", "max_execution_time", "max_connections", "path"]

    async def test_values_and_metadata_come_from_the_rows(self):
        status, _ = _make_introspector(_config_responses())
        items = {i.name: i for i in await status.list_configuration()}

        assert items["max_threads"].value == 8  # parsed from "8"
        assert items["max_threads"].description == "Max query threads"
        assert items["max_threads"].default_value == "auto(8)"
        assert items["max_threads"].unit is None  # MaxThreads is not a time type
        assert items["max_threads"].extra["type"] == "MaxThreads"
        assert items["max_threads"].extra["changed"] is True

        assert items["max_execution_time"].unit == "Seconds"
        assert items["max_execution_time"].extra["source"] == "system.settings"

    async def test_not_in_inventory_is_dropped(self):
        status, _ = _make_introspector(_config_responses())
        assert "not_in_inventory" not in {i.name for i in await status.list_configuration()}

    async def test_server_setting_read_only_flag(self):
        status, _ = _make_introspector(_config_responses())
        items = {i.name: i for i in await status.list_configuration()}
        assert items["max_connections"].is_readonly is True
        assert items["max_connections"].is_dynamic is False
        assert items["path"].is_readonly is False
        assert items["path"].is_dynamic is True

    @pytest.mark.parametrize(
        "category,expected",
        [
            (StatusCategory.PERFORMANCE, {"max_threads", "max_execution_time"}),
            (StatusCategory.CONNECTION, {"max_connections"}),
            (StatusCategory.STORAGE, {"path"}),
            (StatusCategory.REPLICATION, set()),
        ],
    )
    async def test_category_filter(self, category, expected):
        status, _ = _make_introspector(_config_responses())
        items = await status.list_configuration(category)
        assert {i.name for i in items} == expected
        assert all(i.category == category for i in items)

    async def test_empty_rows_give_no_items(self):
        status, _ = _make_introspector()
        assert await status.list_configuration() == []

    async def test_query_error_falls_back_to_empty_rows(self):
        responses = _config_responses()
        responses["ClickHouseSettingsQuery"] = RuntimeError("settings unavailable")
        status, _ = _make_introspector(responses)
        items = await status.list_configuration()
        assert [i.name for i in items] == ["max_connections", "path"]


# --------------------------------------------------------------------------- #
# list_performance_metrics
# --------------------------------------------------------------------------- #

_GAUGE_ROWS = [
    {"metric": "Query", "value": 2, "description": "Number of executing queries"},
    {"metric": "QueryCacheBytes", "value": 512, "description": "Query cache size"},
    {"metric": "FilesystemCacheSize", "value": 4096, "description": "FS cache"},
    {"metric": "not_in_inventory", "value": 9, "description": "extra"},
]
_EVENT_ROWS = [
    {"event": "Query", "value": 10, "description": "Total queries"},
    {"event": "QueryTimeMicroseconds", "value": 500, "description": "Time spent"},
]
_ASYNC_ROWS = [
    {"metric": "Uptime", "value": 60, "description": "Seconds up"},
    {"metric": "NumberOfDatabases", "value": 3, "description": "Database count"},
]


def _metrics_responses():
    return {
        "ClickHouseMetricsQuery": _GAUGE_ROWS,
        "ClickHouseEventsQuery": _EVENT_ROWS,
        "ClickHouseAsynchronousMetricsQuery": _ASYNC_ROWS,
    }


class TestAsyncListPerformanceMetrics:
    async def test_covers_all_three_metric_tables(self):
        status, _ = _make_introspector(_metrics_responses())
        items = await status.list_performance_metrics()
        assert {i.extra["source"] for i in items} == {"system.metrics", "system.events", "system.asynchronous_metrics"}
        assert "not_in_inventory" not in {i.name for i in items}

    async def test_units_and_descriptions(self):
        status, _ = _make_introspector(_metrics_responses())
        items = {(i.name, i.extra["source"]): i for i in await status.list_performance_metrics()}

        query_gauge = items[("Query", "system.metrics")]
        assert query_gauge.value == 2
        assert query_gauge.description == "Number of executing queries"
        assert query_gauge.unit is None
        assert query_gauge.is_readonly is True
        assert query_gauge.is_dynamic is False

        assert items[("QueryCacheBytes", "system.metrics")].unit == "bytes"
        assert items[("QueryTimeMicroseconds", "system.events")].unit == "microseconds"
        assert items[("Uptime", "system.asynchronous_metrics")].extra["source"] == ("system.asynchronous_metrics")
        assert items[("FilesystemCacheSize", "system.metrics")].unit is None

    @pytest.mark.parametrize(
        "category,expected",
        [
            (StatusCategory.STORAGE, {"FilesystemCacheSize", "NumberOfDatabases"}),
            (StatusCategory.CONFIGURATION, {"Uptime"}),
            (StatusCategory.SECURITY, set()),
        ],
    )
    async def test_category_filter(self, category, expected):
        status, _ = _make_introspector(_metrics_responses())
        items = await status.list_performance_metrics(category)
        assert {i.name for i in items} == expected
        assert all(i.category == category for i in items)

    async def test_empty_rows_give_no_items(self):
        status, _ = _make_introspector()
        assert await status.list_performance_metrics() == []

    async def test_one_failing_table_does_not_lose_the_others(self):
        responses = _metrics_responses()
        responses["ClickHouseEventsQuery"] = RuntimeError("events unavailable")
        status, _ = _make_introspector(responses)
        items = await status.list_performance_metrics()
        assert {i.extra["source"] for i in items} == {"system.metrics", "system.asynchronous_metrics"}


# --------------------------------------------------------------------------- #
# get_connection_info
# --------------------------------------------------------------------------- #


class TestAsyncConnectionInfo:
    def _responses(self, gauges=None, max_connections="100"):
        gauge_rows = [
            {"metric": name, "value": value}
            for name, value in (
                gauges
                or [
                    ("HTTPConnection", 2),
                    ("TCPConnection", 3),
                    ("InterserverConnection", 0),
                    ("MySQLConnection", 1),
                    ("PostgreSQLConnection", "4"),
                ]
            )
        ]
        return {
            "ClickHouseConnectionGaugesQuery": gauge_rows,
            "ClickHouseServerSettingQuery": [{"value": max_connections}] if max_connections else [],
        }

    async def test_active_count_sums_listener_gauges(self):
        status, _ = _make_introspector(self._responses())
        info = await status.get_connection_info()
        assert info.active_count == 10
        assert info.max_connections == 100
        assert info.idle_count is None
        assert info.extra["http_connections"] == 2
        assert info.extra["tcp_connections"] == 3
        assert info.extra["interserver_connections"] == 0
        assert info.extra["mysql_connections"] == 1
        assert info.extra["postgresql_connections"] == 4
        assert "Threads_connected" in info.extra["note"]

    async def test_non_numeric_gauge_is_ignored(self):
        gauges = [
            ("HTTPConnection", "not-a-number"),
            ("TCPConnection", 5),
            ("InterserverConnection", 0),
            ("MySQLConnection", 0),
            ("PostgreSQLConnection", 0),
        ]
        status, _ = _make_introspector(self._responses(gauges))
        info = await status.get_connection_info()
        assert info.active_count == 5
        assert info.extra["http_connections"] is None

    async def test_empty_rows_give_none(self):
        status, _ = _make_introspector()
        info = await status.get_connection_info()
        assert info.active_count is None
        assert info.max_connections is None
        for key in (
            "http_connections",
            "tcp_connections",
            "interserver_connections",
            "mysql_connections",
            "postgresql_connections",
        ):
            assert info.extra[key] is None

    async def test_query_errors_fall_back_to_none(self):
        responses = {
            "ClickHouseConnectionGaugesQuery": RuntimeError("metrics down"),
            "ClickHouseServerSettingQuery": RuntimeError("settings down"),
        }
        status, _ = _make_introspector(responses)
        info = await status.get_connection_info()
        assert info.active_count is None
        assert info.max_connections is None

    def test_all_five_listener_gauges_are_requested(self):
        # The sum is only correct if the inventory lists every listener gauge.
        assert len(OPEN_CONNECTION_METRICS) == 5
        assert {
            "HTTPConnection",
            "TCPConnection",
            "InterserverConnection",
            "MySQLConnection",
            "PostgreSQLConnection",
        } == set(OPEN_CONNECTION_METRICS)


# --------------------------------------------------------------------------- #
# get_storage_info
# --------------------------------------------------------------------------- #


class TestAsyncStorageInfo:
    def _responses(self, disks=None, total="1048576"):
        return {
            "ClickHouseDatabaseTotalSizeQuery": [{"total_size": total}] if total is not None else [],
            "ClickHouseDiskListQuery": (
                disks
                if disks is not None
                else [
                    {"name": "default", "path": "/var/lib/clickhouse/", "free_space": "500"},
                    {"name": "other", "path": "/mnt/other", "free_space": "100"},
                ]
            ),
        }

    async def test_total_size_and_default_disk(self):
        status, _ = _make_introspector(self._responses(), database="analytics")
        info = await status.get_storage_info()
        assert info.total_size_bytes == 1048576
        assert info.free_space_bytes == 500
        assert info.extra["database"] == "analytics"
        assert info.extra["data_path"] == "/var/lib/clickhouse/"
        assert len(info.extra["disks"]) == 2

    async def test_no_default_disk_gives_no_free_space(self):
        disks = [{"name": "other", "path": "/mnt/other", "free_space": "100"}]
        status, _ = _make_introspector(self._responses(disks=disks))
        info = await status.get_storage_info()
        assert info.free_space_bytes is None
        assert info.extra["data_path"] is None
        assert info.extra["disks"] == disks

    async def test_total_size_query_error_still_returns_disks(self):
        responses = self._responses()
        responses["ClickHouseDatabaseTotalSizeQuery"] = RuntimeError("size query down")
        status, _ = _make_introspector(responses)
        info = await status.get_storage_info()
        assert info.total_size_bytes is None
        assert len(info.extra["disks"]) == 2

    async def test_empty_rows_give_empty_info(self):
        status, _ = _make_introspector(self._responses(disks=[], total=None))
        info = await status.get_storage_info()
        assert info.total_size_bytes is None
        assert info.free_space_bytes is None
        assert info.extra["disks"] == []


# --------------------------------------------------------------------------- #
# list_databases
# --------------------------------------------------------------------------- #


class TestAsyncListDatabases:
    _DBS = [SimpleNamespace(name="default"), SimpleNamespace(name="analytics")]

    def _responses(self, rows=None):
        return {
            "ClickHouseTableCountQuery": (
                rows
                if rows is not None
                else [
                    {"table_schema": "default", "table_type": "BASE TABLE", "count": 3},
                    {"table_schema": "default", "table_type": "VIEW", "count": 1},
                    {"TABLE_SCHEMA": "analytics", "TABLE_TYPE": "BASE TABLE", "COUNT": 7},
                ]
            )
        }

    async def test_table_and_view_counts_both_spellings(self):
        status, _ = _make_introspector(self._responses(), databases=self._DBS)
        dbs = {db.name: db for db in await status.list_databases()}
        assert dbs["default"].table_count == 3
        assert dbs["default"].view_count == 1
        assert dbs["analytics"].table_count == 7
        assert dbs["analytics"].view_count == 0

    async def test_no_databases_gives_empty_list(self):
        status, _ = _make_introspector(self._responses(), databases=[])
        assert await status.list_databases() == []

    async def test_count_query_error_gives_zero_counts(self):
        responses = self._responses()
        responses["ClickHouseTableCountQuery"] = RuntimeError("information_schema down")
        status, _ = _make_introspector(responses, databases=self._DBS)
        dbs = {db.name: db for db in await status.list_databases()}
        assert all(db.table_count == 0 and db.view_count == 0 for db in dbs.values())


# --------------------------------------------------------------------------- #
# list_users
# --------------------------------------------------------------------------- #

_USER_ROWS = [
    {
        "name": "root",
        "id": 1,
        "auth_type": ["password"],
        "default_database": "default",
        "host_ip": ["::1"],
        "host_names": ["localhost"],
    },
    {"name": "reader", "id": 2, "auth_type": [], "default_database": "", "host_ip": [], "host_names": []},
    {"id": 3, "auth_type": []},  # no name -> skipped
]
_GRANT_ROWS = [
    {"user_name": "root", "access_type": "SYSTEM"},
    {"user_name": "root", "access_type": "SHOW ACCESS"},
    {"user_name": "root", "access_type": "ROLE ADMIN"},
    {"user_name": "root", "access_type": "CREATE USER"},
    {"user_name": "reader", "access_type": "SELECT"},
]
_ROLE_ROWS = [
    {"user_name": "root", "role_name": "admin"},
    {"user_name": "reader", "role_name": "readonly"},
]


def _user_responses():
    return {
        "ClickHouseUserListQuery": _USER_ROWS,
        "ClickHouseGrantListQuery": _GRANT_ROWS,
        "ClickHouseRoleGrantListQuery": _ROLE_ROWS,
    }


class TestAsyncListUsers:
    async def test_users_grants_roles_and_superuser(self):
        status, _ = _make_introspector(_user_responses())
        users = {u.name: u for u in await status.list_users()}
        assert set(users) == {"root", "reader"}

        root = users["root"]
        assert root.is_superuser is True
        assert root.roles == ["admin"]
        assert root.extra["access_types"] == sorted(_SUPERUSER_ACCESS_TYPES)
        assert root.extra["superuser_test"] == list(_SUPERUSER_ACCESS_TYPES)
        assert root.extra["id"] == "1"
        assert root.extra["auth_type"] == ["password"]
        assert root.extra["default_database"] == "default"
        assert root.extra["host_ip"] == ["::1"]
        assert root.extra["host_names"] == ["localhost"]

        reader = users["reader"]
        assert reader.is_superuser is False
        assert reader.roles == ["readonly"]
        assert reader.extra["access_types"] == ["SELECT"]
        assert reader.extra["default_database"] is None

    async def test_no_users_gives_empty_list(self):
        responses = _user_responses()
        responses["ClickHouseUserListQuery"] = []
        status, backend = _make_introspector(responses)
        assert await status.list_users() == []
        # No users -> grant/role queries are not executed at all.
        executed = [call.args[0] for call in backend.execute.call_args_list]
        assert "ClickHouseGrantListQuery" not in executed
        assert "ClickHouseRoleGrantListQuery" not in executed

    async def test_missing_grant_means_not_superuser(self):
        responses = _user_responses()
        responses["ClickHouseGrantListQuery"] = [row for row in _GRANT_ROWS if row["user_name"] == "reader"]
        status, _ = _make_introspector(responses)
        users = {u.name: u for u in await status.list_users()}
        assert users["root"].is_superuser is False
        assert users["reader"].is_superuser is False


# --------------------------------------------------------------------------- #
# get_session_info / list_processes / _get_version_string
# --------------------------------------------------------------------------- #

_SESSION_ROWS = [{"currentUser()": "root"}]


class TestAsyncSessionInfo:
    async def test_user_database_and_password(self):
        responses = {"ClickHouseCurrentUserQuery": _SESSION_ROWS}
        status, _ = _make_introspector(responses, database="analytics", password="secret")
        session = await status.get_session_info()
        assert session.user == "root"
        assert session.database == "analytics"
        assert session.password_used is True
        assert session.ssl_enabled is None

    async def test_query_error_leaves_user_unset(self):
        responses = {"ClickHouseCurrentUserQuery": RuntimeError("user query down")}
        status, _ = _make_introspector(responses, database="default", password=None)
        session = await status.get_session_info()
        assert session.user is None
        assert session.database == "default"
        assert session.password_used is False

    async def test_empty_rows_leave_user_unset(self):
        status, _ = _make_introspector({"ClickHouseCurrentUserQuery": []})
        session = await status.get_session_info()
        assert session.user is None


_PROCESS_ROWS = [
    {
        "query_id": "q1",
        "user": "root",
        "address": "127.0.0.1",
        "current_database": "default",
        "elapsed": 3,
        "query": "SELECT 1",
    },
    {
        "query_id": "q2",
        "user": "reader",
        "address": "",
        "current_database": "analytics",
        "elapsed": 0,
        "query": "SELECT 2",
    },
]


class TestAsyncProcesses:
    async def test_process_fields(self):
        status, _ = _make_introspector({"ClickHouseProcessListQuery": _PROCESS_ROWS})
        procs = await status.list_processes()
        assert len(procs) == 2
        assert procs[0].id == "q1"
        assert procs[0].user == "root"
        assert procs[0].host == "127.0.0.1"
        assert procs[0].database == "default"
        assert procs[0].command == "QUERY"
        assert procs[0].time == 3
        assert procs[0].info == "SELECT 1"
        assert procs[0].state is None
        assert procs[1].host is None  # empty address -> None

    async def test_empty_rows_give_empty_list(self):
        status, _ = _make_introspector()
        assert await status.list_processes() == []


class TestAsyncVersionString:
    async def test_version_from_server(self):
        status, _ = _make_introspector({"ClickHouseVersionQuery": [{"version()": "26.7.3.19"}]})
        assert await status._get_version_string() == "26.7.3.19"

    async def test_falls_back_to_backend_version(self):
        status, _ = _make_introspector(
            {"ClickHouseVersionQuery": RuntimeError("version down")}, version_attr=(26, 7, 3)
        )
        assert await status._get_version_string() == "26.7.3"

    async def test_empty_result_falls_back_to_backend_version(self):
        status, _ = _make_introspector({"ClickHouseVersionQuery": []}, version_attr=(25, 8))
        assert await status._get_version_string() == "25.8"

    async def test_no_version_anywhere_gives_empty_string(self):
        status, _ = _make_introspector()
        assert await status._get_version_string() == ""


# --------------------------------------------------------------------------- #
# get_overview (assembly and full-stack)
# --------------------------------------------------------------------------- #


def _full_responses(replicas=None):
    responses = {}
    responses.update(_config_responses())
    responses.update(_metrics_responses())
    responses.update(
        {
            "ClickHouseConnectionGaugesQuery": [
                {"metric": "HTTPConnection", "value": 1},
                {"metric": "TCPConnection", "value": 2},
                {"metric": "InterserverConnection", "value": 0},
                {"metric": "MySQLConnection", "value": 0},
                {"metric": "PostgreSQLConnection", "value": 0},
            ],
            "ClickHouseServerSettingQuery": [{"value": "100"}],
            "ClickHouseDatabaseTotalSizeQuery": [{"total_size": "1024"}],
            "ClickHouseDiskListQuery": [{"name": "default", "path": "/data", "free_space": "512"}],
            "ClickHouseTableCountQuery": [{"table_schema": "default", "table_type": "BASE TABLE", "count": 1}],
            "ClickHouseUserListQuery": _USER_ROWS,
            "ClickHouseGrantListQuery": _GRANT_ROWS,
            "ClickHouseRoleGrantListQuery": _ROLE_ROWS,
            "ClickHouseCurrentUserQuery": _SESSION_ROWS,
            "ClickHouseProcessListQuery": _PROCESS_ROWS,
            "ClickHouseVersionQuery": [{"version()": "26.7.3.19"}],
            "ClickHouseReplicaListQuery": replicas if replicas is not None else [],
        }
    )
    return responses


class TestAsyncOverview:
    async def test_full_stack_overview(self):
        status, _ = _make_introspector(
            _full_responses(), databases=[SimpleNamespace(name="default")], password="secret"
        )
        overview = await status.get_overview()
        assert overview.server_vendor == "ClickHouse"
        assert overview.server_version == "26.7.3.19"
        assert overview.configuration
        assert overview.performance
        assert overview.connections.max_connections == 100
        assert overview.storage.free_space_bytes == 512
        assert [db.name for db in overview.databases] == ["default"]
        assert {u.name for u in overview.users} == {"root", "reader"}
        assert overview.session.user == "root"
        assert overview.session.database == "default"
        assert len(overview.processes) == 2
        assert "replicas" not in overview.extra

    async def test_replicas_are_included_when_present(self):
        replicas = [{"database": "default", "table": "t", "absolute_delay": 0}]
        status, _ = _make_introspector(_full_responses(replicas=replicas), databases=[SimpleNamespace(name="default")])
        overview = await status.get_overview()
        assert overview.extra["replicas"] == replicas

    async def test_all_subreads_are_awaited(self):
        status, _ = _make_introspector(_full_responses(), databases=[SimpleNamespace(name="default")])
        names = (
            "list_configuration",
            "list_performance_metrics",
            "get_connection_info",
            "get_storage_info",
            "list_databases",
            "list_users",
            "get_session_info",
            "list_processes",
            "_get_version_string",
        )
        for name in names:
            setattr(status, name, AsyncMock(return_value=[]))

        await status.get_overview()
        for name in names:
            getattr(status, name).assert_awaited_once_with()


# --------------------------------------------------------------------------- #
# Edge branches inside the async class
# --------------------------------------------------------------------------- #


class TestAsyncEdgeBranches:
    async def test_unknown_table_type_is_ignored(self):
        responses = {
            "ClickHouseTableCountQuery": [
                {"table_schema": "default", "table_type": "OTHER", "count": 5},
            ]
        }
        status, _ = _make_introspector(responses, databases=[SimpleNamespace(name="default")])
        db = (await status.list_databases())[0]
        assert db.table_count == 0 and db.view_count == 0

    async def test_malformed_grant_and_role_rows_are_ignored(self):
        responses = _user_responses()
        responses["ClickHouseGrantListQuery"] = [
            {"user_name": "root", "access_type": None},
            {"user_name": None, "access_type": "SELECT"},
        ]
        responses["ClickHouseRoleGrantListQuery"] = [
            {"user_name": "root", "role_name": None},
            {"user_name": None, "role_name": "admin"},
        ]
        status, _ = _make_introspector(responses)
        users = {u.name: u for u in await status.list_users()}
        assert users["root"].extra["access_types"] == []
        assert users["root"].roles == []
        assert users["root"].is_superuser is False

    @pytest.mark.parametrize("current_user", [None, ""])
    async def test_falsy_current_user_leaves_session_user_unset(self, current_user):
        status, _ = _make_introspector({"ClickHouseCurrentUserQuery": [{"currentUser()": current_user}]})
        session = await status.get_session_info()
        assert session.user is None


# --------------------------------------------------------------------------- #
# Async contract
# --------------------------------------------------------------------------- #

_PUBLIC_ASYNC_METHODS = (
    "get_overview",
    "list_configuration",
    "list_performance_metrics",
    "get_connection_info",
    "get_storage_info",
    "list_databases",
    "list_users",
    "get_session_info",
    "list_processes",
)


class TestAsyncContract:
    @pytest.mark.parametrize("name", _PUBLIC_ASYNC_METHODS)
    def test_public_methods_are_coroutines(self, name):
        assert getattr(AsyncClickHouseStatusIntrospector, name).__code__.co_flags & 0x80

    def test_same_public_methods_as_sync_class(self):
        sync = {n for n, v in vars(ClickHouseStatusIntrospector).items() if not n.startswith("_") and callable(v)}
        async_methods = {
            n for n, v in vars(AsyncClickHouseStatusIntrospector).items() if not n.startswith("_") and callable(v)
        }
        assert async_methods == sync

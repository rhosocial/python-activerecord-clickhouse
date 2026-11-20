# tests/rhosocial/activerecord_clickhouse_test/feature/backend/construct/cli/test_status_offline.py
"""Offline unit tests for the ClickHouse ``status`` CLI module.

Every test here is a pure-mock test: no ClickHouse server, no socket, no real
network.  The backend, its introspector, the output provider and (where needed)
``rich`` are replaced with fakes.  ClickHouse is synchronous only, so only the
sync paths are exercised; the async placeholder is deliberately not touched.
"""

import argparse
import json
import sys
import types
from dataclasses import dataclass
from enum import Enum
from unittest.mock import MagicMock, patch

import pytest
from rhosocial.activerecord.backend.errors import ConnectionError, QueryError
from rhosocial.activerecord.backend.introspection.status import (
    ConnectionInfo,
    DatabaseBriefInfo,
    ServerOverview,
    SessionInfo,
    StatusCategory,
    StatusItem,
    UserInfo,
)

from rhosocial.activerecord.backend.impl.clickhouse.cli import status as mod


def _make_parser():
    subs = argparse.ArgumentParser(prog="clickhouse").add_subparsers(dest="command")
    return mod.create_parser(subs)


# ---------------------------------------------------------------------------
# create_parser
# ---------------------------------------------------------------------------


class TestStatusParser:
    def test_defaults(self):
        args = _make_parser().parse_args([])
        assert args.type == "all"
        assert args.output == "table"
        assert args.verbose == 0
        assert args.rich_ascii is False
        assert args.is_async is False
        assert args.named_connection is None
        assert args.connection_params == []

    @pytest.mark.parametrize("status_type", mod.STATUS_TYPES)
    def test_all_status_types_accepted(self, status_type):
        assert _make_parser().parse_args([status_type]).type == status_type

    def test_invalid_type_rejected(self):
        with pytest.raises(SystemExit):
            _make_parser().parse_args(["bogus"])

    def test_verbosity_is_counted(self):
        assert _make_parser().parse_args(["-vvv"]).verbose == 3

    @pytest.mark.parametrize("fmt", ["table", "json", "csv", "tsv"])
    def test_output_choices(self, fmt):
        assert _make_parser().parse_args(["-o", fmt]).output == fmt

    def test_output_rejects_unknown(self):
        with pytest.raises(SystemExit):
            _make_parser().parse_args(["-o", "xml"])

    def test_rich_ascii_flag(self):
        assert _make_parser().parse_args(["--rich-ascii"]).rich_ascii is True

    @pytest.mark.parametrize("mode", ["auto", "require", "verify-ca", "verify-full", "disabled"])
    def test_ssl_choices(self, mode):
        assert _make_parser().parse_args(["--ssl", mode]).ssl == mode

    def test_ssl_rejects_unknown(self):
        with pytest.raises(SystemExit):
            _make_parser().parse_args(["--ssl", "insecure"])

    def test_connection_flags(self):
        args = _make_parser().parse_args(
            [
                "--host",
                "db",
                "--port",
                "9000",
                "--database",
                "mydb",
                "--user",
                "u",
                "--password",
                "p",
            ]
        )
        assert (args.host, args.port, args.database, args.user, args.password) == (
            "db",
            9000,
            "mydb",
            "u",
            "p",
        )

    def test_conn_params_and_named_connection(self):
        args = _make_parser().parse_args(
            ["--named-connection", "app.db", "--conn-param", "a=1", "--conn-param", "b=2"]
        )
        assert args.named_connection == "app.db"
        assert args.connection_params == ["a=1", "b=2"]


# ---------------------------------------------------------------------------
# _serialize_for_output
# ---------------------------------------------------------------------------


class _Colour(Enum):
    RED = "red"


@dataclass
class _Point:
    x: int
    y: int


class _WithModelDump:
    def __init__(self, mode="json"):
        self.mode = mode

    def model_dump(self, mode=None):
        if mode is None:
            raise TypeError("no mode argument accepted")
        return {"a": 1, "mode": mode}


class TestSerializeForOutput:
    @pytest.mark.parametrize("value", [None, "x", 7, 1.5, True, False])
    def test_scalars_pass_through(self, value):
        assert mod._serialize_for_output(value) == value

    def test_enum_becomes_value(self):
        assert mod._serialize_for_output(_Colour.RED) == "red"

    def test_dataclass_becomes_dict(self):
        assert mod._serialize_for_output(_Point(1, 2)) == {"x": 1, "y": 2}

    def test_nested_containers_recurse(self):
        obj = {"p": _Point(1, 2), "c": _Colour.RED, "items": [_Colour.RED, {"n": _Point(3, 4)}]}
        assert mod._serialize_for_output(obj) == {
            "p": {"x": 1, "y": 2},
            "c": "red",
            "items": ["red", {"n": {"x": 3, "y": 4}}],
        }

    def test_tuple_becomes_list(self):
        assert mod._serialize_for_output((1, 2, 3)) == [1, 2, 3]

    def test_model_dump_json_mode(self):
        assert mod._serialize_for_output(_WithModelDump("json")) == {"a": 1, "mode": "json"}

    def test_model_dump_typeerror_falls_back_to_no_arg(self):
        class NoMode:
            def model_dump(self):
                return {"ok": True}

        assert mod._serialize_for_output(NoMode()) == {"ok": True}

    def test_unknown_object_falls_back_to_str(self):
        class Weird:
            def __str__(self):
                return "weird-value"

        assert mod._serialize_for_output(Weird()) == "weird-value"


# ---------------------------------------------------------------------------
# _format_size
# ---------------------------------------------------------------------------


class TestFormatSize:
    @pytest.mark.parametrize(
        "size,expected",
        [
            (0, "0.0 B"),
            (512, "512.0 B"),
            (1023, "1023.0 B"),
            (1024, "1.0 KB"),
            (1024 * 512, "512.0 KB"),
            (1024**2, "1.0 MB"),
            (1024**3, "1.0 GB"),
            (1024**4, "1.0 TB"),
            (1024**5, "1.0 PB"),
        ],
    )
    def test_units(self, size, expected):
        assert mod._format_size(size) == expected


# ---------------------------------------------------------------------------
# _display_status_rich (fake rich injected via patch.dict(sys.modules))
# ---------------------------------------------------------------------------


class FakeTable:
    def __init__(self, *args, **kwargs):
        self.columns = []
        self.rows = []

    def add_column(self, header, *args, **kwargs):
        self.columns.append(header)

    def add_row(self, *cells, **kwargs):
        self.rows.append(cells)


class FakeConsole:
    printed = []

    def __init__(self, *args, **kwargs):
        pass

    def print(self, *items, **kwargs):
        for item in items:
            if isinstance(item, FakeTable):
                FakeConsole.printed.append(
                    ("table", list(item.columns), [list(r) for r in item.rows])
                )
            else:
                FakeConsole.printed.append(str(item))


@pytest.fixture
def fake_rich():
    console_mod = types.ModuleType("rich.console")
    console_mod.Console = FakeConsole
    table_mod = types.ModuleType("rich.table")
    table_mod.Table = FakeTable
    rich_mod = types.ModuleType("rich")
    rich_mod.console = console_mod
    rich_mod.table = table_mod
    FakeConsole.printed = []
    with patch.dict(
        sys.modules,
        {"rich": rich_mod, "rich.console": console_mod, "rich.table": table_mod},
    ):
        yield FakeConsole.printed


def _config_item(name, value, category=StatusCategory.CONFIGURATION, **kw):
    return StatusItem(name=name, value=value, category=category, **kw)


def _full_overview():
    return ServerOverview(
        server_version="26.7",
        server_vendor="ClickHouse",
        session=SessionInfo(
            user="alice",
            database="mydb",
            host="10.0.0.1",
            ssl_enabled=True,
            ssl_version="TLSv1.3",
            ssl_cipher="AES256-GCM",
            password_used=True,
        ),
        connections=ConnectionInfo(active_count=12, max_connections=100),
        configuration=[
            _config_item("max_threads", 8, description="Threads", is_readonly=False),
            _config_item("wrong_bucket", 1, category=StatusCategory.PERFORMANCE),
        ],
        performance=[
            _config_item("queries_per_sec", 42, category=StatusCategory.PERFORMANCE, unit="qps"),
            _config_item("wrong_bucket2", 2),
        ],
        databases=[
            DatabaseBriefInfo(name="mydb", size_bytes=2048, table_count=3, view_count=1),
            DatabaseBriefInfo(name="empty", size_bytes=0, table_count=0, view_count=0),
        ],
        users=[
            UserInfo(name="alice", is_superuser=True),
            UserInfo(name="bob", is_superuser=False),
        ],
    )


class TestDisplayStatusRich:
    def test_header_and_version_vendor(self, fake_rich):
        mod._display_status_rich(ServerOverview(server_version="26.7", server_vendor="ClickHouse"))
        out = " ".join(str(x) for x in fake_rich)
        assert "ClickHouse Server Status" in out
        assert "26.7" in out
        assert "ClickHouse" in out

    def test_session_fields_when_present(self, fake_rich):
        mod._display_status_rich(_full_overview())
        out = " ".join(str(x) for x in fake_rich)
        for token in (
            "Session",
            "alice",
            "mydb",
            "10.0.0.1",
            "Enabled",
            "TLSv1.3",
            "AES256-GCM",
            "Password",
        ):
            assert token in out, token

    def test_session_absent_is_ok(self, fake_rich):
        ov = ServerOverview(server_version="1", server_vendor="v", session=None)
        mod._display_status_rich(ov)
        assert "Session" not in " ".join(str(x) for x in fake_rich)

    def test_ssl_disabled_hides_version_and_cipher(self, fake_rich):
        ov = ServerOverview(
            server_version="1",
            server_vendor="v",
            session=SessionInfo(ssl_enabled=False, ssl_version="ignored", ssl_cipher="ignored"),
        )
        mod._display_status_rich(ov)
        out = " ".join(str(x) for x in fake_rich)
        assert "Disabled" in out
        assert "ignored" not in out

    def test_password_false_shows_other_auth(self, fake_rich):
        ov = ServerOverview(
            server_version="1", server_vendor="v", session=SessionInfo(password_used=False)
        )
        mod._display_status_rich(ov)
        assert "Other" in " ".join(str(x) for x in fake_rich)

    def test_connection_counts_rendered(self, fake_rich):
        mod._display_status_rich(_full_overview())
        out = " ".join(str(x) for x in fake_rich)
        assert "Active Connections" in out
        assert "12" in out
        assert "Max Connections" in out
        assert "100" in out

    def test_configuration_table_basic_columns(self, fake_rich):
        mod._display_status_rich(_full_overview())
        tables = [x for x in fake_rich if isinstance(x, tuple) and x[0] == "table"]
        cfg = [
            t
            for t in tables
            if "Parameter" in t[1] and "Value" in t[1] and "Description" not in t[1]
        ]
        assert cfg
        assert any(r[0] == "max_threads" for r in cfg[0][2])

    def test_verbose_adds_extra_columns(self, fake_rich):
        mod._display_status_rich(_full_overview(), verbose=1)
        out = " ".join(str(x) for x in fake_rich)
        assert "Description" in out
        assert "Readonly" in out
        assert "Unit" in out
        assert "Tables" in out
        assert "Views" in out
        assert "Threads" in out  # description value

    def test_only_items_of_matching_category_in_each_table(self, fake_rich):
        mod._display_status_rich(_full_overview(), verbose=1)
        tables = [x for x in fake_rich if isinstance(x, tuple) and x[0] == "table"]
        cfg = next(t for t in tables if "Readonly" in t[1])
        perf = next(t for t in tables if "Unit" in t[1])
        assert all(r[0] in ("max_threads",) for r in cfg[2])
        assert all(r[0] in ("queries_per_sec",) for r in perf[2])

    def test_databases_size_formatting(self, fake_rich):
        mod._display_status_rich(_full_overview(), verbose=1)
        out = " ".join(str(x) for x in fake_rich)
        assert "2.0 KB" in out
        assert "N/A" in out

    def test_users_superuser_column(self, fake_rich):
        mod._display_status_rich(_full_overview())
        tables = [x for x in fake_rich if isinstance(x, tuple) and x[0] == "table"]
        users = next(t for t in tables if "Superuser" in t[1])
        assert ["alice", "Yes"] in users[2]
        assert ["bob", "No"] in users[2]


# ---------------------------------------------------------------------------
# _handle_status_sync
# ---------------------------------------------------------------------------


def _args(**overrides):
    values = dict(
        type="config",
        output="table",
        verbose=0,
        rich_ascii=False,
        database="mydb",
        named_connection=None,
        is_async=False,
    )
    values.update(overrides)
    return MagicMock(**values)


def _backend():
    backend = MagicMock()
    backend._connection = object()
    return backend


@pytest.mark.parametrize(
    "status_type,introspector_method,title,return_value",
    [
        ("config", "list_configuration", "Configuration", [{"name": "x", "value": 1}]),
        ("performance", "list_performance_metrics", "Performance", [{"name": "q", "value": 2}]),
        ("connections", "get_connection_info", "Connections", {"active_count": 4}),
        ("storage", "get_storage_info", "Storage", {"total_size_bytes": 1024}),
        ("databases", "list_databases", "Databases", [{"name": "db"}]),
        ("users", "list_users", "Users", [{"name": "u"}]),
    ],
)
def test_handle_status_sync_dispatches(status_type, introspector_method, title, return_value):
    args = _args(type=status_type)
    backend = _backend()
    getattr(backend.introspector.status, introspector_method).return_value = return_value
    provider = MagicMock()

    mod._handle_status_sync(args, backend, provider)

    backend.connect.assert_called_once_with()
    backend.introspect_and_adapt.assert_called_once_with()
    getattr(backend.introspector.status, introspector_method).assert_called_once()
    provider.display_results.assert_called_once()
    shown, kwargs = provider.display_results.call_args
    assert kwargs["title"] == title
    backend.disconnect.assert_called_once_with()


def test_handle_status_sync_all_json_output(capsys):
    args = _args(type="all", output="json")
    backend = _backend()
    overview = ServerOverview(server_version="26.7", server_vendor="ClickHouse")
    backend.introspector.status.get_overview.return_value = overview
    provider = MagicMock()

    with patch.object(mod, "RICH_AVAILABLE", False):
        mod._handle_status_sync(args, backend, provider)

    payload = json.loads(capsys.readouterr().out)
    assert payload["server_version"] == "26.7"
    provider.display_results.assert_not_called()


@pytest.mark.parametrize("fmt", ["csv", "tsv"])
def test_handle_status_sync_all_falls_back_to_json_for_tabular(fmt, capsys):
    args = _args(type="all", output=fmt)
    backend = _backend()
    backend.introspector.status.get_overview.return_value = ServerOverview(
        server_version="v", server_vendor="c"
    )
    provider = MagicMock()

    with patch.object(mod, "RICH_AVAILABLE", True):
        mod._handle_status_sync(args, backend, provider)

    json.loads(capsys.readouterr().out)
    provider.display_results.assert_not_called()


def test_handle_status_sync_all_rich_display():
    args = _args(type="all", output="table")
    backend = _backend()
    overview = ServerOverview(server_version="v", server_vendor="c")
    backend.introspector.status.get_overview.return_value = overview
    provider = MagicMock()

    with (
        patch.object(mod, "RICH_AVAILABLE", True),
        patch.object(mod, "_display_status_rich") as display,
    ):
        mod._handle_status_sync(args, backend, provider)

    display.assert_called_once_with(overview, 0)


def test_handle_status_sync_disconnects_when_no_connection():
    args = _args()
    backend = _backend()
    backend._connection = None
    backend.introspector.status.list_configuration.return_value = []
    mod._handle_status_sync(args, backend, MagicMock())
    backend.disconnect.assert_not_called()


def test_handle_status_sync_connection_error():
    args = _args()
    backend = _backend()
    backend.connect.side_effect = ConnectionError("down")
    provider = MagicMock()

    with pytest.raises(SystemExit) as exc:
        mod._handle_status_sync(args, backend, provider)
    assert exc.value.code == 1
    provider.display_connection_error.assert_called_once()
    backend.disconnect.assert_called_once()


def test_handle_status_sync_query_error():
    args = _args()
    backend = _backend()
    backend.introspector.status.list_configuration.side_effect = QueryError("bad sql")
    provider = MagicMock()

    with pytest.raises(SystemExit) as exc:
        mod._handle_status_sync(args, backend, provider)
    assert exc.value.code == 1
    provider.display_query_error.assert_called_once()


def test_handle_status_sync_generic_error(capsys):
    args = _args()
    backend = _backend()
    backend.introspect_and_adapt.side_effect = RuntimeError("boom")
    provider = MagicMock()

    with pytest.raises(SystemExit) as exc:
        mod._handle_status_sync(args, backend, provider)
    assert exc.value.code == 1
    assert "Error during status retrieval: boom" in capsys.readouterr().err


# ---------------------------------------------------------------------------
# handle: dispatch guard
# ---------------------------------------------------------------------------


class TestHandleDispatch:
    def test_requires_database(self, capsys):
        args = _args(database=None, named_connection=None)
        with patch.object(mod, "create_provider"):
            with pytest.raises(SystemExit) as exc:
                mod.handle(args)
        assert exc.value.code == 1
        assert "--database is required" in capsys.readouterr().err

    def test_named_connection_bypasses_database_guard(self):
        args = _args(database=None, named_connection="app.db")
        with (
            patch.object(mod, "create_provider"),
            patch.object(mod, "resolve_connection_config_from_args", return_value=MagicMock()),
            patch.object(mod, "ClickHouseBackend") as backend_cls,
            patch.object(mod, "_handle_status_sync") as dispatch,
        ):
            mod.handle(args)
        backend_cls.assert_called_once()
        dispatch.assert_called_once()

    def test_sync_backend_created_and_dispatched(self):
        args = _args(database="mydb")
        config = object()
        with (
            patch.object(mod, "create_provider"),
            patch.object(
                mod, "resolve_connection_config_from_args", return_value=config
            ) as resolve,
            patch.object(mod, "ClickHouseBackend") as backend_cls,
            patch.object(mod, "_handle_status_sync") as dispatch,
        ):
            mod.handle(args)
        resolve.assert_called_once_with(args)
        backend_cls.assert_called_once_with(connection_config=config)
        dispatch.assert_called_once()

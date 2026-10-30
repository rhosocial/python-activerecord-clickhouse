# tests/rhosocial/activerecord_clickhouse_test/feature/backend/cli/test_cli_blackbox.py
"""Black-box CLI tests for the ClickHouse backend.

Strategy: run the CLI entry in-process via main(argv) and assert on stdout.
With `-o json` the stdout is clean structured data (logs go to stderr).
Live server scenarios come from tests/config/clickhouse_scenarios.yaml.
"""

import argparse
import io
import json
from contextlib import redirect_stderr, redirect_stdout

import pytest
from providers.scenarios import get_scenario_raw

from rhosocial.activerecord.backend.impl.clickhouse.__main__ import main
from rhosocial.activerecord.backend.impl.clickhouse.cli import introspect as introspect_mod
from rhosocial.activerecord.backend.impl.clickhouse.cli.introspect import INTROSPECT_TYPES

COMMANDS = [
    "info",
    "query",
    "introspect",
    "status",
    "named-expression",
    "named-procedure",
    "named-procedure-graph",
    "named-migration",
    "named-connection",
]


@pytest.fixture(scope="module")
def conn_args():
    """Connection args from the first available scenario."""
    backend_cls, config = get_scenario_raw("clickhouse_84")
    return [
        "--host",
        config.host,
        "--port",
        str(config.port),
        "--database",
        config.database,
        "--user",
        config.username,
        "--password",
        config.password,
    ]


def run_cli(argv):
    out, err = io.StringIO(), io.StringIO()
    exc = None
    with redirect_stdout(out), redirect_stderr(err):
        try:
            main(argv)
        except SystemExit as e:
            exc = e
    return out.getvalue(), err.getvalue(), exc


class TestCommandSurface:
    def test_help_lists_all_commands(self):
        out, _, _ = run_cli(["--help"])
        for cmd in COMMANDS:
            assert cmd in out

    def test_missing_command_errors(self):
        _, _, exc = run_cli([])
        assert exc is not None and exc.code == 1


class TestQuery:
    def test_query_json(self, conn_args):
        out, err, exc = run_cli(["query"] + conn_args + ["SELECT 1 AS one", "-o", "json"])
        assert exc is None, f"stderr: {err}\nstdout: {out}"
        assert json.loads(out) == [{"one": 1}]

    def test_query_async(self, conn_args):
        # clickhouse-connect is a synchronous-only library, so the ClickHouse
        # backend has no async implementation; the CLI fast-fails with a
        # friendly message instead of running an async query.
        out, _, exc = run_cli(["query"] + conn_args + ["SELECT 1 AS one", "-o", "json", "--async"])
        assert exc is not None


class TestInfoStatus:
    def test_info(self):
        out, _, exc = run_cli(["info"])
        assert exc is None
        assert "ClickHouse" in out or "clickhouse" in out

    def test_status(self, conn_args):
        out, _, exc = run_cli(["status"] + conn_args + ["-o", "json"])
        assert exc is None
        data = json.loads(out)
        assert isinstance(data, dict) or isinstance(data, list)


class TestNamedConnection:
    def test_describe(self, tmp_path):
        import os
        import subprocess
        import sys

        mod_dir = tmp_path / "conns"
        mod_dir.mkdir()
        (mod_dir / "connections.py").write_text(
            "from rhosocial.activerecord.backend.impl.clickhouse.config import ClickHouseConnectionConfig\n"
            "def prod_db():\n"
            "    return ClickHouseConnectionConfig(host='192.168.1.3', port=14683, "
            "database='test_db', username='root', password='password')\n"
        )
        env = dict(os.environ, PYTHONPATH=os.pathsep.join([str(mod_dir)] + sys.path))
        proc = subprocess.run(
            [
                sys.executable,
                "-m",
                "rhosocial.activerecord.backend.impl.clickhouse",
                "named-connection",
                "--describe",
                "connections.prod_db",
            ],
            capture_output=True,
            text=True,
            env=env,
        )
        assert proc.returncode == 0, proc.stderr
        assert "Resolved Configuration" in (proc.stdout + proc.stderr)


# ---------------------------------------------------------------------------
# Offline introspect coverage: a fake backend answers, so no server is needed.
# ---------------------------------------------------------------------------

#: The types whose NAME positional is a table name. The rest are asked without
#: one: this class of test is about the type reaching its branch, not NAME.
_NAME_FOR = {
    "columns": "users",
    "indexes": "users",
    "partitions": "users",
    "table-engine": "users",
}


def parse_introspect_args(argv):
    parser = argparse.ArgumentParser(prog="clickhouse")
    subparsers = parser.add_subparsers(dest="command")
    introspect_mod.create_parser(subparsers)
    return parser.parse_args(argv)


class FakeIntrospector:
    """Records which catalogue question the CLI reached."""

    def __init__(self):
        self.calls = []

    def list_tables(self, schema=None, include_system=False):
        self.calls.append(("list_tables", schema, include_system))
        return [{"name": "users", "table_type": "BASE_TABLE"}]

    def list_views(self, schema=None):
        self.calls.append(("list_views", schema))
        return [{"name": "v1", "definition": "SELECT 1"}]

    def get_view_info(self, view_name, schema=None):
        self.calls.append(("get_view_info", view_name, schema))
        if view_name != "v1":
            return None
        return {"name": "v1", "definition": "SELECT 1", "schema": schema}

    def list_columns(self, table_name, schema=None):
        self.calls.append(("list_columns", table_name, schema))
        return [{"name": "id", "data_type": "Int64"}]

    def list_indexes(self, table_name, schema=None):
        self.calls.append(("list_indexes", table_name, schema))
        return [{"name": "idx_id"}]

    def list_partitions(self, table_name, database=None):
        self.calls.append(("list_partitions", table_name, database))
        return [{"partition_id": "all"}]

    def get_table_engine(self, table_name, database=None):
        self.calls.append(("get_table_engine", table_name, database))
        return {"table_name": table_name, "engine": "MergeTree"}

    def get_database_info(self):
        self.calls.append(("get_database_info",))
        return {"name": "app", "version": "26.7.1"}


class FakeAsyncIntrospector:
    """The same questions, answered as coroutines.

    Only the unsuffixed names exist here, exactly as on the real
    ``AsyncClickHouseIntrospector`` -- the sync and async introspectors share
    one method name, so a call to ``list_tables_async`` fails here the same way
    it failed against the real object.
    """

    def __init__(self, sync):
        self._sync = sync
        self.calls = sync.calls

    async def list_tables(self, schema=None, include_system=False):
        return self._sync.list_tables(schema=schema, include_system=include_system)

    async def list_views(self, schema=None):
        return self._sync.list_views(schema=schema)

    async def get_view_info(self, view_name, schema=None):
        return self._sync.get_view_info(view_name, schema=schema)

    async def list_columns(self, table_name, schema=None):
        return self._sync.list_columns(table_name, schema=schema)

    async def list_indexes(self, table_name, schema=None):
        return self._sync.list_indexes(table_name, schema=schema)

    async def list_partitions(self, table_name, database=None):
        return self._sync.list_partitions(table_name, database=database)

    async def get_table_engine(self, table_name, database=None):
        return self._sync.get_table_engine(table_name, database=database)

    async def get_database_info(self):
        return self._sync.get_database_info()


class FakeBackend:
    last_instance = None

    def __init__(self, connection_config=None):
        self.connection_config = connection_config
        self._connection = None
        self.disconnect_calls = 0
        self.introspector = FakeIntrospector()
        FakeBackend.last_instance = self

    def connect(self):
        self._connection = object()

    def introspect_and_adapt(self):
        """The real backend learns the server version here before rendering."""
        self.adapt_calls = getattr(self, "adapt_calls", 0) + 1

    def disconnect(self):
        self.disconnect_calls += 1
        self._connection = None


class FakeAsyncBackend(FakeBackend):
    def __init__(self, connection_config=None):
        super().__init__(connection_config)
        self.introspector = FakeAsyncIntrospector(self.introspector)

    async def connect(self):
        self._connection = object()

    async def introspect_and_adapt(self):
        self.adapt_calls = getattr(self, "adapt_calls", 0) + 1

    async def disconnect(self):
        self.disconnect_calls += 1
        self._connection = None


class TestIntrospectBranches:
    @pytest.mark.parametrize("introspect_type", INTROSPECT_TYPES)
    @pytest.mark.parametrize("use_async", [False, True], ids=["sync", "async"])
    def test_every_declared_type_reaches_the_introspector(
        self, monkeypatch, capsys, introspect_type, use_async
    ):
        """Each declared type lands on a branch, with or without ``--async``.

        The asynchronous handler used to call ``list_tables_async`` and four
        more names the introspector does not have: sync and async are two
        classes with one set of method names here. The resulting
        ``AttributeError`` was swallowed by the catch-all into "Error during
        introspection" and exit 1, so the async path answered nothing while
        reading like a server failure. Reaching the introspector at all is the
        thing the misspelt names did not do.
        """
        backend_class = FakeAsyncBackend if use_async else FakeBackend
        monkeypatch.setattr(introspect_mod, "ClickHouseBackend", FakeBackend)
        monkeypatch.setattr(introspect_mod, "AsyncClickHouseBackend", FakeAsyncBackend)

        argv = ["introspect", introspect_type]
        if introspect_type in _NAME_FOR:
            argv.append(_NAME_FOR[introspect_type])
        if use_async:
            argv.append("--async")
        argv += ["--database", "app", "-o", "json"]

        introspect_mod.handle(parse_introspect_args(argv))

        backend = backend_class.last_instance
        assert backend.introspector.calls, f"'{introspect_type}' never reached the introspector"
        assert backend.disconnect_calls == 1
        assert "Error during introspection" not in capsys.readouterr().err


class TestIntrospectName:
    @pytest.mark.parametrize("use_async", [False, True], ids=["sync", "async"])
    def test_views_with_a_name_describes_one_view(self, monkeypatch, capsys, use_async):
        """``views NAME`` answers for that view, not for the whole database."""
        backend_class = FakeAsyncBackend if use_async else FakeBackend
        monkeypatch.setattr(introspect_mod, "ClickHouseBackend", FakeBackend)
        monkeypatch.setattr(introspect_mod, "AsyncClickHouseBackend", FakeAsyncBackend)

        argv = ["introspect", "views", "v1"]
        if use_async:
            argv.append("--async")
        argv += ["--database", "app", "-o", "json"]

        introspect_mod.handle(parse_introspect_args(argv))

        data = json.loads(capsys.readouterr().out)
        assert [item["name"] for item in data] == ["v1"]
        assert data[0]["definition"]
        assert backend_class.last_instance.introspector.calls == [("get_view_info", "v1", None)]

    @pytest.mark.parametrize("use_async", [False, True], ids=["sync", "async"])
    def test_an_unknown_view_exits_1(self, monkeypatch, capsys, use_async):
        """A named view that does not exist is a failed request, not empty output."""
        monkeypatch.setattr(introspect_mod, "ClickHouseBackend", FakeBackend)
        monkeypatch.setattr(introspect_mod, "AsyncClickHouseBackend", FakeAsyncBackend)

        argv = ["introspect", "views", "nope"]
        if use_async:
            argv.append("--async")
        argv += ["--database", "app"]

        with pytest.raises(SystemExit) as excinfo:
            introspect_mod.handle(parse_introspect_args(argv))
        assert excinfo.value.code == 1
        assert "View 'nope' not found" in capsys.readouterr().err

    @pytest.mark.parametrize("introspect_type", ["tables", "database"])
    def test_a_name_the_type_cannot_use_exits_2(self, monkeypatch, capsys, introspect_type):
        """A NAME that would be ignored is refused instead of swallowed.

        ``tables`` and ``database`` answer for the whole database. They used to
        accept a name and drop it, so the run printed a full listing that read
        as though it had been narrowed to one object.
        """
        monkeypatch.setattr(introspect_mod, "ClickHouseBackend", FakeBackend)
        FakeBackend.last_instance = None

        with pytest.raises(SystemExit) as excinfo:
            introspect_mod.handle(
                parse_introspect_args(["introspect", introspect_type, "users", "--database", "app"])
            )
        assert excinfo.value.code == 2
        assert "takes no name" in capsys.readouterr().err
        assert FakeBackend.last_instance is None


class FakeDialect:
    """Every capability switch answers True unless a test says otherwise."""

    def __getattr__(self, name):
        if name.startswith("supports_"):
            return lambda: True
        raise AttributeError(name)


class TestIntrospectCapabilities:
    def test_the_advertised_types_are_the_capability_mapping(self):
        """One source for the list: the mapping, not a second hand-written copy."""
        assert list(introspect_mod._TYPE_CAPABILITIES) == INTROSPECT_TYPES

    def test_every_type_names_a_switch_the_dialect_has(self):
        """A type whose switch does not exist would be un-gated, not gated."""
        from rhosocial.activerecord.backend.impl.clickhouse.dialect import ClickHouseDialect

        dialect = ClickHouseDialect(version=(26, 7, 1))
        missing = [
            (cli_type, switch)
            for cli_type, switch in introspect_mod._TYPE_CAPABILITIES.items()
            if not hasattr(dialect, switch)
        ]
        assert missing == []

    def test_the_types_the_help_offers(self):
        """``--help`` lists what the parser accepts, and nothing it does not."""
        out, _, exc = run_cli(["introspect", "--help"])
        assert exc is not None and exc.code == 0
        for introspect_type in INTROSPECT_TYPES:
            assert introspect_type in out
        assert "foreign-keys" not in out
        assert "triggers" not in out

    def test_the_aggregate_table_type_is_gone(self):
        """``table`` answered three catalogue questions and could not be JSON."""
        assert "table" not in INTROSPECT_TYPES
        with pytest.raises(SystemExit) as excinfo:
            parse_introspect_args(["introspect", "table", "users"])
        assert excinfo.value.code == 2

    @pytest.mark.parametrize("use_async", [False, True], ids=["sync", "async"])
    def test_a_type_the_server_cannot_answer_exits_2(self, monkeypatch, capsys, use_async):
        """A declared family the connected server lacks is refused, not run.

        "This server has no views" and "this database has none" are different
        answers; an empty list would read as the second.
        """

        class GatedDialect(FakeDialect):
            def supports_view_introspection(self):
                return False

        class GatedBackend(FakeBackend):
            def __init__(self, connection_config=None):
                super().__init__(connection_config)
                self.dialect = GatedDialect()

        class GatedAsyncBackend(FakeAsyncBackend):
            def __init__(self, connection_config=None):
                super().__init__(connection_config)
                self.dialect = GatedDialect()

        monkeypatch.setattr(introspect_mod, "ClickHouseBackend", GatedBackend)
        monkeypatch.setattr(introspect_mod, "AsyncClickHouseBackend", GatedAsyncBackend)

        argv = ["introspect", "views"]
        if use_async:
            argv.append("--async")
        argv += ["--database", "app"]

        with pytest.raises(SystemExit) as excinfo:
            introspect_mod.handle(parse_introspect_args(argv))

        assert excinfo.value.code == 2
        assert "views introspection is not supported by this server" in capsys.readouterr().err
        assert GatedBackend.last_instance.introspector.calls == []

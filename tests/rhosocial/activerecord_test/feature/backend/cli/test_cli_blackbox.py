# tests/rhosocial/activerecord_test/feature/backend/cli/test_cli_blackbox.py
"""Black-box CLI tests for the ClickHouse backend.

Strategy: run the CLI entry in-process via main(argv) and assert on stdout.
With `-o json` the stdout is clean structured data (logs go to stderr).
Live server scenarios come from tests/config/clickhouse_scenarios.yaml.
"""

import io
import json
from contextlib import redirect_stderr, redirect_stdout

import pytest

from rhosocial.activerecord.backend.impl.clickhouse.__main__ import main
from providers.scenarios import get_scenario_raw

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
        "--host", config.host,
        "--port", str(config.port),
        "--database", config.database,
        "--user", config.username,
        "--password", config.password,
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
        out, _, exc = run_cli(["query"] + conn_args + ["SELECT 1 AS one", "-o", "json", "--async"])
        assert exc is None
        assert json.loads(out) == [{"one": 1}]


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
            [sys.executable, "-m", "rhosocial.activerecord.backend.impl.clickhouse",
             "named-connection", "--describe", "connections.prod_db"],
            capture_output=True, text=True, env=env,
        )
        assert proc.returncode == 0, proc.stderr
        assert "Resolved Configuration" in (proc.stdout + proc.stderr)
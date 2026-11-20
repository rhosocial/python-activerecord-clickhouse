# tests/rhosocial/activerecord_clickhouse_test/feature/backend/execute/cli/test_cli_live.py
"""Real-database CLI integration tests for the ClickHouse backend.

The stub-driven tests in this directory check CLI wiring without a server. These
tests instead drive ``main()`` with connection arguments taken from a real
scenario, so every command actually reaches a live ClickHouse: stdout is parsed
as JSON and the returned facts are asserted. The commands covered here are the
data-facing ones the introspect/catalogue files do not exercise.

ClickHouse is synchronous-only (``clickhouse-connect``), so only the sync CLI
path is used. Requires a live server configured in
``tests/config/clickhouse_scenarios.yaml``; the ``clickhouse_backend_single``
fixture skips these tests when no scenario is configured.
"""

import json

import pytest

from rhosocial.activerecord.backend.impl.clickhouse.__main__ import main


@pytest.fixture
def conn_args(clickhouse_backend_single):
    """Connection flags built from the live fixture's resolved config."""
    config = clickhouse_backend_single.config
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


def _run_json(argv, capsys):
    """Run the CLI with JSON output and return the parsed stdout document."""
    main(argv + ["-o", "json"])
    out = capsys.readouterr().out
    assert out.strip(), "CLI produced no stdout"
    return json.loads(out)


class TestLiveInfo:
    def test_info_connects_and_reports_environment(self, conn_args, capsys):
        """``info`` with no positional argument introspects the connected server."""
        data = _run_json(["info"] + conn_args, capsys)

        assert isinstance(data, dict)
        assert {"database", "features", "protocols"}.issubset(data)
        assert data["database"]["type"] == "clickhouse"
        assert data["database"]["connected"] is True
        assert data["database"]["version"]


class TestLiveQuery:
    def test_query_select_literal(self, conn_args, capsys):
        """A literal SELECT round-trips through the real backend to JSON."""
        data = _run_json(["query"] + conn_args + ["SELECT 1 AS n"], capsys)

        assert isinstance(data, list)
        assert data == [{"n": 1}]


class TestLiveStatus:
    def test_status_all(self, conn_args, capsys):
        """The ``all`` overview is a single nested JSON object."""
        data = _run_json(["status", "all"] + conn_args, capsys)

        assert isinstance(data, dict)
        assert data["server_version"]
        assert "configuration" in data

    def test_status_config(self, conn_args, capsys):
        """The ``config`` type lists the server's settings as JSON rows."""
        data = _run_json(["status", "config"] + conn_args, capsys)

        assert isinstance(data, list)
        assert data
        assert all(isinstance(item, dict) and item.get("name") for item in data)

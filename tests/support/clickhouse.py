# tests/support/clickhouse.py
"""The ClickHouse backend's test scenarios.

The scenario file holds server connection parameters only; the logical database
name comes from the test directory and is injected here.  ClickHouse is a
server backend, so a scenario maps to one database on one server.

Maintenance work (dropping and creating databases, server-level checks) runs on
the ``default`` database every ClickHouse instance ships with, because a
connection cannot drop the database it is currently using.

``AsyncClickHouseBackend`` is a fail-fast placeholder: clickhouse-connect is a
synchronous-only library, so the scenario exposes it only so the testsuite's
environment has the attribute it reads for async fixtures.  The root conftest
skips the async tests before any fixture is set up.
"""

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict

import yaml

from rhosocial.activerecord.backend.impl.clickhouse.backend import (
    AsyncClickHouseBackend,
    ClickHouseBackend,
)
from rhosocial.activerecord.backend.impl.clickhouse.config import (
    ClickHouseConnectionConfig,
)
from rhosocial.activerecord.backend.options import ExecutionOptions
from rhosocial.activerecord.backend.schema import StatementType

CONFIG_PATH = Path(
    os.environ.get("CLICKHOUSE_SCENARIOS_CONFIG_PATH")
    or Path(__file__).resolve().parents[1] / "config" / "clickhouse_scenarios.yaml"
)

# The scenario file describes a server, never a database: the logical name is
# derived from the test directory.  A ``database`` key, if present, is dropped.
# ``enabled`` is a scenario toggle, not a connection parameter.
SERVER_ONLY_KEYS = ("database", "enabled")

# The database every ClickHouse server has, used for server-level connections.
MAINTENANCE_DATABASE = "default"

DDL_OPTIONS = ExecutionOptions(stmt_type=StatementType.DDL)


def _load_scenarios(path: Path = CONFIG_PATH) -> Dict[str, Dict[str, Any]]:
    """Load one server-parameter dict per scenario from the YAML file."""
    with open(path, "r", encoding="utf-8") as file:
        data = yaml.safe_load(file) or {}
    entries = data.get("scenarios")
    if not entries:
        raise ValueError(f"{path} defines no scenarios")
    return {
        name: {key: value for key, value in entry.items() if key not in SERVER_ONLY_KEYS}
        for name, entry in entries.items()
    }


SCENARIO_MAP = _load_scenarios()
SCENARIOS = tuple(SCENARIO_MAP)


def _identifier(name: str) -> str:
    """Quote a ClickHouse identifier (database names come from the testsuite)."""
    return "`" + name.replace("`", "``") + "`"


@dataclass(frozen=True)
class ClickHouseScenario:
    """One ClickHouse test scenario: a server plus the backend classes."""

    name: str
    server: Dict[str, Any]
    backend_class: Any = ClickHouseBackend
    async_backend_class: Any = AsyncClickHouseBackend

    def make_config(self, database: str) -> ClickHouseConnectionConfig:
        """Return the connection configuration for this database on this server."""
        return ClickHouseConnectionConfig(**self.server, database=database)

    def reset_database(self, database: str) -> None:
        """Drop and recreate ``database`` on this scenario's server."""
        backend = self.backend_class(
            connection_config=ClickHouseConnectionConfig(
                **self.server, database=MAINTENANCE_DATABASE
            )
        )
        backend.connect()
        try:
            backend.execute(
                f"DROP DATABASE IF EXISTS {_identifier(database)}",
                (),
                options=DDL_OPTIONS,
            )
            backend.execute(
                f"CREATE DATABASE {_identifier(database)}",
                (),
                options=DDL_OPTIONS,
            )
        finally:
            backend.disconnect()


def scenario(name: str) -> ClickHouseScenario:
    """Return the scenario called ``name``."""
    try:
        server = SCENARIO_MAP[name]
    except KeyError:
        raise KeyError(f"Unknown ClickHouse scenario: {name}") from None
    return ClickHouseScenario(name, server)


def get_enabled_scenarios():
    """Return the scenarios this backend enables, as a name -> server map."""
    return {name: dict(server) for name, server in SCENARIO_MAP.items()}


def get_scenario(name: str):
    """Return ``(backend_class, config)`` for a benchmark database."""
    current = scenario(name)
    current.reset_database("test_benchmark")
    return current.backend_class, current.make_config("test_benchmark")


def get_scenario_raw(name: str):
    """Return ``(backend_class, config)`` for a server-level connection.

    Falls back to the first configured scenario when CI enables only one.
    """
    resolved = name if name in SCENARIO_MAP else next(iter(SCENARIO_MAP), None)
    if resolved is None:
        raise KeyError("No %s scenario configured" % name)
    current = scenario(resolved)
    return current.backend_class, current.make_config(MAINTENANCE_DATABASE)

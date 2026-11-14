# tests/rhosocial/activerecord_clickhouse_test/feature/backend/conftest.py
"""Fixtures for the backend-owned tests.

The backend runs these against a real server. The scenario supplies the
connection parameters; the database name is derived from the directory that
owns the test, so two directories never share tables.

These directories declare no testsuite contract: they drive the backend object
directly instead of configuring models, so they never request ``environment``.
"""
from typing import Any, Dict, Tuple, Type

import pytest
import pytest_asyncio

import support.clickhouse

from rhosocial.activerecord.backend.impl.clickhouse.backend import ClickHouseBackend
from rhosocial.activerecord.backend.impl.clickhouse.config import ClickHouseConnectionConfig

# --- Scenario Loading Logic ---

SCENARIO_MAP: Dict[str, Dict[str, Any]] = dict(support.clickhouse.SCENARIO_MAP)

_PREPARED_DATABASES = set()


def get_enabled_scenarios() -> Dict[str, Any]:
    return SCENARIO_MAP


def get_scenario_names():
    return list(get_enabled_scenarios().keys())


def _database_for(request) -> str:
    """Derive the logical database the directory owning the test runs in.

    The category directory ``feature`` is not part of the name; ``backend``
    leads it so the backend-owned databases are told apart from the feature
    ones at a glance.
    """
    parts = list(request.node.path.parts)
    try:
        index = max(i for i, part in enumerate(parts) if part == "backend")
        names = [part for part in parts[index + 1 : -1] if part]
        return "test_backend" + "".join("_" + name for name in names)
    except ValueError:
        return "test_backend"


def _prepare_database(scenario_name: str, database: str) -> None:
    """Create the directory's database once per scenario."""
    key = (scenario_name, database)
    if key in _PREPARED_DATABASES:
        return
    support.clickhouse.scenario(scenario_name).reset_database(database)
    _PREPARED_DATABASES.add(key)


def get_scenario(
    name: str, database: str = "test_backend"
) -> Tuple[Type[ClickHouseBackend], ClickHouseConnectionConfig]:
    """Return ``(backend_class, config)`` for one directory's database."""
    if name not in SCENARIO_MAP:
        if SCENARIO_MAP:
            name = next(iter(SCENARIO_MAP))
        else:
            raise ValueError("No scenarios registered")
    _prepare_database(name, database)
    return ClickHouseBackend, support.clickhouse.scenario(name).make_config(database)


def pytest_collection_modifyitems(config, items):
    """Pin a backend directory's tests to one worker.

    These directories create and drop tables in the directory's own database,
    so two workers must never run tests from the same directory at once.
    """
    for item in items:
        parts = item.path.parts
        if "backend" not in parts:
            continue
        item.add_marker(
            pytest.mark.xdist_group("clickhouse-backend::" + str(item.path.parent))
        )


# --- Provider Logic ---


class BackendFeatureProvider:
    def __init__(self):
        self._backend = None

    def setup_backend(self, scenario_name: str, database: str):
        if self._backend:
            return self._backend
        backend_class, config = get_scenario(scenario_name, database)
        self._backend = backend_class(connection_config=config)
        self._backend.connect()
        self._backend.introspect_and_adapt()
        return self._backend

    def cleanup(self):
        if self._backend:
            self._backend.disconnect()
            self._backend = None


# --- Fixtures ---


@pytest.fixture(scope="function", params=get_scenario_names())
def clickhouse_backend(request):
    scenario_name = request.param
    provider = BackendFeatureProvider()
    backend = provider.setup_backend(scenario_name, _database_for(request))
    yield backend
    provider.cleanup()


@pytest.fixture(scope="function")
def clickhouse_backend_single(request):
    """Non-parameterized fixture using the first available scenario.

    Use this for tests whose results do not vary across database versions
    (e.g. Protocol conformance, Explain output format). These tests run
    once instead of 7 times, and are pinned to the first scenario's worker
    in --scenario-parallel mode.
    """
    scenario_names = get_scenario_names()
    if not scenario_names:
        pytest.skip("No ClickHouse scenarios configured")
    scenario_name = scenario_names[0]
    provider = BackendFeatureProvider()
    backend = provider.setup_backend(scenario_name, _database_for(request))
    yield backend
    provider.cleanup()


@pytest_asyncio.fixture(scope="function", params=get_scenario_names())
async def async_clickhouse_backend(request):
    pytest.skip("rhosocial-activerecord-clickhouse does not provide an async backend")


@pytest_asyncio.fixture(scope="function")
async def async_clickhouse_backend_single():
    pytest.skip("rhosocial-activerecord-clickhouse does not provide an async backend")


# --- Control Backend for Session Modification Tests ---


@pytest.fixture(scope="function")
def clickhouse_control_backend(clickhouse_backend):
    """
    Dedicated control backend sharing the same connection config as clickhouse_backend.

    This fixture provides an independent backend instance for operations that
    need to control or interfere with the main test backend, such as:
    - KILL CONNECTION statements
    - Setting global variables
    - Monitoring other connections

    Automatically follows the same scenario parametrization as clickhouse_backend.
    """
    backend = ClickHouseBackend(connection_config=clickhouse_backend.config)
    backend.connect()
    backend.introspect_and_adapt()
    yield backend
    backend.disconnect()


@pytest.fixture(scope="function")
def clickhouse_control_backend_single(clickhouse_backend_single):
    """
    Non-parameterized control backend following clickhouse_backend_single.

    Must be used together with clickhouse_backend_single (or async_clickhouse_backend_single
    counterpart) so that KILL CONNECTION / SET GLOBAL operations target the same
    scenario the main backend is pinned to. Mixing a parameterized control backend
    with the single (first-scenario) backend makes KILL target a different server
    under multi-scenario runs.
    """
    backend = ClickHouseBackend(connection_config=clickhouse_backend_single.config)
    backend.connect()
    backend.introspect_and_adapt()
    yield backend
    backend.disconnect()


@pytest_asyncio.fixture(scope="function")
async def async_clickhouse_control_backend(async_clickhouse_backend):
    """
    Async control backend; ClickHouse has no async backend, so this always skips.
    """
    pytest.skip("rhosocial-activerecord-clickhouse does not provide an async backend")


@pytest_asyncio.fixture(scope="function")
async def async_clickhouse_control_backend_single(async_clickhouse_backend_single):
    """
    Async control backend on the pinned single scenario; always skips.
    """
    pytest.skip("rhosocial-activerecord-clickhouse does not provide an async backend")


# --- Type Adapters ---


@pytest.fixture(scope="module")
def json_column_adapter():
    """
    Module-scoped fixture providing ClickHouseJSONAdapter instance.

    This adapter can be used with column_adapters parameter to automatically
    parse JSON columns returned as strings by clickhouse-connector-python.

    Usage:
        result = clickhouse_backend.execute(
            "SELECT data FROM table",
            column_adapters={'data': (json_column_adapter, dict)}
        )
    """
    from rhosocial.activerecord.backend.impl.clickhouse.adapters import ClickHouseJSONAdapter

    return ClickHouseJSONAdapter()


# --- Protocol Requirement Checking ---


@pytest.fixture(scope="function", autouse=True)
def check_protocol_requirements(request):
    """
    Auto-used fixture that checks if the current backend supports required protocols.

    This fixture runs automatically for each test and checks if the test has
    a 'requires_protocol' marker. If so, it verifies that the current backend
    supports the required protocols, skipping the test if not.

    Note: This fixture accesses the backend through request.getfixturevalue()
    to avoid parameterization conflicts.
    """
    requires_protocol_marker = request.node.get_closest_marker("requires_protocol")
    if requires_protocol_marker:
        required_protocol_info = requires_protocol_marker.args[0]

        # Check if we're running an async test
        is_async = "async_clickhouse_backend" in request.fixturenames
        fixture_name = "async_clickhouse_backend" if is_async else "clickhouse_backend"

        if fixture_name in request.fixturenames:
            try:
                # Get the backend fixture
                backend = request.getfixturevalue(fixture_name)

                if backend is not None:
                    protocol_class, method_name = required_protocol_info

                    # Check if backend implements the protocol
                    if not isinstance(backend.dialect, protocol_class):
                        pytest.skip(
                            f"Skipping test - backend dialect does not implement {protocol_class.__name__} protocol"
                        )

                    # If a specific method name is provided, check if it's supported
                    if method_name:
                        if hasattr(backend.dialect, method_name):
                            method = getattr(backend.dialect, method_name)
                            if callable(method):
                                # For support checking methods that return bool
                                if method_name.startswith("supports_"):
                                    if not method():
                                        feature_name = method_name.replace("supports_", "")
                                        pytest.skip(f"Skipping test - backend dialect does not support {feature_name}")
            except Exception:
                pass


@pytest.fixture(scope="function")
def clickhouse_dialect():
    """Fixture providing ClickHouseDialect instance for testing transaction expressions.

    The version has to be set: ``ClickHouseDialect()`` with no version raises
    ``DialectNotAdaptedException`` from the moment anything reads
    ``dialect.version``. It is set to ``(26, 7, 1)`` — a real ClickHouse release
    line, and the same one ``test_unsupported_features.py`` uses — because the
    value is not cosmetic: ``dialect.version`` is what the real gates compare
    against, including ``supports_explain_analyze()`` at ``>= (26, 7, 0)``, the
    JSON gates at ``>= (26, 0, 0)``, the function-version table and the ``QBit``
    floor. The fabricated ``(8, 0, 0)`` this used to set compares *below* every
    one of them, so it silently reported the server as too old for features it
    has. ClickHouse's numbering has never had an 8.0.
    """
    from rhosocial.activerecord.backend.impl.clickhouse.dialect import ClickHouseDialect

    return ClickHouseDialect(version=(26, 7, 1))

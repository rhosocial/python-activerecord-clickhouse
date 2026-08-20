# tests/rhosocial/activerecord_clickhouse_test/feature/backend/conftest.py
import pytest
import pytest_asyncio
import yaml
import os
from typing import Dict, Any, Tuple, Type

from rhosocial.activerecord.backend.impl.clickhouse import ClickHouseBackend, AsyncClickHouseBackend, ClickHouseConnectionConfig

# --- Scenario Loading Logic ---

SCENARIO_MAP: Dict[str, Dict[str, Any]] = {}


def register_scenario(name: str, config: Dict[str, Any]):
    SCENARIO_MAP[name] = config


def _load_scenarios_from_config():
    """
    Load scenarios from a configuration file with the following priority:
    1. Environment variable specified path (highest priority)
    2. Default path tests/config/clickhouse_scenarios.yaml (lowest priority)
    If no valid configuration file is found, terminate with an error.
    """
    config_path = None
    env_config_path = os.getenv("CLICKHOUSE_SCENARIOS_CONFIG_PATH")

    if env_config_path and os.path.exists(env_config_path):
        print(f"Loading ClickHouse scenarios from environment-specified path: {env_config_path}")
        config_path = env_config_path
    else:
        default_path = os.path.join(os.path.dirname(__file__), "../../../../config", "clickhouse_scenarios.yaml")
        if os.path.exists(default_path):
            config_path = default_path
        elif env_config_path:
            # Path from env var was given but not found
            print(f"Warning: Scenario file specified in CLICKHOUSE_SCENARIOS_CONFIG_PATH not found: {env_config_path}")
            return

    if not config_path:
        raise FileNotFoundError(
            "No ClickHouse scenarios configuration file found. "
            "Either set CLICKHOUSE_SCENARIOS_CONFIG_PATH to a valid YAML file "
            "or place clickhouse_scenarios.yaml in the tests/config directory."
        )

    try:
        with open(config_path, "r", encoding="utf-8") as f:
            config_data = yaml.safe_load(f)

        if "scenarios" not in config_data:
            raise ValueError(f"Configuration file {config_path} does not contain 'scenarios' key")

        for scenario_name, config in config_data["scenarios"].items():
            register_scenario(scenario_name, config)

        _apply_scenario_filter()

    except ImportError:
        raise ImportError("PyYAML is required to load ClickHouse scenario configuration files")  # noqa: B904


def _apply_scenario_filter():
    """Filter SCENARIO_MAP based on the active scenarios env var.

    Keeps the backend-feature scenarios consistent with the scenarios active
    for the rest of the test run (set via ``--scenarios``).
    """
    filter_str = os.getenv("CLICKHOUSE_ACTIVE_SCENARIOS") or os.getenv("TESTSUITE_ACTIVE_SCENARIOS")
    if not filter_str:
        return
    allowed = set(s.strip() for s in filter_str.split(",") if s.strip())
    if not allowed:
        return
    for name in [n for n in SCENARIO_MAP if n not in allowed]:
        del SCENARIO_MAP[name]


_load_scenarios_from_config()


def get_scenario(name: str) -> Tuple[Type[ClickHouseBackend], ClickHouseConnectionConfig]:
    if name not in SCENARIO_MAP:
        if SCENARIO_MAP:
            name = next(iter(SCENARIO_MAP))
        else:
            raise ValueError("No scenarios registered")
    scenario_config = SCENARIO_MAP[name].copy()
    # Apply the pooled database name so parallel workers never share a schema.
    from providers.pooling import resolve_database_name

    pooled_db = resolve_database_name(name)
    if pooled_db:
        scenario_config["database"] = pooled_db
    # Extract ssl_disabled if present, otherwise it will be None
    ssl_disabled = scenario_config.pop("ssl_disabled", None)
    config = ClickHouseConnectionConfig(**scenario_config)
    # Re-add ssl_disabled to config if it was present
    if ssl_disabled is not None:
        config.ssl_disabled = ssl_disabled
    return ClickHouseBackend, config


def get_enabled_scenarios() -> Dict[str, Any]:
    return SCENARIO_MAP


# --- Provider Logic ---


class BackendFeatureProvider:
    def __init__(self):
        self._backend = None
        self._async_backend = None

    def setup_backend(self, scenario_name: str):
        if self._backend:
            return self._backend
        backend_class, config = get_scenario(scenario_name)
        self._backend = backend_class(connection_config=config)
        self._backend.connect()
        self._backend.introspect_and_adapt()
        return self._backend

    async def setup_async_backend(self, scenario_name: str):
        if self._async_backend:
            return self._async_backend
        _, config = get_scenario(scenario_name)
        self._async_backend = AsyncClickHouseBackend(connection_config=config)
        await self._async_backend.connect()
        await self._async_backend.introspect_and_adapt()
        return self._async_backend

    def cleanup(self):
        if self._backend:
            self._backend.disconnect()
            self._backend = None

    async def async_cleanup(self):
        if self._async_backend:
            await self._async_backend.disconnect()
            self._async_backend = None


# --- Fixtures ---


def get_scenario_names():
    return list(get_enabled_scenarios().keys())


@pytest.fixture(scope="function", params=get_scenario_names())
def clickhouse_backend(request):
    scenario_name = request.param
    provider = BackendFeatureProvider()
    backend = provider.setup_backend(scenario_name)
    yield backend
    provider.cleanup()


@pytest.fixture(scope="function")
def clickhouse_backend_single():
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
    backend = provider.setup_backend(scenario_name)
    yield backend
    provider.cleanup()


@pytest_asyncio.fixture(scope="function", params=get_scenario_names())
async def async_clickhouse_backend(request):
    scenario_name = request.param
    provider = BackendFeatureProvider()
    backend = await provider.setup_async_backend(scenario_name)
    yield backend
    await provider.async_cleanup()


@pytest_asyncio.fixture(scope="function")
async def async_clickhouse_backend_single():
    """Non-parameterized async fixture using the first available scenario.

    Use this for tests whose results do not vary across database versions.
    See clickhouse_backend_single for rationale.
    """
    scenario_names = get_scenario_names()
    if not scenario_names:
        pytest.skip("No ClickHouse scenarios configured")
    scenario_name = scenario_names[0]
    provider = BackendFeatureProvider()
    backend = await provider.setup_async_backend(scenario_name)
    yield backend
    await provider.async_cleanup()


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
    Dedicated async control backend that connects to the same scenario as async_clickhouse_backend.

    This fixture provides an independent async backend instance for operations that
    need to control or interfere with the main test backend, such as:
    - KILL CONNECTION statements
    - Setting global variables
    - Monitoring other connections

    Automatically follows the same scenario parametrization as async_clickhouse_backend.
    """
    backend = AsyncClickHouseBackend(connection_config=async_clickhouse_backend.config)
    await backend.connect()
    await backend.introspect_and_adapt()
    yield backend
    await backend.disconnect()


@pytest_asyncio.fixture(scope="function")
async def async_clickhouse_control_backend_single(async_clickhouse_backend_single):
    """
    Non-parameterized async control backend following async_clickhouse_backend_single.

    See clickhouse_control_backend_single for the rationale: it must stay on the same
    scenario as the pinned single backend.
    """
    backend = AsyncClickHouseBackend(connection_config=async_clickhouse_backend_single.config)
    await backend.connect()
    await backend.introspect_and_adapt()
    yield backend
    await backend.disconnect()


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
    """Fixture providing ClickHouseDialect instance for testing transaction expressions."""
    from rhosocial.activerecord.backend.impl.clickhouse.dialect import ClickHouseDialect

    dialect = ClickHouseDialect()
    dialect.version = (8, 0, 0)
    return dialect

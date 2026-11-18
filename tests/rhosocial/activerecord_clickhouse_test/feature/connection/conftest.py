# tests/rhosocial/activerecord_clickhouse_test/feature/connection/conftest.py
"""Pytest configuration for the connection pool tests.

The directory owns its logical database the same way every migrated directory
does: ``database_config`` declares the scenario and the directory's database
(name after its path) and every pool fixture builds its backends from that
configuration, so a directory's tests stay on one worker per scenario.

The concurrency tables are created and dropped by ``clickhouse_pool_with_tables``
from ``pool_definitions``, so there is no ``prepare`` / ``teardown`` group here.

ClickHouse is synchronous-only (clickhouse-connect has no async path), so there
are no async pool fixtures here: the async tests in this directory are skipped
by the root conftest before any fixture is set up.
"""
from rhosocial.activerecord.testsuite.pytest_plugin import Declaration

from pathlib import Path
from typing import Generator

import pytest

from rhosocial.activerecord.connection.pool import BackendPool, PoolConfig

from pool_definitions import ConcurrentTestPostsDefinition, ConcurrentTestUsersDefinition


def _database_name() -> str:
    """Database name from this directory's namespace (below ``feature``)."""
    parts = Path(__file__).parent.parts
    start = parts.index("feature") + 1
    return "test_" + "_".join(parts[start:])


def _backend_factory(scenario, config):
    """Return a factory producing sync backends on this scenario."""

    def factory():
        return scenario.backend_class(connection_config=config)

    return factory



# This directory owns a database shared by all its tests within a scenario;
# pin them to one worker so setup/teardown never races on the same database.
DECLARATION = Declaration(
    uses_database=True,
    parallel=True,
    purpose="Directory-owned database shared by this test group.",
)

@pytest.fixture(scope="function")
def clickhouse_pool(database_config) -> Generator[BackendPool, None, None]:
    """Create a BackendPool with ClickHouse backends for testing."""
    scenario, config, _name = database_config
    pool_config = PoolConfig(
        min_size=1,
        max_size=5,
        timeout=30.0,
        validate_on_borrow=True,
        validation_query="SELECT 1",
        backend_factory=_backend_factory(scenario, config),
    )

    pool = BackendPool.create(pool_config)
    yield pool
    pool.close(timeout=5.0, force=True)


@pytest.fixture(scope="function")
def clickhouse_pool_large(database_config) -> Generator[BackendPool, None, None]:
    """Create a larger BackendPool for stress testing."""
    scenario, config, _name = database_config
    pool_config = PoolConfig(
        min_size=1,
        max_size=5,
        timeout=60.0,
        validate_on_borrow=False,  # Faster for stress tests
        backend_factory=_backend_factory(scenario, config),
    )

    pool = BackendPool.create(pool_config)
    yield pool
    pool.close(timeout=5.0, force=True)


@pytest.fixture(scope="function")
def clickhouse_pool_with_tables(clickhouse_pool: BackendPool) -> Generator[BackendPool, None, None]:
    """Create a pool with test tables initialized."""
    definitions = (
        ConcurrentTestUsersDefinition,
        ConcurrentTestPostsDefinition,
    )
    with clickhouse_pool.connection() as backend:
        fixtures = [definition(backend.dialect) for definition in definitions]
        for fixture in fixtures:
            backend.execute(*fixture.drop_table.to_sql())
            backend.execute(*fixture.create_table.to_sql())

    yield clickhouse_pool

    with clickhouse_pool.connection() as backend:
        for fixture in reversed(fixtures):
            backend.execute(*fixture.drop_table.to_sql())


# --- directory contract: this directory's identity for xdist grouping ---
@pytest.fixture(scope="session")
def database_config(backend_scenario):
    """The scenario, its connection configuration, and the directory name.

    The pool fixtures own this database: the conftest creates it here, once per
    scenario, and the table fixture drops and recreates its tables for every
    test.  The fixture declares which directory and scenario the tests belong
    to, which is what keeps a directory's tests on one worker per scenario.
    """
    name = _database_name()
    backend_scenario.reset_database(name)
    return backend_scenario, backend_scenario.make_config(name), name

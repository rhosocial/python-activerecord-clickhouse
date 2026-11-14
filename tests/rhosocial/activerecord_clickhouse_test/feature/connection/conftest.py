# tests/rhosocial/activerecord_clickhouse_test/feature/connection/conftest.py
"""Pytest configuration for the connection pool tests.

The directory owns its logical database the same way every migrated directory
does: it declares the lifecycle here and takes the scenario and configuration
from the testsuite ``environment``, so running against several scenarios gets
one pool per scenario instead of a first-scenario guess.  The concurrency
tables are created and dropped by the table fixtures themselves, so
``prepare`` and ``teardown`` have no group to manage.

ClickHouse is synchronous-only (clickhouse-connect has no async path), so there
are no async pool fixtures here: the async tests in this directory are skipped
by the root conftest before any fixture is set up.
"""

from typing import Generator

import pytest

from rhosocial.activerecord.connection.pool import BackendPool, PoolConfig


def ensure_database(environment):
    """Create the directory's database, or clear it when it already exists."""
    environment.reset_database()


def prepare(environment):
    """No group tables: each table fixture creates what it needs."""


def teardown(environment):
    """No group tables: each table fixture drops what it created."""


def _backend_factory(environment):
    """Return a factory producing sync backends for this environment."""
    config = environment.make_config()

    def factory():
        return environment.scenario.backend_class(connection_config=config)

    return factory


@pytest.fixture(scope="function")
def clickhouse_pool(environment) -> Generator[BackendPool, None, None]:
    """Create a BackendPool with ClickHouse backends for testing."""
    pool_config = PoolConfig(
        min_size=1,
        max_size=5,
        timeout=30.0,
        validate_on_borrow=True,
        validation_query="SELECT 1",
        backend_factory=_backend_factory(environment),
    )

    pool = BackendPool.create(pool_config)
    yield pool
    pool.close(timeout=5.0, force=True)


@pytest.fixture(scope="function")
def clickhouse_pool_large(environment) -> Generator[BackendPool, None, None]:
    """Create a larger BackendPool for stress testing."""
    pool_config = PoolConfig(
        min_size=1,
        max_size=5,
        timeout=60.0,
        validate_on_borrow=False,  # Faster for stress tests
        backend_factory=_backend_factory(environment),
    )

    pool = BackendPool.create(pool_config)
    yield pool
    pool.close(timeout=5.0, force=True)


# --- Table Setup Fixtures ---


@pytest.fixture(scope="function")
def clickhouse_pool_with_tables(clickhouse_pool: BackendPool) -> Generator[BackendPool, None, None]:
    """Create a pool with test tables initialized."""
    with clickhouse_pool.connection() as backend:
        backend.execute("DROP TABLE IF EXISTS concurrent_test_users")
        backend.execute("DROP TABLE IF EXISTS concurrent_test_posts")
        backend.execute("""
            CREATE TABLE concurrent_test_users (
                id Int64,
                thread_id Nullable(Int32),
                name String,
                created_at DateTime DEFAULT now()
            ) ENGINE = MergeTree ORDER BY id SETTINGS enable_block_number_column = 1, enable_block_offset_column = 1
        """)
        backend.execute("""
            CREATE TABLE concurrent_test_posts (
                id Int64,
                thread_id Nullable(Int32),
                user_id Int64,
                title String,
                content String
            ) ENGINE = MergeTree ORDER BY id SETTINGS enable_block_number_column = 1, enable_block_offset_column = 1
        """)

    yield clickhouse_pool

    with clickhouse_pool.connection() as backend:
        backend.execute("DROP TABLE IF EXISTS concurrent_test_posts")
        backend.execute("DROP TABLE IF EXISTS concurrent_test_users")

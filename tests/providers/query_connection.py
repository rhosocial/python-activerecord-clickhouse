# tests/providers/query_connection.py
"""
Concrete implementation of IQueryConnectionProvider for ClickHouse backend.

This provider sets up connection pools and models for testing
query classes context awareness (ActiveQuery, CTEQuery, SetOperationQuery).
"""

from typing import Type, Tuple, Optional, List

from rhosocial.activerecord.model import ActiveRecord, AsyncActiveRecord
from rhosocial.activerecord.backend.impl.clickhouse import ClickHouseBackend
from rhosocial.activerecord.connection.pool import BackendPool, AsyncBackendPool, PoolConfig
from rhosocial.activerecord.backend.options import ExecutionOptions
from rhosocial.activerecord.backend.schema import StatementType

from rhosocial.activerecord.testsuite.feature.query.connection.interfaces import IQueryConnectionProvider
from .scenarios import get_scenario, get_enabled_scenarios


class SyncQueryTestUser(ActiveRecord):
    """Sync test user model for query connection pool tests."""

    __table_name__ = "test_users"
    id: Optional[int] = None
    name: str
    email: str


class AsyncQueryTestUser(AsyncActiveRecord):
    """Async test user model for query connection pool tests."""

    __table_name__ = "test_users"
    id: Optional[int] = None
    name: str
    email: str


class QueryConnectionProvider(IQueryConnectionProvider):
    """
    ClickHouse backend implementation for query connection pool context tests.
    """

    def __init__(self):
        self._active_backends: List = []
        self._active_async_backends: List = []

    def get_test_scenarios(self) -> list:
        """Returns available test scenarios."""
        return list(get_enabled_scenarios().keys())

    def _create_test_table(self, backend):
        """Create the test_users table."""
        try:
            backend.execute("DROP TABLE IF EXISTS test_users", options=ExecutionOptions(stmt_type=StatementType.DDL))
        except Exception:
            pass

        backend.execute(
            """
            CREATE TABLE test_users (
                id INT AUTO_INCREMENT PRIMARY KEY,
                name VARCHAR(255) NOT NULL,
                email VARCHAR(255) NOT NULL
            )
        """,
            options=ExecutionOptions(stmt_type=StatementType.DDL),
        )

    async def _create_test_table_async(self, backend):
        """Create the test_users table asynchronously."""
        try:
            await backend.execute(
                "DROP TABLE IF EXISTS test_users", options=ExecutionOptions(stmt_type=StatementType.DDL)
            )
        except Exception:
            pass

        await backend.execute(
            """
            CREATE TABLE test_users (
                id INT AUTO_INCREMENT PRIMARY KEY,
                name VARCHAR(255) NOT NULL,
                email VARCHAR(255) NOT NULL
            )
        """,
            options=ExecutionOptions(stmt_type=StatementType.DDL),
        )

    def setup_sync_pool_and_model(self, scenario_name: str) -> Tuple[BackendPool, Type[ActiveRecord]]:
        """Setup sync connection pool and model for query context tests."""
        _, config = get_scenario(scenario_name)

        # Create connection pool
        pool_config = PoolConfig(min_size=1, max_size=5, backend_factory=lambda: ClickHouseBackend(connection_config=config))
        pool = BackendPool.create(pool_config)

        # Create table
        with pool.connection() as backend:
            self._create_test_table(backend)
            self._active_backends.append(backend)

        # Configure model to use a separate backend (not pool backend)
        # This tests that model.backend() returns pool context backend
        SyncQueryTestUser.configure(config, ClickHouseBackend)
        self._active_backends.append(SyncQueryTestUser.__backend__)

        return pool, SyncQueryTestUser

    async def setup_async_pool_and_model(self, scenario_name: str) -> Tuple[AsyncBackendPool, Type[AsyncActiveRecord]]:
        """Setup async connection pool and model for query context tests."""
        from rhosocial.activerecord.backend.impl.clickhouse import AsyncClickHouseBackend

        _, config = get_scenario(scenario_name)

        # Create connection pool
        pool_config = PoolConfig(
            min_size=1, max_size=5, backend_factory=lambda: AsyncClickHouseBackend(connection_config=config)
        )

        # Create pool
        pool = await AsyncBackendPool.create(pool_config)

        # Create table
        async with pool.connection() as backend:
            await self._create_test_table_async(backend)
            self._active_async_backends.append(backend)

        # Configure model
        await AsyncQueryTestUser.configure(config, AsyncClickHouseBackend)
        self._active_async_backends.append(AsyncQueryTestUser.__backend__)

        return pool, AsyncQueryTestUser

    def cleanup_sync(self, scenario_name: str, pool: BackendPool):
        """Cleanup after sync tests."""
        pool.close(timeout=1.0)

        # Disconnect backends
        for backend in self._active_backends:
            try:
                backend.disconnect()
            except Exception:
                pass
        self._active_backends.clear()

    async def cleanup_async(self, scenario_name: str, pool: AsyncBackendPool):
        """Cleanup after async tests."""
        await pool.close(timeout=1.0)

        # Disconnect backends
        for backend in self._active_async_backends:
            try:
                await backend.disconnect()
            except Exception:
                pass
        self._active_async_backends.clear()

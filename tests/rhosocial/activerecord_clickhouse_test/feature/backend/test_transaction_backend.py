# tests/rhosocial/activerecord_clickhouse_test/feature/backend/test_transaction_backend.py
"""
ClickHouse backend transaction tests using real database connection.

This module tests transaction handling using ClickHouse backend with real database.
Each test has sync and async versions for complete coverage.
"""

import pytest
import pytest_asyncio
from decimal import Decimal


class TestClickHouseTransactionBackend:
    """Synchronous transaction tests for ClickHouse backend."""

    @pytest.fixture
    def test_table(self, clickhouse_backend):
        """Create a test table."""
        clickhouse_backend.execute("DROP TABLE IF EXISTS test_transaction_table")
        clickhouse_backend.execute("""
            CREATE TABLE test_transaction_table (
                id INT AUTO_INCREMENT PRIMARY KEY,
                name VARCHAR(255),
                amount DECIMAL(10, 2)
            )
        """)
        yield "test_transaction_table"
        clickhouse_backend.execute("DROP TABLE IF EXISTS test_transaction_table")

    def test_transaction_context_manager(self, clickhouse_backend, test_table):
        """Test transaction using context manager."""
        with clickhouse_backend.transaction():
            clickhouse_backend.execute(
                "INSERT INTO test_transaction_table (name, amount) VALUES (%s, %s)", ("TxTest1", Decimal("100.00"))
            )

        rows = clickhouse_backend.fetch_all("SELECT name FROM test_transaction_table")
        assert len(rows) == 1
        assert rows[0]["name"] == "TxTest1"

    def test_transaction_rollback(self, clickhouse_backend, test_table):
        """Test transaction rollback."""
        try:
            with clickhouse_backend.transaction():
                clickhouse_backend.execute(
                    "INSERT INTO test_transaction_table (name, amount) VALUES (%s, %s)",
                    ("TxRollback", Decimal("200.00")),
                )
                raise Exception("Force rollback")
        except Exception:
            pass

        rows = clickhouse_backend.fetch_all("SELECT name FROM test_transaction_table")
        assert len(rows) == 0


class TestAsyncClickHouseTransactionBackend:
    """Asynchronous transaction tests for ClickHouse backend."""

    @pytest_asyncio.fixture
    async def async_test_table(self, async_clickhouse_backend):
        """Create a test table."""
        await async_clickhouse_backend.execute("DROP TABLE IF EXISTS test_transaction_table")
        await async_clickhouse_backend.execute("""
            CREATE TABLE test_transaction_table (
                id INT AUTO_INCREMENT PRIMARY KEY,
                name VARCHAR(255),
                amount DECIMAL(10, 2)
            )
        """)
        yield "test_transaction_table"
        await async_clickhouse_backend.execute("DROP TABLE IF EXISTS test_transaction_table")

    async def test_async_transaction_context_manager(self, async_clickhouse_backend, async_test_table):
        """Test transaction using context manager (async)."""
        async with async_clickhouse_backend.transaction():
            await async_clickhouse_backend.execute(
                "INSERT INTO test_transaction_table (name, amount) VALUES (%s, %s)", ("TxTest1", Decimal("100.00"))
            )

        rows = await async_clickhouse_backend.fetch_all("SELECT name FROM test_transaction_table")
        assert len(rows) == 1
        assert rows[0]["name"] == "TxTest1"

    async def test_async_transaction_rollback(self, async_clickhouse_backend, async_test_table):
        """Test transaction rollback (async)."""
        try:
            async with async_clickhouse_backend.transaction():
                await async_clickhouse_backend.execute(
                    "INSERT INTO test_transaction_table (name, amount) VALUES (%s, %s)",
                    ("TxRollback", Decimal("200.00")),
                )
                raise Exception("Force rollback")
        except Exception:
            pass

        rows = await async_clickhouse_backend.fetch_all("SELECT name FROM test_transaction_table")
        assert len(rows) == 0

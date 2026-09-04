# tests/rhosocial/activerecord_clickhouse_test/feature/backend/dml/test_crud_backend.py
"""
ClickHouse backend CRUD tests using real database connection.

This module tests basic CRUD operations using ClickHouse backend with real database.
"""

import pytest
from decimal import Decimal


class TestClickHouseCRUDBackend:
    """Synchronous CRUD tests for ClickHouse backend."""

    @pytest.fixture
    def test_table(self, clickhouse_backend):
        """Create a test table using ClickHouse native types."""
        clickhouse_backend.execute("DROP TABLE IF EXISTS test_crud_table")
        clickhouse_backend.execute("""
            CREATE TABLE test_crud_table (
                id UInt32,
                name String,
                age UInt8,
                balance Decimal(10, 2)
            ) ENGINE = MergeTree()
            ORDER BY id
        """)
        yield "test_crud_table"
        clickhouse_backend.execute("DROP TABLE IF EXISTS test_crud_table")

    def test_insert_and_fetch(self, clickhouse_backend, test_table):
        """Test inserting data and fetching it back."""
        result = clickhouse_backend.execute(
            "INSERT INTO test_crud_table (id, name, age, balance) VALUES (%s, %s, %s, %s)",
            (1, "Alice", 25, Decimal("100.50")),
        )

        row = clickhouse_backend.fetch_one("SELECT * FROM test_crud_table WHERE name = %s", ("Alice",))
        assert row is not None
        assert row["name"] == "Alice"
        assert row["age"] == 25
        assert row["balance"] == Decimal("100.50")

    def test_fetch_all(self, clickhouse_backend, test_table):
        """Test fetching multiple rows."""
        for i in range(3):
            clickhouse_backend.execute(
                "INSERT INTO test_crud_table (id, name, age, balance) VALUES (%s, %s, %s, %s)",
                (i, f"User{i}", 20 + i, Decimal(f"{100 + i * 50}")),
            )

        rows = clickhouse_backend.fetch_all("SELECT name FROM test_crud_table ORDER BY name")
        assert len(rows) == 3
        assert rows[0]["name"] == "User0"
        assert rows[1]["name"] == "User1"
        assert rows[2]["name"] == "User2"

    def test_fetch_none(self, clickhouse_backend, test_table):
        """Test fetching when no results exist."""
        row = clickhouse_backend.fetch_one("SELECT * FROM test_crud_table WHERE name = %s", ("NonExistent",))
        assert row is None

    def test_transaction_is_noop(self, clickhouse_backend, test_table):
        """The transaction() context manager is a no-op (ClickHouse has no ACID).

        It must not raise, because generic operations (e.g. bulk_create) run
        inside ``with backend.transaction():`` blocks.
        """
        with clickhouse_backend.transaction():
            pass  # no error; statements simply auto-commit as usual
# tests/rhosocial/activerecord_clickhouse_test/feature/dml/test_insert_ignore.py
"""
ClickHouse INSERT IGNORE tests.

Tests for the ClickHouse-specific INSERT IGNORE functionality which silently
ignores rows that would cause duplicate key errors.

Official Documentation:
- INSERT: https://dev.clickhouse.com/doc/refman/8.0/en/insert.html
"""

import pytest
import pytest_asyncio

from rhosocial.activerecord.backend.expression.statements import InsertExpression, ValuesSource
from rhosocial.activerecord.backend.expression import core


class TestClickHouseInsertIgnore:
    """Synchronous INSERT IGNORE tests for ClickHouse backend."""

    @pytest.fixture
    def test_table(self, clickhouse_backend):
        """Create a test table with unique constraint."""
        clickhouse_backend.execute("DROP TABLE IF EXISTS test_insert_ignore")
        clickhouse_backend.execute("""
            CREATE TABLE test_insert_ignore (
                id INT AUTO_INCREMENT PRIMARY KEY,
                email VARCHAR(255) UNIQUE,
                name VARCHAR(255)
            ) ENGINE=InnoDB
        """)
        yield "test_insert_ignore"
        clickhouse_backend.execute("DROP TABLE IF EXISTS test_insert_ignore")

    def test_supports_insert_ignore(self, clickhouse_backend):
        """Test that ClickHouse dialect supports INSERT IGNORE."""
        assert clickhouse_backend.dialect.supports_insert_ignore() is True

    def test_insert_ignore_single_row_no_conflict(self, clickhouse_backend, test_table):
        """Test INSERT IGNORE with no conflict - should insert normally."""
        dialect = clickhouse_backend.dialect

        expr = InsertExpression(
            dialect=dialect,
            into=test_table,
            source=ValuesSource(
                dialect, [[core.Literal(dialect, "alice@example.com"), core.Literal(dialect, "Alice")]]
            ),
            columns=["email", "name"],
            dialect_options={"ignore": True},
        )

        sql, params = expr.to_sql()
        assert "INSERT IGNORE INTO" in sql
        assert "alice@example.com" in str(params) or "%s" in sql

        result = clickhouse_backend.execute(sql, params)
        assert result.affected_rows == 1

        # Verify data was inserted
        row = clickhouse_backend.fetch_one("SELECT * FROM test_insert_ignore WHERE email = %s", ("alice@example.com",))
        assert row is not None
        assert row["name"] == "Alice"

    def test_insert_ignore_with_conflict(self, clickhouse_backend, test_table):
        """Test INSERT IGNORE with unique key conflict - should silently ignore."""
        dialect = clickhouse_backend.dialect

        # Insert first row
        clickhouse_backend.execute(
            "INSERT INTO test_insert_ignore (email, name) VALUES (%s, %s)", ("bob@example.com", "Bob")
        )

        # Try to insert duplicate with IGNORE
        expr = InsertExpression(
            dialect=dialect,
            into=test_table,
            source=ValuesSource(dialect, [[core.Literal(dialect, "bob@example.com"), core.Literal(dialect, "Bob 2")]]),
            columns=["email", "name"],
            dialect_options={"ignore": True},
        )

        sql, params = expr.to_sql()
        result = clickhouse_backend.execute(sql, params)

        # Should succeed without error (affected_rows may be 0 or 1 depending on ClickHouse version)
        # ClickHouse returns 0 affected rows when row is ignored
        assert result.affected_rows == 0

        # Verify original data unchanged
        row = clickhouse_backend.fetch_one("SELECT * FROM test_insert_ignore WHERE email = %s", ("bob@example.com",))
        assert row is not None
        assert row["name"] == "Bob"  # Original name, not "Bob 2"

    def test_insert_ignore_multiple_rows_partial_conflict(self, clickhouse_backend, test_table):
        """Test INSERT IGNORE with multiple rows where some conflict."""
        dialect = clickhouse_backend.dialect

        # Insert first row
        clickhouse_backend.execute(
            "INSERT INTO test_insert_ignore (email, name) VALUES (%s, %s)", ("existing@example.com", "Existing User")
        )

        # Insert multiple rows, one conflicts
        expr = InsertExpression(
            dialect=dialect,
            into=test_table,
            source=ValuesSource(
                dialect,
                [
                    [core.Literal(dialect, "new1@example.com"), core.Literal(dialect, "New 1")],
                    [core.Literal(dialect, "existing@example.com"), core.Literal(dialect, "Duplicate")],
                    [core.Literal(dialect, "new2@example.com"), core.Literal(dialect, "New 2")],
                ],
            ),
            columns=["email", "name"],
            dialect_options={"ignore": True},
        )

        sql, params = expr.to_sql()
        result = clickhouse_backend.execute(sql, params)

        # Should insert 2 rows, ignore 1
        assert result.affected_rows == 2

        # Verify all rows
        rows = clickhouse_backend.fetch_all("SELECT * FROM test_insert_ignore ORDER BY email")
        assert len(rows) == 3  # existing + 2 new
        emails = [r["email"] for r in rows]
        assert "existing@example.com" in emails
        assert "new1@example.com" in emails
        assert "new2@example.com" in emails

    def test_insert_ignore_without_option(self, clickhouse_backend, test_table):
        """Test regular INSERT without IGNORE - should fail on conflict."""
        dialect = clickhouse_backend.dialect

        # Insert first row
        clickhouse_backend.execute(
            "INSERT INTO test_insert_ignore (email, name) VALUES (%s, %s)", ("test@example.com", "Test")
        )

        # Regular insert without IGNORE should fail
        expr = InsertExpression(
            dialect=dialect,
            into=test_table,
            source=ValuesSource(
                dialect, [[core.Literal(dialect, "test@example.com"), core.Literal(dialect, "Duplicate")]]
            ),
            columns=["email", "name"],
        )

        sql, params = expr.to_sql()
        assert "INSERT INTO" in sql
        assert "IGNORE" not in sql

        # This should raise an error
        with pytest.raises(Exception):  # ClickHouse IntegrityError  # noqa: B017
            clickhouse_backend.execute(sql, params)


class TestClickHouseAsyncInsertIgnore:
    """Asynchronous INSERT IGNORE tests for ClickHouse backend."""

    @pytest_asyncio.fixture
    async def test_table(self, async_clickhouse_backend):
        """Create a test table with unique constraint."""
        await async_clickhouse_backend.execute("DROP TABLE IF EXISTS test_insert_ignore_async")
        await async_clickhouse_backend.execute("""
            CREATE TABLE test_insert_ignore_async (
                id INT AUTO_INCREMENT PRIMARY KEY,
                email VARCHAR(255) UNIQUE,
                name VARCHAR(255)
            ) ENGINE=InnoDB
        """)
        yield "test_insert_ignore_async"
        await async_clickhouse_backend.execute("DROP TABLE IF EXISTS test_insert_ignore_async")

    async def test_insert_ignore_async(self, async_clickhouse_backend, test_table):
        """Test async INSERT IGNORE with conflict."""
        dialect = async_clickhouse_backend.dialect

        # Insert first row
        await async_clickhouse_backend.execute(
            "INSERT INTO test_insert_ignore_async (email, name) VALUES (%s, %s)", ("async@example.com", "Async User")
        )

        # Try to insert duplicate with IGNORE
        expr = InsertExpression(
            dialect=dialect,
            into=test_table,
            source=ValuesSource(
                dialect, [[core.Literal(dialect, "async@example.com"), core.Literal(dialect, "Duplicate")]]
            ),
            columns=["email", "name"],
            dialect_options={"ignore": True},
        )

        sql, params = expr.to_sql()
        result = await async_clickhouse_backend.execute(sql, params)

        # Should succeed, 0 affected rows
        assert result.affected_rows == 0

        # Verify original data unchanged
        row = await async_clickhouse_backend.fetch_one(
            "SELECT * FROM test_insert_ignore_async WHERE email = %s", ("async@example.com",)
        )
        assert row is not None
        assert row["name"] == "Async User"

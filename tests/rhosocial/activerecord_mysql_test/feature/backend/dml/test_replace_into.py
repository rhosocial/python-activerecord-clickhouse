# tests/rhosocial/activerecord_clickhouse_test/feature/dml/test_replace_into.py
"""
ClickHouse REPLACE INTO tests.

Tests for the ClickHouse-specific REPLACE INTO functionality which deletes
and re-inserts rows on duplicate key conflicts.

Official Documentation:
- REPLACE: https://dev.clickhouse.com/doc/refman/8.0/en/replace.html
"""

import pytest
import pytest_asyncio

from rhosocial.activerecord.backend.expression.statements import InsertExpression, ValuesSource
from rhosocial.activerecord.backend.expression import core


class TestClickHouseReplaceInto:
    """Synchronous REPLACE INTO tests for ClickHouse backend."""

    @pytest.fixture
    def test_table(self, clickhouse_backend):
        """Create a test table with unique constraint."""
        clickhouse_backend.execute("DROP TABLE IF EXISTS test_replace_into")
        clickhouse_backend.execute("""
            CREATE TABLE test_replace_into (
                id INT AUTO_INCREMENT PRIMARY KEY,
                email VARCHAR(255) UNIQUE,
                name VARCHAR(255)
            ) ENGINE=InnoDB
        """)
        yield "test_replace_into"
        clickhouse_backend.execute("DROP TABLE IF EXISTS test_replace_into")

    def test_supports_replace_into(self, clickhouse_backend):
        """Test that ClickHouse dialect supports REPLACE INTO."""
        assert clickhouse_backend.dialect.supports_replace_into() is True

    def test_replace_into_single_row_no_conflict(self, clickhouse_backend, test_table):
        """Test REPLACE INTO with no conflict - should insert normally."""
        dialect = clickhouse_backend.dialect

        expr = InsertExpression(
            dialect=dialect,
            into=test_table,
            source=ValuesSource(
                dialect, [[core.Literal(dialect, "alice@example.com"), core.Literal(dialect, "Alice")]]
            ),
            columns=["email", "name"],
            dialect_options={"replace": True},
        )

        sql, params = expr.to_sql()
        assert "REPLACE INTO" in sql
        assert "INSERT" not in sql

        result = clickhouse_backend.execute(sql, params)
        assert result.affected_rows == 1

        # Verify data was inserted
        row = clickhouse_backend.fetch_one("SELECT * FROM test_replace_into WHERE email = %s", ("alice@example.com",))
        assert row is not None
        assert row["name"] == "Alice"

    def test_replace_into_with_conflict(self, clickhouse_backend, test_table):
        """Test REPLACE INTO with unique key conflict - should delete and re-insert."""
        dialect = clickhouse_backend.dialect

        # Insert first row
        clickhouse_backend.execute("INSERT INTO test_replace_into (email, name) VALUES (%s, %s)", ("bob@example.com", "Bob"))

        # Get the original ID
        original_row = clickhouse_backend.fetch_one(
            "SELECT id FROM test_replace_into WHERE email = %s", ("bob@example.com",)
        )
        original_row["id"]

        # REPLACE with new data
        expr = InsertExpression(
            dialect=dialect,
            into=test_table,
            source=ValuesSource(dialect, [[core.Literal(dialect, "bob@example.com"), core.Literal(dialect, "Bob 2")]]),
            columns=["email", "name"],
            dialect_options={"replace": True},
        )

        sql, params = expr.to_sql()
        result = clickhouse_backend.execute(sql, params)

        # REPLACE returns 2 for delete+insert, or 1 if no conflict
        assert result.affected_rows in (1, 2)

        # Verify data was replaced
        row = clickhouse_backend.fetch_one("SELECT * FROM test_replace_into WHERE email = %s", ("bob@example.com",))
        assert row is not None
        assert row["name"] == "Bob 2"
        # Note: AUTO_INCREMENT may change on REPLACE
        # This is expected ClickHouse behavior

    def test_replace_into_multiple_rows(self, clickhouse_backend, test_table):
        """Test REPLACE INTO with multiple rows."""
        dialect = clickhouse_backend.dialect

        # Insert some initial data
        clickhouse_backend.execute(
            "INSERT INTO test_replace_into (email, name) VALUES (%s, %s)", ("existing@example.com", "Existing User")
        )

        # REPLACE multiple rows, one conflicts
        expr = InsertExpression(
            dialect=dialect,
            into=test_table,
            source=ValuesSource(
                dialect,
                [
                    [core.Literal(dialect, "new1@example.com"), core.Literal(dialect, "New 1")],
                    [core.Literal(dialect, "existing@example.com"), core.Literal(dialect, "Replaced")],
                    [core.Literal(dialect, "new2@example.com"), core.Literal(dialect, "New 2")],
                ],
            ),
            columns=["email", "name"],
            dialect_options={"replace": True},
        )

        sql, params = expr.to_sql()
        result = clickhouse_backend.execute(sql, params)

        # Should affect all rows (inserts + replacements)
        assert result.affected_rows >= 3

        # Verify all rows
        rows = clickhouse_backend.fetch_all("SELECT * FROM test_replace_into ORDER BY email")
        assert len(rows) == 3
        emails = [r["email"] for r in rows]
        assert "existing@example.com" in emails
        assert "new1@example.com" in emails
        assert "new2@example.com" in emails

        # Verify replaced name
        replaced_row = next(r for r in rows if r["email"] == "existing@example.com")
        assert replaced_row["name"] == "Replaced"

    def test_replace_into_with_on_conflict_raises_error(self, clickhouse_backend, test_table):
        """Test that REPLACE INTO with ON CONFLICT raises an error."""
        from rhosocial.activerecord.backend.expression.statements import OnConflictClause

        dialect = clickhouse_backend.dialect

        # This should raise ValueError
        with pytest.raises(ValueError, match="REPLACE INTO does not support ON CONFLICT"):
            expr = InsertExpression(
                dialect=dialect,
                into=test_table,
                source=ValuesSource(
                    dialect, [[core.Literal(dialect, "test@example.com"), core.Literal(dialect, "Test")]]
                ),
                columns=["email", "name"],
                dialect_options={"replace": True},
                on_conflict=OnConflictClause(dialect, ["email"], do_nothing=True),  # Invalid combination
            )
            expr.to_sql()

    def test_replace_and_ignore_mutually_exclusive(self, clickhouse_backend, test_table):
        """Test that replace and ignore options are mutually exclusive."""
        dialect = clickhouse_backend.dialect

        with pytest.raises(ValueError, match="Cannot use both 'replace' and 'ignore'"):
            expr = InsertExpression(
                dialect=dialect,
                into=test_table,
                source=ValuesSource(
                    dialect, [[core.Literal(dialect, "test@example.com"), core.Literal(dialect, "Test")]]
                ),
                columns=["email", "name"],
                dialect_options={"replace": True, "ignore": True},
            )
            expr.to_sql()


class TestClickHouseAsyncReplaceInto:
    """Asynchronous REPLACE INTO tests for ClickHouse backend."""

    @pytest_asyncio.fixture
    async def test_table(self, async_clickhouse_backend):
        """Create a test table with unique constraint."""
        await async_clickhouse_backend.execute("DROP TABLE IF EXISTS test_replace_into_async")
        await async_clickhouse_backend.execute("""
            CREATE TABLE test_replace_into_async (
                id INT AUTO_INCREMENT PRIMARY KEY,
                email VARCHAR(255) UNIQUE,
                name VARCHAR(255)
            ) ENGINE=InnoDB
        """)
        yield "test_replace_into_async"
        await async_clickhouse_backend.execute("DROP TABLE IF EXISTS test_replace_into_async")

    async def test_replace_into_async(self, async_clickhouse_backend, test_table):
        """Test async REPLACE INTO with conflict."""
        dialect = async_clickhouse_backend.dialect

        # Insert first row
        await async_clickhouse_backend.execute(
            "INSERT INTO test_replace_into_async (email, name) VALUES (%s, %s)", ("async@example.com", "Async User")
        )

        # REPLACE with new data
        expr = InsertExpression(
            dialect=dialect,
            into=test_table,
            source=ValuesSource(
                dialect, [[core.Literal(dialect, "async@example.com"), core.Literal(dialect, "Replaced Async")]]
            ),
            columns=["email", "name"],
            dialect_options={"replace": True},
        )

        sql, params = expr.to_sql()
        await async_clickhouse_backend.execute(sql, params)

        # Verify data was replaced
        row = await async_clickhouse_backend.fetch_one(
            "SELECT * FROM test_replace_into_async WHERE email = %s", ("async@example.com",)
        )
        assert row is not None
        assert row["name"] == "Replaced Async"

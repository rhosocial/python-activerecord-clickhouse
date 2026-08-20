# tests/rhosocial/activerecord_clickhouse_test/feature/dml/test_load_data.py
"""
ClickHouse LOAD DATA INFILE tests.

Tests for the ClickHouse-specific LOAD DATA INFILE functionality which provides
high-performance bulk data import from files.

Official Documentation:
- LOAD DATA: https://dev.clickhouse.com/doc/refman/8.0/en/load-data.html
"""

import pytest
import pytest_asyncio

from rhosocial.activerecord.backend.impl.clickhouse.expression import ClickHouseLoadDataExpression, LoadDataOptions


class TestClickHouseLoadData:
    """Synchronous LOAD DATA INFILE tests for ClickHouse backend."""

    @pytest.fixture
    def test_table(self, clickhouse_backend):
        """Create a test table for LOAD DATA."""
        clickhouse_backend.execute("DROP TABLE IF EXISTS test_load_data")
        clickhouse_backend.execute("""
            CREATE TABLE test_load_data (
                id INT AUTO_INCREMENT PRIMARY KEY,
                name VARCHAR(255),
                email VARCHAR(255),
                age INT
            ) ENGINE=InnoDB
        """)
        yield "test_load_data"
        clickhouse_backend.execute("DROP TABLE IF EXISTS test_load_data")

    def test_supports_load_data(self, clickhouse_backend):
        """Test that ClickHouse dialect supports LOAD DATA."""
        assert clickhouse_backend.dialect.supports_load_data() is True

    def test_load_data_expression_basic(self, clickhouse_backend):
        """Test basic ClickHouseLoadDataExpression generation."""
        expr = ClickHouseLoadDataExpression(dialect=clickhouse_backend.dialect, file_path="/tmp/test.csv", table="users")

        sql, params = expr.to_sql()
        assert "LOAD DATA" in sql
        assert "INFILE '/tmp/test.csv'" in sql
        assert "INTO TABLE `users`" in sql
        assert params == ()

    def test_load_data_expression_local(self, clickhouse_backend):
        """Test LOAD DATA LOCAL expression."""
        expr = ClickHouseLoadDataExpression(
            dialect=clickhouse_backend.dialect, file_path="/tmp/test.csv", table="users", options=LoadDataOptions(local=True)
        )

        sql, params = expr.to_sql()
        assert "LOAD DATA LOCAL INFILE" in sql

    def test_load_data_expression_fields_terminated(self, clickhouse_backend):
        """Test LOAD DATA with custom field terminator."""
        expr = ClickHouseLoadDataExpression(
            dialect=clickhouse_backend.dialect,
            file_path="/tmp/test.csv",
            table="users",
            options=LoadDataOptions(local=True, fields_terminated_by=","),
        )

        sql, params = expr.to_sql()
        assert "FIELDS TERMINATED BY ','" in sql

    def test_load_data_expression_ignore_lines(self, clickhouse_backend):
        """Test LOAD DATA with IGNORE n LINES."""
        expr = ClickHouseLoadDataExpression(
            dialect=clickhouse_backend.dialect,
            file_path="/tmp/test.csv",
            table="users",
            options=LoadDataOptions(local=True, ignore_lines=1),
        )

        sql, params = expr.to_sql()
        assert "IGNORE 1 LINES" in sql

    def test_load_data_expression_replace_mode(self, clickhouse_backend):
        """Test LOAD DATA with REPLACE mode."""
        expr = ClickHouseLoadDataExpression(
            dialect=clickhouse_backend.dialect,
            file_path="/tmp/test.csv",
            table="users",
            options=LoadDataOptions(local=True, replace=True),
        )

        sql, params = expr.to_sql()
        assert "REPLACE" in sql

    def test_load_data_expression_ignore_mode(self, clickhouse_backend):
        """Test LOAD DATA with IGNORE mode."""
        expr = ClickHouseLoadDataExpression(
            dialect=clickhouse_backend.dialect,
            file_path="/tmp/test.csv",
            table="users",
            options=LoadDataOptions(local=True, ignore=True),
        )

        sql, params = expr.to_sql()
        # IGNORE mode comes before INTO TABLE
        assert "IGNORE" in sql

    def test_load_data_replace_and_ignore_mutually_exclusive(self, clickhouse_backend):
        """Test that REPLACE and IGNORE are mutually exclusive."""
        expr = ClickHouseLoadDataExpression(
            dialect=clickhouse_backend.dialect,
            file_path="/tmp/test.csv",
            table="users",
            options=LoadDataOptions(local=True, replace=True, ignore=True),
        )

        with pytest.raises(ValueError, match="Cannot use both REPLACE and IGNORE"):
            expr.to_sql()

    def test_load_data_expression_with_columns(self, clickhouse_backend):
        """Test LOAD DATA with column list."""
        expr = ClickHouseLoadDataExpression(
            dialect=clickhouse_backend.dialect,
            file_path="/tmp/test.csv",
            table="users",
            options=LoadDataOptions(local=True, column_list=["name", "email", "age"]),
        )

        sql, params = expr.to_sql()
        assert "(`name`, `email`, `age`)" in sql

    def test_load_data_expression_with_lines_terminated(self, clickhouse_backend):
        """Test LOAD DATA with custom line terminator."""
        expr = ClickHouseLoadDataExpression(
            dialect=clickhouse_backend.dialect,
            file_path="/tmp/test.csv",
            table="users",
            options=LoadDataOptions(local=True, lines_terminated_by="\n"),
        )

        sql, params = expr.to_sql()
        assert "LINES TERMINATED BY" in sql

    def test_load_data_expression_character_set(self, clickhouse_backend):
        """Test LOAD DATA with character set."""
        expr = ClickHouseLoadDataExpression(
            dialect=clickhouse_backend.dialect,
            file_path="/tmp/test.csv",
            table="users",
            options=LoadDataOptions(local=True, character_set="utf8mb4"),
        )

        sql, params = expr.to_sql()
        assert "CHARACTER SET utf8mb4" in sql

    def test_load_data_expression_full_csv(self, clickhouse_backend):
        """Test full LOAD DATA expression for CSV import."""
        expr = ClickHouseLoadDataExpression(
            dialect=clickhouse_backend.dialect,
            file_path="/tmp/data.csv",
            table="users",
            options=LoadDataOptions(
                local=True,
                fields_terminated_by=",",
                fields_enclosed_by='"',
                lines_terminated_by="\n",
                ignore_lines=1,
                column_list=["name", "email", "age"],
            ),
        )

        sql, params = expr.to_sql()
        assert "LOAD DATA LOCAL INFILE '/tmp/data.csv'" in sql
        assert "INTO TABLE `users`" in sql
        assert "FIELDS TERMINATED BY ','" in sql
        assert "ENCLOSED BY" in sql and '"' in sql
        assert "LINES TERMINATED BY" in sql
        assert "IGNORE 1 LINES" in sql
        assert "(`name`, `email`, `age`)" in sql


class TestClickHouseAsyncLoadData:
    """Asynchronous LOAD DATA INFILE tests for ClickHouse backend."""

    @pytest_asyncio.fixture
    async def test_table(self, async_clickhouse_backend):
        """Create a test table for LOAD DATA."""
        await async_clickhouse_backend.execute("DROP TABLE IF EXISTS test_load_data_async")
        await async_clickhouse_backend.execute("""
            CREATE TABLE test_load_data_async (
                id INT AUTO_INCREMENT PRIMARY KEY,
                name VARCHAR(255),
                email VARCHAR(255),
                age INT
            ) ENGINE=InnoDB
        """)
        yield "test_load_data_async"
        await async_clickhouse_backend.execute("DROP TABLE IF EXISTS test_load_data_async")

    async def test_load_data_expression_async(self, async_clickhouse_backend, test_table):
        """Test async LOAD DATA expression generation."""
        expr = ClickHouseLoadDataExpression(dialect=async_clickhouse_backend.dialect, file_path="/tmp/test.csv", table=test_table)

        sql, params = expr.to_sql()
        assert "LOAD DATA" in sql
        assert "INTO TABLE" in sql

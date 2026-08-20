# tests/rhosocial/activerecord_clickhouse_test/feature/backend/test_dialect.py
"""
ClickHouse backend dialect tests using real database connection.

This module tests ClickHouse dialect formatting using real database.
Each test has sync and async versions for complete coverage.
"""

import pytest


class TestClickHouseDialectBackend:
    """Synchronous dialect tests for ClickHouse backend."""

    def test_format_identifier(self, clickhouse_backend):
        """Test identifier formatting."""
        dialect = clickhouse_backend.dialect

        result = dialect.format_identifier("test_table")
        assert result == "`test_table`"

        result = dialect.format_identifier("user_name")
        assert result == "`user_name`"

    def test_quote_parameter(self, clickhouse_backend):
        """Test parameter quoting for ClickHouse."""
        sql = "SELECT * FROM users WHERE name = %s"
        params = ("John",)

        result_sql, result_params = clickhouse_backend._prepare_sql_and_params(sql, params)

        assert "%s" in result_sql or "?" in result_sql


class TestAsyncClickHouseDialectBackend:
    """Asynchronous dialect tests for ClickHouse backend."""

    @pytest.mark.asyncio
    async def test_async_format_identifier(self, async_clickhouse_backend):
        """Test identifier formatting (async)."""
        dialect = async_clickhouse_backend.dialect

        result = dialect.format_identifier("test_table")
        assert result == "`test_table`"

        result = dialect.format_identifier("user_name")
        assert result == "`user_name`"

    @pytest.mark.asyncio
    async def test_async_quote_parameter(self, async_clickhouse_backend):
        """Test parameter quoting for ClickHouse (async)."""
        sql = "SELECT * FROM users WHERE name = %s"
        params = ("John",)

        result_sql, result_params = async_clickhouse_backend._prepare_sql_and_params(sql, params)

        assert "%s" in result_sql or "?" in result_sql

# tests/rhosocial/activerecord_clickhouse_test/feature/query/test_json_table.py
"""
ClickHouse JSON_TABLE tests.

Tests for the ClickHouse-specific JSON_TABLE functionality which converts
JSON data to relational format. Requires ClickHouse 8.0.4+.

Official Documentation:
- JSON_TABLE: https://dev.clickhouse.com/doc/refman/8.0/en/json-table-functions.html
"""

import pytest
import pytest_asyncio

from rhosocial.activerecord.backend.impl.clickhouse.expression import ClickHouseJSONTableExpression, JSONTableColumn, NestedPath


class TestClickHouseJSONTable:
    """Synchronous JSON_TABLE tests for ClickHouse backend."""

    @pytest.fixture
    def test_table(self, clickhouse_backend):
        """Create a test table with JSON column."""
        clickhouse_backend.execute("DROP TABLE IF EXISTS test_json_table")
        clickhouse_backend.execute("""
            CREATE TABLE test_json_table (
                id INT AUTO_INCREMENT PRIMARY KEY,
                data JSON
            ) ENGINE=InnoDB
        """)
        yield "test_json_table"
        clickhouse_backend.execute("DROP TABLE IF EXISTS test_json_table")

    def test_supports_json_table(self, clickhouse_backend):
        """Test that ClickHouse dialect supports JSON_TABLE version check."""
        # Result depends on ClickHouse version
        result = clickhouse_backend.dialect.supports_json_table()
        assert isinstance(result, bool)

    def test_json_table_basic_expression(self, clickhouse_backend):
        """Test basic JSON_TABLE expression generation."""
        json_doc = r"'[{" "name" ": " "Alice" ", " "age" ": 30}]'"
        expr = ClickHouseJSONTableExpression(
            dialect=clickhouse_backend.dialect,
            json_doc=json_doc,
            path="$[*]",
            columns=[
                JSONTableColumn(name="name", type="VARCHAR(255)", path="$.name"),
                JSONTableColumn(name="age", type="INT", path="$.age"),
            ],
            alias="jt",
        )

        sql, params = expr.to_sql()
        assert "JSON_TABLE" in sql
        assert "COLUMNS" in sql
        assert "`name`" in sql
        assert "VARCHAR(255)" in sql
        assert "PATH" in sql
        assert params == ()

    def test_json_table_for_ordinality(self, clickhouse_backend):
        """Test JSON_TABLE with FOR ORDINALITY column."""
        expr = ClickHouseJSONTableExpression(
            dialect=clickhouse_backend.dialect,
            json_doc="'[1, 2, 3]'",
            path="$[*]",
            columns=[
                JSONTableColumn(name="row_num", ordinality=True),
                JSONTableColumn(name="value", type="INT", path="$"),
            ],
            alias="jt",
        )

        sql, params = expr.to_sql()
        assert "FOR ORDINALITY" in sql
        assert "`row_num`" in sql

    def test_json_table_exists_path(self, clickhouse_backend):
        """Test JSON_TABLE with EXISTS PATH."""
        expr = ClickHouseJSONTableExpression(
            dialect=clickhouse_backend.dialect,
            json_doc=r"'{" "a" ": 1, " "b" ": 2}'",
            path="$",
            columns=[
                JSONTableColumn(name="has_a", type="BOOLEAN", path="$.a", exists=True),
                JSONTableColumn(name="has_c", type="BOOLEAN", path="$.c", exists=True),
            ],
            alias="jt",
        )

        sql, params = expr.to_sql()
        assert "EXISTS PATH" in sql

    def test_json_table_nested_path(self, clickhouse_backend):
        """Test JSON_TABLE with NESTED PATH."""
        expr = ClickHouseJSONTableExpression(
            dialect=clickhouse_backend.dialect,
            json_doc=r"'[{" "name" ": " "Alice" ", " "orders" ": [{" "id" ": 1}, {" "id" ": 2}]}]'",
            path="$[*]",
            columns=[
                JSONTableColumn(name="customer_name", type="VARCHAR(255)", path="$.name"),
            ],
            nested_paths=[
                NestedPath(
                    path="$.orders[*]",
                    columns=[
                        JSONTableColumn(name="order_id", type="INT", path="$.id"),
                    ],
                    alias="orders",
                )
            ],
            alias="jt",
        )

        sql, params = expr.to_sql()
        assert "NESTED PATH" in sql
        assert "`order_id`" in sql

    def test_json_table_with_alias(self, clickhouse_backend):
        """Test JSON_TABLE with table alias."""
        expr = ClickHouseJSONTableExpression(
            dialect=clickhouse_backend.dialect,
            json_doc="'[1, 2, 3]'",
            path="$[*]",
            columns=[
                JSONTableColumn(name="value", type="INT", path="$"),
            ],
            alias="my_table",
        )

        sql, params = expr.to_sql()
        # ClickHouse uses backticks for identifier quoting
        assert "`my_table`" in sql

    def test_json_table_error_handling_null(self, clickhouse_backend):
        """Test JSON_TABLE with NULL ON ERROR."""
        expr = ClickHouseJSONTableExpression(
            dialect=clickhouse_backend.dialect,
            json_doc="'[1, 2, 3]'",
            path="$[*]",
            columns=[
                JSONTableColumn(name="value", type="VARCHAR(255)", path="$.nonexistent", error_handling="NULL"),
            ],
            alias="jt",
        )

        sql, params = expr.to_sql()
        assert "NULL ON ERROR" in sql

    def test_json_table_multiple_columns(self, clickhouse_backend):
        """Test JSON_TABLE with multiple columns."""
        expr = ClickHouseJSONTableExpression(
            dialect=clickhouse_backend.dialect,
            json_doc=r"'[{" "id" ": 1, " "name" ": " "Alice" ", " "email" ": " "alice@example.com" "}]'",
            path="$[*]",
            columns=[
                JSONTableColumn(name="id", type="INT", path="$.id"),
                JSONTableColumn(name="name", type="VARCHAR(255)", path="$.name"),
                JSONTableColumn(name="email", type="VARCHAR(255)", path="$.email"),
            ],
            alias="jt",
        )

        sql, params = expr.to_sql()
        assert "`id`" in sql
        assert "`name`" in sql
        assert "`email`" in sql


class TestClickHouseAsyncJSONTable:
    """Asynchronous JSON_TABLE tests for ClickHouse backend."""

    @pytest_asyncio.fixture
    async def test_table(self, async_clickhouse_backend):
        """Create a test table with JSON column."""
        await async_clickhouse_backend.execute("DROP TABLE IF EXISTS test_json_table_async")
        await async_clickhouse_backend.execute("""
            CREATE TABLE test_json_table_async (
                id INT AUTO_INCREMENT PRIMARY KEY,
                data JSON
            ) ENGINE=InnoDB
        """)
        yield "test_json_table_async"
        await async_clickhouse_backend.execute("DROP TABLE IF EXISTS test_json_table_async")

    async def test_json_table_expression_async(self, async_clickhouse_backend):
        """Test async JSON_TABLE expression generation."""
        expr = ClickHouseJSONTableExpression(
            dialect=async_clickhouse_backend.dialect,
            json_doc="'[1, 2, 3]'",
            path="$[*]",
            columns=[
                JSONTableColumn(name="value", type="INT", path="$"),
            ],
            alias="jt",
        )

        sql, params = expr.to_sql()
        assert "JSON_TABLE" in sql
        assert "COLUMNS" in sql
        assert params == ()

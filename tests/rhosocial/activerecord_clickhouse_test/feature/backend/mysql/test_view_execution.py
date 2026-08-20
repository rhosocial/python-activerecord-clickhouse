# tests/rhosocial/activerecord_clickhouse_test/feature/backend/clickhouse/test_view_execution.py
"""
Tests for ClickHouse VIEW functionality with actual database execution.

These tests verify that generated SQL statements execute correctly
against an actual ClickHouse database.
"""

import pytest
from rhosocial.activerecord.backend.expression import (
    Column,
    Literal,
    TableExpression,
    QueryExpression,
    CreateViewExpression,
    DropViewExpression,
    CreateMaterializedViewExpression,
    DropMaterializedViewExpression,
    RefreshMaterializedViewExpression,
)
from rhosocial.activerecord.backend.expression.query_parts import WhereClause
from rhosocial.activerecord.backend.dialect.exceptions import UnsupportedFeatureError
from rhosocial.activerecord.backend.options import ExecutionOptions
from rhosocial.activerecord.backend.schema import StatementType


@pytest.fixture
def clickhouse_view_backend(clickhouse_backend):
    """Provides a ClickHouseBackend instance with test data for view tests."""
    backend = clickhouse_backend

    # Drop existing tables if they exist
    backend.execute("DROP VIEW IF EXISTS user_view", (), options=ExecutionOptions(stmt_type=StatementType.DDL))
    backend.execute("DROP VIEW IF EXISTS active_users", (), options=ExecutionOptions(stmt_type=StatementType.DDL))
    backend.execute("DROP TABLE IF EXISTS orders", (), options=ExecutionOptions(stmt_type=StatementType.DDL))
    backend.execute("DROP TABLE IF EXISTS users", (), options=ExecutionOptions(stmt_type=StatementType.DDL))

    # Create users table
    backend.execute(
        """
        CREATE TABLE users (
            id INT AUTO_INCREMENT PRIMARY KEY,
            name VARCHAR(100) NOT NULL,
            email VARCHAR(255),
            status VARCHAR(20) DEFAULT 'active'
        )
    """,
        (),
        options=ExecutionOptions(stmt_type=StatementType.DDL),
    )

    # Create orders table
    backend.execute(
        """
        CREATE TABLE orders (
            id INT AUTO_INCREMENT PRIMARY KEY,
            user_id INT,
            amount DECIMAL(10, 2),
            order_date DATE,
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    """,
        (),
        options=ExecutionOptions(stmt_type=StatementType.DDL),
    )

    # Insert test data
    backend.execute(
        "INSERT INTO users (name, email, status) VALUES (%s, %s, %s)",
        ("Alice", "alice@example.com", "active"),
        options=ExecutionOptions(stmt_type=StatementType.DML),
    )
    backend.execute(
        "INSERT INTO users (name, email, status) VALUES (%s, %s, %s)",
        ("Bob", "bob@example.com", "inactive"),
        options=ExecutionOptions(stmt_type=StatementType.DML),
    )
    backend.execute(
        "INSERT INTO users (name, email, status) VALUES (%s, %s, %s)",
        ("Charlie", "charlie@example.com", "active"),
        options=ExecutionOptions(stmt_type=StatementType.DML),
    )

    backend.execute(
        "INSERT INTO orders (user_id, amount, order_date) VALUES (%s, %s, %s)",
        (1, 100.0, "2024-01-01"),
        options=ExecutionOptions(stmt_type=StatementType.DML),
    )
    backend.execute(
        "INSERT INTO orders (user_id, amount, order_date) VALUES (%s, %s, %s)",
        (1, 200.0, "2024-01-15"),
        options=ExecutionOptions(stmt_type=StatementType.DML),
    )
    backend.execute(
        "INSERT INTO orders (user_id, amount, order_date) VALUES (%s, %s, %s)",
        (2, 50.0, "2024-01-10"),
        options=ExecutionOptions(stmt_type=StatementType.DML),
    )

    yield backend

    # Cleanup
    backend.execute("DROP VIEW IF EXISTS user_view", (), options=ExecutionOptions(stmt_type=StatementType.DDL))
    backend.execute("DROP VIEW IF EXISTS active_users", (), options=ExecutionOptions(stmt_type=StatementType.DDL))
    backend.execute("DROP TABLE IF EXISTS orders", (), options=ExecutionOptions(stmt_type=StatementType.DDL))
    backend.execute("DROP TABLE IF EXISTS users", (), options=ExecutionOptions(stmt_type=StatementType.DDL))


class TestClickHouseViewExecution:
    """Tests for CREATE VIEW and DROP VIEW with actual execution."""

    def test_create_view_basic(self, clickhouse_view_backend):
        """Test basic CREATE VIEW executes successfully."""
        dialect = clickhouse_view_backend.dialect

        query = QueryExpression(
            dialect,
            select=[Column(dialect, "id"), Column(dialect, "name"), Column(dialect, "email")],
            from_=TableExpression(dialect, "users"),
        )

        create_view = CreateViewExpression(dialect, view_name="user_view", query=query)

        sql, params = create_view.to_sql()

        result = clickhouse_view_backend.execute(sql, params, options=ExecutionOptions(stmt_type=StatementType.DDL))

        result = clickhouse_view_backend.execute(
            "SELECT * FROM user_view",
            (),
            options=ExecutionOptions(stmt_type=StatementType.SELECT, process_result_set=True),
        )

        assert result.data is not None
        assert len(result.data) == 3
        assert result.data[0]["name"] == "Alice"

    def test_create_view_with_where(self, clickhouse_view_backend):
        """Test CREATE VIEW with WHERE clause."""
        dialect = clickhouse_view_backend.dialect

        query = QueryExpression(
            dialect,
            select=[Column(dialect, "id"), Column(dialect, "name")],
            from_=TableExpression(dialect, "users"),
            where=WhereClause(dialect, condition=Column(dialect, "status") == Literal(dialect, "active")),
        )

        create_view = CreateViewExpression(dialect, view_name="active_users", query=query)

        sql, params = create_view.to_sql()

        result = clickhouse_view_backend.execute(sql, params, options=ExecutionOptions(stmt_type=StatementType.DDL))

        result = clickhouse_view_backend.execute(
            "SELECT * FROM active_users",
            (),
            options=ExecutionOptions(stmt_type=StatementType.SELECT, process_result_set=True),
        )

        assert result.data is not None
        assert len(result.data) == 2

    def test_create_or_replace_view(self, clickhouse_view_backend):
        """Test CREATE OR REPLACE VIEW."""
        dialect = clickhouse_view_backend.dialect

        query = QueryExpression(dialect, select=[Column(dialect, "id")], from_=TableExpression(dialect, "users"))

        create_view = CreateViewExpression(dialect, view_name="user_view", query=query)

        sql, params = create_view.to_sql()
        clickhouse_view_backend.execute(sql, params, options=ExecutionOptions(stmt_type=StatementType.DDL))

        # Create again with OR REPLACE
        query2 = QueryExpression(
            dialect, select=[Column(dialect, "id"), Column(dialect, "name")], from_=TableExpression(dialect, "users")
        )

        create_view2 = CreateViewExpression(dialect, view_name="user_view", query=query2, replace=True)

        sql, params = create_view2.to_sql()
        result = clickhouse_view_backend.execute(sql, params, options=ExecutionOptions(stmt_type=StatementType.DDL))
        assert result is not None

    def test_drop_view(self, clickhouse_view_backend):
        """Test DROP VIEW."""
        dialect = clickhouse_view_backend.dialect

        query = QueryExpression(dialect, select=[Column(dialect, "id")], from_=TableExpression(dialect, "users"))

        create_view = CreateViewExpression(dialect, view_name="user_view", query=query)

        sql, params = create_view.to_sql()
        clickhouse_view_backend.execute(sql, params, options=ExecutionOptions(stmt_type=StatementType.DDL))

        drop_view = DropViewExpression(dialect, view_name="user_view")

        sql, params = drop_view.to_sql()
        result = clickhouse_view_backend.execute(sql, params, options=ExecutionOptions(stmt_type=StatementType.DDL))
        assert result is not None

    def test_drop_view_if_exists(self, clickhouse_view_backend):
        """Test DROP VIEW IF EXISTS."""
        dialect = clickhouse_view_backend.dialect

        drop_view = DropViewExpression(dialect, view_name="nonexistent_view", if_exists=True)

        sql, params = drop_view.to_sql()
        result = clickhouse_view_backend.execute(sql, params, options=ExecutionOptions(stmt_type=StatementType.DDL))
        assert result is not None


class TestClickHouseMaterializedViewExecution:
    """Tests for materialized view operations (should all fail for ClickHouse)."""

    def test_create_materialized_view_raises_error(self, clickhouse_view_backend):
        """Test that CREATE MATERIALIZED VIEW raises UnsupportedFeatureError."""
        dialect = clickhouse_view_backend.dialect

        query = QueryExpression(dialect, select=[Column(dialect, "id")], from_=TableExpression(dialect, "users"))

        create_mv = CreateMaterializedViewExpression(dialect, view_name="test_mv", query=query)

        with pytest.raises(UnsupportedFeatureError) as exc_info:
            create_mv.to_sql()

        assert "CREATE MATERIALIZED VIEW" in str(exc_info.value)
        assert "ClickHouse" in str(exc_info.value)

    def test_drop_materialized_view_raises_error(self, clickhouse_view_backend):
        """Test that DROP MATERIALIZED VIEW raises UnsupportedFeatureError."""
        dialect = clickhouse_view_backend.dialect

        drop_mv = DropMaterializedViewExpression(dialect, view_name="test_mv")

        with pytest.raises(UnsupportedFeatureError) as exc_info:
            drop_mv.to_sql()

        assert "DROP MATERIALIZED VIEW" in str(exc_info.value)

    def test_refresh_materialized_view_raises_error(self, clickhouse_view_backend):
        """Test that REFRESH MATERIALIZED VIEW raises UnsupportedFeatureError."""
        dialect = clickhouse_view_backend.dialect

        refresh_mv = RefreshMaterializedViewExpression(dialect, view_name="test_mv")

        with pytest.raises(UnsupportedFeatureError) as exc_info:
            refresh_mv.to_sql()

        assert "REFRESH MATERIALIZED VIEW" in str(exc_info.value)

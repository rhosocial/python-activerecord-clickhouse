# tests/rhosocial/activerecord_clickhouse_test/feature/backend/ddl/test_create_table_like.py
"""
ClickHouse CREATE TABLE ... AS <source> syntax tests.

ClickHouse has no ``LIKE`` keyword; copying a table's structure is expressed
with ``AS <source>``.  These tests cover the ClickHouse override of the core
``CreateTableLikeExpression`` formatter.
"""

from rhosocial.activerecord.backend.expression import (
    CreateTableExpression,
    CreateTableLikeExpression,
    ColumnDefinition,
)
from rhosocial.activerecord.backend.expression.core import TableExpression
from rhosocial.activerecord.backend.expression.statements import ColumnConstraint, ColumnConstraintType
from rhosocial.activerecord.backend.expression.types import IntegerType, VarCharType
from rhosocial.activerecord.backend.impl.clickhouse.dialect import ClickHouseDialect


class TestClickHouseCreateTableLike:
    """Tests for ClickHouse CREATE TABLE ... AS <source> syntax."""

    def test_basic_as_syntax(self):
        """Test basic CREATE TABLE ... AS <source> syntax."""
        dialect = ClickHouseDialect()
        create_expr = CreateTableLikeExpression(
            dialect=dialect, table="users_copy", like_table="users"
        )
        sql, params = create_expr.to_sql()

        assert sql == "CREATE TABLE `users_copy` AS `users`"
        assert params == ()

    def test_as_with_if_not_exists(self):
        """Test CREATE TABLE ... AS <source> with IF NOT EXISTS."""
        dialect = ClickHouseDialect()
        create_expr = CreateTableLikeExpression(
            dialect=dialect, table="users_copy", like_table="users", if_not_exists=True
        )
        sql, params = create_expr.to_sql()

        assert sql == "CREATE TABLE IF NOT EXISTS `users_copy` AS `users`"
        assert params == ()

    def test_as_with_temporary(self):
        """Test CREATE TEMPORARY TABLE ... AS <source>."""
        dialect = ClickHouseDialect()
        create_expr = CreateTableLikeExpression(
            dialect=dialect, table="temp_users", like_table="users", temporary=True
        )
        sql, params = create_expr.to_sql()

        assert sql == "CREATE TEMPORARY TABLE `temp_users` AS `users`"
        assert params == ()

    def test_as_with_schema_qualified_table(self):
        """Test CREATE TABLE ... AS <source> with a schema-qualified source."""
        dialect = ClickHouseDialect()
        create_expr = CreateTableLikeExpression(
            dialect=dialect, table="users_copy", like_table=("production", "users")
        )
        sql, params = create_expr.to_sql()

        assert sql == "CREATE TABLE `users_copy` AS `production`.`users`"
        assert params == ()

    def test_source_as_table_expression(self):
        """Test that a TableExpression source is normalized and rendered."""
        dialect = ClickHouseDialect()
        create_expr = CreateTableLikeExpression(
            dialect=dialect,
            table="users_copy",
            like_table=TableExpression(dialect, "users", schema_name="production"),
        )
        sql, params = create_expr.to_sql()

        assert sql == "CREATE TABLE `users_copy` AS `production`.`users`"
        assert params == ()

    def test_as_with_temporary_and_if_not_exists(self):
        """Test CREATE TEMPORARY TABLE ... AS <source> with IF NOT EXISTS."""
        dialect = ClickHouseDialect()
        create_expr = CreateTableLikeExpression(
            dialect=dialect,
            table="temp_users_copy",
            like_table=("test_db", "users"),
            temporary=True,
            if_not_exists=True,
        )
        sql, params = create_expr.to_sql()

        assert sql == "CREATE TEMPORARY TABLE IF NOT EXISTS `temp_users_copy` AS `test_db`.`users`"
        assert params == ()

    def test_explicit_schema_still_renders(self):
        """The explicit-schema form is unaffected by the AS override."""
        dialect = ClickHouseDialect()
        columns = [
            ColumnDefinition(
                dialect,
                "id",
                IntegerType(dialect),
                constraints=[ColumnConstraint(dialect, ColumnConstraintType.PRIMARY_KEY)],
            ),
            ColumnDefinition(
                dialect,
                "name",
                VarCharType(length=255, dialect=dialect),
                constraints=[ColumnConstraint(dialect, ColumnConstraintType.NOT_NULL)],
            ),
        ]
        create_expr = CreateTableExpression(dialect=dialect, table="users", columns=columns)
        sql, params = create_expr.to_sql()

        assert "CREATE TABLE" in sql
        assert "`users`" in sql
        assert "`id`" in sql
        assert "`name`" in sql
        assert "PRIMARY KEY" in sql
        assert "NOT NULL" in sql

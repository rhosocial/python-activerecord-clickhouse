# tests/rhosocial/activerecord_clickhouse_test/feature/backend/ddl/test_create_table_like.py
"""
ClickHouse CREATE TABLE ... AS <source> and ... CLONE AS <source> tests.

ClickHouse has no ``LIKE`` keyword; copying a table's structure is expressed
with ``AS <source>``, and the zero-copy clone with ``CLONE AS <source>``. Both
statements hold the target and the source as :class:`Table` objects, each
carrying its own ``catalog_name``, so a database on either side is rendered by
``format_table_object``.
"""

import pytest

from rhosocial.activerecord.backend.dialect.exceptions import UnsupportedFeatureError
from rhosocial.activerecord.backend.expression import (
    ColumnDefinition,
    CreateTableExpression,
    CreateTableLikeExpression,
)
from rhosocial.activerecord.backend.expression.objects import Table, View
from rhosocial.activerecord.backend.expression.statements import (
    ColumnConstraint,
    ColumnConstraintType,
)
from rhosocial.activerecord.backend.expression.statements.ddl_table import (
    CreateTableCloneExpression,
    CreateTableCloneMode,
)
from rhosocial.activerecord.backend.expression.types import IntegerType, VarCharType
from rhosocial.activerecord.backend.impl.clickhouse.dialect import ClickHouseDialect


def _statement(dialect, table, like_table, **kwargs):
    """Build a CreateTableLikeExpression naming *table* and *like_table*."""
    return CreateTableLikeExpression(
        dialect=dialect, table=table, like_table=like_table, **kwargs
    )


def _create_table(dialect, table, columns, **kwargs):
    """Build a CreateTableExpression naming *table*."""
    return CreateTableExpression(
        dialect=dialect, table=table, columns=columns, **kwargs
    )


def _clone(dialect, table, source_table, **kwargs):
    """Build a CreateTableCloneExpression naming *table* and *source_table*."""
    return CreateTableCloneExpression(
        dialect=dialect, table=table, source_table=source_table, **kwargs
    )


class TestClickHouseCreateTableLike:
    """Tests for ClickHouse CREATE TABLE ... AS <source> syntax."""

    def test_basic_as_syntax(self):
        """Test basic CREATE TABLE ... AS <source> syntax."""
        dialect = ClickHouseDialect()
        sql, params = _statement(
            dialect, Table(dialect, "users_copy"), Table(dialect, "users")
        ).to_sql()

        assert sql == "CREATE TABLE `users_copy` AS `users`"
        assert params == ()

    def test_as_with_if_not_exists(self):
        """Test CREATE TABLE ... AS <source> with IF NOT EXISTS."""
        dialect = ClickHouseDialect()
        sql, params = _statement(
            dialect, Table(dialect, "users_copy"), Table(dialect, "users"), if_not_exists=True
        ).to_sql()

        assert sql == "CREATE TABLE IF NOT EXISTS `users_copy` AS `users`"
        assert params == ()

    def test_as_with_temporary(self):
        """Test CREATE TEMPORARY TABLE ... AS <source>."""
        dialect = ClickHouseDialect()
        sql, params = _statement(
            dialect, Table(dialect, "temp_users"), Table(dialect, "users"), temporary=True
        ).to_sql()

        assert sql == "CREATE TEMPORARY TABLE `temp_users` AS `users`"
        assert params == ()

    def test_as_with_qualified_source(self):
        """The source's database is the source's, and is rendered."""
        dialect = ClickHouseDialect()
        sql, params = _statement(
            dialect, Table(dialect, "users_copy"), Table(dialect, "users", catalog_name="production")
        ).to_sql()

        assert sql == "CREATE TABLE `users_copy` AS `production`.`users`"
        assert params == ()

    def test_as_with_qualified_target(self):
        dialect = ClickHouseDialect()
        sql, params = _statement(
            dialect,
            Table(dialect, "users_copy", catalog_name="staging"),
            Table(dialect, "users", catalog_name="production"),
        ).to_sql()

        assert sql == "CREATE TABLE `staging`.`users_copy` AS `production`.`users`"
        assert params == ()

    def test_as_with_temporary_and_if_not_exists(self):
        """Test CREATE TEMPORARY TABLE ... AS <source> with IF NOT EXISTS."""
        dialect = ClickHouseDialect()
        sql, params = _statement(
            dialect,
            Table(dialect, "temp_users_copy"),
            Table(dialect, "users", catalog_name="test_db"),
            temporary=True,
            if_not_exists=True,
        ).to_sql()

        assert sql == (
            "CREATE TEMPORARY TABLE IF NOT EXISTS `temp_users_copy` "
            "AS `test_db`.`users`"
        )
        assert params == ()

    def test_a_bare_string_target_is_refused(self):
        """Nothing is wrapped: a bare ``str`` has no database to keep.

        The refusal happens while rendering, not while constructing. The check
        belongs to the formatter because that is where the value is consumed:
        at construction the dialect may not be settled yet, and an object is
        routinely built before the slots are filled (the testsuite's foreign-key
        fixture constructs ``Table(None, ...)``). More to the point, a statement
        holding a ``str`` where a ``Table`` belongs renders perfectly well --
        the formatter only has to ask what it was handed.
        """
        dialect = ClickHouseDialect()
        expr = _statement(dialect, "users_copy", Table(dialect, "users"))
        with pytest.raises(TypeError, match="must be a Table"):
            expr.to_sql()

    def test_a_bare_string_source_is_refused(self):
        """The source side is checked too, and named separately."""
        dialect = ClickHouseDialect()
        expr = _statement(dialect, Table(dialect, "users_copy"), "users")
        with pytest.raises(TypeError, match="like_table must be a Table"):
            expr.to_sql()

    def test_a_view_where_a_table_belongs_is_refused(self):
        """A View carries its own ``to_sql()``, so it renders -- as a table's name.

        This is the defect the check exists for: without it the statement is
        well-formed and names an object the caller never asked about.
        """
        dialect = ClickHouseDialect()
        expr = _statement(dialect, View(dialect, "users_copy"), Table(dialect, "users"))
        with pytest.raises(TypeError, match="must be a Table, got View"):
            expr.to_sql()

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
        sql, params = _create_table(dialect, Table(dialect, "users"), columns).to_sql()

        assert "CREATE TABLE" in sql
        assert "`users`" in sql
        assert "`id`" in sql
        assert "`name`" in sql
        assert "PRIMARY KEY" in sql
        assert "NOT NULL" in sql

    def test_explicit_schema_keeps_the_target_database(self):
        """Reading table_name instead of table used to lose the database."""
        dialect = ClickHouseDialect()
        sql, _ = _create_table(
            dialect,
            Table(dialect, "users", catalog_name="analytics"),
            [ColumnDefinition(dialect, "id", IntegerType(dialect))],
        ).to_sql()
        assert "CREATE TABLE `analytics`.`users`" in sql


class TestClickHouseCreateTableClone:
    """``CLONE AS`` is ClickHouse's own grammar, not a docstring."""

    def test_clone_as_is_advertised(self):
        assert ClickHouseDialect().supports_create_table_clone() is True

    def test_clone_as(self):
        dialect = ClickHouseDialect()
        sql, params = _clone(dialect, Table(dialect, "users_copy"), Table(dialect, "users")).to_sql()
        assert sql == "CREATE TABLE `users_copy` CLONE AS `users`"
        assert params == ()

    def test_clone_as_qualified_and_guarded(self):
        dialect = ClickHouseDialect()
        sql, _ = _clone(
            dialect,
            Table(dialect, "users_copy", catalog_name="staging"),
            Table(dialect, "users", catalog_name="production"),
            if_not_exists=True,
        ).to_sql()
        assert sql == (
            "CREATE TABLE IF NOT EXISTS `staging`.`users_copy` "
            "CLONE AS `production`.`users`"
        )

    def test_clone_mode_is_not_rendered(self):
        """COPY is not a ClickHouse clone mode; the keyword is fixed."""
        dialect = ClickHouseDialect()
        expr = _clone(
            dialect, Table(dialect, "t"), Table(dialect, "s"), mode=CreateTableCloneMode.COPY
        )
        sql, _ = expr.to_sql()
        assert sql == "CREATE TABLE `t` CLONE AS `s`"

    def test_clone_rejects_clauses_clickhouse_lacks(self):
        dialect = ClickHouseDialect()
        for field, message in (
            ("copy_grants", "COPY GRANTS"),
            ("at", "AT"),
            ("before", "BEFORE"),
        ):
            expr = _clone(dialect, Table(dialect, "t"), Table(dialect, "s"))
            setattr(expr, field, "whatever" if field != "copy_grants" else True)
            with pytest.raises(UnsupportedFeatureError, match=message):
                expr.to_sql()

    def test_clone_refuses_a_bare_string_target(self):
        """Checked while rendering, for the reason given on the LIKE side."""
        dialect = ClickHouseDialect()
        expr = _clone(dialect, "users_copy", Table(dialect, "users"))
        with pytest.raises(TypeError, match="must be a Table, got str"):
            expr.to_sql()

    def test_clone_refuses_a_bare_string_source(self):
        dialect = ClickHouseDialect()
        expr = _clone(dialect, Table(dialect, "users_copy"), "users")
        with pytest.raises(TypeError, match="source_table must be a Table"):
            expr.to_sql()

    def test_create_table_refuses_a_non_table_target(self):
        """CREATE TABLE is the same shape and gets the same guard.

        A bare ``str`` would render as ``CREATE TABLE users_copy (...)``: valid
        SQL aimed at whatever database the connection happens to be on.
        """
        dialect = ClickHouseDialect()
        columns = [ColumnDefinition(dialect, "id", IntegerType(dialect))]
        expr = _create_table(dialect, "users_copy", columns)
        with pytest.raises(TypeError, match="CreateTableExpression.table must be a Table"):
            expr.to_sql()

    def test_create_table_refuses_a_view_target(self):
        dialect = ClickHouseDialect()
        columns = [ColumnDefinition(dialect, "id", IntegerType(dialect))]
        expr = _create_table(dialect, View(dialect, "users_copy"), columns)
        with pytest.raises(TypeError, match="must be a Table, got View"):
            expr.to_sql()


class TestClickHouseCreateTableOptions:
    """ClickHouse CREATE OR REPLACE TABLE via CreateTableOptions."""

    def test_create_or_replace(self):
        from rhosocial.activerecord.backend.expression import CreateTableOptions

        dialect = ClickHouseDialect()
        sql, params = _create_table(
            dialect,
            Table(dialect, "t"),
            [],
            table_options=CreateTableOptions(dialect, or_replace=True),
        ).to_sql()
        assert sql.startswith("CREATE OR REPLACE TABLE `t`")
        assert params == ()
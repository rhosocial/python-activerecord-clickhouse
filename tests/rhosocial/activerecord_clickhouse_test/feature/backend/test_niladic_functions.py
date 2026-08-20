# tests/rhosocial/activerecord_clickhouse_test/feature/backend/test_niladic_functions.py
"""
ClickHouse niladic function integration tests.

Verifies that ClickHouse accepts both the SQL:2003 niladic form (no parentheses)
and the parenthesized form for CURRENT_TIMESTAMP, CURRENT_DATE, CURRENT_TIME
in both DDL DEFAULT and SELECT contexts.

ClickHouse is unique in accepting both forms:
- CURRENT_TIMESTAMP  (SQL:2003 niladic, standard)
- CURRENT_TIMESTAMP() (ClickHouse extension with parentheses)

Both are valid in DDL DEFAULT and SELECT contexts across ClickHouse 5.6+.
"""

import pytest

from rhosocial.activerecord.backend.expression import (
    CreateTableExpression,
    DropTableExpression,
    QueryExpression,
)
from rhosocial.activerecord.backend.expression.core import FunctionCall
from rhosocial.activerecord.backend.expression.functions.datetime import (
    current_timestamp,
    current_date,
    current_time,
    now,
)
from rhosocial.activerecord.backend.expression.statements import (
    ColumnDefinition,
    ColumnConstraint,
    ColumnConstraintType,
)
from rhosocial.activerecord.backend.expression.types import IntegerType, TimestampType
from rhosocial.activerecord.backend.options import ExecutionOptions
from rhosocial.activerecord.backend.schema import StatementType


DQL_OPTIONS = ExecutionOptions(stmt_type=StatementType.DQL)


class TestClickHouseNiladicSelectContext:
    """Test niladic functions in SELECT context against real ClickHouse."""

    def test_select_current_timestamp_niladic(self, clickhouse_backend):
        """SELECT CURRENT_TIMESTAMP (niladic, no parentheses) works in ClickHouse."""
        query = QueryExpression(
            dialect=clickhouse_backend.dialect,
            select=[current_timestamp(clickhouse_backend.dialect)],
        )
        sql, params = query.to_sql()
        assert sql == "SELECT CURRENT_TIMESTAMP"
        assert "(" not in sql.replace("SELECT ", "")
        result = clickhouse_backend.execute(sql, params, options=DQL_OPTIONS)
        assert result.data is not None
        assert len(result.data) == 1

    def test_select_current_timestamp_with_parens(self, clickhouse_backend):
        """SELECT CURRENT_TIMESTAMP() (with parentheses) also works in ClickHouse."""
        query = QueryExpression(
            dialect=clickhouse_backend.dialect,
            select=[FunctionCall(clickhouse_backend.dialect, "CURRENT_TIMESTAMP")],
        )
        sql, params = query.to_sql()
        assert "CURRENT_TIMESTAMP()" in sql
        result = clickhouse_backend.execute(sql, params, options=DQL_OPTIONS)
        assert result.data is not None
        assert len(result.data) == 1

    def test_select_current_date_niladic(self, clickhouse_backend):
        """SELECT CURRENT_DATE (niladic) works in ClickHouse."""
        query = QueryExpression(
            dialect=clickhouse_backend.dialect,
            select=[current_date(clickhouse_backend.dialect)],
        )
        sql, params = query.to_sql()
        assert "CURRENT_DATE" in sql
        result = clickhouse_backend.execute(sql, params, options=DQL_OPTIONS)
        assert result.data is not None
        assert len(result.data) == 1

    def test_select_current_time_niladic(self, clickhouse_backend):
        """SELECT CURRENT_TIME (niladic) works in ClickHouse."""
        query = QueryExpression(
            dialect=clickhouse_backend.dialect,
            select=[current_time(clickhouse_backend.dialect)],
        )
        sql, params = query.to_sql()
        assert "CURRENT_TIME" in sql
        result = clickhouse_backend.execute(sql, params, options=DQL_OPTIONS)
        assert result.data is not None
        assert len(result.data) == 1

    def test_select_now(self, clickhouse_backend):
        """SELECT NOW() (regular function, always with parentheses) works in ClickHouse."""
        query = QueryExpression(
            dialect=clickhouse_backend.dialect,
            select=[now(clickhouse_backend.dialect)],
        )
        sql, params = query.to_sql()
        assert "NOW()" in sql
        result = clickhouse_backend.execute(sql, params, options=DQL_OPTIONS)
        assert result.data is not None
        assert len(result.data) == 1


class TestClickHouseNiladicDDLContext:
    """Test niladic functions in DDL DEFAULT context against real ClickHouse."""

    def test_ddl_default_current_timestamp_niladic(self, clickhouse_backend):
        """DEFAULT CURRENT_TIMESTAMP (niladic) works in ClickHouse DDL."""
        dialect = clickhouse_backend.dialect
        table_name = "test_niladic_ddl_1"

        # Clean up
        clickhouse_backend.execute(*DropTableExpression(dialect=dialect, table=table_name, if_exists=True).to_sql())

        create = CreateTableExpression(
            dialect=dialect,
            table=table_name,
            columns=[
                ColumnDefinition(
                    "id",
                    IntegerType(),
                    constraints=[
                        ColumnConstraint(ColumnConstraintType.PRIMARY_KEY),
                        ColumnConstraint(ColumnConstraintType.NOT_NULL, is_auto_increment=True),
                    ],
                ),
                ColumnDefinition(
                    "ts",
                    TimestampType(),
                    constraints=[
                        ColumnConstraint(ColumnConstraintType.DEFAULT, default_value=current_timestamp(dialect)),
                    ],
                ),
            ],
            if_not_exists=True,
        )
        sql, params = create.to_sql()
        assert "DEFAULT CURRENT_TIMESTAMP" in sql
        assert "DEFAULT CURRENT_TIMESTAMP()" not in sql

        try:
            clickhouse_backend.execute(sql, params)
            # Verify table was created
            cols = clickhouse_backend.introspector.list_columns(table_name)
            col_names = [c.name for c in cols]
            assert "ts" in col_names
        finally:
            clickhouse_backend.execute(*DropTableExpression(dialect=dialect, table=table_name, if_exists=True).to_sql())

    def test_ddl_default_current_timestamp_with_parens(self, clickhouse_backend):
        """DEFAULT CURRENT_TIMESTAMP() (with parentheses) also works in ClickHouse DDL."""
        dialect = clickhouse_backend.dialect
        table_name = "test_niladic_ddl_2"

        # Clean up
        clickhouse_backend.execute(*DropTableExpression(dialect=dialect, table=table_name, if_exists=True).to_sql())

        create = CreateTableExpression(
            dialect=dialect,
            table=table_name,
            columns=[
                ColumnDefinition(
                    "id",
                    IntegerType(),
                    constraints=[
                        ColumnConstraint(ColumnConstraintType.PRIMARY_KEY),
                        ColumnConstraint(ColumnConstraintType.NOT_NULL, is_auto_increment=True),
                    ],
                ),
                ColumnDefinition(
                    "ts",
                    TimestampType(),
                    constraints=[
                        ColumnConstraint(
                            ColumnConstraintType.DEFAULT, default_value=FunctionCall(dialect, "CURRENT_TIMESTAMP")
                        ),
                    ],
                ),
            ],
            if_not_exists=True,
        )
        sql, params = create.to_sql()
        assert "DEFAULT CURRENT_TIMESTAMP()" in sql

        try:
            clickhouse_backend.execute(sql, params)
            # Verify table was created
            cols = clickhouse_backend.introspector.list_columns(table_name)
            col_names = [c.name for c in cols]
            assert "ts" in col_names
        finally:
            clickhouse_backend.execute(*DropTableExpression(dialect=dialect, table=table_name, if_exists=True).to_sql())

    def test_ddl_default_current_timestamp_with_precision(self, clickhouse_backend):
        """DEFAULT CURRENT_TIMESTAMP(6) (with precision) works in ClickHouse DDL."""
        dialect = clickhouse_backend.dialect
        table_name = "test_niladic_ddl_3"

        # Clean up
        clickhouse_backend.execute(*DropTableExpression(dialect=dialect, table=table_name, if_exists=True).to_sql())

        create = CreateTableExpression(
            dialect=dialect,
            table=table_name,
            columns=[
                ColumnDefinition(
                    "id",
                    IntegerType(),
                    constraints=[
                        ColumnConstraint(ColumnConstraintType.PRIMARY_KEY),
                        ColumnConstraint(ColumnConstraintType.NOT_NULL, is_auto_increment=True),
                    ],
                ),
                ColumnDefinition(
                    "ts",
                    TimestampType(6),
                    constraints=[
                        ColumnConstraint(ColumnConstraintType.DEFAULT, default_value=current_timestamp(dialect, 6)),
                    ],
                ),
            ],
            if_not_exists=True,
        )
        sql, params = create.to_sql()
        assert "CURRENT_TIMESTAMP(%s)" in sql or "CURRENT_TIMESTAMP(?)" in sql

        try:
            clickhouse_backend.execute(sql, params)
            # Verify table was created
            cols = clickhouse_backend.introspector.list_columns(table_name)
            col_names = [c.name for c in cols]
            assert "ts" in col_names
        finally:
            clickhouse_backend.execute(*DropTableExpression(dialect=dialect, table=table_name, if_exists=True).to_sql())


class TestAsyncClickHouseNiladicSelectContext:
    """Async niladic function tests in SELECT context against real ClickHouse."""

    @pytest.mark.asyncio
    async def test_async_select_current_timestamp_niladic(self, async_clickhouse_backend):
        """SELECT CURRENT_TIMESTAMP (niladic) works in ClickHouse (async)."""
        query = QueryExpression(
            dialect=async_clickhouse_backend.dialect,
            select=[current_timestamp(async_clickhouse_backend.dialect)],
        )
        sql, params = query.to_sql()
        assert sql == "SELECT CURRENT_TIMESTAMP"
        result = await async_clickhouse_backend.execute(sql, params, options=DQL_OPTIONS)
        assert result.data is not None
        assert len(result.data) == 1


class TestAsyncClickHouseNiladicDDLContext:
    """Async niladic function tests in DDL DEFAULT context against real ClickHouse."""

    @pytest.mark.asyncio
    async def test_async_ddl_default_current_timestamp_niladic(self, async_clickhouse_backend):
        """DEFAULT CURRENT_TIMESTAMP (niladic) works in ClickHouse DDL (async)."""
        dialect = async_clickhouse_backend.dialect
        table_name = "test_async_niladic_ddl_1"

        # Clean up
        await async_clickhouse_backend.execute(
            *DropTableExpression(dialect=dialect, table=table_name, if_exists=True).to_sql()
        )

        create = CreateTableExpression(
            dialect=dialect,
            table=table_name,
            columns=[
                ColumnDefinition(
                    "id",
                    IntegerType(),
                    constraints=[
                        ColumnConstraint(ColumnConstraintType.PRIMARY_KEY),
                        ColumnConstraint(ColumnConstraintType.NOT_NULL, is_auto_increment=True),
                    ],
                ),
                ColumnDefinition(
                    "ts",
                    TimestampType(),
                    constraints=[
                        ColumnConstraint(ColumnConstraintType.DEFAULT, default_value=current_timestamp(dialect)),
                    ],
                ),
            ],
            if_not_exists=True,
        )
        sql, params = create.to_sql()

        try:
            await async_clickhouse_backend.execute(sql, params)
            cols = await async_clickhouse_backend.introspector.list_columns(table_name)
            col_names = [c.name for c in cols]
            assert "ts" in col_names
        finally:
            await async_clickhouse_backend.execute(
                *DropTableExpression(dialect=dialect, table=table_name, if_exists=True).to_sql()
            )

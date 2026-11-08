# tests/rhosocial/activerecord_clickhouse_test/feature/backend/expression/test_seconds_between_expression.py
"""``seconds_between`` rendered by the ClickHouse dialect.

``dateDiff`` counts whole units, so the node's fractional contract is met by
counting the finest unit the engine has -- milliseconds -- and dividing by
``1000.0``. These cases pin the four things the SQL alone decides:

* the spelling, including the quoted unit;
* the sign, which the argument order carries rather than a leading ``-``;
* the bind parameters, whose order follows the SQL text (``start`` first);
* the alias, applied to the whole division rather than to one operand.
"""

import pytest

from rhosocial.activerecord.backend.expression import (
    Column,
    Literal,
    QueryStatement,
    SecondsBetweenExpression,
)
from rhosocial.activerecord.backend.expression.column_types import TimestampColumn
from rhosocial.activerecord.backend.expression.value_types import NumericValue
from rhosocial.activerecord.backend.impl.clickhouse.dialect import ClickHouseDialect


@pytest.fixture()
def dialect() -> ClickHouseDialect:
    """A dialect at the release the backend tests measure against."""
    return ClickHouseDialect(version=(26, 7, 1))


class TestSecondsBetweenSpelling:
    """The SQL ``dateDiff('millisecond', ...) / 1000.0`` writes."""

    def test_columns(self, dialect: ClickHouseDialect):
        expr = SecondsBetweenExpression(
            dialect,
            Column(dialect, "started_at"),
            Column(dialect, "ended_at"),
        )

        sql, params = expr.to_sql()

        assert sql == "dateDiff('millisecond', `started_at`, `ended_at`) / 1000.0"
        assert params == ()

    def test_signed_in_argument_order(self, dialect: ClickHouseDialect):
        """A backdated end renders the same SQL; the sign is arithmetic."""
        reversed_expr = SecondsBetweenExpression(
            dialect,
            Column(dialect, "ended_at"),
            Column(dialect, "started_at"),
        )

        sql, params = reversed_expr.to_sql()

        assert sql == "dateDiff('millisecond', `ended_at`, `started_at`) / 1000.0"
        assert params == ()

    def test_alias_applies_to_the_division(self, dialect: ClickHouseDialect):
        expr = SecondsBetweenExpression(
            dialect,
            Column(dialect, "started_at"),
            Column(dialect, "ended_at"),
        ).as_("elapsed_seconds")

        sql, params = expr.to_sql()

        assert sql == (
            "dateDiff('millisecond', `started_at`, `ended_at`) / 1000.0 "
            "AS `elapsed_seconds`"
        )
        assert params == ()

    def test_factory_renders_the_same_sql(self, dialect: ClickHouseDialect):
        from rhosocial.activerecord.backend.expression import seconds_between

        expr = seconds_between(
            dialect,
            Column(dialect, "started_at"),
            Column(dialect, "ended_at"),
        )

        sql, params = expr.to_sql()

        assert sql == "dateDiff('millisecond', `started_at`, `ended_at`) / 1000.0"
        assert params == ()

    def test_factory_coerces_string_to_column(self, dialect: ClickHouseDialect):
        from rhosocial.activerecord.backend.expression import seconds_between

        expr = seconds_between(dialect, "started_at", "ended_at")

        sql, params = expr.to_sql()

        assert sql == "dateDiff('millisecond', `started_at`, `ended_at`) / 1000.0"
        assert params == ()

    def test_column_method_renders_the_same_sql(self, dialect: ClickHouseDialect):
        started = TimestampColumn(dialect, "started_at")
        ended = TimestampColumn(dialect, "ended_at")

        sql, params = started.seconds_between(ended).to_sql()

        assert sql == "dateDiff('millisecond', `started_at`, `ended_at`) / 1000.0"
        assert params == ()


class TestSecondsBetweenBindOrder:
    """``start`` is written first, so its parameter binds first."""

    def test_literal_parameters_follow_the_sql(self, dialect: ClickHouseDialect):
        expr = SecondsBetweenExpression(
            dialect,
            Literal(dialect, "2026-01-01 00:00:00"),
            Literal(dialect, "2026-01-02 00:00:00"),
        )

        sql, params = expr.to_sql()

        assert sql == "dateDiff('millisecond', %s, %s) / 1000.0"
        # The SQL names ``start`` first, so its parameter precedes ``end``.
        assert params == ("2026-01-01 00:00:00", "2026-01-02 00:00:00")

    def test_mixed_operands_keep_their_rendered_order(self, dialect: ClickHouseDialect):
        expr = SecondsBetweenExpression(
            dialect,
            Literal(dialect, "2026-01-01 00:00:00"),
            Column(dialect, "ended_at"),
        )

        sql, params = expr.to_sql()

        assert sql == "dateDiff('millisecond', %s, `ended_at`) / 1000.0"
        assert params == ("2026-01-01 00:00:00",)


class TestSecondsBetweenNodeIdentity:
    """The node is a fractional number, not a temporal value."""

    def test_node_type_and_format_method(self, dialect: ClickHouseDialect):
        from rhosocial.activerecord.backend.expression import seconds_between

        expr = seconds_between(
            dialect,
            Column(dialect, "started_at"),
            Column(dialect, "ended_at"),
        )

        assert isinstance(expr, SecondsBetweenExpression)
        assert isinstance(expr, NumericValue)
        assert expr.format_method == "format_seconds_between_expression"

    def test_renders_inside_a_query(self, dialect: ClickHouseDialect):
        from rhosocial.activerecord.backend.expression import seconds_between

        expr = seconds_between(
            dialect,
            Column(dialect, "started_at"),
            Column(dialect, "ended_at"),
        ).as_("queue_seconds")
        query = QueryStatement(
            dialect,
            select=[expr, Column(dialect, "id")],
            from_="spans",
        )

        sql, params = query.to_sql()

        assert (
            "dateDiff('millisecond', `started_at`, `ended_at`) / 1000.0 "
            "AS `queue_seconds`"
        ) in sql
        assert params == ()

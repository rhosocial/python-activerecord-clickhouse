# tests/test_expression_registry_contract.py
"""Construct-level contract for ClickHouse's ``Parameter`` rendering.

Rendering is the dialect's business: a value binds by default, and an
``inline=True`` value becomes text through ClickHouse's ``format_literal``.
No live server or emulator is involved in any of it.
"""

import pytest

from rhosocial.activerecord.backend.expression import (
    Column,
    ComparisonPredicate,
    Parameter,
)
from rhosocial.activerecord.backend.expression.coerce import value_expression
from rhosocial.activerecord.backend.impl.clickhouse.dialect import ClickHouseDialect


@pytest.fixture
def dialect():
    return ClickHouseDialect()


# ---------------------------------------------------------------------------
# Rendering: one position, one decision (bind or text)
# ---------------------------------------------------------------------------


def test_parameter_binds_by_default(dialect: ClickHouseDialect) -> None:
    sql, params = Parameter(dialect, "abc").to_sql()
    assert sql == "%s" == dialect.get_parameter_placeholder()
    assert params == ("abc",)


def test_inline_parameter_renders_clickhouse_text_with_no_params(
    dialect: ClickHouseDialect,
) -> None:
    sql, params = Parameter(dialect, "O'Reilly", inline=True).to_sql()
    assert sql == "'O''Reilly'"
    assert params == ()

    # ClickHouse's own tier-2 literal spelling, not a generic one: bytes go
    # through ``unhex()`` because the dialect really rendered this value.
    assert Parameter(dialect, b"\x01\x02", inline=True).to_sql() == (
        "unhex('0102')",
        (),
    )


def test_raw_value_at_a_value_position_binds(dialect: ClickHouseDialect) -> None:
    coerced = value_expression(dialect, 42)
    assert isinstance(coerced, Parameter)
    assert coerced.to_sql() == ("%s", (42,))

    predicate = ComparisonPredicate(dialect, "=", Column(dialect, "id"), "42")
    assert isinstance(predicate.right, Parameter)
    sql, params = predicate.to_sql()
    assert sql == "`id` = %s"
    assert "42" not in sql
    assert params == ("42",)

# tests/rhosocial/activerecord_clickhouse_test/feature/backend/dialect/test_dql_set_operation_for_update.py
"""Q01: ClickHouse must fail fast on set-operation FOR UPDATE."""

import pytest

from rhosocial.activerecord.backend.dialect.exceptions import UnsupportedFeatureError
from rhosocial.activerecord.backend.expression import Column, ForUpdateClause
from rhosocial.activerecord.backend.expression.query_sources import SetOperationExpression
from rhosocial.activerecord.backend.expression.statements import QueryExpression
from rhosocial.activerecord.backend.impl.clickhouse.dialect import ClickHouseDialect


@pytest.fixture
def dialect():
    return ClickHouseDialect(version=(24, 3, 0))


def test_set_operation_for_update_raises(dialect):
    expr = SetOperationExpression(
        dialect,
        left=QueryExpression(dialect, select=[Column(dialect, "id")], from_="t1"),
        right=QueryExpression(dialect, select=[Column(dialect, "id")], from_="t2"),
        operation="UNION",
        for_update_clause=ForUpdateClause(dialect),
    )
    with pytest.raises(UnsupportedFeatureError, match="FOR UPDATE in set operations"):
        expr.to_sql()


def test_set_operation_without_for_update_renders(dialect):
    expr = SetOperationExpression(
        dialect,
        left=QueryExpression(dialect, select=[Column(dialect, "id")], from_="t1"),
        right=QueryExpression(dialect, select=[Column(dialect, "id")], from_="t2"),
        operation="UNION",
    )
    sql, _ = expr.to_sql()
    assert "UNION DISTINCT" in sql

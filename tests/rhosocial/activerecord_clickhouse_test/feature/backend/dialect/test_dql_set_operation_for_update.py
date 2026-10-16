# tests/rhosocial/activerecord_clickhouse_test/feature/backend/dialect/test_dql_set_operation_for_update.py
"""Q01: ClickHouse must fail fast on FOR UPDATE.

FOR UPDATE is a statement-level clause, not part of a set operation. The
``SetOperation`` node carries exactly ``op`` / ``left`` / ``right``, so a
compound query cannot smuggle a lock clause in -- and where FOR UPDATE
actually lives, the statement, ClickHouse still refuses it rather than
emitting SQL the server rejects.
"""

import pytest

from rhosocial.activerecord.backend.dialect.exceptions import UnsupportedFeatureError
from rhosocial.activerecord.backend.expression import Column, ForUpdateClause
from rhosocial.activerecord.backend.expression.query_sources import SetOperation
from rhosocial.activerecord.backend.expression.statements import QueryStatement
from rhosocial.activerecord.backend.impl.clickhouse.dialect import ClickHouseDialect


@pytest.fixture
def dialect():
    return ClickHouseDialect(version=(24, 3, 0))


def test_set_operation_cannot_carry_a_for_update_clause(dialect):
    """The node has no slot for one: the keyword is not a construction parameter."""
    with pytest.raises(TypeError):
        SetOperation(
            dialect,
            op="union",
            left=QueryStatement(dialect, select=[Column(dialect, "id")], from_="t1"),
            right=QueryStatement(dialect, select=[Column(dialect, "id")], from_="t2"),
            for_update_clause=ForUpdateClause(dialect),
        )


def test_set_operation_renders_without_a_lock_clause(dialect):
    expr = SetOperation(
        dialect,
        op="union",
        left=QueryStatement(dialect, select=[Column(dialect, "id")], from_="t1"),
        right=QueryStatement(dialect, select=[Column(dialect, "id")], from_="t2"),
    )
    sql, _ = expr.to_sql()
    assert "UNION DISTINCT" in sql
    assert "FOR UPDATE" not in sql


def test_query_statement_for_update_raises(dialect):
    """Where FOR UPDATE belongs, ClickHouse still refuses it."""
    expr = QueryStatement(
        dialect,
        select=[Column(dialect, "id")],
        from_="t1",
        for_update=ForUpdateClause(dialect),
    )
    with pytest.raises(UnsupportedFeatureError, match="FOR UPDATE"):
        expr.to_sql()
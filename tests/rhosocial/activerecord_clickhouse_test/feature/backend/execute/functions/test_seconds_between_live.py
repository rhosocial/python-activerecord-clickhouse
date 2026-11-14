# tests/rhosocial/activerecord_clickhouse_test/feature/backend/execute/functions/test_seconds_between_live.py
"""Signed fractional seconds executed on a live ClickHouse.

The rendering test pins the SQL text; this file asks the engine for the value
the SQL produces. ``dateDiff('millisecond', ...)`` is a whole-unit count, so
the cases that matter are the ones the division and the argument order decide:

* the sign -- an ``end`` earlier than the ``start`` must be negative;
* the fraction -- ``/ 1000.0`` must keep the millisecond, not round it away;
* the boundaries -- a month change and a year change are ordinary arithmetic,
  not a component sum.

Requires a live ClickHouse (``tests/config/clickhouse_scenarios.yaml``); the
fixtures skip when no scenario is configured.
"""

import pytest

from rhosocial.activerecord.backend.expression import (
    Column,
    Literal,
    QueryStatement,
    cast,
    seconds_between,
)
from rhosocial.activerecord.backend.impl.clickhouse.expression.types import (
    ClickHouseDateTime64Type,
)
from rhosocial.activerecord.backend.options import ExecutionOptions
from rhosocial.activerecord.backend.schema import StatementType


def _millisecond_instant(dialect, value: str):
    """A ``DateTime64(3)`` expression over a bound literal.

    The cast is part of the operand, not the node: ``dateDiff`` needs a
    temporal type, and ``DateTime64(3)`` is the resolution these cases assert.
    """
    return cast(
        dialect,
        Literal(dialect, value),
        ClickHouseDateTime64Type(dialect, precision=3),
    )


def _elapsed(backend, start: str, end: str) -> float:
    """Run ``seconds_between(start, end)`` and return the scalar."""
    dialect = backend.dialect
    expr = seconds_between(
        dialect,
        _millisecond_instant(dialect, start),
        _millisecond_instant(dialect, end),
    ).as_("seconds")
    query = QueryStatement(dialect, select=[expr])
    sql, params = query.to_sql()
    result = backend.execute(
        sql,
        params,
        options=ExecutionOptions(stmt_type=StatementType.DQL),
    )
    return result.data[0]["seconds"]


class TestSecondsBetweenExecution:
    """The value ClickHouse's spelling actually produces."""

    @pytest.mark.parametrize(
        "start,end,expected",
        [
            ("2026-06-04 10:00:00.000", "2026-06-04 10:00:00.000", 0.0),
            ("2026-06-04 10:00:00.000", "2026-06-04 11:00:00.000", 3600.0),
            ("2026-06-04 11:00:00.000", "2026-06-04 10:00:00.000", -3600.0),
            ("2026-01-31 23:59:59.000", "2026-02-01 00:00:00.000", 1.0),
            ("2025-12-31 12:00:00.000", "2026-01-01 12:00:00.000", 86400.0),
            ("2026-06-04 10:00:00.000", "2026-06-04 10:00:00.500", 0.5),
            ("2026-06-04 10:00:00.250", "2026-06-04 10:00:00.000", -0.25),
        ],
    )
    def test_interval(self, clickhouse_backend_single, start, end, expected):
        assert _elapsed(clickhouse_backend_single, start, end) == pytest.approx(
            expected, abs=1e-9
        )

    def test_columns_in_a_row(self, clickhouse_backend_single):
        """The same question asked of two columns, not two literals."""
        backend = clickhouse_backend_single
        backend.execute("DROP TABLE IF EXISTS seconds_between_spans")
        backend.execute(
            """
            CREATE TABLE seconds_between_spans (
                id UInt32,
                started_at DateTime64(3),
                ended_at DateTime64(3)
            ) ENGINE = MergeTree() ORDER BY id
            """
        )
        backend.execute(
            "INSERT INTO seconds_between_spans VALUES (%s, %s, %s)",
            (1, "2026-03-01 00:00:00.000", "2026-03-02 00:00:00.000"),
        )
        backend.execute(
            "INSERT INTO seconds_between_spans VALUES (%s, %s, %s)",
            (2, "2026-03-02 00:00:00.000", "2026-03-01 00:00:00.000"),
        )
        backend.execute(
            "INSERT INTO seconds_between_spans VALUES (%s, %s, %s)",
            (3, "2026-03-01 00:00:00.750", "2026-03-01 00:00:01.000"),
        )

        dialect = backend.dialect
        expr = seconds_between(
            dialect,
            Column(dialect, "started_at"),
            Column(dialect, "ended_at"),
        ).as_("seconds")
        query = QueryStatement(
            dialect,
            select=[expr, Column(dialect, "id")],
            from_="seconds_between_spans",
        )
        sql, params = query.to_sql()
        result = backend.execute(
            sql,
            params,
            options=ExecutionOptions(stmt_type=StatementType.DQL),
        )

        rows = {row["id"]: row["seconds"] for row in result.data}
        assert rows[1] == pytest.approx(86400.0, abs=1e-9)
        assert rows[2] == pytest.approx(-86400.0, abs=1e-9)
        assert rows[3] == pytest.approx(0.25, abs=1e-9)
        backend.execute("DROP TABLE IF EXISTS seconds_between_spans")

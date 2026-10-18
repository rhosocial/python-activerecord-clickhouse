# tests/rhosocial/activerecord_clickhouse_test/feature/backend/dml/test_insert_value_cells.py
"""INSERT VALUES cells: expressions render, bare host values bind.

The VALUES branch of the ClickHouse INSERT formatter delegates to the
core's ``format_insert_values_source`` (core ``8e2e4d82``), which is the one
place that decides a cell is an expression (rendered through its own
``to_sql()``) or a bare host value (a bind parameter). The old branch here
re-implemented the rows and called ``to_sql()`` unconditionally, so a bare
scalar cell crashed before it ever reached the driver.
"""

import pytest

from rhosocial.activerecord.backend.expression.objects import Table
from rhosocial.activerecord.backend.expression.statements import (
    InsertStatement,
    ValuesSource,
)
from rhosocial.activerecord.backend.expression.values import IntegerValue, StringValue
from rhosocial.activerecord.backend.impl.clickhouse.dialect import ClickHouseDialect

#: The dialect floor the formatter's behaviour is pinned at; the cell
#: decision itself carries no version gate.
MEASURED_VERSION = (26, 7, 3)


@pytest.fixture()
def dialect() -> ClickHouseDialect:
    return ClickHouseDialect(version=MEASURED_VERSION)


class TestValueCells:
    def test_expression_cells_render_through_their_own_to_sql(self, dialect):
        stmt = InsertStatement(
            dialect,
            into=Table(dialect, "t"),
            columns=["id", "name"],
            source=ValuesSource(
                dialect,
                [[IntegerValue(dialect, 1), StringValue(dialect, "alice")]],
            ),
        )
        sql, params = stmt.to_sql()
        assert sql == "INSERT INTO `t` (`id`, `name`) VALUES (%s, %s)"
        assert params == (1, "alice")

    def test_bare_host_value_cells_bind(self, dialect):
        stmt = InsertStatement(
            dialect,
            into=Table(dialect, "t"),
            columns=["id", "name"],
            source=ValuesSource(dialect, [[1, "alice"]]),
        )
        sql, params = stmt.to_sql()
        assert sql == "INSERT INTO `t` (`id`, `name`) VALUES (%s, %s)"
        assert params == (1, "alice")

    def test_mixed_cells_share_one_row(self, dialect):
        """A row may mix an expression with a bare host value; each cell
        takes its own path and the parameters line up in order."""
        stmt = InsertStatement(
            dialect,
            into=Table(dialect, "t"),
            columns=["id", "name"],
            source=ValuesSource(dialect, [[IntegerValue(dialect, 7), "bob"]]),
        )
        sql, params = stmt.to_sql()
        assert sql == "INSERT INTO `t` (`id`, `name`) VALUES (%s, %s)"
        assert params == (7, "bob")

    def test_bare_cells_across_several_rows(self, dialect):
        stmt = InsertStatement(
            dialect,
            into=Table(dialect, "t"),
            columns=["id"],
            source=ValuesSource(dialect, [[1], [2], [3]]),
        )
        sql, params = stmt.to_sql()
        assert sql == "INSERT INTO `t` (`id`) VALUES (%s), (%s), (%s)"
        assert params == (1, 2, 3)

    def test_refusals_still_precede_the_source(self, dialect):
        """The delegation did not move the gates: OR REPLACE / OR IGNORE /
        ON CONFLICT are refused before any row renders."""
        from rhosocial.activerecord.backend.dialect.exceptions import (
            UnsupportedFeatureError,
        )

        with pytest.raises(UnsupportedFeatureError, match="REPLACE INTO"):
            InsertStatement(
                dialect,
                into=Table(dialect, "t"),
                columns=["id"],
                source=ValuesSource(dialect, [[1]]),
                or_replace=True,
            ).to_sql()
        with pytest.raises(UnsupportedFeatureError, match="INSERT IGNORE"):
            InsertStatement(
                dialect,
                into=Table(dialect, "t"),
                columns=["id"],
                source=ValuesSource(dialect, [[1]]),
                or_ignore=True,
            ).to_sql()

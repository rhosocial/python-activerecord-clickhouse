# tests/rhosocial/activerecord_clickhouse_test/feature/backend/ddl/test_update_filter_qualification.py
"""An UPDATE filter may only carry a table qualifier where ClickHouse accepts one.

A ClickHouse UPDATE is a mutation. The server rewrites it into
``_CAST(if(<filter>, <new>, <old>), <type>)`` and evaluates the filter against the
part's columns. Until 26.7 that path did not resolve a table qualifier, so
``WHERE t.id = 1`` was read as a column named ``t.id`` and the statement failed
with ``Missing columns: 't.id'`` -- see ClickHouse/ClickHouse#71760, fixed by
PR #109491 in 26.7.

So the same statement has to render two different ways depending on the server
it is talking to, which is what these tests pin down. Both renderings were run
against real 26.3 and 26.7 servers and both applied the mutation.
"""
import pytest

from rhosocial.activerecord.backend.expression.core import Column, Literal, TableExpression
from rhosocial.activerecord.backend.expression.statements.dml import UpdateExpression
from rhosocial.activerecord.backend.impl.clickhouse.dialect import ClickHouseDialect

#: (version, whether the server resolves a qualified column in a mutation filter)
SUPPORTED = [
    ((25, 8, 0), False),
    ((26, 3, 0), False),
    ((26, 7, 0), True),
]


def _update(dialect):
    """An UPDATE in the shape soft-delete restore() builds."""
    where = Column(dialect, "id", table="tasks") == Literal(dialect, 1)
    return UpdateExpression(
        dialect,
        table=TableExpression(dialect, "tasks"),
        assignments={"deleted_at": Literal(dialect, None)},
        where=where,
    )


class TestVersionGate:
    """The gate must track the release that fixed the mutation path."""

    @pytest.mark.parametrize("version,expected", SUPPORTED)
    def test_gate_matches_release(self, version, expected):
        dialect = ClickHouseDialect(version=version)
        assert dialect.supports_update_column_qualification() is expected

    def test_gate_is_26_7(self):
        """Named explicitly so moving the boundary is a visible edit here too."""
        from rhosocial.activerecord.backend.impl.clickhouse.mixins.update import (
            ClickHouseUpdateMixin,
        )

        assert (
            ClickHouseUpdateMixin.QUALIFIED_MUTATION_COLUMN_VERSION == (26, 7, 0)
        )


class TestFilterRendering:
    """The filter renders qualified or bare, matching the server."""

    @pytest.mark.parametrize("version,expected", SUPPORTED)
    def test_filter_qualification_follows_gate(self, version, expected):
        dialect = ClickHouseDialect(version=version)
        sql = _update(dialect).to_sql()[0]
        if expected:
            assert "`tasks`.`id`" in sql, (
                "26.7 resolves the qualifier itself, so the column must keep "
                f"its table: {sql}"
            )
        else:
            assert "`id`" in sql and "`tasks`.`id`" not in sql, (
                "below 26.7 the mutation engine reads a qualified column as one "
                f"identifier and fails, so the filter must be bare: {sql}"
            )

    @pytest.mark.parametrize("version,_expected", SUPPORTED)
    def test_table_is_still_qualified(self, version, _expected):
        """Only the filter loses the qualifier; the target keeps it."""
        dialect = ClickHouseDialect(version=version)
        sql = _update(dialect).to_sql()[0]
        assert sql.startswith("UPDATE `tasks`"), sql

    @pytest.mark.parametrize("version,_expected", SUPPORTED)
    def test_assignment_and_params_survive(self, version, _expected):
        """Rebuilding the expression must not disturb the SET clause or params."""
        dialect = ClickHouseDialect(version=version)
        sql, params = _update(dialect).to_sql()
        assert "`deleted_at` = %s" in sql, sql
        assert params == (None, 1), params


class TestCompoundFilters:
    """Every Column in a filter loses its qualifier, not just the first.

    A restore() on a composite primary key builds a conjunction, so a fix that
    only handled one comparison would pass the single-column tests and still
    fail there.
    """

    @pytest.mark.parametrize("version,_expected", SUPPORTED)
    def test_conjunction_is_unqualified(self, version, _expected):
        dialect = ClickHouseDialect(version=version)
        where = (Column(dialect, "tenant", table="tasks") == Literal(dialect, 9)) & (
            Column(dialect, "id", table="tasks") == Literal(dialect, 1)
        )
        expr = UpdateExpression(
            dialect,
            table=TableExpression(dialect, "tasks"),
            assignments={"deleted_at": Literal(dialect, None)},
            where=where,
        )
        sql = expr.to_sql()[0]
        if dialect.supports_update_column_qualification():
            assert sql.count("`tasks`.") == 2, sql
        else:
            assert "`tasks`.`" not in sql.split("WHERE", 1)[1], sql
            assert "`tenant`" in sql and "`id`" in sql, sql

    @pytest.mark.parametrize("version,_expected", SUPPORTED)
    def test_function_over_qualified_column_is_unqualified(self, version, _expected):
        """A column inside a function call is rewritten too."""
        from rhosocial.activerecord.backend.expression.core import FunctionCall

        dialect = ClickHouseDialect(version=version)
        call = FunctionCall(dialect, "length", Column(dialect, "name", table="tasks"))
        expr = UpdateExpression(
            dialect,
            table=TableExpression(dialect, "tasks"),
            assignments={"deleted_at": Literal(dialect, None)},
            where=call > Literal(dialect, 3),
        )
        sql = expr.to_sql()[0]
        where_part = sql.split("WHERE", 1)[1]
        if dialect.supports_update_column_qualification():
            assert "`tasks`.`name`" in where_part, sql
        else:
            assert "`tasks`." not in where_part, sql
            assert "`name`" in where_part, sql


class TestColumnWithoutTable:
    """A Column with no table is left alone -- there is nothing to strip."""

    @pytest.mark.parametrize("version,_expected", SUPPORTED)
    def test_bare_column_unchanged(self, version, _expected):
        dialect = ClickHouseDialect(version=version)
        expr = UpdateExpression(
            dialect,
            table=TableExpression(dialect, "tasks"),
            assignments={"deleted_at": Literal(dialect, None)},
            where=Column(dialect, "id") == Literal(dialect, 1),
        )
        assert "`id`" in expr.to_sql()[0]

class TestEveryPredicateShape:
    """Each predicate a filter can be built from loses the qualifier.

    Enumerated rather than sampled: a rewrite that handled ComparisonPredicate
    alone would satisfy the tests above and still emit a qualified column for
    these, which the server rejects.
    """

    @pytest.mark.parametrize("version,qualified", SUPPORTED)
    def test_all_predicate_kinds(self, version, qualified):
        from rhosocial.activerecord.backend.expression.core import FunctionCall
        from rhosocial.activerecord.backend.expression.predicates import (
            BetweenPredicate,
            InPredicate,
            LikePredicate,
            LogicalPredicate,
        )

        dialect = ClickHouseDialect(version=version)

        def col(name):
            return Column(dialect, name, table="tasks")

        cases = {
            "like": LikePredicate(dialect, "LIKE", col("name"), Literal(dialect, "x")),
            "in": InPredicate(dialect, col("state"), Literal(dialect, ["a", "b"])),
            "between": BetweenPredicate(
                dialect, col("age"), Literal(dialect, 1), Literal(dialect, 9)
            ),
            "and": LogicalPredicate(
                dialect, "AND", col("a") == Literal(dialect, 1), col("b") == Literal(dialect, 2)
            ),
            "or": LogicalPredicate(
                dialect, "OR", col("a") == Literal(dialect, 1), col("b") == Literal(dialect, 2)
            ),
            "not": LogicalPredicate(dialect, "NOT", col("a") == Literal(dialect, 1)),
            "function": FunctionCall(dialect, "length", col("name")) > Literal(dialect, 3),
            "in_list": col("state") == Literal(dialect, ["a"]),
        }
        for kind, where in cases.items():
            expr = UpdateExpression(
                dialect,
                table=TableExpression(dialect, "tasks"),
                assignments={"deleted_at": Literal(dialect, None)},
                where=where,
            )
            sql, params = expr.to_sql()
            where_part = sql.split("WHERE", 1)[1]
            if qualified:
                assert "`tasks`." in where_part, f"{kind}: {sql}"
            else:
                assert "`tasks`." not in where_part, f"{kind}: {sql}"
            # The SET clause and its parameter must survive every rebuild.
            assert "`deleted_at` = %s" in sql, f"{kind}: {sql}"
            assert params[0] is None, f"{kind}: {params}"

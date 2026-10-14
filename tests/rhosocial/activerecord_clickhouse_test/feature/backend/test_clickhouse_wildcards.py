# tests/rhosocial/activerecord_clickhouse_test/feature/backend/test_clickhouse_wildcards.py
"""ClickHouse's wildcard positions, in the two contracts core split apart.

Core split the asterisk by grammar position (spec 4.10): the select-list ``*``
expands columns and belongs to ``AllColumnsWildcard``, while ``COUNT(*)``'s
asterisk counts rows and belongs to ``RowCountWildcard``.  Each position names
its own formatter, so a dialect overrides the one whose *spelling* differs.

ClickHouse differs in the row-count position only, and in one way:
``COUNT(DISTINCT *)`` counts the distinct combinations of every column's value
where ``COUNT(*)`` counts the rows.  Of the eleven backends the wildcard survey
measured, only ClickHouse accepts it, so it is this backend's own node
(:class:`ClickHouseRowCountDistinctWildcard`) and this backend's own
``format_row_count_wildcard`` override.

**Evidence level: documented, not re-measured.**  The ``COUNT(DISTINCT *)``
spelling is a documented ClickHouse extension and the verdict the survey
records for this backend; no ClickHouse instance is reachable from this
worktree, so what the assertions below verify is the *rendering contract* --
which node renders which words -- rather than the server's acceptance.
"""

import pytest

from rhosocial.activerecord.backend.expression import (
    AllColumnsWildcard,
    Column,
    RowCountWildcard,
)
from rhosocial.activerecord.backend.expression.core import FunctionCall
from rhosocial.activerecord.backend.expression.functions.aggregate import count, sum_
from rhosocial.activerecord.backend.expression.objects import Table
from rhosocial.activerecord.backend.expression.sources import NamedRelationRef
from rhosocial.activerecord.backend.impl.clickhouse.dialect import ClickHouseDialect
from rhosocial.activerecord.backend.impl.clickhouse.mixins.wildcard import (
    ClickHouseWildcardMixin,
)


@pytest.fixture
def dialect():
    return ClickHouseDialect()


class TestAllColumnsPosition:
    """The select-list ``*`` is core's verbatim, so nothing is overridden."""

    def test_bare_asterisk(self, dialect):
        assert AllColumnsWildcard(dialect).to_sql() == ("*", ())

    def test_qualified_asterisk_uses_the_query_s_spelling(self, dialect):
        """The qualifier is the name the query itself uses -- core's rule."""
        wc = AllColumnsWildcard(
            dialect,
            relation=NamedRelationRef(dialect, Table(dialect, "users"), alias="u"),
        )
        assert wc.to_sql() == ("`u`.*", ())

    def test_clickhouse_does_not_override_the_all_columns_formatter(self):
        """ClickHouse spells ``*`` / ``rel.*`` exactly as core does.

        Asserted on the class rather than by rendering, because the point is
        that no override exists: a future override would make the two spellings
        need keeping in step, and this test is where that decision would have to
        be recorded.
        """
        assert "format_all_columns_wildcard" not in ClickHouseWildcardMixin.__dict__


class TestRowCountPosition:
    """The row-count position is the one ClickHouse spells differently."""

    def test_bare_asterisk_is_core_s(self, dialect):
        """``COUNT(*)`` stays core's bare asterisk -- the override delegates."""
        assert RowCountWildcard(dialect).to_sql() == ("*", ())

    def test_count_of_the_bare_asterisk_is_unchanged(self, dialect):
        assert count(dialect, "*").to_sql() == ("COUNT(*)", ())

    def test_distinct_asterisk_is_this_backend_s_node(self, dialect):
        """``COUNT(DISTINCT *)`` is ClickHouse-only, so it is ClickHouse's node."""
        from rhosocial.activerecord.backend.impl.clickhouse.expression import (
            ClickHouseRowCountDistinctWildcard,
        )

        wc = ClickHouseRowCountDistinctWildcard(dialect)
        assert wc.to_sql() == ("DISTINCT *", ())

    def test_the_distinct_spelling_reaches_the_aggregate(self, dialect):
        """The full statement, through the flag the aggregate carries.

        Core's shared ``format_function_call`` answers a row-count wildcard with
        the asterisk and takes the ``DISTINCT`` from the call's own
        ``is_distinct``; so the complete spelling is reached through the
        factory's keyword rather than through the argument alone.  That core
        short-circuit is recorded against the PostgreSQL and Snowflake
        row-count wildcards too.
        """
        assert count(dialect, "*", is_distinct=True).to_sql() == (
            "COUNT(DISTINCT *)",
            (),
        )
        assert count(
            dialect, "*", is_distinct=True, alias="n"
        ).to_sql() == ("COUNT(DISTINCT *) AS `n`", ())

    def test_the_node_is_a_row_count_wildcard(self, dialect):
        """It extends core's node, so it is admissible wherever that one is."""
        from rhosocial.activerecord.backend.impl.clickhouse.expression import (
            ClickHouseRowCountDistinctWildcard,
        )

        assert issubclass(ClickHouseRowCountDistinctWildcard, RowCountWildcard)

    def test_the_override_is_reached_before_core(self):
        """The mixin must precede ``ExpressionMixin`` in the MRO.

        C3 gives the earlier name in the dialect's base list priority. Listed
        after ``ExpressionMixin``, this override would never be consulted: the
        node would still render, as core's bare ``*``, and nothing about the SQL
        would look wrong until the server returned a different number.
        """
        from rhosocial.activerecord.backend.dialect.mixins.expression import (
            ExpressionMixin,
        )

        mro = ClickHouseDialect.__mro__
        assert mro.index(ClickHouseWildcardMixin) < mro.index(ExpressionMixin)


class TestTheCountContractIsUnchanged:
    """Core's aggregate contract, asserted here because it is what the node relies on.

    ``RowCountWildcard`` -- and so its ClickHouse derivative -- is admissible
    only as ``COUNT``'s argument: ``COUNT`` refuses the all-columns wildcard
    (it expands columns rather than counting rows) and the other aggregates
    refuse every wildcard.  None of that is this backend's to change; the
    assertions record the contract the node is built against.
    """

    def test_count_refuses_the_all_columns_wildcard(self, dialect):
        with pytest.raises(ValueError, match="all-columns wildcard"):
            count(dialect, AllColumnsWildcard(dialect))

    @pytest.mark.parametrize("factory", [sum_])
    def test_the_other_aggregates_refuse_a_row_count_wildcard(self, dialect, factory):
        with pytest.raises(ValueError, match="row-count wildcard"):
            factory(dialect, RowCountWildcard(dialect))

    def test_count_accepts_a_column(self, dialect):
        assert count(dialect, Column(dialect, "a")).to_sql() == ("COUNT(`a`)", ())

    def test_a_plain_function_call_can_hold_the_node(self, dialect):
        """The node renders wherever a value is expected, not only via ``count``."""
        from rhosocial.activerecord.backend.impl.clickhouse.expression import (
            ClickHouseRowCountDistinctWildcard,
        )

        call = FunctionCall(
            dialect, "COUNT", ClickHouseRowCountDistinctWildcard(dialect)
        )
        assert call.to_sql() == ("COUNT(*)", ())

# tests/rhosocial/activerecord_clickhouse_test/feature/backend/test_clause_pair_guard.py
"""Guard: every two-spelling clause ClickHouse consumes keeps its four states
distinguishable.

The round's rule (the same one core's ``test_clause_pair_guard.py`` enforces):
each spellable alternative has its own parameter; "unspecified" is the state
where none of a pair's parameters is set; setting both is API misuse and
raises ``ValueError`` at construction. For every pair *this dialect consumes*,
the four states must be pairwise distinguishable:

============================  =============================================
neither parameter             the dialect's spelling of "no modifier"
parameter A                   A's spelling rendered, or refused by name
parameter B                   B's spelling rendered, or refused by name
both parameters               ``ValueError``
============================  =============================================

ClickHouse has no form for several of the spellings, so for those the faithful
outcome is a refusal *by name* -- never a silent drop, and never SQL the
server rejects. A pair whose formatter ignores one of the parameters fails
here because that state becomes indistinguishable from another.

The refusal is asserted through ``UnsupportedFeatureError.feature_name``,
which names the exact spelling, so a refusal for an unrelated reason fails
instead of passing quietly.

**Live measurements.** Every "no spelling" verdict below was measured against
ClickHouse 26.7.3.19 over the HTTP interface (``.claude/plan/2026-10-07/
live_measure.txt``), bracketed by two sentinels: a deliberately invalid
statement was REJECTED and ``SELECT 1`` was ACCEPTED, so a transport failure
cannot masquerade as a verdict. The rejected spellings: ``DROP VIEW`` /
``DROP TABLE`` / ``DROP DATABASE`` CASCADE and RESTRICT (Code 62),
``TRUNCATE`` CASCADE / RESTRICT / RESTART IDENTITY / CONTINUE IDENTITY
(Code 62), ``CREATE TABLE ... WITH [NO] DATA`` and ``CREATE MATERIALIZED VIEW
... WITH [NO] DATA`` (Code 62), ``REFRESH MATERIALIZED VIEW`` (Code 62), and
CTE ``AS NOT MATERIALIZED`` (Code 62). Accepted: CTE ``AS MATERIALIZED``,
``UNION ALL``, ``UNION DISTINCT``.

**The one exception** is the set-operation qualifier, whose grammar has no
bare form with the server's default ``union_default_mode`` (bare ``UNION`` is
Code 558). :class:`TestSetOperationQualifier` asserts that mapping explicitly
instead of the generic four-state check.

**The four master probes core's gate round consults.** Core now consults
``supports_materialized_cte()`` in every ``format_cte_clause``,
``supports_truncate()`` in ``format_truncate_statement``, and the new
``supports_with_data_clause()`` in the CTAS / CREATE MATERIALIZED VIEW /
REFRESH MATERIALIZED VIEW renderers; the wait pair added to the two
transaction expressions is gated by the new ``supports_transaction_wait()``.
Measured live over the same HTTP interface
(``.claude/plan/2026-10-07/probe_measure_out.txt``, bracketed by the two
sentinels): ``WITH c AS MATERIALIZED`` ACCEPTED (with and without
``enable_materialized_cte=1``), ``AS NOT MATERIALIZED`` Code 62 even with the
setting; ``CREATE TABLE ... ENGINE = Memory`` + ``TRUNCATE TABLE``
end-to-end ACCEPTED (count 1 -> 0); ``WITH [NO] DATA`` on CTAS and MV create
Code 62, ``REFRESH MATERIALIZED VIEW`` Code 62; ``BEGIN TRANSACTION`` Code 48
(NOT_IMPLEMENTED), ``SET TRANSACTION`` only accepts ``SNAPSHOT``, and both
``WAIT`` and ``NO WAIT`` spellings are Code 62.
:class:`TestCoreGatedMasterProbes` pins this dialect's declarations,
:class:`TestWaitPairRefusesByName` pins that the pair is refused by name
rather than dropped.

Run red first: this file was run against the unmodified tree before any
formatter was changed; the failing ids are recorded in the round's report.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Optional, Tuple

import pytest

from rhosocial.activerecord.backend.dialect.exceptions import UnsupportedFeatureError
from rhosocial.activerecord.backend.expression.core import Column
from rhosocial.activerecord.backend.expression.objects import (
    MaterializedView,
    Table,
    View,
)
from rhosocial.activerecord.backend.expression.query_sources import (
    CTEClause,
    SetOperation,
)
from rhosocial.activerecord.backend.expression.statements.ddl_table import (
    CreateTableAsStatement,
    DropTableStatement,
)
from rhosocial.activerecord.backend.expression.statements.ddl_truncate import (
    TruncateStatement,
)
from rhosocial.activerecord.backend.expression.statements.ddl_view import (
    CreateMaterializedViewStatement,
    DropMaterializedViewStatement,
    DropViewStatement,
    RefreshMaterializedViewStatement,
)
from rhosocial.activerecord.backend.expression.statements.dql import (
    QueryStatement,
)
from rhosocial.activerecord.backend.expression.transaction import (
    BeginTransactionStatement,
    SetTransactionExpression,
)
from rhosocial.activerecord.backend.impl.clickhouse.dialect import ClickHouseDialect


def _dialect() -> ClickHouseDialect:
    return ClickHouseDialect(version=(26, 7, 3, 19))


def _table(d: ClickHouseDialect, name: str = "t") -> Table:
    return Table(d, name)


def _query(d: ClickHouseDialect) -> QueryStatement:
    return QueryStatement(d, select=[Column(d, "id")], from_=_table(d))


def _union(d: ClickHouseDialect, op: str = "union") -> SetOperation:
    return SetOperation(
        d,
        op=op,
        left=QueryStatement(d, select=[Column(d, "a")], from_=_table(d, "t1")),
        right=QueryStatement(d, select=[Column(d, "a")], from_=_table(d, "t2")),
    )


def _generic_mv_with_target(d: ClickHouseDialect, **kw: Any) -> Any:
    """A generic CREATE MATERIALIZED VIEW carrying the ClickHouse TO target.

    The generic node has no ``to_table``/``engine`` fields; the ClickHouse
    formatter reads them through ``getattr``. Setting them on the instance
    simulates the subclass that has them, so the with-data check is reached
    with the rest of the statement valid -- otherwise the "neither" state
    would be refused for the missing target and the pair could not be
    observed at all.
    """
    expr = CreateMaterializedViewStatement(
        d, MaterializedView(d, "mv"), _query(d), **kw
    )
    expr.to_table = _table(d, "target")
    return expr


#: One state's expected outcome: rendered SQL, or a refusal naming the spelling.
@dataclass(frozen=True)
class Expected:
    sql: Optional[str] = None
    refused_as: Optional[str] = None

    def __post_init__(self) -> None:
        assert (self.sql is None) != (self.refused_as is None), (
            "a state is either rendered or refused by name"
        )


@dataclass(frozen=True)
class PairCase:
    case_id: str
    builder: Callable[..., Any]
    a_name: str
    b_name: str
    neither: Expected
    a: Expected
    b: Expected


def _case(
    case_id: str,
    builder: Callable[..., Any],
    a_name: str,
    b_name: str,
    neither: Expected,
    a: Expected,
    b: Expected,
) -> PairCase:
    return PairCase(case_id, builder, a_name, b_name, neither, a, b)


#: The pairs this dialect consumes, in the formatters that read them.
#: Pairs whose whole statement is refused (sequences, identity, schema,
#: routines, UNPIVOT, transactions, ALTER CONSTRAINT) are out of scope: the
#: refusal happens before the pair is read, so no state is silently dropped.
PAIR_CASES: Tuple[PairCase, ...] = (
    _case(
        "TruncateStatement.cascade",
        lambda d, **kw: TruncateStatement(d, _table(d), **kw),
        "cascade",
        "restrict",
        Expected(sql="TRUNCATE TABLE `t`"),
        Expected(refused_as="TRUNCATE ... CASCADE"),
        Expected(refused_as="TRUNCATE ... RESTRICT"),
    ),
    _case(
        "TruncateStatement.restart_identity",
        lambda d, **kw: TruncateStatement(d, _table(d), **kw),
        "restart_identity",
        "continue_identity",
        Expected(sql="TRUNCATE TABLE `t`"),
        Expected(refused_as="TRUNCATE ... RESTART IDENTITY"),
        Expected(refused_as="TRUNCATE ... CONTINUE IDENTITY"),
    ),
    _case(
        "DropTableStatement.cascade",
        lambda d, **kw: DropTableStatement(d, _table(d), **kw),
        "cascade",
        "restrict",
        Expected(sql="DROP TABLE `t`"),
        Expected(refused_as="DROP TABLE ... CASCADE"),
        Expected(refused_as="DROP TABLE ... RESTRICT"),
    ),
    _case(
        "DropViewStatement.cascade",
        lambda d, **kw: DropViewStatement(d, View(d, "v"), **kw),
        "cascade",
        "restrict",
        Expected(sql="DROP VIEW `v`"),
        Expected(refused_as="DROP VIEW CASCADE"),
        Expected(refused_as="DROP VIEW RESTRICT"),
    ),
    _case(
        "DropMaterializedViewStatement.cascade",
        lambda d, **kw: DropMaterializedViewStatement(
            d, MaterializedView(d, "mv"), **kw
        ),
        "cascade",
        "restrict",
        Expected(sql="DROP VIEW `mv`"),
        Expected(refused_as="DROP MATERIALIZED VIEW CASCADE"),
        Expected(refused_as="DROP MATERIALIZED VIEW RESTRICT"),
    ),
    _case(
        "RefreshMaterializedViewStatement.with_data",
        lambda d, **kw: RefreshMaterializedViewStatement(
            d, MaterializedView(d, "mv"), **kw
        ),
        "with_data",
        "no_data",
        Expected(sql="SYSTEM REFRESH VIEW `mv`"),
        Expected(refused_as="REFRESH MATERIALIZED VIEW WITH DATA"),
        Expected(refused_as="REFRESH MATERIALIZED VIEW WITH NO DATA"),
    ),
    _case(
        "CreateMaterializedViewStatement.with_data",
        _generic_mv_with_target,
        "with_data",
        "no_data",
        Expected(
            sql=(
                "CREATE MATERIALIZED VIEW `mv` TO `target` "
                "AS SELECT `id` FROM `t`"
            )
        ),
        Expected(refused_as="CREATE MATERIALIZED VIEW WITH DATA"),
        Expected(refused_as="CREATE MATERIALIZED VIEW WITH NO DATA"),
    ),
    _case(
        "CreateTableAsStatement.with_data",
        lambda d, **kw: CreateTableAsStatement(d, _table(d), _query(d), **kw),
        "with_data",
        "no_data",
        Expected(sql="CREATE TABLE `t` AS SELECT `id` FROM `t`"),
        Expected(refused_as="CREATE TABLE ... WITH DATA"),
        Expected(refused_as="CREATE TABLE ... WITH NO DATA"),
    ),
    _case(
        "CTEClause.materialized",
        lambda d, **kw: CTEClause(d, "c", _query(d), **kw),
        "materialized",
        "not_materialized",
        Expected(sql="`c` AS (SELECT `id` FROM `t`)"),
        Expected(sql="`c` AS MATERIALIZED (SELECT `id` FROM `t`)"),
        Expected(refused_as="CTE NOT MATERIALIZED"),
    ),
)

PAIR_IDS = [case.case_id for case in PAIR_CASES]

#: Every consumed pair. The set operation is deliberately absent: its
#: qualifier is no longer a boolean pair at all. ``all_`` / ``distinct`` are
#: gone with the trailing clauses, and the ALL/DISTINCT choice is now carried by
#: the ``union`` / ``union_all`` operation word -- a closed word set the node
#: validates at construction, not two flags that could be set independently.
#: ``TestSetOperationSpelling`` guards that mapping instead.
ALL_CONSUMED_PAIRS = frozenset(PAIR_IDS)


def _render(case: PairCase, **kwargs: Any) -> Tuple[str, str]:
    """Return ``(kind, detail)``: rendered SQL, a refusal name, or the ValueError."""
    d = _dialect()
    try:
        sql, _params = case.builder(d, **kwargs).to_sql()
    except UnsupportedFeatureError as exc:
        return "refused", exc.feature_name
    except ValueError as exc:
        return "ValueError", str(exc)
    return "rendered", sql


def _assert_state(case: PairCase, expected: Expected, **kwargs: Any) -> str:
    kind, detail = _render(case, **kwargs)
    if expected.sql is not None:
        assert kind == "rendered", (
            f"{case.case_id}: expected the render {expected.sql!r}, "
            f"got {kind}: {detail}"
        )
        assert detail == expected.sql, (
            f"{case.case_id}: rendered SQL differs.\n"
            f"  expected: {expected.sql!r}\n"
            f"  actual:   {detail!r}"
        )
    else:
        assert kind == "refused", (
            f"{case.case_id}: expected a refusal naming "
            f"{expected.refused_as!r}, got {kind}: {detail}"
        )
        assert detail == expected.refused_as, (
            f"{case.case_id}: refusal names the wrong spelling.\n"
            f"  expected: {expected.refused_as!r}\n"
            f"  actual:   {detail!r}"
        )
    return f"{kind}:{detail}"


class TestFourStatesArePairwiseDistinguishable:
    """Every state of every consumed pair produces its own outcome."""

    @pytest.mark.parametrize("case", PAIR_CASES, ids=PAIR_IDS)
    def test_neither_set_renders_the_dialect_default(self, case):
        _assert_state(case, case.neither)

    @pytest.mark.parametrize("case", PAIR_CASES, ids=PAIR_IDS)
    def test_a_set_is_distinguishable(self, case):
        _assert_state(case, case.a, **{case.a_name: True})

    @pytest.mark.parametrize("case", PAIR_CASES, ids=PAIR_IDS)
    def test_b_set_is_distinguishable(self, case):
        _assert_state(case, case.b, **{case.b_name: True})

    @pytest.mark.parametrize("case", PAIR_CASES, ids=PAIR_IDS)
    def test_both_set_is_refused(self, case):
        d = _dialect()
        with pytest.raises(
            ValueError, match=f"{case.a_name} and {case.b_name} are mutually exclusive"
        ):
            case.builder(d, **{case.a_name: True, case.b_name: True})

    @pytest.mark.parametrize("case", PAIR_CASES, ids=PAIR_IDS)
    def test_all_four_outcomes_are_pairwise_distinct(self, case):
        outcomes = [
            _render(case),
            _render(case, **{case.a_name: True}),
            _render(case, **{case.b_name: True}),
        ]
        both = _render(case, **{case.a_name: True, case.b_name: True})
        assert both[0] == "ValueError", both
        outcomes.append(both)
        assert len(set(outcomes)) == 4, (
            f"{case.case_id}: two of the four states are indistinguishable: "
            f"{outcomes}"
        )


class TestSetOperationSpelling:
    """The four operation words and the spelling each one gets here.

    ClickHouse's grammar has no bare UNION under the default
    ``union_default_mode`` (measured: ``Code: 558. Expected ALL or DISTINCT in
    SelectWithUnion query``), so every rendering carries an explicit ALL or
    DISTINCT. The node names the operation with a word and the dialect maps it,
    which is what makes ``union`` and ``union_all`` distinguishable here: they
    differ by the modifier, not only by the keyword.

    The former ``all_`` / ``distinct`` flag pair is gone, so the collision this
    class used to record -- "unspecified" and "explicit DISTINCT" rendering
    identically -- cannot occur: the word set has no duplicate member, and the
    node refuses anything outside it at construction.
    """

    def test_union_spells_distinct(self):
        sql, _ = _union(_dialect()).to_sql()
        assert sql == (
            "SELECT `a` FROM `t1` UNION DISTINCT SELECT `a` FROM `t2`"
        ), sql

    def test_union_all_spells_all(self):
        sql, _ = _union(_dialect(), "union_all").to_sql()
        assert sql == "SELECT `a` FROM `t1` UNION ALL SELECT `a` FROM `t2`", sql

    def test_the_two_union_words_are_distinguishable(self):
        assert _union(_dialect()).to_sql()[0] != _union(_dialect(), "union_all").to_sql()[0]

    def test_intersect_and_except_keep_the_required_modifier(self):
        """The same required-default mapping applies to every set operation."""
        d = _dialect()
        for op, expected in (
            ("intersect", "INTERSECT DISTINCT"),
            ("except", "EXCEPT DISTINCT"),
        ):
            expr = _union(d, op)
            sql, _ = expr.to_sql()
            assert expected in sql, (op, sql)

    def test_the_word_is_case_insensitive_and_normalized(self):
        d = _dialect()
        expr = _union(d, "UNION_ALL")
        assert expr.op == "union_all"
        assert "UNION ALL" in expr.to_sql()[0]

    def test_every_operation_word_is_covered_and_distinct(self):
        """Each word renders its own SQL, and no bare form is ever emitted."""
        d = _dialect()
        rendered = {}
        for op in ("union", "union_all", "intersect", "except"):
            sql, _ = _union(d, op).to_sql()
            rendered[op] = sql
            keyword = sql.split(" FROM `t1` ")[1].split(" SELECT")[0]
            assert "ALL" in keyword or "DISTINCT" in keyword, (op, sql)
        assert len(set(rendered.values())) == 4, rendered

    def test_an_unknown_operation_word_is_refused(self):
        with pytest.raises(ValueError, match="op must be one of"):
            _union(_dialect(), "minus")


class TestGuardIsNotVacuous:
    """Guards so the checks above cannot pass by accident."""

    def test_every_case_has_two_distinct_parameters(self):
        for case in PAIR_CASES:
            assert case.a_name != case.b_name, case.case_id

    def test_every_pair_is_covered(self):
        """The pairs this dialect consumes are all in the table."""
        expected = {
            "TruncateStatement.cascade",
            "TruncateStatement.restart_identity",
            "DropTableStatement.cascade",
            "DropViewStatement.cascade",
            "DropMaterializedViewStatement.cascade",
            "RefreshMaterializedViewStatement.with_data",
            "CreateMaterializedViewStatement.with_data",
            "CreateTableAsStatement.with_data",
            "CTEClause.materialized",
        }
        assert expected == ALL_CONSUMED_PAIRS, (
            f"pairs in scope but not guarded: "
            f"{sorted(expected - ALL_CONSUMED_PAIRS)}; "
            f"guarded but not in scope: "
            f"{sorted(ALL_CONSUMED_PAIRS - expected)}"
        )

    def test_the_distinguishability_check_rejects_a_fabricated_collision(self):
        """A checker that cannot see a collision makes every verdict vacuous.

        The fabricated case is built by hand rather than borrowed from the
        table: its builder ignores which flag was set and renders the same SQL
        for all three renderable states, refusing only the fourth. Two of the
        outcomes therefore collide, so a checker that claimed pairwise
        distinguishability here would be lying. (It cannot be borrowed from the
        table: the set operation used to be the one real collision on this
        dialect, and the word-form rewrite made it fully distinguishable.)
        """
        union_sql = "SELECT `a` FROM `t1` UNION DISTINCT SELECT `a` FROM `t2`"

        def _colliding(d: ClickHouseDialect, **kw: Any) -> Any:
            if sum(bool(v) for v in kw.values()) > 1:
                raise ValueError("a_set and b_set are mutually exclusive")
            return _union(d)

        fabricated = _case(
            "fabricated",
            _colliding,
            "a_set",
            "b_set",
            Expected(sql=union_sql),
            Expected(sql=union_sql),
            Expected(sql=union_sql),
        )
        outcomes = [
            _render(fabricated),
            _render(fabricated, a_set=True),
            _render(fabricated, b_set=True),
        ]
        assert len(set(outcomes)) == 1, (
            "the sentinel is expected to collide; if it does not, this guard's "
            "distinguishability assertion is not testing what it claims"
        )
        both = _render(fabricated, a_set=True, b_set=True)
        assert both[0] == "ValueError", both
        assert len(set(outcomes) | {both}) != 4, (
            "a colliding pair must not yield four distinct outcomes"
        )


class TestProbesMatchTheMeasuredGrammar:
    """The probes the consumed pairs consult answer the measured capability."""

    def test_drop_table_probes_are_false(self):
        d = _dialect()
        assert d.supports_drop_table_cascade() is False
        assert d.supports_drop_table_restrict() is False

    def test_truncate_probes_are_false(self):
        d = _dialect()
        assert d.supports_truncate_restart_identity() is False
        assert d.supports_truncate_cascade() is False
        assert d.supports_truncate_restrict() is False

    def test_view_probes_are_false(self):
        d = _dialect()
        assert d.supports_cascade_view() is False
        assert d.supports_restrict_view() is False
        assert d.supports_materialized_view_restrict() is False

    def test_probe_owners_are_not_shadowed_by_core_defaults(self):
        """A core mixin earlier in the MRO must not answer for ClickHouse.

        ``supports_drop_table_cascade``/``restrict`` live on core's
        ``TableMixin``, which sits *after* ``ClickHouseTableMixin`` but
        *before* ``ClickHouseConstraintMixin``. Declared on the wrong mixin
        they are dead code and the formatter renders SQL the server rejects;
        this pins the owner that actually answers.
        """
        d = _dialect()
        for name in (
            "supports_drop_table_cascade",
            "supports_drop_table_restrict",
        ):
            owner = getattr(d, name).__qualname__
            assert owner == f"ClickHouseTableMixin.{name}", (
                f"{name} resolves to {owner}, so ClickHouse's answer is shadowed"
            )


class TestCoreGatedMasterProbes:
    """The master probes core's gate round reads, answered by this dialect.

    Each declaration below was measured live (see the module docstring); the
    owner assertions pin that ClickHouse answers, not a core default that
    happens to coincide. A core default flipping silently would change what
    this dialect claims without any ClickHouse change, which is exactly how
    ``supports_drop_table_cascade`` once rendered server-rejected DROP TABLE.
    """

    def test_materialized_cte_probe_is_true_and_materialized_renders(self):
        d = _dialect()
        assert d.supports_materialized_cte() is True
        owner = d.supports_materialized_cte.__qualname__
        assert owner == "ClickHouseCTEMixin.supports_materialized_cte"
        sql, _params = CTEClause(d, "c", _query(d), materialized=True).to_sql()
        assert sql == "`c` AS MATERIALIZED (SELECT `id` FROM `t`)"

    def test_materialized_cte_negative_spelling_is_refused_by_name(self):
        """``AS NOT MATERIALIZED`` is Code 62 on ClickHouse 26.7 (measured,
        including with ``enable_materialized_cte=1``); the grammar is
        ``AS [MATERIALIZED]``. Rendering it would be SQL the server rejects,
        so the by-name refusal is the faithful outcome."""
        d = _dialect()
        with pytest.raises(UnsupportedFeatureError) as excinfo:
            CTEClause(d, "c", _query(d), not_materialized=True).to_sql()
        assert excinfo.value.dialect_name == "ClickHouse"
        assert excinfo.value.feature_name == "CTE NOT MATERIALIZED"

    def test_truncate_probe_is_true_and_the_statement_renders(self):
        d = _dialect()
        assert d.supports_truncate() is True
        owner = d.supports_truncate.__qualname__
        assert owner == "ClickHouseTruncateMixin.supports_truncate"
        sql, _params = TruncateStatement(d, _table(d)).to_sql()
        assert sql == "TRUNCATE TABLE `t`"

    def test_with_data_clause_is_declared_false_by_this_dialect(self):
        """ClickHouse has no ``WITH [NO] DATA`` on any of the three consumers
        (measured: Code 62). The declaration is this dialect's own so a core
        default cannot answer for it."""
        d = _dialect()
        assert d.supports_with_data_clause() is False
        owner = d.supports_with_data_clause.__qualname__
        assert owner == "ClickHouseMaterializedViewMixin.supports_with_data_clause"

    def test_transaction_wait_is_declared_false_by_this_dialect(self):
        """ClickHouse has no WAIT / NO WAIT clause (measured: Code 62 for both
        spellings, while the bare statement is Code 48 / SNAPSHOT-only). The
        bare protocol stub answers ``None``; a dialected answer must be bool."""
        d = _dialect()
        assert d.supports_transaction_wait() is False
        owner = d.supports_transaction_wait.__qualname__
        assert owner == "ClickHouseTransactionMixin.supports_transaction_wait"

    def test_with_data_gate_refusals_are_this_dialects_own(self):
        """Every WITH [NO] DATA consumer is refused by a ClickHouse formatter
        with ClickHouse's own feature name and advice -- not by core's generic
        gate, whose feature would be the bare ``WITH DATA`` / ``WITH NO DATA``.
        """
        d = _dialect()
        cases = (
            (
                CreateTableAsStatement(d, _table(d), _query(d), with_data=True),
                "CREATE TABLE ... WITH DATA",
            ),
            (
                CreateTableAsStatement(d, _table(d), _query(d), no_data=True),
                "CREATE TABLE ... WITH NO DATA",
            ),
            (_generic_mv_with_target(d, with_data=True), "CREATE MATERIALIZED VIEW WITH DATA"),
            (_generic_mv_with_target(d, no_data=True), "CREATE MATERIALIZED VIEW WITH NO DATA"),
            (
                RefreshMaterializedViewStatement(d, MaterializedView(d, "mv"), with_data=True),
                "REFRESH MATERIALIZED VIEW WITH DATA",
            ),
            (
                RefreshMaterializedViewStatement(d, MaterializedView(d, "mv"), no_data=True),
                "REFRESH MATERIALIZED VIEW WITH NO DATA",
            ),
        )
        for expr, feature in cases:
            with pytest.raises(UnsupportedFeatureError) as excinfo:
                expr.to_sql()
            assert excinfo.value.dialect_name == "ClickHouse"
            assert excinfo.value.feature_name == feature
            suggestion = excinfo.value.suggestion or ""
            assert "ClickHouse" in suggestion, (
                f"{feature}: refusal advice is not ClickHouse's own: {suggestion!r}"
            )


class TestWaitPairRefusesByName:
    """``supports_transaction_wait()`` is False: the pair is refused by name.

    ``wait`` / ``no_wait`` are two spellings with one parameter each; with
    neither set the whole statement keeps its blanket refusal, and requesting
    either spelling refuses *that spelling* -- never renders a statement with
    the clause dropped.
    """

    @pytest.mark.parametrize(
        "expression_class",
        [BeginTransactionStatement, SetTransactionExpression],
        ids=["BeginTransactionStatement", "SetTransactionExpression"],
    )
    @pytest.mark.parametrize(
        "parameter,spelling", [("wait", "WAIT"), ("no_wait", "NO WAIT")]
    )
    def test_either_spelling_refuses_by_name(
        self, expression_class, parameter, spelling
    ):
        d = _dialect()
        with pytest.raises(UnsupportedFeatureError) as excinfo:
            expression_class(d, **{parameter: True}).to_sql()
        assert excinfo.value.dialect_name == "ClickHouse"
        assert excinfo.value.feature_name == f"transaction {spelling}"
        assert spelling in (excinfo.value.suggestion or "")

    @pytest.mark.parametrize(
        "expression_class",
        [BeginTransactionStatement, SetTransactionExpression],
        ids=["BeginTransactionStatement", "SetTransactionExpression"],
    )
    def test_neither_spelling_still_refuses_the_whole_statement(
        self, expression_class
    ):
        d = _dialect()
        with pytest.raises(UnsupportedFeatureError) as excinfo:
            expression_class(d).to_sql()
        assert excinfo.value.feature_name == "transactions"

    @pytest.mark.parametrize(
        "expression_class",
        [BeginTransactionStatement, SetTransactionExpression],
        ids=["BeginTransactionStatement", "SetTransactionExpression"],
    )
    def test_both_spellings_are_api_misuse(self, expression_class):
        d = _dialect()
        with pytest.raises(
            ValueError, match="wait and no_wait are mutually exclusive"
        ):
            expression_class(d, wait=True, no_wait=True)

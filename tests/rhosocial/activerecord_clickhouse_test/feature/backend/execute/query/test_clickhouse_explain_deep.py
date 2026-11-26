# tests/rhosocial/activerecord_clickhouse_test/feature/backend/execute/query/test_clickhouse_explain_deep.py
"""Backend-local, deep EXPLAIN tests for ClickHouse (synchronous only).

The shared testsuite only guarantees that an EXPLAIN clause can *run*. This
module interprets what ClickHouse actually returns, which is deliberately not
generalized into the testsuite because dialects disagree on plan shape:

* Capability gates. ``supports_explain_plan()`` is always True here;
  ``supports_explain_analyze()`` is version-gated (the ANALYZE keyword is only
  accepted from ClickHouse 26.7); the per-format switches recognise TEXT/JSON/
  TREE and reject XML/YAML/TRADITIONAL, and the generic EXPLAIN options
  (VERBOSE/COSTS/BUFFERS/TIMING/SETTINGS/WAL) are all unsupported.
* Rendering. ``format_explain_statement`` emits ``EXPLAIN <stmt>``, prefixes
  ``ANALYZE`` and ``FORMAT=<name>`` when requested, and preserves the inner
  statement's bind parameters. An unsupported option or format raises
  ``UnsupportedFeatureError`` instead of being rendered. Every statement here
  is an expression object; no hand-built SQL string is ever handed to the
  backend.
* Result interpretation. A real server returns rows exposing an ``explain``
  String column whose lines name plan nodes (``Output``, ``Filter`` /
  ``Prewhere filter``, ``ReadFromMergeTree`` / ``ReadFromStorage``).
  ``EXPLAIN ANALYZE`` adds a runtime header. The plan is read from the
  ``ClickHouseExplainResult`` returned by ``backend.explain()``.

ClickHouse is synchronous-only, so there is intentionally no async half.
"""

from typing import Any, Dict, List, Optional, Tuple

import pytest
from rhosocial.activerecord.backend.dialect.exceptions import UnsupportedFeatureError
from rhosocial.activerecord.backend.expression import (
    AllColumnsWildcard,
    Column,
    ColumnDefinition,
    ComparisonPredicate,
    CreateTableStatement,
    DropTableStatement,
    ExplainStatement,
    InsertStatement,
    Literal,
    QueryStatement,
    ValuesSource,
)
from rhosocial.activerecord.backend.expression.objects import Table
from rhosocial.activerecord.backend.expression.query_parts import WhereClause
from rhosocial.activerecord.backend.expression.sources import NamedRelationRef
from rhosocial.activerecord.backend.expression.statements import (
    ExplainFormat,
    ExplainOptions,
    ExplainType,
)
from rhosocial.activerecord.backend.expression.types import IntegerType

from rhosocial.activerecord.backend.impl.clickhouse.dialect import ClickHouseDialect
from rhosocial.activerecord.backend.impl.clickhouse.explain import ClickHouseExplainResult
from rhosocial.activerecord.backend.impl.clickhouse.expression import (
    ClickHouseCreateTableOptions,
    ClickHouseEngineSpec,
    ClickHouseStorageOptionKind,
    ClickHouseTableStorageOption,
)

_TABLE = "ch_explain_deep"
_BASE_SELECT = "SELECT * FROM `ch_explain_deep`"
_PARAM_SELECT = "SELECT `id` FROM `ch_explain_deep` WHERE `id` = %s"

# ClickHouse plan-node markers that identify a genuine, interpretable plan.
# Different server versions and table states name the leaf differently
# (``ReadFromStorage`` on older releases, ``ReadFromMergeTree`` on newer ones).
_PLAN_NODE_MARKERS = (
    "ReadFromMergeTree",
    "ReadFromStorage",
    "ReadFromMemory",
    "ReadNothing",
    "Expression",
    "Filter",
    "Output",
    "Aggregating",
)


def _query(
    dialect: ClickHouseDialect,
    condition: Optional[ComparisonPredicate] = None,
) -> QueryStatement:
    """A SELECT over the fixture table, built entirely from expression nodes."""
    kwargs: Dict[str, Any] = {}
    if condition is not None:
        kwargs["where"] = WhereClause(dialect, condition=condition)
    return QueryStatement(
        dialect,
        select=[AllColumnsWildcard(dialect)],
        from_=NamedRelationRef(dialect, Table(dialect, _TABLE)),
        **kwargs,
    )


def _render(
    dialect: ClickHouseDialect,
    options: Optional[ExplainOptions] = None,
    *,
    with_param: bool = False,
) -> Tuple[str, tuple]:
    """Render an EXPLAIN statement from expression nodes (no database needed)."""
    if with_param:
        query = QueryStatement(
            dialect,
            select=[Column(dialect, "id")],
            from_=NamedRelationRef(dialect, Table(dialect, _TABLE)),
            where=WhereClause(
                dialect,
                condition=ComparisonPredicate(
                    dialect, "=", Column(dialect, "id"), Literal(dialect, 42)
                ),
            ),
        )
    else:
        query = _query(dialect)
    return ExplainStatement(dialect, statement=query, options=options).to_sql()


def _plan_text(rows: List[Dict[str, Any]]) -> str:
    """Join every string cell of an opaque EXPLAIN result into searchable text."""
    lines: List[str] = []
    for row in rows:
        if not isinstance(row, dict):
            lines.append(str(row))
            continue
        for value in row.values():
            if value is not None:
                lines.append(str(value))
    return "\n".join(lines)


def _has_explain_column(rows: List[Dict[str, Any]]) -> bool:
    """Whether the opaque plan rows expose ClickHouse's ``explain`` column."""
    return any(isinstance(row, dict) and "explain" in row for row in rows)


def _drop_expr(dialect: ClickHouseDialect) -> DropTableStatement:
    return DropTableStatement(dialect=dialect, table=Table(dialect, _TABLE), if_exists=True)


def _create_expr(dialect: ClickHouseDialect) -> CreateTableStatement:
    """A ClickHouse MergeTree table, expressed with the backend's storage nodes."""
    return CreateTableStatement(
        dialect=dialect,
        table=Table(dialect, _TABLE),
        columns=[
            ColumnDefinition(dialect, "id", IntegerType(dialect)),
            ColumnDefinition(dialect, "age", IntegerType(dialect)),
        ],
        table_options=ClickHouseCreateTableOptions(
            dialect=dialect,
            table_storage_options=[
                ClickHouseTableStorageOption(
                    dialect,
                    ClickHouseStorageOptionKind.ENGINE,
                    value=ClickHouseEngineSpec(dialect, "MergeTree"),
                ),
                ClickHouseTableStorageOption(
                    dialect,
                    ClickHouseStorageOptionKind.ORDER_BY,
                    value=[Column(dialect, "id")],
                ),
            ],
        ),
    )


def _seed_expr(dialect: ClickHouseDialect) -> InsertStatement:
    rows = [[i, i * 7] for i in range(6)]
    return InsertStatement(
        dialect=dialect,
        into=Table(dialect, _TABLE),
        columns=["id", "age"],
        source=ValuesSource(dialect, [[Literal(dialect, value) for value in row] for row in rows]),
    )


class TestClickHouseExplainCapabilities:
    """Capability probes and SQL rendering -- no database connection required."""

    @pytest.fixture
    def dialect(self) -> ClickHouseDialect:
        return ClickHouseDialect(version=(26, 7, 3))

    def test_supports_explain_plan(self, dialect: ClickHouseDialect) -> None:
        assert dialect.supports_explain_plan() is True

    def test_supports_explain_analyze_is_version_gated(self, dialect: ClickHouseDialect) -> None:
        # ANALYZE is accepted from 26.7; older maintained lines reject it, and
        # a dialect that cannot name its version must not claim the capability.
        assert dialect.supports_explain_analyze() is True
        assert ClickHouseDialect(version=(26, 7, 0)).supports_explain_analyze() is True
        assert ClickHouseDialect(version=(26, 6, 9)).supports_explain_analyze() is False
        assert ClickHouseDialect(version=(25, 8, 1)).supports_explain_analyze() is False
        assert ClickHouseDialect().supports_explain_analyze() is False

    @pytest.mark.parametrize("fmt", [ExplainFormat.TEXT, ExplainFormat.JSON, ExplainFormat.TREE])
    def test_supported_explain_format_switches(
        self, dialect: ClickHouseDialect, fmt: ExplainFormat
    ) -> None:
        assert getattr(dialect, f"supports_explain_format_{fmt.value.lower()}")() is True

    @pytest.mark.parametrize(
        "fmt",
        [ExplainFormat.XML, ExplainFormat.YAML, ExplainFormat.TRADITIONAL],
    )
    def test_rejected_explain_format_switches(
        self, dialect: ClickHouseDialect, fmt: ExplainFormat
    ) -> None:
        assert getattr(dialect, f"supports_explain_format_{fmt.value.lower()}")() is False

    @pytest.mark.parametrize(
        "switch",
        [
            "supports_explain_verbose",
            "supports_explain_costs",
            "supports_explain_buffers",
            "supports_explain_timing",
            "supports_explain_settings",
            "supports_explain_wal",
        ],
    )
    def test_generic_explain_options_are_unsupported(
        self, dialect: ClickHouseDialect, switch: str
    ) -> None:
        assert getattr(dialect, switch)() is False

    def test_format_explain_statement_basic(self, dialect: ClickHouseDialect) -> None:
        sql, params = _render(dialect)
        assert sql == f"EXPLAIN {_BASE_SELECT}"
        assert params == ()

    def test_format_explain_statement_analyze(self, dialect: ClickHouseDialect) -> None:
        sql, _ = _render(dialect, ExplainOptions(analyze=True))
        assert sql == f"EXPLAIN ANALYZE {_BASE_SELECT}"

    def test_analyze_gate_drives_rendering(self, dialect: ClickHouseDialect) -> None:
        # The version gate reports whether ANALYZE is usable, and rendering
        # refuses the option when the dialect cannot name a version that
        # accepts it.
        assert dialect.supports_explain_analyze() is True
        sql, _ = _render(dialect, ExplainOptions(analyze=True))
        assert "ANALYZE" in sql
        old = ClickHouseDialect(version=(25, 8, 1))
        assert old.supports_explain_analyze() is False
        with pytest.raises(UnsupportedFeatureError):
            _render(old, ExplainOptions(analyze=True))

    def test_format_explain_statement_format_json(self, dialect: ClickHouseDialect) -> None:
        sql, _ = _render(dialect, ExplainOptions(format=ExplainFormat.JSON))
        assert sql == f"EXPLAIN FORMAT=JSON {_BASE_SELECT}"

    @pytest.mark.parametrize("fmt", [ExplainFormat.TEXT, ExplainFormat.JSON, ExplainFormat.TREE])
    def test_supported_formats_render_format_clause(
        self, dialect: ClickHouseDialect, fmt: ExplainFormat
    ) -> None:
        assert getattr(dialect, f"supports_explain_format_{fmt.value.lower()}")() is True
        sql, _ = _render(dialect, ExplainOptions(format=fmt))
        assert f"FORMAT={fmt.value}" in sql

    @pytest.mark.parametrize(
        "fmt",
        [ExplainFormat.XML, ExplainFormat.YAML, ExplainFormat.TRADITIONAL],
    )
    def test_unsupported_format_rendering_raises(
        self, dialect: ClickHouseDialect, fmt: ExplainFormat
    ) -> None:
        with pytest.raises(UnsupportedFeatureError):
            _render(dialect, ExplainOptions(format=fmt))

    @pytest.mark.parametrize(
        "options",
        [
            ExplainOptions(verbose=True),
            ExplainOptions(costs=False),
            ExplainOptions(buffers=True),
            ExplainOptions(timing=True),
            ExplainOptions(settings=True),
            ExplainOptions(wal=True),
        ],
        ids=["verbose", "costs", "buffers", "timing", "settings", "wal"],
    )
    def test_unsupported_options_raise(
        self, dialect: ClickHouseDialect, options: ExplainOptions
    ) -> None:
        with pytest.raises(UnsupportedFeatureError):
            _render(dialect, options)

    def test_query_plan_type_has_no_extra_clause(self, dialect: ClickHouseDialect) -> None:
        # ClickHouse has no QUERY_PLAN keyword; the option is accepted but maps
        # to a plain EXPLAIN, so the gate for EXPLAIN in general still holds.
        sql, _ = _render(dialect, ExplainOptions(type=ExplainType.QUERY_PLAN))
        assert sql == f"EXPLAIN {_BASE_SELECT}"
        assert "QUERY_PLAN" not in sql

    def test_analyze_and_format_combined(self, dialect: ClickHouseDialect) -> None:
        sql, _ = _render(
            dialect,
            ExplainOptions(analyze=True, format=ExplainFormat.JSON),
        )
        assert sql == f"EXPLAIN ANALYZE FORMAT=JSON {_BASE_SELECT}"

    def test_render_preserves_inner_params(self, dialect: ClickHouseDialect) -> None:
        sql, params = _render(dialect, with_param=True)
        assert sql == f"EXPLAIN {_PARAM_SELECT}"
        assert params == (42,)

    def test_to_sql_delegates_to_dialect_formatter(self, dialect: ClickHouseDialect) -> None:
        # ExplainStatement.to_sql() must reach the same ClickHouse formatter,
        # not the generic dialect mixin's PostgreSQL-style renderer.
        expr = ExplainStatement(
            dialect,
            statement=_query(dialect),
            options=ExplainOptions(analyze=True),
        )
        assert expr.to_sql() == dialect.format_explain_statement(expr)


@pytest.fixture
def indexed_backend(clickhouse_backend_single):
    """Sync backend with a small MergeTree table, built and cleaned via expressions."""
    backend = clickhouse_backend_single
    dialect = backend.dialect
    backend.execute(*_drop_expr(dialect).to_sql())
    backend.execute(*_create_expr(dialect).to_sql())
    backend.execute(*_seed_expr(dialect).to_sql())
    yield backend
    backend.execute(*_drop_expr(dialect).to_sql())


class TestClickHouseExplainDeep:
    """Interpret the EXPLAIN result from a real ClickHouse server (synchronous)."""

    @staticmethod
    def _gate(backend) -> None:
        if not backend.dialect.supports_explain_plan():
            pytest.skip("backend does not support EXPLAIN")

    def test_basic_plan_has_explain_column_and_plan_nodes(self, indexed_backend) -> None:
        self._gate(indexed_backend)
        result = indexed_backend.explain(_query(indexed_backend.dialect))
        assert isinstance(result, ClickHouseExplainResult)
        assert result.sql.upper().startswith("EXPLAIN")
        assert result.duration >= 0.0
        plan = result.raw_rows
        assert isinstance(plan, list) and plan, "EXPLAIN must return a non-empty row list"
        assert _has_explain_column(plan), "ClickHouse EXPLAIN rows expose an 'explain' column"
        text = _plan_text(plan)
        assert any(
            marker in text for marker in _PLAN_NODE_MARKERS
        ), f"expected a recognisable ClickHouse plan node in: {text!r}"

    def test_filter_predicate_shows_filter_node(self, indexed_backend) -> None:
        self._gate(indexed_backend)
        dialect = indexed_backend.dialect
        condition = ComparisonPredicate(dialect, ">", Column(dialect, "age"), Literal(dialect, 30))
        result = indexed_backend.explain(_query(dialect, condition=condition))
        text = _plan_text(result.raw_rows)
        # Older releases label the predicate node "WHERE"; newer ones surface a
        # Filter / Prewhere filter node. Either form proves it reached the plan.
        lowered = text.lower()
        assert (
            "filter" in lowered or "where" in lowered
        ), f"a WHERE predicate must surface filter/WHERE evidence: {text!r}"
        assert _has_explain_column(result.raw_rows)

    def test_primary_key_predicate_still_yields_a_plan(self, indexed_backend) -> None:
        self._gate(indexed_backend)
        dialect = indexed_backend.dialect
        condition = ComparisonPredicate(dialect, "=", Column(dialect, "id"), Literal(dialect, 1))
        result = indexed_backend.explain(_query(dialect, condition=condition))
        text = _plan_text(result.raw_rows)
        assert any(
            marker in text for marker in _PLAN_NODE_MARKERS
        ), f"expected a storage/scan node for a PK predicate: {text!r}"

    def test_explain_analyze_returns_runtime_summary_when_supported(self, indexed_backend) -> None:
        self._gate(indexed_backend)
        if not indexed_backend.dialect.supports_explain_analyze():
            pytest.skip("EXPLAIN ANALYZE requires ClickHouse >= 26.7")
        result = indexed_backend.explain(
            _query(indexed_backend.dialect), options=ExplainOptions(analyze=True)
        )
        assert result.sql.upper().startswith("EXPLAIN ANALYZE")
        plan = result.raw_rows
        assert isinstance(plan, list) and plan
        assert _has_explain_column(plan)
        text = _plan_text(plan)
        # ANALYZE prepends a live-run summary header to the plan tree.
        assert (
            "Query summary" in text or "Execution" in text or "Time:" in text
        ), f"expected an EXPLAIN ANALYZE runtime header: {text!r}"

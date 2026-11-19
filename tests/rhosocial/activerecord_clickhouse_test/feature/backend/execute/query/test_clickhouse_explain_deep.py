# tests/rhosocial/activerecord_clickhouse_test/feature/backend/execute/query/test_clickhouse_explain_deep.py
"""Backend-local, deep EXPLAIN tests for ClickHouse (synchronous only).

The shared testsuite only guarantees that an EXPLAIN clause can *run*. This
module interprets what ClickHouse actually returns, which is deliberately not
generalized into the testsuite because dialects disagree on plan shape:

* Capability gates. ``supports_explain_plan()`` is always True here;
  ``supports_explain_analyze()`` is version-gated (the ANALYZE keyword is only
  accepted from ClickHouse 26.7); ``supports_explain_format()`` recognises the
  TEXT/JSON/TREE/TABULAR/TSV/CSV family but rejects XML/YAML.
* Rendering. ``format_explain_statement`` emits ``EXPLAIN <stmt>``, prefixes
  ``ANALYZE`` and ``FORMAT=<name>`` when requested, and preserves the inner
  statement's bind parameters.
* Result interpretation. A real server returns rows exposing an ``explain``
  String column whose lines name plan nodes (``Output``, ``Filter``,
  ``ReadFromMergeTree`` / ``ReadFromStorage``). ``EXPLAIN ANALYZE`` adds a
  runtime header and ``EXPLAIN PIPELINE`` exposes ``*Transform`` steps.

The capability/render checks are construction-level and need no database; the
interpretation checks run against the real ClickHouse service used in CI and
share the backend-owned fixtures of this directory. ClickHouse is
synchronous-only, so there is intentionally no async half.
"""

from typing import Any, Dict, List, Optional, Tuple

import pytest
from rhosocial.activerecord.backend.expression import (
    ExplainFormat,
    ExplainOptions,
    ExplainStatement,
    ExplainType,
    RawSQL,
)

from rhosocial.activerecord.backend.impl.clickhouse.dialect import ClickHouseDialect

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


def _explain_stmt(
    dialect: ClickHouseDialect,
    sql: str,
    options: Optional[ExplainOptions] = None,
    params: tuple = (),
) -> ExplainStatement:
    """Wrap a raw SELECT in an ExplainStatement for the given dialect."""
    return ExplainStatement(dialect, RawSQL(dialect, sql, params), options)


def _render(
    dialect: ClickHouseDialect,
    sql: str,
    options: Optional[ExplainOptions] = None,
    params: tuple = (),
) -> Tuple[str, tuple]:
    """Render an ExplainStatement to (sql, params) via the dialect formatter."""
    return dialect.format_explain_statement(_explain_stmt(dialect, sql, options, params))


def _plan_text(plan: List[Dict[str, Any]]) -> str:
    """Join every string cell of an opaque EXPLAIN plan into one searchable text."""
    lines: List[str] = []
    for row in plan:
        if not isinstance(row, dict):
            lines.append(str(row))
            continue
        for value in row.values():
            if value is not None:
                lines.append(str(value))
    return "\n".join(lines)


def _has_explain_column(plan: List[Dict[str, Any]]) -> bool:
    """Whether the opaque plan rows expose ClickHouse's ``explain`` column."""
    return any(isinstance(row, dict) and "explain" in row for row in plan)


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

    @pytest.mark.parametrize("fmt", ["TEXT", "JSON", "TREE", "TABULAR", "TSV", "CSV"])
    def test_supports_explain_format_recognised(self, dialect: ClickHouseDialect, fmt: str) -> None:
        assert dialect.supports_explain_format(fmt) is True
        assert dialect.supports_explain_format(fmt.lower()) is True

    @pytest.mark.parametrize("fmt", ["XML", "YAML", "TRADITIONAL", "NOT_A_FORMAT", ""])
    def test_supports_explain_format_rejected(self, dialect: ClickHouseDialect, fmt: str) -> None:
        assert dialect.supports_explain_format(fmt) is False

    def test_format_explain_statement_basic(self, dialect: ClickHouseDialect) -> None:
        sql, params = _render(dialect, "SELECT 1")
        assert sql == "EXPLAIN SELECT 1"
        assert params == ()

    def test_format_explain_statement_analyze(self, dialect: ClickHouseDialect) -> None:
        sql, _ = _render(dialect, "SELECT 1", ExplainOptions(analyze=True))
        assert sql == "EXPLAIN ANALYZE SELECT 1"

    def test_analyze_gate_drives_callers_not_rendering(self, dialect: ClickHouseDialect) -> None:
        # The version gate reports whether ANALYZE is usable; callers must
        # consult it. Rendering itself honours the requested option verbatim.
        assert dialect.supports_explain_analyze() is True
        sql, _ = _render(dialect, "SELECT 1", ExplainOptions(analyze=True))
        assert "ANALYZE" in sql
        old = ClickHouseDialect(version=(25, 8, 1))
        assert old.supports_explain_analyze() is False

    def test_format_explain_statement_format_json(self, dialect: ClickHouseDialect) -> None:
        sql, _ = _render(dialect, "SELECT 1", ExplainOptions(format=ExplainFormat.JSON))
        assert sql == "EXPLAIN FORMAT=JSON SELECT 1"

    @pytest.mark.parametrize("fmt", ["TEXT", "JSON", "TREE"])
    def test_supported_formats_render_format_clause(
        self, dialect: ClickHouseDialect, fmt: str
    ) -> None:
        assert dialect.supports_explain_format(fmt) is True
        sql, _ = _render(dialect, "SELECT 1", ExplainOptions(format=ExplainFormat[fmt]))
        assert f"FORMAT={fmt}" in sql

    def test_query_plan_type_has_no_extra_clause(self, dialect: ClickHouseDialect) -> None:
        # ClickHouse has no QUERY_PLAN keyword; the option is accepted but maps
        # to a plain EXPLAIN, so the gate for EXPLAIN in general still holds.
        sql, _ = _render(dialect, "SELECT 1", ExplainOptions(type=ExplainType.QUERY_PLAN))
        assert sql == "EXPLAIN SELECT 1"
        assert "QUERY_PLAN" not in sql

    def test_analyze_and_format_combined(self, dialect: ClickHouseDialect) -> None:
        sql, _ = _render(
            dialect,
            "SELECT 1",
            ExplainOptions(analyze=True, format=ExplainFormat.JSON),
        )
        assert sql == "EXPLAIN ANALYZE FORMAT=JSON SELECT 1"

    def test_render_preserves_inner_params(self, dialect: ClickHouseDialect) -> None:
        sql, params = _render(dialect, "SELECT %s", ExplainOptions(), (42,))
        assert sql == "EXPLAIN SELECT %s"
        assert params == (42,)

    def test_to_sql_delegates_to_dialect_formatter(self, dialect: ClickHouseDialect) -> None:
        # ExplainStatement.to_sql() must reach the same ClickHouse formatter,
        # not the generic dialect mixin's PostgreSQL-style renderer.
        stmt = _explain_stmt(dialect, "SELECT 1", ExplainOptions(analyze=True))
        assert stmt.to_sql() == ("EXPLAIN ANALYZE SELECT 1", ())


@pytest.fixture
def indexed_backend(clickhouse_backend_single):
    """Non-parameterized sync backend with a small MergeTree table and seed rows."""
    backend = clickhouse_backend_single
    backend.execute("DROP TABLE IF EXISTS ch_explain_deep")
    backend.execute(
        "CREATE TABLE ch_explain_deep (id UInt32, age UInt32) " "ENGINE = MergeTree() ORDER BY id"
    )
    for i in range(6):
        backend.execute("INSERT INTO ch_explain_deep (id, age) VALUES (%s, %s)", (i, i * 7))
    yield backend
    try:
        backend.execute("DROP TABLE IF EXISTS ch_explain_deep")
    except Exception:
        pass


def _explain_plan(backend, where: Optional[str] = None, options: Optional[ExplainOptions] = None):
    """Run an EXPLAIN through the same renderer/DB path .explain().aggregate() uses."""
    dialect = backend.dialect
    sql = "SELECT * FROM ch_explain_deep"
    if where is not None:
        sql = f"{sql} WHERE {where}"
    explain_sql, params = _render(dialect, sql, options)
    return backend.fetch_all(explain_sql, params)


class TestClickHouseExplainDeep:
    """Interpret EXPLAIN output from a real ClickHouse server (synchronous)."""

    @staticmethod
    def _gate(backend) -> None:
        if not backend.dialect.supports_explain_plan():
            pytest.skip("backend does not support EXPLAIN")

    def test_basic_plan_has_explain_column_and_plan_nodes(self, indexed_backend) -> None:
        self._gate(indexed_backend)
        plan = _explain_plan(indexed_backend)
        assert isinstance(plan, list) and plan, "EXPLAIN must return a non-empty list of rows"
        assert _has_explain_column(plan), "ClickHouse EXPLAIN rows expose an 'explain' column"
        text = _plan_text(plan)
        assert any(
            marker in text for marker in _PLAN_NODE_MARKERS
        ), f"expected a recognisable ClickHouse plan node in: {text!r}"

    def test_filter_predicate_shows_filter_node(self, indexed_backend) -> None:
        self._gate(indexed_backend)
        plan = _explain_plan(indexed_backend, where="age > 30")
        text = _plan_text(plan)
        # ClickHouse may push the predicate into PREWHERE instead of a plain
        # Filter node; either form is evidence the WHERE clause reached the plan.
        assert "filter" in text.lower(), f"a WHERE predicate must surface a filter: {text!r}"
        assert _has_explain_column(plan)

    def test_primary_key_predicate_still_yields_a_plan(self, indexed_backend) -> None:
        self._gate(indexed_backend)
        plan = _explain_plan(indexed_backend, where="id = 1")
        text = _plan_text(plan)
        assert any(
            marker in text for marker in _PLAN_NODE_MARKERS
        ), f"expected a storage/scan node for a PK predicate: {text!r}"

    def test_explain_analyze_returns_runtime_summary_when_supported(self, indexed_backend) -> None:
        self._gate(indexed_backend)
        if not indexed_backend.dialect.supports_explain_analyze():
            pytest.skip("EXPLAIN ANALYZE requires ClickHouse >= 26.7")
        plan = _explain_plan(indexed_backend, options=ExplainOptions(analyze=True))
        assert isinstance(plan, list) and plan
        assert _has_explain_column(plan)
        text = _plan_text(plan)
        # ANALYZE prepends a live-run summary header to the plan tree.
        assert (
            "Query summary" in text or "Execution" in text or "Time:" in text
        ), f"expected an EXPLAIN ANALYZE runtime header: {text!r}"

    def test_explain_pipeline_exposes_transform_steps(self, indexed_backend) -> None:
        # PIPELINE is a ClickHouse-only form the dialect has no option for, so
        # it is executed directly; its plan names individual Transform steps.
        self._gate(indexed_backend)
        plan = indexed_backend.fetch_all("EXPLAIN PIPELINE SELECT * FROM ch_explain_deep")
        assert isinstance(plan, list) and plan
        text = _plan_text(plan)
        assert (
            "Transform" in text or "Expression" in text
        ), f"expected pipeline transform steps in: {text!r}"

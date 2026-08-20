# tests/rhosocial/activerecord_clickhouse_test/feature/backend/test_backend_explain.py
"""
Integration tests for ClickHouseBackend.explain().

These tests require a real ClickHouse connection configured via clickhouse_scenarios.yaml.
The tests create a temporary table, run EXPLAIN, and verify the typed result objects.
"""

import pytest

from rhosocial.activerecord.backend.explain import SyncExplainBackendProtocol
from rhosocial.activerecord.backend.expression import RawSQLExpression
from rhosocial.activerecord.backend.expression.statements import ExplainOptions
from rhosocial.activerecord.backend.impl.clickhouse import (
    ClickHouseExplainResult,
    ClickHouseExplainRow,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="function")
def indexed_backend(clickhouse_backend_single):
    """Sync backend with a small ClickHouse-native test table."""
    backend = clickhouse_backend_single
    backend.execute("DROP TABLE IF EXISTS explain_orders")
    backend.execute("""
        CREATE TABLE explain_orders (
            id UInt32,
            status String,
            amount Decimal(10, 2)
        ) ENGINE = MergeTree()
        ORDER BY id
    """)
    backend.execute(
        "INSERT INTO explain_orders (id, status, amount) VALUES (%s, %s, %s)",
        (1, "pending", 10.00),
    )
    backend.execute(
        "INSERT INTO explain_orders (id, status, amount) VALUES (%s, %s, %s)",
        (2, "shipped", 20.00),
    )
    backend.execute(
        "INSERT INTO explain_orders (id, status, amount) VALUES (%s, %s, %s)",
        (3, "pending", 30.00),
    )
    backend.execute(
        "INSERT INTO explain_orders (id, status, amount) VALUES (%s, %s, %s)",
        (4, "delivered", 40.00),
    )
    yield backend
    try:
        backend.execute("DROP TABLE IF EXISTS explain_orders")
    except Exception:
        pass


# ---------------------------------------------------------------------------
# Protocol checking
# ---------------------------------------------------------------------------


class TestExplainProtocol:
    def test_sync_backend_implements_protocol(self, clickhouse_backend_single):
        assert isinstance(clickhouse_backend_single, SyncExplainBackendProtocol)


# ---------------------------------------------------------------------------
# Sync explain – basic structure
# ---------------------------------------------------------------------------


class TestSyncExplainBasic:
    def test_explain_returns_clickhouse_explain_result(self, indexed_backend):
        dialect = indexed_backend.dialect
        expr = RawSQLExpression(dialect, "SELECT * FROM explain_orders")
        result = indexed_backend.explain(expr)
        assert isinstance(result, ClickHouseExplainResult)

    def test_result_has_rows(self, indexed_backend):
        dialect = indexed_backend.dialect
        expr = RawSQLExpression(dialect, "SELECT * FROM explain_orders")
        result = indexed_backend.explain(expr)
        assert len(result.rows) > 0

    def test_result_row_type(self, indexed_backend):
        dialect = indexed_backend.dialect
        expr = RawSQLExpression(dialect, "SELECT * FROM explain_orders")
        result = indexed_backend.explain(expr)
        for row in result.rows:
            assert isinstance(row, ClickHouseExplainRow)

    def test_result_has_sql(self, indexed_backend):
        dialect = indexed_backend.dialect
        expr = RawSQLExpression(dialect, "SELECT * FROM explain_orders")
        result = indexed_backend.explain(expr)
        assert "explain_orders" in result.sql.lower()
        assert result.sql.upper().startswith("EXPLAIN")

    def test_result_has_duration(self, indexed_backend):
        dialect = indexed_backend.dialect
        expr = RawSQLExpression(dialect, "SELECT * FROM explain_orders")
        result = indexed_backend.explain(expr)
        assert result.duration >= 0.0

    def test_result_has_raw_rows(self, indexed_backend):
        dialect = indexed_backend.dialect
        expr = RawSQLExpression(dialect, "SELECT * FROM explain_orders")
        result = indexed_backend.explain(expr)
        assert isinstance(result.raw_rows, list)
        assert len(result.raw_rows) == len(result.rows)

    def test_row_fields_present(self, indexed_backend):
        """Verify ClickHouseExplainRow has expected attribute names."""
        dialect = indexed_backend.dialect
        expr = RawSQLExpression(dialect, "SELECT * FROM explain_orders")
        result = indexed_backend.explain(expr)
        row = result.rows[0]
        # All expected fields must exist (may be None for some)
        assert hasattr(row, "id")
        assert hasattr(row, "select_type")
        assert hasattr(row, "table")
        assert hasattr(row, "type")
        assert hasattr(row, "key")
        assert hasattr(row, "rows")
        assert hasattr(row, "extra")


# ---------------------------------------------------------------------------
# ClickHouse-specific EXPLAIN variants
# ---------------------------------------------------------------------------


class TestClickHouseExplainVariants:
    def test_explain_analyze(self, indexed_backend):
        """EXPLAIN ANALYZE returns a result (if supported)."""
        dialect = indexed_backend.dialect
        if not dialect.supports_explain_analyze():
            pytest.skip("ClickHouse version does not support EXPLAIN ANALYZE")
        expr = RawSQLExpression(dialect, "SELECT * FROM explain_orders")
        result = indexed_backend.explain(expr, ExplainOptions(analyze=True))
        assert isinstance(result, ClickHouseExplainResult)
        assert result.sql.upper().startswith("EXPLAIN ANALYZE")
        assert len(result.raw_rows) > 0

    def test_explain_pipeline(self, indexed_backend):
        """EXPLAIN PIPELINE returns rows.

        The dialect has no structured option for the ClickHouse-only
        ``PIPELINE`` keyword, so the raw query is executed directly.
        """
        rows = indexed_backend.fetch_all("EXPLAIN PIPELINE SELECT * FROM explain_orders")
        assert isinstance(rows, list)
        assert len(rows) > 0

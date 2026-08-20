# tests/rhosocial/activerecord_clickhouse_test/feature/backend/clickhouse/test_optimizer_hint_execution.py
"""
Tests for ClickHouse optimizer hint execution with actual ClickHouse 9.7.

Verifies that generated hint syntax executes correctly and
the hypergraph optimizer can be toggled per-statement.
"""

import pytest
from rhosocial.activerecord.backend.impl.clickhouse.expression import (
    ClickHouseOptimizerHintExpression,
    SetVarHint,
)


def _requires_clickhouse_97(backend):
    """Skip test if ClickHouse version < 9.7."""
    if backend.dialect.version < (9, 7, 0):
        pytest.skip("Requires ClickHouse 9.7+ for hypergraph optimizer")


class TestOptimizerHintExecution:
    """Test optimizer hint execution on ClickHouse 9.7."""

    def test_select_with_hypergraph_on(self, clickhouse_backend):
        backend = clickhouse_backend
        _requires_clickhouse_97(backend)

        hint_expr = ClickHouseOptimizerHintExpression(
            backend.dialect, [SetVarHint("optimizer_switch", "hypergraph_optimizer=on")]
        )
        hint_sql, _ = hint_expr.to_sql()

        result = backend.execute(f"SELECT {hint_sql} 1 AS val", ())
        assert len(result.data) == 1
        assert result.data[0]["val"] == 1

    def test_select_with_hypergraph_off(self, clickhouse_backend):
        backend = clickhouse_backend
        _requires_clickhouse_97(backend)

        hint_expr = ClickHouseOptimizerHintExpression(
            backend.dialect, [SetVarHint("optimizer_switch", "hypergraph_optimizer=off")]
        )
        hint_sql, _ = hint_expr.to_sql()

        result = backend.execute(f"SELECT {hint_sql} 1 + 1 AS val", ())
        assert len(result.data) == 1
        assert result.data[0]["val"] == 2

    def test_hint_with_table_query(self, clickhouse_backend):
        backend = clickhouse_backend
        _requires_clickhouse_97(backend)

        from rhosocial.activerecord.backend.options import ExecutionOptions
        from rhosocial.activerecord.backend.schema import StatementType

        ddl_opts = ExecutionOptions(stmt_type=StatementType.DDL)
        backend.execute("DROP TABLE IF EXISTS hint_test", (), options=ddl_opts)
        backend.execute("CREATE TABLE hint_test (id INT PRIMARY KEY, val VARCHAR(50))", (), options=ddl_opts)
        backend.execute("INSERT INTO hint_test VALUES (1, 'hello'), (2, 'world')", ())

        hint_expr = ClickHouseOptimizerHintExpression(
            backend.dialect, [SetVarHint("optimizer_switch", "hypergraph_optimizer=on")]
        )
        hint_sql, _ = hint_expr.to_sql()

        result = backend.execute(f"SELECT {hint_sql} * FROM hint_test ORDER BY id", ())
        assert len(result.data) == 2
        assert result.data[0]["val"] == "hello"
        assert result.data[1]["val"] == "world"

        backend.execute("DROP TABLE IF EXISTS hint_test", (), options=ddl_opts)

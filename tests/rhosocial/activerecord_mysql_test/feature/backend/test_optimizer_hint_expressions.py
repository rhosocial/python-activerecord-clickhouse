# tests/rhosocial/activerecord_clickhouse_test/feature/backend/test_optimizer_hint_expressions.py
"""
Tests for ClickHouse optimizer hint expression classes.

Tests SQL generation for:
- ClickHouseOptimizerHintExpression with SET_VAR hints
- Hypergraph optimizer hint generation
- Multiple hints in single expression
- Version-gated capability detection
"""

import pytest
from rhosocial.activerecord.backend.impl.clickhouse.dialect import ClickHouseDialect
from rhosocial.activerecord.backend.impl.clickhouse.expression import (
    ClickHouseOptimizerHintExpression,
    SetVarHint,
)


@pytest.fixture
def dialect_97():
    return ClickHouseDialect(version=(9, 7, 0))


@pytest.fixture
def dialect_80():
    return ClickHouseDialect(version=(8, 0, 0))


@pytest.fixture
def dialect_56():
    return ClickHouseDialect(version=(5, 6, 0))


class TestOptimizerHintSupport:
    """Test version-gated capability detection."""

    def test_supported_on_97(self, dialect_97):
        assert dialect_97.supports_optimizer_hint()
        assert dialect_97.supports_hypergraph_optimizer()

    def test_hint_supported_on_80(self, dialect_80):
        assert dialect_80.supports_optimizer_hint()
        assert not dialect_80.supports_hypergraph_optimizer()

    def test_not_supported_on_56(self, dialect_56):
        assert not dialect_56.supports_optimizer_hint()
        assert not dialect_56.supports_hypergraph_optimizer()


class TestOptimizerHintExpression:
    """Test optimizer hint SQL generation."""

    def test_hypergraph_on(self, dialect_97):
        expr = ClickHouseOptimizerHintExpression(dialect_97, [SetVarHint("optimizer_switch", "hypergraph_optimizer=on")])
        sql, params = expr.to_sql()
        assert sql == "/*+ SET_VAR(optimizer_switch='hypergraph_optimizer=on') */"
        assert params == ()

    def test_hypergraph_off(self, dialect_97):
        expr = ClickHouseOptimizerHintExpression(dialect_97, [SetVarHint("optimizer_switch", "hypergraph_optimizer=off")])
        sql, params = expr.to_sql()
        assert sql == "/*+ SET_VAR(optimizer_switch='hypergraph_optimizer=off') */"
        assert params == ()

    def test_multiple_hints(self, dialect_97):
        expr = ClickHouseOptimizerHintExpression(
            dialect_97,
            [
                SetVarHint("optimizer_switch", "hypergraph_optimizer=on"),
                SetVarHint("max_execution_time", "1000"),
            ],
        )
        sql, params = expr.to_sql()
        assert "SET_VAR(optimizer_switch='hypergraph_optimizer=on')" in sql
        assert "SET_VAR(max_execution_time='1000')" in sql
        assert sql.startswith("/*+ ")
        assert sql.endswith(" */")
        assert params == ()

    def test_single_set_var(self, dialect_80):
        expr = ClickHouseOptimizerHintExpression(dialect_80, [SetVarHint("max_execution_time", "5000")])
        sql, params = expr.to_sql()
        assert sql == "/*+ SET_VAR(max_execution_time='5000') */"
        assert params == ()

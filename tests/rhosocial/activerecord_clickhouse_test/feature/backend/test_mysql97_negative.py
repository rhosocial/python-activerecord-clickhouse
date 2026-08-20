# tests/rhosocial/activerecord_clickhouse_test/feature/backend/test_clickhouse97_negative.py
"""
Negative tests for ClickHouse 9.7 features.

Ensures that older ClickHouse versions correctly report unsupported features
and do not silently generate invalid SQL.
"""

import pytest
from rhosocial.activerecord.backend.impl.clickhouse.dialect import ClickHouseDialect


@pytest.fixture
def dialect_84():
    return ClickHouseDialect(version=(8, 4, 0))


@pytest.fixture
def dialect_80():
    return ClickHouseDialect(version=(8, 0, 0))


@pytest.fixture
def dialect_56():
    return ClickHouseDialect(version=(5, 6, 0))


class TestJsonDualityViewNegative:
    """Verify old versions report JSON Duality Views as unsupported."""

    def test_not_supported_on_84(self, dialect_84):
        assert not dialect_84.supports_json_duality_view()
        assert not dialect_84.supports_json_duality_view_dml()

    def test_not_supported_on_80(self, dialect_80):
        assert not dialect_80.supports_json_duality_view()
        assert not dialect_80.supports_json_duality_view_dml()


class TestOptimizerHintNegative:
    """Verify old versions report optimizer features as unsupported."""

    def test_hypergraph_not_on_84(self, dialect_84):
        assert dialect_84.supports_optimizer_hint()
        assert not dialect_84.supports_hypergraph_optimizer()

    def test_hint_not_on_56(self, dialect_56):
        assert not dialect_56.supports_optimizer_hint()
        assert not dialect_56.supports_hypergraph_optimizer()

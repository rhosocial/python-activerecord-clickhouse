# tests/rhosocial/activerecord_clickhouse_test/feature/backend/construct/dialect/test_generated_value_suggestion.py
"""ClickHouse's generated-value suggestion is a plain, no-clause DDL answer."""

import pytest
from rhosocial.activerecord.backend.expression.types import IntegerType
from rhosocial.activerecord.backend.impl.clickhouse.dialect import ClickHouseDialect
from rhosocial.activerecord.backend.impl.clickhouse.suggestion import (
    ClickHouseGeneratedValueSuggestionMixin,
)
from rhosocial.activerecord.backend.suggestion.protocols import (
    GeneratedValueSuggestionSupport,
)


@pytest.fixture
def dialect():
    return ClickHouseDialect()


def test_dialect_implements_generated_value_suggestion(dialect):
    assert isinstance(dialect, GeneratedValueSuggestionSupport)
    assert isinstance(dialect, ClickHouseGeneratedValueSuggestionMixin)


def test_suggestion_keeps_the_declared_type_and_adds_no_clause(dialect):
    declared = IntegerType()
    suggestion = dialect.suggest_generated_value(declared)
    assert suggestion.state == "embedded-in-type"
    assert suggestion.storage_type is declared
    assert suggestion.clause is None


def test_mixin_does_not_inherit_the_protocol():
    """A Protocol base would swallow constructor arguments under strict validation."""
    assert not any(
        base.__name__ == "Protocol" for base in ClickHouseGeneratedValueSuggestionMixin.__mro__
    )

# tests/rhosocial/activerecord_clickhouse_test/feature/backend/test_clickhouse_column_definition.py
"""Tests for the ClickHouse-specific column definition expressions."""

import pytest

from rhosocial.activerecord.backend.expression import ColumnDefinition, FunctionCall
from rhosocial.activerecord.backend.expression.types import IntegerType
from rhosocial.activerecord.backend.impl.clickhouse.expression import (
    ClickHouseColumnDefinition,
    ClickHouseColumnOptions,
)


@pytest.fixture
def dialect():
    from rhosocial.activerecord.backend.impl.clickhouse.dialect import ClickHouseDialect

    return ClickHouseDialect((24, 1, 0))


def _column(dialect, **kwargs):
    return ClickHouseColumnDefinition(dialect, "x", IntegerType(dialect), **kwargs)


def test_derives_generic_column_definition():
    assert ColumnDefinition in ClickHouseColumnDefinition.__mro__


def test_codec(dialect):
    sql, _ = _column(dialect, codec=["ZSTD(3)", "LZ4"]).to_sql()
    assert sql == "`x` Int32 CODEC(ZSTD(3), LZ4)"


def test_materialized(dialect):
    sql, _ = _column(dialect, materialized=FunctionCall(dialect, "now")).to_sql()
    assert sql == "`x` Int32 MATERIALIZED NOW()"


def test_alias(dialect):
    sql, _ = _column(dialect, alias=FunctionCall(dialect, "now")).to_sql()
    assert sql == "`x` Int32 ALIAS NOW()"


def test_ttl(dialect):
    sql, _ = _column(dialect, ttl=FunctionCall(dialect, "now")).to_sql()
    assert sql == "`x` Int32 TTL NOW()"


def test_generic_column_still_renders_on_clickhouse(dialect):
    generic = ColumnDefinition(dialect, "x", IntegerType(dialect), comment="c")
    sql, _ = generic.to_sql()
    assert sql == "`x` Int32 COMMENT 'c'"


def test_invalid_materialized_type(dialect):
    with pytest.raises(TypeError, match="BaseExpression"):
        _column(dialect, materialized="now")


def test_options_select_clickhouse_column_class():
    assert ClickHouseColumnOptions(codec=["LZ4"]).column_definition_class() is (
        ClickHouseColumnDefinition
    )


def test_options_apply_to(dialect):
    options = ClickHouseColumnOptions(codec=["LZ4"], ttl=FunctionCall(dialect, "now"))
    col = ClickHouseColumnDefinition(dialect, "c", IntegerType(dialect))
    options.apply_to(col)
    assert col.codec == ["LZ4"]
    assert col.ttl is options.ttl


def test_options_apply_to_rejects_generic_column(dialect):
    options = ClickHouseColumnOptions(codec=["LZ4"])
    generic = ColumnDefinition(dialect, "c", IntegerType(dialect))
    with pytest.raises(TypeError, match="ClickHouseColumnDefinition"):
        options.apply_to(generic)

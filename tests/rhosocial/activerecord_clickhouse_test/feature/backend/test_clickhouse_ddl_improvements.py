# tests/rhosocial/activerecord_clickhouse_test/feature/backend/test_clickhouse_ddl_improvements.py
"""Tests for ClickHouse DDL improvements: capability gating, UnsupportedFeatureError."""
import pytest
from unittest.mock import patch

from rhosocial.activerecord.backend.dialect.exceptions import UnsupportedFeatureError
from rhosocial.activerecord.backend.expression import (
    Column,
    CreateTableExpression,
    CreateViewExpression,
    QueryExpression,
    TableExpression,
)
from rhosocial.activerecord.backend.expression.statements import (
    ColumnDefinition,
    ViewCheckOption,
    ViewOptions,
)
from rhosocial.activerecord.backend.expression.types import IntegerType
from rhosocial.activerecord.backend.impl.clickhouse.dialect import ClickHouseDialect


class TestClickHouseViewCapabilityGating:
    """Tests for ClickHouse VIEW DDL capability gating."""

    def test_create_view_check_option_gated(self):
        """WITH CHECK OPTION must fail fast when the capability is off."""
        dialect = ClickHouseDialect()
        query = QueryExpression(
            dialect, select=[Column(dialect, "id")], from_=TableExpression(dialect, "t")
        )
        expr = CreateViewExpression(
            dialect,
            view_name="v",
            query=query,
            options=ViewOptions(check_option=ViewCheckOption.CASCADED),
        )
        with patch.object(type(dialect), "supports_view_check_option", return_value=False):
            with pytest.raises(UnsupportedFeatureError, match="CHECK OPTION"):
                expr.to_sql()

    def test_create_or_replace_view_supported(self):
        """ClickHouse supports CREATE OR REPLACE VIEW."""
        dialect = ClickHouseDialect()
        assert dialect.supports_create_or_replace_view() is True

    def test_create_view_if_not_exists_supported(self):
        """ClickHouse supports CREATE VIEW IF NOT EXISTS."""
        dialect = ClickHouseDialect()
        assert dialect.supports_if_not_exists_view() is True

    def test_drop_view_if_exists_supported(self):
        """ClickHouse supports DROP VIEW IF EXISTS."""
        dialect = ClickHouseDialect()
        assert dialect.supports_if_exists_view() is True

    def test_materialized_view_supported(self):
        """ClickHouse materialized views (incremental and refreshable)."""
        dialect = ClickHouseDialect()
        assert dialect.supports_materialized_view() is True


class TestClickHouseSchemaCapabilityGating:
    """Tests for ClickHouse SCHEMA DDL capability gating."""

    def test_create_schema_not_supported(self):
        """ClickHouse does not support CREATE SCHEMA."""
        dialect = ClickHouseDialect()
        assert dialect.supports_create_schema() is False

    def test_drop_schema_not_supported(self):
        """ClickHouse does not support DROP SCHEMA."""
        dialect = ClickHouseDialect()
        assert dialect.supports_drop_schema() is False


class TestClickHouseTableDeclarationGating:
    def test_table_declaration_defaults_are_absent(self):
        dialect = ClickHouseDialect(version=(26, 7, 3))
        expression = CreateTableExpression(
            dialect,
            "plain_table_defaults",
            [ColumnDefinition(dialect, "id", IntegerType(dialect))],
        )
        sql, params = expression.to_sql()
        assert expression.inherits == []
        assert expression.tablespace is None
        assert "plain_table_defaults" in sql.lower()
        assert "id" in sql.lower()
        assert params == ()

    def test_table_inherits_is_propagated_and_rejected(self):
        dialect = ClickHouseDialect(version=(26, 7, 3))
        assert dialect.supports_table_inheritance() is False
        expression = CreateTableExpression(
            dialect,
            "inherited",
            [ColumnDefinition(dialect, "id", IntegerType(dialect))],
            inherits=["parent_a", "parent_b"],
        )
        assert expression.inherits == ["parent_a", "parent_b"]
        with pytest.raises(UnsupportedFeatureError, match="INHERITS"):
            expression.to_sql()

    def test_table_tablespace_is_propagated_and_rejected(self):
        dialect = ClickHouseDialect(version=(26, 7, 3))
        assert dialect.supports_table_tablespace() is False
        expression = CreateTableExpression(
            dialect,
            "tablespaced",
            [ColumnDefinition(dialect, "id", IntegerType(dialect))],
            tablespace="ts_data",
        )
        assert expression.tablespace == "ts_data"
        with pytest.raises(UnsupportedFeatureError, match="TABLESPACE"):
            expression.to_sql()

# tests/rhosocial/activerecord_clickhouse_test/feature/backend/test_clickhouse_ddl_improvements.py
"""Tests for ClickHouse DDL improvements: capability gating, UnsupportedFeatureError."""
import pytest
from unittest.mock import patch, PropertyMock

from rhosocial.activerecord.backend.expression import (
    Column,
    TableExpression,
    QueryExpression,
    CreateViewExpression,
    DropViewExpression,
)
from rhosocial.activerecord.backend.impl.clickhouse.dialect import ClickHouseDialect
from rhosocial.activerecord.backend.dialect.exceptions import UnsupportedFeatureError


class TestClickHouseViewCapabilityGating:
    """Tests for ClickHouse VIEW DDL capability gating."""

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
        """ClickHouse supports materialized views."""
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

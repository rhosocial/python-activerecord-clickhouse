# tests/rhosocial/activerecord_clickhouse_test/feature/backend/schema/test_schema_support.py
"""Tests for the SchemaSupport capability declared on the ClickHouse dialect.

ClickHouse namespaces objects with databases only; there is no schema layer,
so the umbrella ``supports_schema()`` flag must be False (explicitly declared,
not inherited from the core default).
"""
from rhosocial.activerecord.backend.dialect.protocols import SchemaSupport
from rhosocial.activerecord.backend.impl.clickhouse.dialect import ClickHouseDialect


class TestSchemaCapability:
    """Umbrella flag and granular schema DDL capability bits."""

    def _dialect(self) -> ClickHouseDialect:
        return ClickHouseDialect()

    def test_supports_schema_is_false(self):
        assert self._dialect().supports_schema() is False

    def test_implements_schema_support_protocol(self):
        assert isinstance(self._dialect(), SchemaSupport)

    def test_no_schema_ddl_capabilities(self):
        d = self._dialect()
        assert d.supports_create_schema() is False
        assert d.supports_drop_schema() is False
        assert d.supports_schema_if_not_exists() is False
        assert d.supports_schema_if_exists() is False

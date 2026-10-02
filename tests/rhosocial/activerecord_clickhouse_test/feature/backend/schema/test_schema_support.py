# tests/rhosocial/activerecord_clickhouse_test/feature/backend/schema/test_schema_support.py
"""Tests for the SchemaSupport capability declared on the ClickHouse dialect.

ClickHouse namespaces objects with databases only -- there is no schema layer.
A ``schema_name`` is nevertheless accepted and used as the database, because a
database is a namespace this dialect can express, so the umbrella
``supports_schema()`` flag is True while the schema DDL capabilities stay
False. Refusing the value would be wrong: it is usable, it just is not a schema.
"""
from rhosocial.activerecord.backend.dialect.protocols import SchemaSupport
from rhosocial.activerecord.backend.impl.clickhouse.dialect import ClickHouseDialect


class TestSchemaCapability:
    """Umbrella flag and granular schema DDL capability bits."""

    def _dialect(self) -> ClickHouseDialect:
        return ClickHouseDialect()

    def test_supports_schema_is_true(self):
        """A schema_name is usable here; it names a database."""
        assert self._dialect().supports_schema() is True

    def test_implements_schema_support_protocol(self):
        assert isinstance(self._dialect(), SchemaSupport)

    def test_no_schema_ddl_capabilities(self):
        """CREATE SCHEMA does not exist in ClickHouse, so these stay False.

        The umbrella flag being True does not imply any of these: being able to
        *use* a namespace is separate from being able to *create* one.
        """
        d = self._dialect()
        assert d.supports_create_schema() is False
        assert d.supports_drop_schema() is False
        assert d.supports_schema_if_not_exists() is False
        assert d.supports_schema_if_exists() is False

    def test_qualified_reference_is_accepted(self):
        """A supplied schema reaches the SQL as the database part."""
        from rhosocial.activerecord.backend.expression.core import TableExpression

        sql, _ = TableExpression(
            self._dialect(), "orders", schema_name="app"
        ).to_sql()
        assert sql == "`app`.`orders`"

    def test_unqualified_reference_is_unchanged(self):
        from rhosocial.activerecord.backend.expression.core import TableExpression

        sql, _ = TableExpression(self._dialect(), "orders").to_sql()
        assert sql == "`orders`"
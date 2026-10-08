# tests/rhosocial/activerecord_clickhouse_test/feature/backend/schema/test_schema_support.py
"""Tests for the namespace switches the ClickHouse dialect declares.

ClickHouse namespaces objects with databases only; there is no schema layer.
The dialect therefore answers the two catalog switches True -- the database is
real and is rendered when a name carries one -- and leaves
``supports_schema_qualification`` False. A name that arrives carrying an inner
schema is reported rather than rendered as a namespace the server would not
understand.
"""
import pytest

from rhosocial.activerecord.backend.dialect.exceptions import UnsupportedFeatureError
from rhosocial.activerecord.backend.dialect.protocols import NamespaceSupport
from rhosocial.activerecord.backend.expression.objects import Table
from rhosocial.activerecord.backend.impl.clickhouse.dialect import ClickHouseDialect


class TestCatalogNamespace:
    """The database is the one namespace ClickHouse has."""

    def _dialect(self) -> ClickHouseDialect:
        return ClickHouseDialect()

    def test_implements_namespace_support(self):
        assert isinstance(self._dialect(), NamespaceSupport)

    def test_catalog_switches(self):
        d = self._dialect()
        assert d.supports_catalog() is True
        assert d.supports_catalog_qualification() is True

    def test_catalog_qualifies_the_name(self):
        assert self._dialect().format_table_object(
            Table(self._dialect(), "users", catalog_name="analytics")
        ) == ("`analytics`.`users`", ())

    def test_unqualified_name_is_left_alone(self):
        d = self._dialect()
        assert d.format_table_object(Table(d, "users")) == ("`users`", ())


class TestNoSchemaNamespace:
    """There is no inner schema, and the dialect says so."""

    def _dialect(self) -> ClickHouseDialect:
        return ClickHouseDialect()

    def test_schema_qualification_is_off(self):
        """The inner namespace switch is what governs this.

        A ``supports_schema_qualification()`` that answered True would make
        ``render_namespace`` append a second namespace ClickHouse does not
        have, producing a name the server cannot resolve.
        """
        assert self._dialect().supports_schema_qualification() is False

    def test_schema_ddl_probes_are_gone(self):
        """The ``supports_*_schema`` DDL switches go with the DDL protocols.

        Leaving them in place would keep ``isinstance(dialect,
        CreateSchemaSupport)`` true -- ``runtime_checkable`` checks method
        presence, not the base list -- and the dialect would then advertise
        ``CREATE SCHEMA``, which ClickHouse does not have.
        """
        d = self._dialect()
        for probe in (
            "supports_schema",
            "supports_create_schema",
            "supports_drop_schema",
            "supports_schema_if_not_exists",
            "supports_schema_if_exists",
        ):
            assert not hasattr(d, probe), probe

    def test_carried_schema_is_reported_not_rendered(self):
        with pytest.raises(UnsupportedFeatureError) as exc:
            self._dialect().format_table_object(
                Table(self._dialect(), "users", schema_name="inner")
            )
        assert "schema-qualified names" in str(exc.value)
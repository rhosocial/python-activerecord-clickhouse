# tests/rhosocial/activerecord_clickhouse_test/feature/backend/test_clickhouse_unsupported_features.py
"""
Fast-fail contract tests for ClickHouse-unsupported feature stubs.

ClickHouse does not support a large MySQL/SQL-standard feature surface
(triggers, spatial types, VECTOR, SET, stored routines, LOAD XML,
admin commands, TABLE/VALUES constructors, whole-table maintenance,
optimizer hints, JSON Duality Views, FULLTEXT, JSON_TABLE). The dialect
mixins for these features are fail-fast stubs: ``supports_*`` returns
``False`` and ``format_*`` raises :class:`UnsupportedFeatureError`.

These tests verify that contract without a database connection (pure
dialect method calls).
"""

import pytest

from rhosocial.activerecord.backend.dialect.exceptions import UnsupportedFeatureError
from rhosocial.activerecord.backend.impl.clickhouse.dialect import ClickHouseDialect


@pytest.fixture(scope="module")
def dialect():
    return ClickHouseDialect(version=(26, 7, 1))


def _assert_unsupported(dialect, supports_method, format_method):
    """A feature is unsupported iff supports_* is False and format_* raises."""
    assert getattr(dialect, supports_method)() is False
    with pytest.raises(UnsupportedFeatureError):
        getattr(dialect, format_method)(None)


class TestTriggerStub:
    def test_supports_flags(self, dialect):
        for m in (
            "supports_trigger", "supports_create_trigger", "supports_drop_trigger",
            "supports_instead_of_trigger", "supports_statement_trigger",
            "supports_trigger_referencing", "supports_trigger_when",
            "supports_trigger_if_not_exists",
        ):
            assert getattr(dialect, m)() is False, m

    def test_format_create_trigger_raises(self, dialect):
        with pytest.raises(UnsupportedFeatureError):
            dialect.format_create_trigger_statement(None)

    def test_format_drop_trigger_raises(self, dialect):
        with pytest.raises(UnsupportedFeatureError):
            dialect.format_drop_trigger_statement(None)


class TestSpatialStub:
    def test_supports_flags(self, dialect):
        assert dialect.supports_spatial_type("POINT") is False
        assert dialect.supports_spatial_index() is False
        assert dialect.supports_geojson() is False
        assert dialect.supports_geometry_type() is False
        assert dialect.supports_point_type() is False

    def test_format_spatial_literal_raises(self, dialect):
        with pytest.raises(UnsupportedFeatureError):
            dialect.format_spatial_literal("POINT(0 0)")

    def test_format_st_geom_from_text_raises(self, dialect):
        with pytest.raises(UnsupportedFeatureError):
            dialect.format_st_geom_from_text("POINT(0 0)")

    def test_format_create_spatial_index_raises(self, dialect):
        with pytest.raises(UnsupportedFeatureError):
            dialect.format_create_spatial_index("idx", "t", "geom")


class TestVectorStub:
    def test_supports_flags(self, dialect):
        assert dialect.supports_vector_type() is False
        assert dialect.supports_vector_index() is False

    def test_format_vector_literal_raises(self, dialect):
        with pytest.raises(UnsupportedFeatureError):
            dialect.format_vector_literal([1.0, 2.0])

    def test_format_create_vector_index_raises(self, dialect):
        with pytest.raises(UnsupportedFeatureError):
            dialect.format_create_vector_index("idx", "t", "emb")


class TestOptimizerHintStub:
    def test_supports_flags(self, dialect):
        assert dialect.supports_optimizer_hint() is False
        assert dialect.supports_hypergraph_optimizer() is False

    def test_format_optimizer_hint_raises(self, dialect):
        with pytest.raises(UnsupportedFeatureError):
            dialect.format_optimizer_hint(None)


class TestTableStatementStub:
    def test_supports_flags(self, dialect):
        assert dialect.supports_table_statement() is False
        assert dialect.supports_values_table_constructor() is False

    def test_format_table_statement_raises(self, dialect):
        with pytest.raises(UnsupportedFeatureError):
            dialect.format_table_statement(None)

    def test_format_values_statement_raises(self, dialect):
        with pytest.raises(UnsupportedFeatureError):
            dialect.format_values_statement(None)


class TestMaintenanceStub:
    def test_supports_flags(self, dialect):
        for m in (
            "supports_analyze_table", "supports_check_table",
            "supports_checksum_table", "supports_optimize_table",
            "supports_repair_table",
        ):
            assert getattr(dialect, m)() is False, m

    def test_format_table_maintenance_statement_raises(self, dialect):
        with pytest.raises(UnsupportedFeatureError):
            dialect.format_table_maintenance_statement(None)


class TestRoutineStub:
    def test_supports_flags(self, dialect):
        assert dialect.supports_procedure() is False
        assert dialect.supports_stored_function() is False
        assert dialect.supports_call() is False

    def test_format_create_procedure_raises(self, dialect):
        with pytest.raises(UnsupportedFeatureError):
            dialect.format_create_procedure_statement(None)

    def test_format_call_statement_raises(self, dialect):
        with pytest.raises(UnsupportedFeatureError):
            dialect.format_call_statement(None)


class TestLoadXmlStub:
    def test_supports_load_xml(self, dialect):
        assert dialect.supports_load_xml() is False

    def test_format_load_xml_raises(self, dialect):
        with pytest.raises(UnsupportedFeatureError):
            dialect.format_load_xml_statement(None)


class TestAdminCommandStub:
    def test_supports_flags(self, dialect):
        for m in (
            "supports_flush", "supports_reset", "supports_cache_index",
            "supports_install_component", "supports_install_plugin",
            "supports_clone", "supports_restart", "supports_binlog",
            "supports_handler", "supports_do", "supports_kill",
            "supports_shutdown", "supports_help", "supports_create_user",
            "supports_drop_user", "supports_grant", "supports_revoke",
        ):
            assert getattr(dialect, m)() is False, m

    def test_format_flush_raises(self, dialect):
        with pytest.raises(UnsupportedFeatureError):
            dialect.format_flush_statement(None)

    def test_format_kill_raises(self, dialect):
        with pytest.raises(UnsupportedFeatureError):
            dialect.format_kill_statement(None)


class TestJsonDualityViewStub:
    def test_supports_flags(self, dialect):
        assert dialect.supports_json_duality_view() is False
        assert dialect.supports_json_duality_view_dml() is False

    def test_format_create_json_duality_view_raises(self, dialect):
        with pytest.raises(UnsupportedFeatureError):
            dialect.format_create_json_duality_view_statement(None)


class TestFullTextStub:
    def test_supports_flags(self, dialect):
        assert dialect.supports_fulltext_index() is False
        assert dialect.supports_fulltext_search() is False

    def test_format_match_against_raises(self, dialect):
        with pytest.raises(UnsupportedFeatureError):
            dialect.format_match_against(["c"], "term")


class TestJsonTableStub:
    def test_supports_json_table(self, dialect):
        assert dialect.supports_json_table() is False

    def test_format_json_table_raises(self, dialect):
        with pytest.raises(UnsupportedFeatureError):
            dialect.format_json_table_expression(None)


class TestUpsertStub:
    def test_supports_on_conflict(self, dialect):
        assert dialect.supports_on_conflict_clause() is False

    def test_format_on_conflict_raises(self, dialect):
        with pytest.raises(UnsupportedFeatureError):
            dialect.format_on_conflict_clause(None)

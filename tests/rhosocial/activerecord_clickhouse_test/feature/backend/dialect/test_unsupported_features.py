# tests/rhosocial/activerecord_clickhouse_test/feature/backend/dialect/test_unsupported_features.py
"""
Fast-fail contract tests for ClickHouse-unsupported feature stubs.

ClickHouse does not support a large MySQL/SQL-standard feature surface
(triggers, spatial types, VECTOR, SET, stored routines, LOAD XML,
admin commands, TABLE/VALUES constructors, whole-table maintenance,
optimizer hints, JSON Duality Views, FULLTEXT, JSON_TABLE). The dialect
mixins for these features are fail-fast stubs: ``supports_*`` returns
``False`` and ``format_*`` raises :class:`UnsupportedFeatureError`.

These tests verify that contract without a database connection by building
the relevant expression node and rendering it via ``to_sql()``, so the real
expression-to-formatter dispatch path is exercised.
"""

import pytest

from rhosocial.activerecord.backend.dialect.exceptions import UnsupportedFeatureError
from rhosocial.activerecord.backend.expression.statements import OnConflictClause
from rhosocial.activerecord.backend.expression.statements.ddl_trigger import (
    CreateTriggerExpression,
    DropTriggerExpression,
    TriggerEvent,
    TriggerTiming,
)
from rhosocial.activerecord.backend.impl.clickhouse.dialect import ClickHouseDialect
from rhosocial.activerecord.backend.impl.clickhouse.expression.admin import (
    ClickHouseFlushExpression,
    ClickHouseKillExpression,
    FlushOption,
)
from rhosocial.activerecord.backend.impl.clickhouse.expression.json_duality_view import (
    CreateJsonDualityViewExpression,
    DualityObjectSpec,
)
from rhosocial.activerecord.backend.impl.clickhouse.expression.json_table import (
    ClickHouseJSONTableExpression,
    JSONTableColumn,
)
from rhosocial.activerecord.backend.impl.clickhouse.expression.load_xml import (
    ClickHouseLoadXMLEXpression,
)
from rhosocial.activerecord.backend.impl.clickhouse.expression.maintenance import (
    ClickHouseAnalyzeTableExpression,
)
from rhosocial.activerecord.backend.impl.clickhouse.expression.match_against import (
    ClickHouseMatchAgainstExpression,
)
from rhosocial.activerecord.backend.impl.clickhouse.expression.optimizer_hint import (
    ClickHouseOptimizerHintExpression,
    SetVarHint,
)
from rhosocial.activerecord.backend.impl.clickhouse.expression.routine import (
    ClickHouseCallExpression,
    ClickHouseCreateProcedureExpression,
)
from rhosocial.activerecord.backend.impl.clickhouse.expression.spatial import (
    ClickHouseCreateSpatialIndexExpression,
    ClickHouseSpatialLiteralExpression,
    ClickHouseSTGeomFromTextExpression,
)
from rhosocial.activerecord.backend.impl.clickhouse.expression.table_statement import (
    ClickHouseTableExpression,
    ClickHouseValuesExpression,
)
from rhosocial.activerecord.backend.impl.clickhouse.expression.vector import (
    ClickHouseCreateVectorIndexExpression,
    ClickHouseVectorLiteralExpression,
)


@pytest.fixture(scope="module")
def dialect():
    return ClickHouseDialect(version=(26, 7, 1))


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
            CreateTriggerExpression(
                dialect, "trg", "tbl", TriggerTiming.BEFORE, [TriggerEvent.INSERT], "fn"
            ).to_sql()

    def test_format_drop_trigger_raises(self, dialect):
        with pytest.raises(UnsupportedFeatureError):
            DropTriggerExpression(dialect, "trg", "tbl").to_sql()


class TestSpatialStub:
    def test_supports_flags(self, dialect):
        assert dialect.supports_spatial_type("POINT") is False
        assert dialect.supports_spatial_index() is False
        assert dialect.supports_geojson() is False
        assert dialect.supports_geometry_type() is False
        assert dialect.supports_point_type() is False

    def test_format_spatial_literal_raises(self, dialect):
        with pytest.raises(UnsupportedFeatureError):
            ClickHouseSpatialLiteralExpression(dialect, "POINT(0 0)").to_sql()

    def test_format_st_geom_from_text_raises(self, dialect):
        with pytest.raises(UnsupportedFeatureError):
            ClickHouseSTGeomFromTextExpression(dialect, "POINT(0 0)").to_sql()

    def test_format_create_spatial_index_raises(self, dialect):
        with pytest.raises(UnsupportedFeatureError):
            ClickHouseCreateSpatialIndexExpression(dialect, "idx", "tbl", "col").to_sql()


class TestVectorStub:
    def test_supports_flags(self, dialect):
        assert dialect.supports_vector_type() is False
        assert dialect.supports_vector_index() is False

    def test_format_vector_literal_raises(self, dialect):
        with pytest.raises(UnsupportedFeatureError):
            ClickHouseVectorLiteralExpression(dialect, [1.0, 2.0]).to_sql()

    def test_format_create_vector_index_raises(self, dialect):
        with pytest.raises(UnsupportedFeatureError):
            ClickHouseCreateVectorIndexExpression(dialect, "idx", "tbl", "col").to_sql()


class TestOptimizerHintStub:
    def test_supports_flags(self, dialect):
        assert dialect.supports_optimizer_hint() is False
        assert dialect.supports_hypergraph_optimizer() is False

    def test_format_optimizer_hint_raises(self, dialect):
        with pytest.raises(UnsupportedFeatureError):
            ClickHouseOptimizerHintExpression(
                dialect, [SetVarHint("optimizer_switch", "hypergraph_optimizer=on")]
            ).to_sql()


class TestTableStatementStub:
    def test_supports_flags(self, dialect):
        assert dialect.supports_table_statement() is False
        assert dialect.supports_values_table_constructor() is False

    def test_format_table_statement_raises(self, dialect):
        with pytest.raises(UnsupportedFeatureError):
            ClickHouseTableExpression(dialect, "tbl").to_sql()

    def test_format_values_statement_raises(self, dialect):
        with pytest.raises(UnsupportedFeatureError):
            ClickHouseValuesExpression(dialect, [[1]]).to_sql()


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
            ClickHouseAnalyzeTableExpression(dialect, ["tbl"]).to_sql()


class TestRoutineStub:
    def test_supports_flags(self, dialect):
        assert dialect.supports_procedure() is False
        assert dialect.supports_stored_function() is False
        assert dialect.supports_call() is False

    def test_format_create_procedure_raises(self, dialect):
        with pytest.raises(UnsupportedFeatureError):
            ClickHouseCreateProcedureExpression(dialect, "proc").to_sql()

    def test_format_call_statement_raises(self, dialect):
        with pytest.raises(UnsupportedFeatureError):
            ClickHouseCallExpression(dialect, "proc").to_sql()


class TestLoadXmlStub:
    def test_supports_load_xml(self, dialect):
        assert dialect.supports_load_xml() is False

    def test_format_load_xml_raises(self, dialect):
        with pytest.raises(UnsupportedFeatureError):
            ClickHouseLoadXMLEXpression(dialect, "/tmp/data.xml", "tbl").to_sql()


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
            ClickHouseFlushExpression(dialect, [FlushOption.TABLES]).to_sql()

    def test_format_kill_raises(self, dialect):
        with pytest.raises(UnsupportedFeatureError):
            ClickHouseKillExpression(dialect, 1).to_sql()


class TestJsonDualityViewStub:
    def test_supports_flags(self, dialect):
        assert dialect.supports_json_duality_view() is False
        assert dialect.supports_json_duality_view_dml() is False

    def test_format_create_json_duality_view_raises(self, dialect):
        with pytest.raises(UnsupportedFeatureError):
            CreateJsonDualityViewExpression(dialect, "v", DualityObjectSpec()).to_sql()


class TestFullTextStub:
    def test_supports_flags(self, dialect):
        assert dialect.supports_fulltext_index() is False
        assert dialect.supports_fulltext_search() is False

    def test_format_match_against_raises(self, dialect):
        with pytest.raises(UnsupportedFeatureError):
            ClickHouseMatchAgainstExpression(dialect, ["title"], "term").to_sql()


class TestJsonTableStub:
    def test_supports_json_table(self, dialect):
        assert dialect.supports_json_table() is False

    def test_format_json_table_raises(self, dialect):
        with pytest.raises(UnsupportedFeatureError):
            ClickHouseJSONTableExpression(
                dialect,
                '{"key": "value"}',
                "$.key",
                [JSONTableColumn(name="col1", type="VARCHAR(255)", path="$.col1")],
            ).to_sql()


class TestUpsertStub:
    def test_supports_on_conflict(self, dialect):
        assert dialect.supports_on_conflict_clause() is False

    def test_format_on_conflict_raises(self, dialect):
        with pytest.raises(UnsupportedFeatureError):
            OnConflictClause(dialect, None, do_nothing=True).to_sql()

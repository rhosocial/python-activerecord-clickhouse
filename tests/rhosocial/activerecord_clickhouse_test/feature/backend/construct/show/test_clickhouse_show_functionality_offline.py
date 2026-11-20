# tests/rhosocial/activerecord_clickhouse_test/feature/backend/construct/show/
# test_clickhouse_show_functionality_offline.py
"""Offline unit tests for ``ClickHouseShowFunctionality``.

Every method is exercised with a ``MagicMock`` backend: ``backend.execute`` is
fed a controlled result whose ``.data`` is a list of row dicts, and the mapped
dataclasses are asserted field by field. No ClickHouse server, socket or
``clickhouse-connect`` client is involved.

Only the synchronous class exists for this backend -- clickhouse-connect is a
sync-only library and there is no ``AsyncClickHouseShowFunctionality`` -- so
there are deliberately no async tests here.

The parse helpers for the MySQL-only statements are tested directly too. Their
public entry points raise ``UnsupportedFeatureError`` before reaching them, but
the helpers themselves are pure and part of this module's surface.
"""

from dataclasses import astuple
from datetime import datetime
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from rhosocial.activerecord.backend.dialect.exceptions import UnsupportedFeatureError

from rhosocial.activerecord.backend.impl.clickhouse.dialect import ClickHouseDialect
from rhosocial.activerecord.backend.impl.clickhouse.show import types as show_types
from rhosocial.activerecord.backend.impl.clickhouse.show.functionality import (
    ClickHouseShowFunctionality,
)


def _result(rows):
    """Mimic the object ``backend.execute()`` returns: it exposes ``.data``."""
    return SimpleNamespace(data=rows)


@pytest.fixture
def functionality():
    backend = MagicMock()
    backend.dialect = ClickHouseDialect(version=(26, 7, 3))
    return ClickHouseShowFunctionality(backend=backend, version=(26, 7, 3))


def _feed(functionality, rows):
    """Make ``backend.execute`` return ``rows`` and hand back the mock."""
    backend = functionality._backend
    backend.execute.return_value = _result(rows)
    return backend


class TestConstruction:
    """The object keeps the backend, its dialect and the recorded version."""

    def test_init_wires_backend_dialect_and_version(self, functionality):
        assert isinstance(functionality._backend, MagicMock)
        assert isinstance(functionality.dialect, ClickHouseDialect)
        assert functionality._version == (26, 7, 3)
        assert functionality.dialect is functionality._backend.dialect

    def test_version_defaults_to_none(self):
        backend = MagicMock()
        backend.dialect = ClickHouseDialect(version=(26, 7, 3))
        func = ClickHouseShowFunctionality(backend=backend)
        assert func._version is None

    def test_show_parser_is_the_shared_mixin(self, functionality):
        from rhosocial.activerecord.backend.impl.clickhouse.introspection.show_introspector import (
            ShowMixin,
        )

        assert functionality._show_parser() is ShowMixin


class TestCreateTable:
    """``SHOW CREATE TABLE`` answers a single ``statement`` column."""

    def test_maps_statement_column(self, functionality):
        stmt = "CREATE TABLE default.t\n(\n    `id` Int64\n)\nENGINE = MergeTree"
        backend = _feed(functionality, [{"statement": stmt}])
        result = functionality.create_table("t")
        assert isinstance(result, show_types.ShowCreateTableResult)
        assert result.table_name == "t"
        assert result.create_statement == stmt
        backend.execute.assert_called_once()
        sql, params = backend.execute.call_args.args
        assert sql.startswith("SHOW CREATE TABLE")
        assert isinstance(params, tuple)

    def test_schema_is_rendered_into_the_sql(self, functionality):
        backend = _feed(functionality, [{"statement": "..."}])
        functionality.create_table("t", schema="db")
        sql = backend.execute.call_args.args[0]
        assert "db" in sql

    def test_empty_rows_return_none(self, functionality):
        _feed(functionality, [])
        assert functionality.create_table("t") is None

    def test_mysql_column_names_are_not_consulted(self, functionality):
        _feed(functionality, [{"Create Table": "..."}])
        assert functionality.create_table("t").create_statement == ""


class TestCreateView:
    """``SHOW CREATE VIEW`` also answers a single ``statement`` column."""

    def test_maps_statement_column_and_leaves_mysql_fields_empty(self, functionality):
        stmt = "CREATE VIEW default.v AS SELECT id FROM t"
        _feed(functionality, [{"statement": stmt}])
        result = functionality.create_view("v", schema="db")
        assert isinstance(result, show_types.ShowCreateViewResult)
        assert result.view_name == "v"
        assert result.create_statement == stmt
        assert result.character_set_client is None
        assert result.collation_connection is None

    def test_empty_rows_return_none(self, functionality):
        _feed(functionality, [])
        assert functionality.create_view("v") is None

    def test_executes_rendered_sql(self, functionality):
        backend = _feed(functionality, [{"statement": "..."}])
        functionality.create_view("v")
        backend.execute.assert_called_once()
        assert backend.execute.call_args.args[0].startswith("SHOW CREATE VIEW")


class TestColumns:
    """``SHOW [FULL] COLUMNS`` answers lower-cased ClickHouse names."""

    COLUMN_ROWS = [
        {"field": "al", "type": "UInt8", "null": "NO", "key": "", "default": "id", "extra": ""},
        {
            "field": "id",
            "type": "UInt32",
            "null": "NO",
            "key": "PRI SOR",
            "default": None,
            "extra": "",
        },
    ]
    FULL_COLUMN_ROWS = [
        {
            "field": "id",
            "type": "UInt32",
            "null": "NO",
            "key": "PRI SOR",
            "default": None,
            "extra": "",
            "collation": None,
            "comment": "c",
            "privileges": "",
        }
    ]

    def test_maps_lowercase_fields(self, functionality):
        _feed(functionality, self.COLUMN_ROWS)
        result = functionality.columns("t")
        assert all(isinstance(row, show_types.ShowColumnResult) for row in result)
        assert [(r.field, r.type, r.null, r.key) for r in result] == [
            ("al", "UInt8", "NO", ""),
            ("id", "UInt32", "NO", "PRI SOR"),
        ]
        assert [(r.default, r.extra) for r in result] == [("id", ""), (None, "")]

    def test_full_flag_reads_the_full_only_columns(self, functionality):
        _feed(functionality, self.FULL_COLUMN_ROWS)
        row = functionality.columns("t", full=True)[0]
        assert (row.collation, row.comment, row.privileges) == (None, "c", "")

    def test_plain_columns_leave_full_only_fields_empty(self, functionality):
        _feed(functionality, self.COLUMN_ROWS)
        assert all(
            r.collation is None and r.comment is None and r.privileges is None
            for r in functionality.columns("t")
        )

    def test_like_and_schema_reach_the_sql(self, functionality):
        backend = _feed(functionality, [])
        assert functionality.columns("t", schema="db", like="i%", full=True) == []
        sql, params = backend.execute.call_args.args
        assert "FULL COLUMNS" in sql and "db" in sql
        assert params == ("i%",)

    def test_empty_rows_return_empty_list(self, functionality):
        _feed(functionality, [])
        assert functionality.columns("t") == []


class TestIndexes:
    """``SHOW INDEX`` answers ``pk_col`` where MySQL answers ``Column_name``."""

    INDEX_ROWS = [
        {
            "table": "t",
            "non_unique": 1,
            "key_name": "idx_s",
            "seq_in_index": 1,
            "pk_col": "",
            "collation": None,
            "cardinality": 0,
            "sub_part": None,
            "packed": None,
            "null": None,
            "index_type": "BLOOM_FILTER",
            "comment": "",
            "index_comment": "",
            "visible": "YES",
            "expression": "s",
        },
        {
            "table": "t",
            "non_unique": 1,
            "key_name": "PRIMARY",
            "seq_in_index": 1,
            "pk_col": "id",
            "collation": "A",
            "cardinality": 0,
            "sub_part": None,
            "packed": None,
            "null": None,
            "index_type": "PRIMARY",
            "comment": "",
            "index_comment": "",
            "visible": "YES",
            "expression": "",
        },
    ]

    def test_maps_pk_col_and_clickhouse_index_type(self, functionality):
        _feed(functionality, self.INDEX_ROWS)
        result = functionality.indexes("t")
        assert all(isinstance(row, show_types.ShowIndexResult) for row in result)
        assert [r.column_name for r in result] == ["", "id"]
        assert [r.index_type for r in result] == ["BLOOM_FILTER", "PRIMARY"]
        assert [r.key_name for r in result] == ["idx_s", "PRIMARY"]
        assert [r.expression for r in result] == ["s", ""]

    def test_empty_rows_return_empty_list(self, functionality):
        backend = _feed(functionality, [])
        assert functionality.indexes("t", schema="db") == []
        assert backend.execute.call_args.args[0].startswith("SHOW INDEX")


class TestTables:
    """``SHOW [FULL] TABLES`` names the column ``name`` and reports an engine."""

    def test_full_tables_map_name_and_engine(self, functionality):
        _feed(
            functionality, [{"name": "a", "engine": "MergeTree"}, {"name": "v", "engine": "View"}]
        )
        result = functionality.tables(full=True)
        assert all(isinstance(row, show_types.ShowTableResult) for row in result)
        assert [(r.name, r.table_type) for r in result] == [
            ("a", "MergeTree"),
            ("v", "View"),
        ]

    def test_plain_tables_have_no_engine(self, functionality):
        _feed(functionality, [{"name": "a"}])
        assert [(r.name, r.table_type) for r in functionality.tables()] == [("a", None)]

    def test_empty_rows_return_empty_list(self, functionality):
        _feed(functionality, [])
        assert functionality.tables(like="a%") == []


class TestDatabases:
    """``SHOW DATABASES`` names its column ``name``, not ``Database``."""

    def test_maps_names(self, functionality):
        _feed(functionality, [{"name": "default"}, {"name": "system"}])
        result = functionality.databases()
        assert all(isinstance(row, show_types.ShowDatabaseResult) for row in result)
        assert [r.name for r in result] == ["default", "system"]

    def test_empty_rows_return_empty_list(self, functionality):
        backend = _feed(functionality, [])
        assert functionality.databases(like="d%") == []
        assert backend.execute.call_args.args[0].startswith("SHOW DATABASES")


class TestProcesslist:
    """``SHOW PROCESSLIST`` is ``system.processes`` verbatim."""

    ROW = {
        "query_id": "0a944dd1-8a7e-4fd2-9733-e9e44f4d9f53",
        "user": "root",
        "address": "::ffff:192.168.65.1",
        "port": 39550,
        "elapsed": 0.00164,
        "current_database": "test_db",
        "query": "SELECT 1",
    }

    def test_maps_system_process_columns(self, functionality):
        _feed(functionality, [self.ROW])
        row = functionality.processlist()[0]
        assert isinstance(row, show_types.ShowProcessListResult)
        assert row.id == self.ROW["query_id"]
        assert row.user == "root"
        assert row.host == "::ffff:192.168.65.1:39550"
        assert row.time == pytest.approx(0.00164)
        assert row.db == "test_db"
        assert row.info == "SELECT 1"
        assert row.command is None and row.state is None

    def test_host_without_port_is_stringified(self, functionality):
        _feed(functionality, [{"query_id": "q", "user": "u", "address": "localhost", "port": None}])
        assert functionality.processlist()[0].host == "localhost"

    def test_full_flag_is_accepted_and_does_not_change_sql(self, functionality):
        backend = _feed(functionality, [])
        assert functionality.processlist(full=True) == []
        assert backend.execute.call_args.args[0] == "SHOW PROCESSLIST"

    def test_empty_rows_return_empty_list(self, functionality):
        _feed(functionality, [])
        assert functionality.processlist() == []


class TestEngines:
    """``SHOW ENGINES`` is ``system.table_engines``: name plus supports_* flags."""

    ROW = {
        "name": "AggregatingMergeTree",
        "supports_settings": 1,
        "supports_skipping_indices": 1,
        "supports_projections": 1,
        "supports_sort_order": 1,
        "supports_ttl": 1,
        "supports_replication": 0,
        "supports_deduplication": 0,
        "supports_parallel_insert": 1,
        "description": "# AggregatingMergeTree",
        "syntax": "AGGREGATING",
        "examples": "",
        "introduced_in": "",
        "related": ["ReplicatedAggregatingMergeTree"],
    }

    def test_maps_all_fields(self, functionality):
        _feed(functionality, [self.ROW])
        row = functionality.engines()[0]
        assert isinstance(row, show_types.ShowEngineResult)
        assert row.engine == "AggregatingMergeTree"
        assert (row.supports_settings, row.supports_skipping_indices) == (1, 1)
        assert (row.supports_projections, row.supports_sort_order) == (1, 1)
        assert (row.supports_ttl, row.supports_replication) == (1, 0)
        assert (row.supports_deduplication, row.supports_parallel_insert) == (0, 1)
        assert (row.description, row.syntax, row.examples) == (
            "# AggregatingMergeTree",
            "AGGREGATING",
            "",
        )
        assert row.introduced_in == ""
        assert row.related == ["ReplicatedAggregatingMergeTree"]

    def test_missing_documentation_columns_yield_none(self, functionality):
        _feed(functionality, [{"name": "Memory"}])
        row = functionality.engines()[0]
        assert row.engine == "Memory"
        assert row.description is None and row.syntax is None and row.related is None

    def test_empty_rows_return_empty_list(self, functionality):
        backend = _feed(functionality, [])
        assert functionality.engines() == []
        assert backend.execute.call_args.args[0] == "SHOW ENGINES"


class TestGrants:
    """``SHOW GRANTS`` returns one column named after the statement and format."""

    def test_reads_the_native_protocol_column(self, functionality):
        _feed(functionality, [{"GRANTS FORMAT Native": "GRANT SELECT ON *.* TO root"}])
        result = functionality.grants()
        assert isinstance(result[0], show_types.ShowGrantResult)
        assert result[0].grants == "GRANT SELECT ON *.* TO root"

    def test_reads_a_single_unrecognised_column(self, functionality):
        _feed(functionality, [{"SHOW GRANTS": "GRANT ALL ON *.* TO u"}])
        assert functionality.grants()[0].grants == "GRANT ALL ON *.* TO u"

    def test_user_is_rendered_but_host_is_dropped(self, functionality):
        backend = _feed(functionality, [{"GRANTS FOR root": "GRANT ALL"}])
        functionality.grants(user="root", host="localhost")
        sql = backend.execute.call_args.args[0]
        assert "GRANTS FOR" in sql and "root" in sql
        assert "localhost" not in sql

    def test_empty_rows_return_empty_list(self, functionality):
        _feed(functionality, [])
        assert functionality.grants() == []


class TestUnsupportedMethods:
    """Every MySQL-only SHOW fails fast without touching ``backend.execute``."""

    @pytest.mark.parametrize(
        "method, kwargs, feature, suggestion",
        [
            ("table_status", {}, "SHOW TABLE STATUS", "system.tables"),
            ("triggers", {}, "SHOW TRIGGERS", "does not support triggers"),
            (
                "create_trigger",
                {"trigger": "trg"},
                "SHOW CREATE TRIGGER",
                "does not support triggers",
            ),
            ("variables", {}, "SHOW VARIABLES", "system.settings"),
            ("status", {}, "SHOW STATUS", "system.metrics"),
            ("warnings", {}, "SHOW WARNINGS", "system.query_log"),
            ("errors", {}, "SHOW ERRORS", "system.errors"),
            ("charset", {}, "SHOW CHARACTER SET", "system.character_sets"),
            ("collation", {}, "SHOW COLLATION", "system.collations"),
            ("plugins", {}, "SHOW PLUGINS", "system.functions"),
        ],
    )
    def test_unsupported_methods_raise(self, functionality, method, kwargs, feature, suggestion):
        with pytest.raises(UnsupportedFeatureError) as excinfo:
            getattr(functionality, method)(**kwargs)
        assert excinfo.value.dialect_name == "ClickHouse"
        assert excinfo.value.feature_name == feature
        assert suggestion in excinfo.value.suggestion
        functionality._backend.execute.assert_not_called()


class TestInlineParseHelpers:
    """The private parsers are pure and reachable directly, unlike their public methods."""

    def test_parse_table_status(self, functionality):
        rows = [
            {
                "Name": "t",
                "Engine": "MergeTree",
                "Version": 1,
                "Row_format": "Fixed",
                "Rows": 10,
                "Avg_row_length": 20,
                "Data_length": 200,
                "Max_data_length": 0,
                "Index_length": 0,
                "Data_free": 0,
                "Auto_increment": None,
                "Create_time": datetime(2026, 1, 2, 3, 4, 5),
                "Update_time": None,
                "Check_time": None,
                "Collation": None,
                "Checksum": None,
                "Create_options": "",
                "Comment": "c",
            }
        ]
        row = functionality._parse_table_status_result(_result(rows))[0]
        assert isinstance(row, show_types.ShowTableStatusResult)
        assert row.name == "t" and row.engine == "MergeTree"
        assert row.rows == 10 and row.avg_row_length == 20
        assert row.create_time == "2026-01-02 03:04:05"
        assert row.update_time is None and row.check_time is None
        assert row.comment == "c"

    def test_parse_table_status_empty(self, functionality):
        assert functionality._parse_table_status_result(_result([])) == []

    @pytest.mark.parametrize(
        "row, expected_name, expected_event",
        [
            (
                {
                    "Trigger": "trg",
                    "Event": "INSERT",
                    "Table": "t",
                    "Statement": "SQL",
                    "Timing": "BEFORE",
                },
                "trg",
                "INSERT",
            ),
            (
                {
                    "TRIGGER_NAME": "trg2",
                    "EVENT_MANIPULATION": "UPDATE",
                    "EVENT_OBJECT_TABLE": "t2",
                    "ACTION_STATEMENT": "SQL2",
                    "ACTION_TIMING": "AFTER",
                },
                "trg2",
                "UPDATE",
            ),
        ],
    )
    def test_parse_triggers(self, functionality, row, expected_name, expected_event):
        result = functionality._parse_triggers_result(_result([row]))[0]
        assert isinstance(result, show_types.ShowTriggerResult)
        assert result.trigger_name == expected_name
        assert result.event == expected_event
        assert result.table_name in ("t", "t2")
        assert result.statement in ("SQL", "SQL2")
        assert result.timing in ("BEFORE", "AFTER")

    def test_parse_create_trigger_and_empty(self, functionality):
        row = {
            "Trigger": "trg",
            "SQL Original Statement": "CREATE TRIGGER ...",
            "character_set_client": "utf8",
            "collation_connection": "utf8_general_ci",
            "Database Collation": "utf8_general_ci",
        }
        result = functionality._parse_create_trigger_result(_result([row]), "trg")
        assert isinstance(result, show_types.ShowCreateTriggerResult)
        assert result.trigger_name == "trg"
        assert result.create_statement == "CREATE TRIGGER ..."
        assert result.character_set_client == "utf8"
        assert result.database_collation == "utf8_general_ci"
        assert functionality._parse_create_trigger_result(_result([]), "trg") is None

    @pytest.mark.parametrize(
        "helper, result_type, rows, expected",
        [
            (
                "_parse_variables_result",
                show_types.ShowVariableResult,
                [{"Variable_name": "v", "Value": "1"}],
                [("v", "1")],
            ),
            (
                "_parse_status_result",
                show_types.ShowStatusResult,
                [{"Variable_name": "s", "Value": "2"}],
                [("s", "2")],
            ),
            (
                "_parse_warnings_result",
                show_types.ShowWarningResult,
                [{"Level": "Warning", "Code": 3, "Message": "m"}],
                [("Warning", 3, "m")],
            ),
            (
                "_parse_errors_result",
                show_types.ShowWarningResult,
                [{"Level": "Error", "Code": 4, "Message": "e"}],
                [("Error", 4, "e")],
            ),
            (
                "_parse_charset_result",
                show_types.ShowCharsetResult,
                [
                    {
                        "Charset": "utf8",
                        "Description": "UTF-8",
                        "Default collation": "utf8_general_ci",
                        "Maxlen": 3,
                    }
                ],
                [("utf8", "UTF-8", "utf8_general_ci", 3)],
            ),
            (
                "_parse_collation_result",
                show_types.ShowCollationResult,
                [
                    {
                        "Collation": "c",
                        "Charset": "utf8",
                        "Id": 1,
                        "Default": "Yes",
                        "Compiled": "Yes",
                        "Sortlen": 1,
                    }
                ],
                [("c", "utf8", 1, "Yes", "Yes", 1)],
            ),
            (
                "_parse_plugins_result",
                show_types.ShowPluginResult,
                [
                    {
                        "Name": "p",
                        "Status": "ACTIVE",
                        "Type": "STORAGE ENGINE",
                        "Library": "l",
                        "License": "GPL",
                    }
                ],
                [("p", "ACTIVE", "STORAGE ENGINE", "l", "GPL")],
            ),
        ],
    )
    def test_simple_parse_helpers(self, functionality, helper, result_type, rows, expected):
        result = getattr(functionality, helper)(_result(rows))
        assert len(result) == 1
        assert isinstance(result[0], result_type)
        assert astuple(result[0]) == expected[0]

    def test_simple_parse_helpers_on_empty_rows(self, functionality):
        for helper in (
            "_parse_variables_result",
            "_parse_status_result",
            "_parse_warnings_result",
            "_parse_errors_result",
            "_parse_charset_result",
            "_parse_collation_result",
            "_parse_plugins_result",
        ):
            assert getattr(functionality, helper)(_result([])) == []

# tests/rhosocial/activerecord_clickhouse_test/feature/backend/execute/introspection/test_show_introspector_offline.py
"""Offline, mock-only tests for :mod:`.show_introspector`.

ClickHouse is synchronous only -- ``clickhouse-connect`` is a sync driver and
``AsyncShowIntrospector`` is a ``NotImplementedError`` placeholder that cannot
run in production -- so this module deliberately covers only ``ShowMixin``
(pure ``parse_*`` helpers) and the synchronous ``ShowIntrospector``.

No real database, socket or driver is involved.  The ``parse_*`` helpers are
called directly with representative ClickHouse rows, and the sync
introspector is wired to a ``MagicMock`` backend (for ``dialect``) and a
``MagicMock`` executor (for the single I/O seam ``_exec`` -> ``execute``).
"""
from unittest.mock import MagicMock

import pytest

from rhosocial.activerecord.backend.dialect.exceptions import UnsupportedFeatureError
from rhosocial.activerecord.backend.impl.clickhouse.dialect import ClickHouseDialect
from rhosocial.activerecord.backend.impl.clickhouse.introspection.show_introspector import (
    ShowIntrospector,
    ShowMixin,
)
from rhosocial.activerecord.backend.impl.clickhouse.show import types as show_types


# --------------------------------------------------------------------------- #
# Pure parse helpers
# --------------------------------------------------------------------------- #


class TestParseCreateStatements:
    """``SHOW CREATE TABLE`` / ``VIEW`` / ``TRIGGER`` answer a ``statement`` column."""

    CREATE_ROW = {"statement": "CREATE TABLE default.t\n(\n    `id` Int64\n)\nENGINE = MergeTree"}
    VIEW_ROW = {"statement": "CREATE VIEW default.v AS SELECT 1"}

    def test_create_table_reads_statement_column(self):
        result = ShowMixin.parse_create_table([self.CREATE_ROW], "t")
        assert isinstance(result, show_types.ShowCreateTableResult)
        assert result.table_name == "t"
        assert result.create_statement == self.CREATE_ROW["statement"]

    def test_create_table_ignores_mysql_column_names(self):
        result = ShowMixin.parse_create_table([{"Table": "t", "Create Table": "..."}], "t")
        assert result.create_statement == ""

    def test_create_view_reads_statement_column(self):
        result = ShowMixin.parse_create_view([self.VIEW_ROW], "v")
        assert isinstance(result, show_types.ShowCreateViewResult)
        assert result.view_name == "v"
        assert result.create_statement == self.VIEW_ROW["statement"]

    def test_create_view_leaves_optional_fields_none(self):
        result = ShowMixin.parse_create_view([self.VIEW_ROW], "v")
        assert result.character_set_client is None
        assert result.collation_connection is None

    def test_create_parsers_return_none_for_no_rows(self):
        assert ShowMixin.parse_create_table([], "t") is None
        assert ShowMixin.parse_create_view([], "v") is None

    def test_create_trigger_reads_mysql_shape(self):
        row = {
            "Trigger": "trg",
            "SQL Original Statement": "CREATE TRIGGER trg ...",
            "character_set_client": "utf8",
            "collation_connection": "utf8_general_ci",
            "Database Collation": "utf8_general_ci",
        }
        result = ShowMixin.parse_create_trigger([row], "trg")
        assert isinstance(result, show_types.ShowCreateTriggerResult)
        assert (result.trigger_name, result.create_statement) == ("trg", "CREATE TRIGGER trg ...")
        assert result.character_set_client == "utf8"
        assert result.collation_connection == "utf8_general_ci"
        assert result.database_collation == "utf8_general_ci"

    def test_create_trigger_reads_information_schema_shape(self):
        row = {"TRIGGER": "trg2", "CREATE TRIGGER": "CREATE TRIGGER trg2 ..."}
        result = ShowMixin.parse_create_trigger([row], "fallback")
        assert result.trigger_name == "trg2"
        assert result.create_statement == "CREATE TRIGGER trg2 ..."

    def test_create_trigger_falls_back_to_the_called_name(self):
        result = ShowMixin.parse_create_trigger([{}], "my_trigger")
        assert result.trigger_name == "my_trigger"
        assert result.create_statement == ""

    def test_create_trigger_returns_none_for_no_rows(self):
        assert ShowMixin.parse_create_trigger([], "trg") is None


class TestParseColumnsAndIndexes:
    """ClickHouse's lower-cased column names, including ``pk_col`` for indexes."""

    COLUMN_ROWS = [
        {
            "field": "al", "type": "UInt8", "null": "NO", "key": "", "default": "id", "extra": "",
        },
        {
            "field": "id", "type": "UInt32", "null": "NO", "key": "PRI SOR", "default": None,
            "extra": "",
        },
    ]
    FULL_COLUMN_ROW = {
        "field": "id", "type": "UInt32", "null": "NO", "key": "PRI SOR", "default": None,
        "extra": "", "collation": None, "comment": "comment", "privileges": "",
    }

    def test_columns_read_clickhouse_field_names(self):
        result = ShowMixin.parse_columns(self.COLUMN_ROWS)
        assert all(isinstance(r, show_types.ShowColumnResult) for r in result)
        assert [(r.field, r.type, r.null, r.key) for r in result] == [
            ("al", "UInt8", "NO", ""),
            ("id", "UInt32", "NO", "PRI SOR"),
        ]

    def test_columns_carry_default_and_extra(self):
        result = ShowMixin.parse_columns(self.COLUMN_ROWS)
        assert [(r.default, r.extra) for r in result] == [("id", ""), (None, "")]

    def test_full_columns_read_collation_comment_and_privileges(self):
        result = ShowMixin.parse_columns([self.FULL_COLUMN_ROW])
        assert (result[0].collation, result[0].comment, result[0].privileges) == (
            None, "comment", "",
        )

    def test_columns_ignore_mysql_field_names(self):
        result = ShowMixin.parse_columns(
            [{"Field": "id", "Type": "int", "Null": "NO", "Key": "PRI", "Extra": ""}]
        )
        assert (result[0].field, result[0].type, result[0].key) == (None, None, None)

    def test_indexes_read_pk_col_as_column_name(self):
        rows = [
            {
                "table": "t", "non_unique": 1, "key_name": "PRIMARY", "seq_in_index": 1,
                "pk_col": "id", "collation": "A", "cardinality": 0, "index_type": "PRIMARY",
                "comment": "", "index_comment": "", "visible": "YES", "expression": "",
            },
            {
                "table": "t", "non_unique": 1, "key_name": "idx_s", "seq_in_index": 1,
                "pk_col": "", "collation": None, "cardinality": 0,
                "index_type": "BLOOM_FILTER", "expression": "s",
            },
        ]
        result = ShowMixin.parse_indexes(rows)
        assert all(isinstance(r, show_types.ShowIndexResult) for r in result)
        assert [r.column_name for r in result] == ["id", ""]
        assert [r.index_type for r in result] == ["PRIMARY", "BLOOM_FILTER"]
        assert result[1].expression == "s"

    def test_indexes_ignore_mysql_column_names(self):
        result = ShowMixin.parse_indexes(
            [{"Table": "t", "Key_name": "PRIMARY", "Column_name": "id", "Index_type": "BTREE"}]
        )
        assert (result[0].table_name, result[0].column_name, result[0].index_type) == (
            None, None, None,
        )


class TestParseListRows:
    """``SHOW TABLES`` / ``SHOW DATABASES`` use ClickHouse's ``name`` column."""

    def test_tables_read_name_only(self):
        result = ShowMixin.parse_tables([{"name": "a"}, {"name": "b"}])
        assert all(isinstance(r, show_types.ShowTableResult) for r in result)
        assert [(r.name, r.table_type) for r in result] == [("a", None), ("b", None)]

    def test_full_tables_treat_engine_as_table_type(self):
        result = ShowMixin.parse_tables([{"name": "t", "engine": "MergeTree"}])
        assert (result[0].name, result[0].table_type) == ("t", "MergeTree")

    def test_databases_read_name(self):
        result = ShowMixin.parse_databases([{"name": "default"}, {"name": "system"}])
        assert all(isinstance(r, show_types.ShowDatabaseResult) for r in result)
        assert [r.name for r in result] == ["default", "system"]

    def test_list_parsers_ignore_mysql_column_names(self):
        assert ShowMixin.parse_tables([{"Tables_in_db": "t"}])[0].name is None
        assert ShowMixin.parse_databases([{"Database": "default"}])[0].name is None


class TestParseTableStatusAndTriggers:
    """Result shapes for statements ClickHouse does not emit, still parsed faithfully."""

    def test_table_status_reads_fields_and_stringifies_times(self):
        row = {
            "Name": "t", "Engine": "MergeTree", "Version": 1, "Rows": 10,
            "Create_time": "2026-01-01 00:00:00", "Comment": "hello",
        }
        result = ShowMixin.parse_table_status([row])
        assert isinstance(result[0], show_types.ShowTableStatusResult)
        assert result[0].name == "t"
        assert result[0].engine == "MergeTree"
        assert result[0].rows == 10
        assert result[0].create_time == "2026-01-01 00:00:00"
        assert result[0].comment == "hello"

    @pytest.mark.parametrize("field", ["Create_time", "Update_time", "Check_time"])
    def test_table_status_leaves_falsy_times_none(self, field):
        result = ShowMixin.parse_table_status([{"Name": "t", field: 0}])[0]
        assert getattr(result, field.lower()) is None

    def test_triggers_read_mysql_shape(self):
        row = {
            "Trigger": "trg", "Event": "INSERT", "Table": "t", "Statement": "SET @x = 1",
            "Timing": "BEFORE", "Created": "2026-01-01", "sql_mode": "STRICT",
            "Definer": "root@localhost", "character_set_client": "utf8",
            "collation_connection": "utf8_general_ci", "Database Collation": "utf8_general_ci",
        }
        result = ShowMixin.parse_triggers([row])
        assert isinstance(result[0], show_types.ShowTriggerResult)
        assert (result[0].trigger_name, result[0].event, result[0].table_name) == (
            "trg", "INSERT", "t",
        )
        assert (result[0].statement, result[0].timing) == ("SET @x = 1", "BEFORE")
        assert result[0].database_collation == "utf8_general_ci"

    def test_triggers_read_information_schema_shape(self):
        row = {
            "TRIGGER_NAME": "trg2", "EVENT_MANIPULATION": "UPDATE",
            "EVENT_OBJECT_TABLE": "t2", "ACTION_STATEMENT": "SET @y = 2",
            "ACTION_TIMING": "AFTER",
        }
        result = ShowMixin.parse_triggers([row])[0]
        assert (result.trigger_name, result.event, result.table_name, result.statement) == (
            "trg2", "UPDATE", "t2", "SET @y = 2",
        )
        assert result.timing == "AFTER"


class TestParseVariablesStatusWarnings:
    """The simple two- and three-column MySQL-shaped parsers."""

    def test_variables(self):
        result = ShowMixin.parse_variables(
            [{"Variable_name": "max_threads", "Value": "16"}]
        )
        assert isinstance(result[0], show_types.ShowVariableResult)
        assert (result[0].variable_name, result[0].value) == ("max_threads", "16")

    def test_status(self):
        result = ShowMixin.parse_status([{"Variable_name": "Uptime", "Value": "42"}])
        assert isinstance(result[0], show_types.ShowStatusResult)
        assert (result[0].variable_name, result[0].value) == ("Uptime", "42")

    def test_warnings(self):
        result = ShowMixin.parse_warnings(
            [{"Level": "Warning", "Code": 1234, "Message": "careful"}]
        )
        assert isinstance(result[0], show_types.ShowWarningResult)
        assert (result[0].level, result[0].code, result[0].message) == (
            "Warning", 1234, "careful",
        )


class TestParseProcessList:
    """``SHOW PROCESSLIST`` maps ``system.processes`` onto MySQL-shaped fields."""

    ROW = {
        "query_id": "0a944dd1-8a7e-4fd2-9733-e9e44f4d9f53", "user": "root",
        "address": "192.168.65.1", "port": 39550, "elapsed": 0.00164,
        "current_database": "test_db", "query": "SELECT 1",
    }

    def test_maps_clickhouse_columns(self):
        result = ShowMixin.parse_processlist([self.ROW])
        assert isinstance(result[0], show_types.ShowProcessListResult)
        row = result[0]
        assert row.id == "0a944dd1-8a7e-4fd2-9733-e9e44f4d9f53"
        assert row.user == "root"
        assert row.host == "192.168.65.1:39550"
        assert row.time == pytest.approx(0.00164)
        assert row.db == "test_db"
        assert row.info == "SELECT 1"

    def test_command_and_state_are_always_none(self):
        row = ShowMixin.parse_processlist([self.ROW])[0]
        assert row.command is None
        assert row.state is None

    @pytest.mark.parametrize(
        ("address", "port", "expected"),
        [
            ("192.168.0.1", 9000, "192.168.0.1:9000"),
            ("192.168.0.1", None, "192.168.0.1"),
            (None, 9000, None),
            (None, None, None),
        ],
    )
    def test_host_joining(self, address, port, expected):
        row = {"query_id": "q", "user": "u", "address": address, "port": port}
        assert ShowMixin.parse_processlist([row])[0].host == expected

    def test_ignores_mysql_processlist_columns(self):
        row = {"Id": 1, "User": "root", "Host": "localhost", "Command": "Query", "Time": 0}
        result = ShowMixin.parse_processlist([row])[0]
        assert (result.id, result.user, result.host, result.command, result.time) == (
            None, None, None, None, None,
        )


class TestParseEngines:
    """``SHOW ENGINES`` is ``system.table_engines`` verbatim."""

    FULL_ROW = {
        "name": "MergeTree", "supports_settings": 1, "supports_skipping_indices": 1,
        "supports_projections": 1, "supports_sort_order": 1, "supports_ttl": 1,
        "supports_replication": 0, "supports_deduplication": 0,
        "supports_parallel_insert": 1, "description": "# MergeTree", "syntax": "MERGE",
        "examples": "", "introduced_in": "", "related": ["ReplicatedMergeTree"],
    }

    def test_reads_all_eight_support_flags(self):
        row = ShowMixin.parse_engines([self.FULL_ROW])[0]
        assert isinstance(row, show_types.ShowEngineResult)
        assert row.engine == "MergeTree"
        assert (
            row.supports_settings, row.supports_skipping_indices, row.supports_projections,
            row.supports_sort_order, row.supports_ttl, row.supports_replication,
            row.supports_deduplication, row.supports_parallel_insert,
        ) == (1, 1, 1, 1, 1, 0, 0, 1)

    def test_reads_documentation_columns(self):
        row = ShowMixin.parse_engines([self.FULL_ROW])[0]
        assert (row.description, row.syntax, row.examples, row.introduced_in) == (
            "# MergeTree", "MERGE", "", "",
        )
        assert row.related == ["ReplicatedMergeTree"]

    def test_older_servers_leave_documentation_columns_none(self):
        row = ShowMixin.parse_engines([{"name": "Memory", "supports_settings": 1}])[0]
        assert row.engine == "Memory"
        assert all(
            getattr(row, field) is None
            for field in ("description", "syntax", "examples", "introduced_in", "related")
        )

    def test_ignores_mysql_engine_columns(self):
        row = ShowMixin.parse_engines(
            [{"Engine": "InnoDB", "Support": "DEFAULT", "Transactions": "YES"}]
        )[0]
        assert row.engine is None
        assert row.supports_settings is None


class TestParseCharsetCollationPlugins:
    """The remaining MySQL-shaped result dataclasses."""

    def test_charset(self):
        row = {
            "Charset": "utf8", "Description": "UTF-8", "Default collation": "utf8_general_ci",
            "Maxlen": 3,
        }
        result = ShowMixin.parse_charset([row])[0]
        assert isinstance(result, show_types.ShowCharsetResult)
        assert (result.charset, result.description, result.default_collation, result.maxlen) == (
            "utf8", "UTF-8", "utf8_general_ci", 3,
        )

    def test_collation(self):
        row = {
            "Collation": "utf8_bin", "Charset": "utf8", "Id": 83, "Default": "",
            "Compiled": "Yes", "Sortlen": 1,
        }
        result = ShowMixin.parse_collation([row])[0]
        assert isinstance(result, show_types.ShowCollationResult)
        assert (result.collation, result.charset, result.id, result.default,
                result.compiled, result.sortlen) == ("utf8_bin", "utf8", 83, "", "Yes", 1)

    def test_plugins(self):
        rows = [
            {"Name": "p1", "Status": "ACTIVE", "Type": "STORAGE ENGINE",
             "Library": "p1.so", "License": "GPL"},
            {"Name": "p2", "Status": "ACTIVE", "Type": "INFORMATION_SCHEMA"},
        ]
        result = ShowMixin.parse_plugins(rows)
        assert all(isinstance(r, show_types.ShowPluginResult) for r in result)
        assert (result[0].name, result[0].library, result[0].license) == ("p1", "p1.so", "GPL")
        assert (result[1].library, result[1].license) == (None, None)


class TestParseGrants:
    """``SHOW GRANTS`` has one column whose name depends on the emitted statement."""

    def test_reads_grants_prefixed_column(self):
        rows = [{"GRANTS FORMAT Native": "GRANT ALL ON *.* TO root"}]
        result = ShowMixin.parse_grants(rows)
        assert isinstance(result[0], show_types.ShowGrantResult)
        assert result[0].grants == "GRANT ALL ON *.* TO root"

    def test_falls_back_to_single_unnamed_column(self):
        result = ShowMixin.parse_grants([{"SHOW GRANTS": "GRANT SELECT ON db.* TO u"}])
        assert result[0].grants == "GRANT SELECT ON db.* TO u"

    def test_prefers_grants_prefixed_column_when_several_exist(self):
        row = {"GRANTS FOR u": "GRANT SELECT", "Other": "value"}
        assert ShowMixin.parse_grants([row])[0].grants == "GRANT SELECT"

    def test_empty_row_yields_none(self):
        assert ShowMixin.parse_grants([{}])[0].grants is None

    def test_multiple_unrecognised_columns_yield_none(self):
        row = {"a": "one", "b": "two"}
        assert ShowMixin.parse_grants([row])[0].grants is None


class TestListParsersEmptyRows:
    """Every list-returning parser returns ``[]`` for no rows."""

    @pytest.mark.parametrize(
        "parser",
        [
            ShowMixin.parse_columns,
            ShowMixin.parse_indexes,
            ShowMixin.parse_tables,
            ShowMixin.parse_databases,
            ShowMixin.parse_table_status,
            ShowMixin.parse_triggers,
            ShowMixin.parse_variables,
            ShowMixin.parse_status,
            ShowMixin.parse_processlist,
            ShowMixin.parse_warnings,
            ShowMixin.parse_engines,
            ShowMixin.parse_charset,
            ShowMixin.parse_collation,
            ShowMixin.parse_grants,
            ShowMixin.parse_plugins,
        ],
    )
    def test_empty_rows_give_empty_list(self, parser):
        assert parser([]) == []


# --------------------------------------------------------------------------- #
# Synchronous ShowIntrospector -- MagicMock backend and executor only
# --------------------------------------------------------------------------- #


class TestShowIntrospectorSync:
    """Public methods build SQL through the dialect and parse mocked rows."""

    @pytest.fixture
    def dialect(self):
        return ClickHouseDialect(version=(26, 7, 3))

    @pytest.fixture
    def executor(self):
        return MagicMock()

    @pytest.fixture
    def introspector(self, dialect, executor):
        backend = MagicMock()
        backend.dialect = dialect
        return ShowIntrospector(backend, executor)

    def test_dialect_property_delegates_to_backend(self, introspector, dialect):
        assert introspector.dialect is dialect

    def test_create_table_maps_executor_rows(self, introspector, executor):
        executor.execute.return_value = [{"statement": "CREATE TABLE default.t (id Int64)"}]
        result = introspector.create_table("t")
        assert isinstance(result, show_types.ShowCreateTableResult)
        assert (result.table_name, result.create_statement) == (
            "t", "CREATE TABLE default.t (id Int64)",
        )
        executor.execute.assert_called_once_with("SHOW CREATE TABLE `t`", ())

    def test_create_view_maps_executor_rows(self, introspector, executor):
        executor.execute.return_value = [{"statement": "CREATE VIEW default.v AS SELECT 1"}]
        result = introspector.create_view("v")
        assert (result.view_name, result.create_statement) == (
            "v", "CREATE VIEW default.v AS SELECT 1",
        )
        executor.execute.assert_called_once_with("SHOW CREATE VIEW `v`", ())

    def test_columns_maps_executor_rows(self, introspector, executor):
        executor.execute.return_value = [
            {"field": "id", "type": "UInt32", "null": "NO", "key": "PRI SOR"}
        ]
        result = introspector.columns("t")
        assert [r.field for r in result] == ["id"]
        executor.execute.assert_called_once_with("SHOW COLUMNS FROM `t`", ())

    def test_columns_passes_schema_full_and_like(self, introspector, executor):
        executor.execute.return_value = []
        assert introspector.columns("t", schema="db", full=True, like="i%") == []
        executor.execute.assert_called_once_with(
            "SHOW FULL COLUMNS FROM `db`.`t` LIKE %s", ("i%",),
        )

    def test_indexes_maps_executor_rows(self, introspector, executor):
        executor.execute.return_value = [
            {
                "table": "t", "non_unique": 1, "key_name": "PRIMARY", "seq_in_index": 1,
                "pk_col": "id", "index_type": "PRIMARY",
            }
        ]
        result = introspector.indexes("t")
        assert [r.column_name for r in result] == ["id"]
        executor.execute.assert_called_once_with("SHOW INDEX FROM `t`", ())

    def test_tables_maps_executor_rows(self, introspector, executor):
        executor.execute.return_value = [{"name": "t", "engine": "MergeTree"}]
        result = introspector.tables()
        assert [(r.name, r.table_type) for r in result] == [("t", "MergeTree")]
        executor.execute.assert_called_once_with("SHOW TABLES", ())

    def test_tables_full_passes_through(self, introspector, executor):
        executor.execute.return_value = []
        assert introspector.tables(full=True) == []
        executor.execute.assert_called_once_with("SHOW FULL TABLES", ())

    def test_databases_maps_executor_rows(self, introspector, executor):
        executor.execute.return_value = [{"name": "default"}]
        assert [r.name for r in introspector.databases()] == ["default"]
        executor.execute.assert_called_once_with("SHOW DATABASES", ())

    def test_databases_passes_like_pattern(self, introspector, executor):
        executor.execute.return_value = []
        assert introspector.databases(like="d%") == []
        executor.execute.assert_called_once_with("SHOW DATABASES LIKE %s", ("d%",))

    def test_processlist_maps_executor_rows(self, introspector, executor):
        executor.execute.return_value = [
            {"query_id": "q-1", "user": "root", "address": "127.0.0.1", "port": 9000}
        ]
        result = introspector.processlist()
        assert [(r.id, r.host) for r in result] == [("q-1", "127.0.0.1:9000")]
        executor.execute.assert_called_once_with("SHOW PROCESSLIST", ())

    def test_engines_maps_executor_rows(self, introspector, executor):
        executor.execute.return_value = [{"name": "MergeTree", "supports_ttl": 1}]
        result = introspector.engines()
        assert [(r.engine, r.supports_ttl) for r in result] == [("MergeTree", 1)]
        executor.execute.assert_called_once_with("SHOW ENGINES", ())

    def test_grants_maps_executor_rows(self, introspector, executor):
        executor.execute.return_value = [{"GRANTS": "GRANT ALL ON *.* TO root"}]
        result = introspector.grants()
        assert [r.grants for r in result] == ["GRANT ALL ON *.* TO root"]
        executor.execute.assert_called_once_with("SHOW GRANTS", ())

    def test_grants_passes_user_but_ignores_host(self, introspector, executor):
        executor.execute.return_value = []
        assert introspector.grants(user="root", host="localhost") == []
        executor.execute.assert_called_once_with("SHOW GRANTS FOR `root`", ())

    def test_exec_delegates_to_executor(self, introspector, executor):
        executor.execute.return_value = [{"name": "x"}]
        assert introspector._exec("SOMETHING", ("p",)) == [{"name": "x"}]
        executor.execute.assert_called_once_with("SOMETHING", ("p",))


class TestShowIntrospectorUnsupportedMethods:
    """MySQL-only SHOW methods fail fast before any executor call."""

    @pytest.fixture
    def introspector(self):
        backend = MagicMock()
        backend.dialect = ClickHouseDialect(version=(26, 7, 3))
        executor = MagicMock()
        return ShowIntrospector(backend, executor), executor

    @pytest.mark.parametrize(
        "call",
        [
            lambda s: s.table_status(),
            lambda s: s.triggers(),
            lambda s: s.create_trigger("trg"),
            lambda s: s.variables(),
            lambda s: s.status(),
            lambda s: s.warnings(),
            lambda s: s.errors(),
            lambda s: s.charset(),
            lambda s: s.collation(),
            lambda s: s.plugins(),
        ],
    )
    def test_unsupported_methods_raise_without_executing(self, introspector, call):
        subject, executor = introspector
        with pytest.raises(UnsupportedFeatureError):
            call(subject)
        executor.execute.assert_not_called()

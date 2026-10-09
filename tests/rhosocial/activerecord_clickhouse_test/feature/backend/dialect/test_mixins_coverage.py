# tests/rhosocial/activerecord_clickhouse_test/feature/backend/dialect/test_mixins_coverage.py
"""
Coverage tests for ClickHouse column mixin, partition mixin, and explain types.
"""

import pytest

from rhosocial.activerecord.backend.impl.clickhouse.dialect import ClickHouseDialect


@pytest.fixture
def dialect():
    return ClickHouseDialect(version=(26, 7, 3))


class TestModifyColumnMixin:
    """ClickHouseModifyColumnMixin coverage."""

    def test_modify_column_no_after_no_first(self, dialect):
        from rhosocial.activerecord.backend.expression.types import IntegerType
        from rhosocial.activerecord.backend.expression.statements import ColumnDefinition
        from types import SimpleNamespace

        action = SimpleNamespace(
            column=ColumnDefinition(dialect, "id", IntegerType(dialect)),
            after_column=None,
            first=False,
        )
        sql, _ = dialect.format_modify_column_action(action)
        assert "MODIFY COLUMN" in sql
        assert "id" in sql
        assert "AFTER" not in sql
        assert "FIRST" not in sql

    def test_modify_column_with_after(self, dialect):
        from rhosocial.activerecord.backend.expression.types import VarCharType
        from rhosocial.activerecord.backend.expression.statements import ColumnDefinition
        from types import SimpleNamespace

        action = SimpleNamespace(
            column=ColumnDefinition(dialect, "name", VarCharType(length=50, dialect=dialect)),
            after_column="id",
            first=False,
        )
        sql, _ = dialect.format_modify_column_action(action)
        assert "MODIFY COLUMN" in sql
        assert "AFTER" in sql
        assert "id" in sql

    def test_change_column(self, dialect):
        from rhosocial.activerecord.backend.expression.types import IntegerType
        from rhosocial.activerecord.backend.expression.statements import ColumnDefinition
        from types import SimpleNamespace

        action = SimpleNamespace(
            column=ColumnDefinition(dialect, "new_id", IntegerType(dialect)),
            old_name="old_id",
            after_column=None,
            first=False,
        )
        sql, _ = dialect.format_change_column_action(action)
        assert "CHANGE COLUMN" in sql
        assert "old_id" in sql
        assert "new_id" in sql

    def test_change_column_with_after(self, dialect):
        from rhosocial.activerecord.backend.expression.types import VarCharType
        from rhosocial.activerecord.backend.expression.statements import ColumnDefinition
        from types import SimpleNamespace

        action = SimpleNamespace(
            column=ColumnDefinition(dialect, "name", VarCharType(length=50, dialect=dialect)),
            old_name="old_name",
            after_column="id",
            first=False,
        )
        sql, _ = dialect.format_change_column_action(action)
        assert "CHANGE COLUMN" in sql
        assert "AFTER" in sql
        assert "id" in sql


class TestPartitionMixinCoverage:
    """ClickHousePartitionMixin supports_* flags."""

    def test_table_partitioning_supported(self, dialect):
        assert dialect.supports_table_partitioning() is True

    def test_partitioned_table_creation_supported(self, dialect):
        assert dialect.supports_partitioned_table_creation() is True

    def test_partition_metadata_introspection_supported(self, dialect):
        """ClickHouse reports partitions in ``system.parts``, not information_schema."""
        assert dialect.supports_partition_metadata_introspection() is True

    def test_mysql_partition_types_unsupported(self, dialect):
        """The MySQL strategies are gone; the generic contract still answers False."""
        assert dialect.supports_range_table_partitioning() is False
        assert dialect.supports_list_table_partitioning() is False
        assert dialect.supports_hash_table_partitioning() is False
        assert dialect.supports_subpartitioning() is False

    def test_partition_maintenance_supported(self, dialect):
        """``ALTER TABLE ... DROP/DETACH/ATTACH PARTITION ID`` are ClickHouse's own."""
        assert dialect.supports_drop_partition() is True
        assert dialect.supports_detach_partition() is True
        assert dialect.supports_attach_partition() is True

    def test_mysql_partition_statement_switches_are_gone(self, dialect):
        """No ``supports_*`` switch exists for a statement ClickHouse lacks.

        One switch per MySQL statement would be an inventory of statements this
        server has never had; the authoritative inventory is the ALTER ... PARTITION
        reference. Absence of the method is the honest answer.
        """
        for name in (
            "supports_range_columns_partitioning",
            "supports_list_columns_partitioning",
            "supports_key_table_partitioning",
            "supports_linear_hash_partitioning",
            "supports_linear_key_partitioning",
            "supports_partition_definition_options",
            "supports_partition_value_maxvalue",
            "supports_add_partition",
            "supports_truncate_partition",
            "supports_reorganize_partition",
            "supports_remove_partitioning",
            "supports_coalesce_partition",
            "supports_exchange_partition",
            "supports_analyze_partition",
            "supports_check_partition",
            "supports_optimize_partition",
            "supports_rebuild_partition",
            "supports_repair_partition",
        ):
            assert not hasattr(dialect, name), name

    def test_mysql_partition_formatters_are_gone(self, dialect):
        for name in (
            "format_partition_by_range",
            "format_partition_by_range_columns",
            "format_partition_by_list",
            "format_partition_by_list_columns",
            "format_partition_by_hash",
            "format_partition_by_key",
            "format_partition_definition_options",
            "format_partition_value",
            "format_partition_name_list",
            "format_subpartition_by",
            "format_subpartition_definition",
            "format_add_partition_statement",
            "format_truncate_partition_statement",
            "format_reorganize_partition_statement",
            "format_exchange_partition_statement",
            "format_remove_partitioning_statement",
            "format_coalesce_partition_statement",
            "format_analyze_partition_statement",
            "format_check_partition_statement",
            "format_optimize_partition_statement",
            "format_rebuild_partition_statement",
            "format_repair_partition_statement",
            "format_get_partitions_expression",
        ):
            assert not hasattr(dialect, name), name

    def test_inventory_records_what_clickhouse_does_have(self, dialect):
        """The ALTER-partition inventory is kept as data, so it can be asserted on."""
        from rhosocial.activerecord.backend.impl.clickhouse.mixins.partition import (
            ALTER_PARTITION_INVENTORY,
            MYSQL_ONLY_PARTITION_STATEMENTS,
            MYSQL_ONLY_PARTITION_SYNTAX,
        )

        assert "DETACH PARTITION|PART" in ALTER_PARTITION_INVENTORY
        assert "DROP PARTITION|PART" in ALTER_PARTITION_INVENTORY
        assert "ATTACH PARTITION|PART" in ALTER_PARTITION_INVENTORY
        # No MySQL partition statement appears in the ClickHouse inventory.
        for statement in MYSQL_ONLY_PARTITION_STATEMENTS:
            assert statement not in ALTER_PARTITION_INVENTORY, statement
        # Nor does any MySQL inline boundary spelling.
        for syntax in MYSQL_ONLY_PARTITION_SYNTAX:
            assert syntax not in ALTER_PARTITION_INVENTORY, syntax


class TestExplainTypesCoverage:
    """ClickHouseExplainResult and ClickHouseExplainRow coverage."""

    def test_clickhouse_explain_row_attributes(self, dialect):
        from rhosocial.activerecord.backend.impl.clickhouse.explain import (
            ClickHouseExplainRow, ClickHouseExplainResult
        )
        row = ClickHouseExplainRow(
            id=1, select_type="SIMPLE", table="t", type="ALL",
            possible_keys=None, key=None, key_len=None, ref=None,
            rows=100, extra="Using where",
        )
        assert row.id == 1
        assert row.select_type == "SIMPLE"
        assert row.type == "ALL"
        assert row.rows == 100
        assert row.extra == "Using where"

    def test_clickhouse_explain_result_from_raw_rows(self):
        from rhosocial.activerecord.backend.impl.clickhouse.explain import (
            ClickHouseExplainResult, ClickHouseExplainRow
        )
        raw = [{"id": 1, "select_type": "SIMPLE", "table": "t", "type": "ALL",
                "possible_keys": None, "key": None, "key_len": None, "ref": None,
                "rows": 10, "extra": ""}]
        result = ClickHouseExplainResult(
            raw_rows=raw, sql="EXPLAIN SELECT 1", duration=0.01,
            rows=[ClickHouseExplainRow(**r) for r in raw],
        )
        assert result.sql == "EXPLAIN SELECT 1"
        assert result.duration == 0.01
        assert len(result.rows) == 1
        assert result.is_full_scan is True
        assert result.is_index_used is False
        assert result.is_covering_index is False
        # analyze_index_usage returns MySQL-style strings (legacy)
        assert result.analyze_index_usage() == "full_scan"
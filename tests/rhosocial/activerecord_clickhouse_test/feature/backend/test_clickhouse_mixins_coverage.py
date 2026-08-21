# tests/rhosocial/activerecord_clickhouse_test/feature/backend/test_clickhouse_mixins_coverage.py
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
            column=ColumnDefinition("id", IntegerType()),
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
            column=ColumnDefinition("name", VarCharType(50)),
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
            column=ColumnDefinition("new_id", IntegerType()),
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
            column=ColumnDefinition("name", VarCharType(50)),
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

    def test_mysql_partition_types_unsupported(self, dialect):
        assert dialect.supports_range_table_partitioning() is False
        assert dialect.supports_list_table_partitioning() is False
        assert dialect.supports_hash_table_partitioning() is False


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
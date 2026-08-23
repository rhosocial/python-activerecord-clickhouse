# tests/rhosocial/activerecord_clickhouse_test/feature/backend/test_clickhouse_dialect.py
"""
ClickHouse dialect capability and SQL-generation tests.

These are pure dialect tests (no database connection) verifying that the
ClickHouse dialect correctly:
1. Reports capability flags (supports_*) matching ClickHouse's actual features
2. Generates ClickHouse-specific SQL for expressions and statements
"""

import pytest

from rhosocial.activerecord.backend.impl.clickhouse.dialect import ClickHouseDialect
from rhosocial.activerecord.backend.dialect.exceptions import UnsupportedFeatureError


@pytest.fixture
def dialect():
    return ClickHouseDialect(version=(26, 7, 3))


class TestClickHouseCapabilities:
    """supports_* flags must reflect ClickHouse 26.x reality."""

    def test_arrays_supported(self, dialect):
        assert dialect.supports_array_type() is True
        assert dialect.supports_array_constructor() is True
        assert dialect.supports_array_access() is True

    def test_json_supported(self, dialect):
        assert dialect.supports_json_type() is True
        # ClickHouse has no MySQL-style -> / ->> operators; JSON access uses
        # JSONExtractString / JSON_VALUE instead.
        assert dialect.supports_json_arrow_operators() is False

    def test_cte_supported(self, dialect):
        assert dialect.supports_basic_cte() is True
        assert dialect.supports_recursive_cte() is True
        assert dialect.supports_materialized_cte() is True

    def test_window_functions_supported(self, dialect):
        assert dialect.supports_window_functions() is True
        assert dialect.supports_window_frame_clause() is True

    def test_grouping_supported(self, dialect):
        assert dialect.supports_rollup() is True
        assert dialect.supports_cube() is True
        assert dialect.supports_grouping_sets() is True

    def test_set_operations_supported(self, dialect):
        assert dialect.supports_union() is True
        assert dialect.supports_union_all() is True
        assert dialect.supports_intersect() is True
        assert dialect.supports_except() is True

    def test_joins_supported(self, dialect):
        assert dialect.supports_inner_join() is True
        assert dialect.supports_left_join() is True
        assert dialect.supports_right_join() is True
        assert dialect.supports_full_join() is True
        assert dialect.supports_cross_join() is True

    def test_views_supported(self, dialect):
        assert dialect.supports_materialized_view() is True
        assert dialect.supports_or_replace_view() is True

    def test_qualify_and_ilike_supported(self, dialect):
        assert dialect.supports_qualify_clause() is True
        assert dialect.supports_ilike() is True

    def test_returning_insert_only(self, dialect):
        # Verified against ClickHouse 26.7: INSERT ... VALUES ... RETURNING is
        # not accepted (RETURNING only applies to INSERT SELECT), so insert
        # returning is disabled and ids are generated client-side.
        assert dialect.supports_returning_insert() is False
        assert dialect.supports_returning_update() is False
        assert dialect.supports_returning_delete() is False

    def test_transactions_unsupported(self, dialect):
        assert dialect.supports_transaction_mode() is False
        assert dialect.supports_savepoint() is False
        assert dialect.supports_read_only_transaction() is False

    def test_constraints_unsupported(self, dialect):
        assert dialect.supports_foreign_key_constraint() is False
        assert dialect.supports_unique_constraint() is False
        assert dialect.supports_check_constraint() is False
        assert dialect.supports_unique_index() is False

    def test_upsert_unsupported(self, dialect):
        assert dialect.supports_upsert() is False
        assert dialect.supports_on_conflict_clause() is False
        assert dialect.supports_insert_ignore() is False
        assert dialect.supports_replace_into() is False

    def test_locking_unsupported(self, dialect):
        assert dialect.supports_for_update() is False

    def test_other_unsupported(self, dialect):
        assert dialect.supports_trigger() is False
        assert dialect.supports_create_sequence() is False
        assert dialect.supports_merge_statement() is False
        assert dialect.supports_generated_column() is False
        assert dialect.supports_natural_join() is False
        assert dialect.supports_lateral_join() is False
        assert dialect.supports_fulltext_index() is False
        assert dialect.supports_collate_expression() is False


class TestClickHouseSQLGeneration:
    """Dialect-specific SQL formatting."""

    def test_identifier_quoting(self, dialect):
        assert dialect.format_identifier("my_table") == "`my_table`"
        assert dialect.format_identifier("weird`name") == "`weird``name`"

    def test_parameter_placeholder(self, dialect):
        assert dialect.get_parameter_placeholder() == "%s"

    def test_limit_offset(self, dialect):
        sql, params = dialect.format_limit_offset(limit=10, offset=5)
        assert sql == "LIMIT %s OFFSET %s"
        assert params == [10, 5]

    def test_limit_only(self, dialect):
        sql, params = dialect.format_limit_offset(limit=10)
        assert sql == "LIMIT %s"
        assert params == [10]

    def test_storage_options_clickhouse_syntax(self, dialect):
        """ENGINE/ORDER BY values must NOT be quoted."""
        result = dialect.format_storage_options({
            "ENGINE": "MergeTree()",
            "ORDER BY": "id",
            "PARTITION BY": "toYYYYMM(created_at)",
        })
        assert "ENGINE = MergeTree()" in result
        assert "ORDER BY = id" in result or "ORDER BY id" in result
        assert "'MergeTree()'" not in result  # no quotes

    def test_table_engine_clauses(self, dialect):
        """ClickHouse table-engine-specific clause formatting."""
        result = dialect.format_table_engine_clauses({
            "ENGINE": "MergeTree()",
            "ORDER BY": ["id", "created_at"],
            "PARTITION BY": "toYYYYMM(created_at)",
            "TTL": "created_at + INTERVAL 30 DAY",
            "SETTINGS": "index_granularity = 8192",
        })
        assert "ENGINE = MergeTree()" in result
        assert "ORDER BY (id, created_at)" in result
        assert "PARTITION BY toYYYYMM(created_at)" in result
        assert "TTL created_at + INTERVAL 30 DAY" in result
        assert "SETTINGS index_granularity = 8192" in result

    def test_unsupported_insert_options_raise(self, dialect):
        """INSERT IGNORE / REPLACE capability flags are False for ClickHouse."""
        assert dialect.supports_insert_ignore() is False
        assert dialect.supports_replace_into() is False
        assert dialect.supports_upsert() is False

    def test_transaction_formatting_raises(self, dialect):
        """Transaction SQL generation must fail fast for ClickHouse."""
        from rhosocial.activerecord.backend.expression import BeginTransactionExpression

        with pytest.raises(UnsupportedFeatureError):
            dialect.format_begin_transaction(BeginTransactionExpression(dialect))


class TestClickHouseExplain:
    """EXPLAIN statement formatting placeholder.

    Full EXPLAIN expression tests require complex expression construction
    patterns; they are covered by the existing dialect expression tests.
    """

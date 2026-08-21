# tests/rhosocial/activerecord_clickhouse_test/feature/backend/test_clickhouse_introspection.py
"""
ClickHouse introspection tests using a live database connection.

Verifies table/column introspection against ClickHouse system tables.
"""

import pytest


@pytest.fixture
def intro_table(clickhouse_backend):
    backend = clickhouse_backend
    backend.execute("DROP TABLE IF EXISTS test_intro_ch")
    backend.execute("""
        CREATE TABLE test_intro_ch (
            id UInt32,
            name String,
            score Float64,
            created_at DateTime
        ) ENGINE = MergeTree()
        ORDER BY id
    """)
    yield backend, "test_intro_ch"
    backend.execute("DROP TABLE IF EXISTS test_intro_ch")


class TestClickHouseIntrospection:
    def test_list_tables_finds_created_table(self, clickhouse_backend, intro_table):
        backend, table = intro_table
        tables = backend.introspector.list_tables("test_db")
        names = [t.name for t in tables]
        assert table in names

    def test_get_table_info_returns_table(self, clickhouse_backend, intro_table):
        backend, table = intro_table
        info = backend.introspector.get_table_info(table)
        assert info is not None
        assert info.name == table

    def test_table_info_has_clickhouse_columns(self, clickhouse_backend, intro_table):
        backend, table = intro_table
        info = backend.introspector.get_table_info(table)
        col_names = [c.name for c in (info.columns or [])]
        assert "id" in col_names
        assert "name" in col_names
        assert "score" in col_names
        assert "created_at" in col_names

    def test_column_data_types(self, clickhouse_backend, intro_table):
        backend, table = intro_table
        info = backend.introspector.get_table_info(table)
        types = {c.name: c.data_type for c in (info.columns or [])}
        assert types["id"].lower().startswith("uint32")
        assert types["name"].lower().startswith("string")
        assert types["score"].lower().startswith("float64")
        assert types["created_at"].lower().startswith("datetime")

    def test_list_columns(self, clickhouse_backend, intro_table):
        backend, table = intro_table
        cols = backend.introspector.list_columns(table)
        assert len(cols) == 4

    def test_foreign_keys_fail_fast(self, clickhouse_backend, intro_table):
        """ClickHouse has no foreign keys; introspection raises fast."""
        from rhosocial.activerecord.backend.dialect.exceptions import UnsupportedFeatureError
        backend, table = intro_table
        with pytest.raises(UnsupportedFeatureError):
            backend.introspector.list_foreign_keys(table)

    def test_get_table_info_nonexistent_returns_none(self, clickhouse_backend):
        info = clickhouse_backend.introspector.get_table_info("no_such_table_xyz")
        assert info is None

    def test_supports_introspection_capabilities(self, clickhouse_backend):
        d = clickhouse_backend.dialect
        assert d.supports_introspection() is True
        assert d.supports_table_introspection() is True
        assert d.supports_column_introspection() is True
        assert d.supports_foreign_key_introspection() is False
        assert d.supports_trigger_introspection() is False

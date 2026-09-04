# tests/rhosocial/activerecord_clickhouse_test/feature/backend/backend/test_backend_ops.py
"""
ClickHouse backend operational tests.

Covers backend execution features: execute_many, ping, reconnection,
parameter handling, and error mapping.
"""

import pytest

from rhosocial.activerecord.backend.impl.clickhouse import ClickHouseBackend, ClickHouseConnectionConfig


@pytest.fixture
def ops_table(clickhouse_backend):
    backend = clickhouse_backend
    backend.execute("DROP TABLE IF EXISTS test_ops")
    backend.execute("""
        CREATE TABLE test_ops (
            id UInt32,
            name String,
            val Int32
        ) ENGINE = MergeTree()
        ORDER BY id
    """)
    yield "test_ops"
    backend.execute("DROP TABLE IF EXISTS test_ops")


class TestClickHouseBackendOperations:
    def test_execute_many(self, clickhouse_backend, ops_table):
        """Batch execution of the same statement with different params."""
        params_list = [(1, "a", 10), (2, "b", 20), (3, "c", 30)]
        for params in params_list:
            clickhouse_backend.execute(
                f"INSERT INTO {ops_table} (id, name, val) VALUES (%s, %s, %s)",
                params,
            )
        rows = clickhouse_backend.fetch_all(f"SELECT id FROM {ops_table} ORDER BY id")
        assert [r["id"] for r in rows] == [1, 2, 3]

    def test_ping(self, clickhouse_backend):
        """ping() returns True for a live connection."""
        assert clickhouse_backend.ping() is True

    def test_ping_reconnect(self, clickhouse_backend):
        """ping() with reconnect works."""
        assert clickhouse_backend.ping(reconnect=True) is True

    def test_disconnect_then_reconnect(self, clickhouse_backend, ops_table):
        """Backend auto-reconnects after disconnect."""
        clickhouse_backend.disconnect()
        assert clickhouse_backend._connection is None
        # execute triggers reconnect
        clickhouse_backend.execute(f"SELECT count() FROM {ops_table}")
        assert clickhouse_backend._connection is not None

    def test_fetch_all_and_fetch_one(self, clickhouse_backend, ops_table):
        clickhouse_backend.execute(
            f"INSERT INTO {ops_table} (id, name, val) VALUES (%s, %s, %s)", (1, "x", 5)
        )
        clickhouse_backend.execute(
            f"INSERT INTO {ops_table} (id, name, val) VALUES (%s, %s, %s)", (2, "y", 6)
        )
        all_rows = clickhouse_backend.fetch_all(f"SELECT id FROM {ops_table} ORDER BY id")
        assert len(all_rows) == 2
        one = clickhouse_backend.fetch_one(f"SELECT name FROM {ops_table} WHERE id = %s", (1,))
        assert one["name"] == "x"

    def test_invalid_sql_raises_database_error(self, clickhouse_backend):
        """Invalid SQL maps to a DatabaseError."""
        from rhosocial.activerecord.backend.errors import DatabaseError
        with pytest.raises(DatabaseError):
            clickhouse_backend.execute("SELECT * FROM nonexistent_table_xyz")

    def test_get_server_version(self, clickhouse_backend):
        """Server version is a tuple (major, minor, patch)."""
        version = clickhouse_backend.get_server_version()
        assert isinstance(version, tuple)
        assert len(version) == 3
        assert version[0] >= 20  # ClickHouse version 20+

    def test_dialect_is_clickhouse(self, clickhouse_backend):
        from rhosocial.activerecord.backend.impl.clickhouse.dialect import ClickHouseDialect
        assert isinstance(clickhouse_backend.dialect, ClickHouseDialect)

    def test_execute_with_parameters(self, clickhouse_backend, ops_table):
        """Parameterized query with %s placeholders."""
        clickhouse_backend.execute(
            f"INSERT INTO {ops_table} (id, name, val) VALUES (%s, %s, %s)", (7, "param", 70)
        )
        row = clickhouse_backend.fetch_one(
            f"SELECT val FROM {ops_table} WHERE name = %s", ("param",)
        )
        assert row["val"] == 70


class TestClickHouseConnectionConfig:
    def test_config_kwargs(self):
        """Backend can be built from kwargs without explicit config."""
        backend = ClickHouseBackend(
            host="localhost", port=8123, database="db",
            username="user", password="pass",
        )
        assert backend.config.host == "localhost"
        assert backend.config.port == 8123

    def test_config_default_port(self):
        """Default port is 8123 (ClickHouse HTTP)."""
        backend = ClickHouseBackend(host="localhost", database="db")
        assert backend.config.port == 8123

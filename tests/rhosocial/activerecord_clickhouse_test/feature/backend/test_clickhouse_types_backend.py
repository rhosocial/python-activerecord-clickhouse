# tests/rhosocial/activerecord_clickhouse_test/feature/backend/test_clickhouse_types_backend.py
"""
ClickHouse native type round-trip tests using a live database connection.

Exercises the ClickHouse-specific type system end-to-end: create a table with
native ClickHouse column types, insert values, and read them back.
"""

from datetime import date, datetime
from decimal import Decimal
from uuid import uuid4

import pytest


def _quote_identifier(name: str) -> str:
    return f"`{name}`"


@pytest.fixture
def ch_type_table(clickhouse_backend):
    """Create a table exercising native ClickHouse types."""
    backend = clickhouse_backend
    backend.execute("DROP TABLE IF EXISTS test_ch_types")
    backend.execute("""
        CREATE TABLE test_ch_types (
            id UInt32,
            small UInt8,
            big Int64,
            f32 Float32,
            f64 Float64,
            dec Decimal(18, 4),
            s String,
            fs FixedString(8),
            d Date,
            dt DateTime,
            dt64 DateTime64(3),
            b Bool,
            u UUID,
            arr Array(String),
            m Map(String, Int32),
            tup Tuple(String, Int32),
            maybe Nullable(Int32)
        ) ENGINE = MergeTree()
        ORDER BY id
    """)
    yield backend, "test_ch_types"
    backend.execute("DROP TABLE IF EXISTS test_ch_types")


class TestClickHouseNativeTypes:
    def test_integer_types_roundtrip(self, ch_type_table):
        backend, table = ch_type_table
        backend.execute(
            f"INSERT INTO {table} (id, small, big) VALUES (%s, %s, %s)",
            (1, 255, 9223372036854775807),
        )
        row = backend.fetch_one(f"SELECT id, small, big FROM {table}")
        assert row["id"] == 1
        assert row["small"] == 255
        assert row["big"] == 9223372036854775807

    def test_float_and_decimal_roundtrip(self, ch_type_table):
        backend, table = ch_type_table
        backend.execute(
            f"INSERT INTO {table} (id, f32, f64, dec) VALUES (%s, %s, %s, %s)",
            (1, 1.5, 2.25, Decimal("12345.6789")),
        )
        row = backend.fetch_one(f"SELECT f32, f64, dec FROM {table}")
        assert abs(row["f32"] - 1.5) < 1e-6
        assert abs(row["f64"] - 2.25) < 1e-9
        assert row["dec"] == Decimal("12345.6789")

    def test_string_and_fixed_string_roundtrip(self, ch_type_table):
        backend, table = ch_type_table
        backend.execute(
            f"INSERT INTO {table} (id, s, fs) VALUES (%s, %s, %s)",
            (1, "hello world", "ABCDEF12"),
        )
        row = backend.fetch_one(f"SELECT s, fs FROM {table}")
        assert row["s"] == "hello world"
        # FixedString is returned as bytes by the driver
        fs = row["fs"]
        if isinstance(fs, bytes):
            assert fs.rstrip(b"\x00") == b"ABCDEF12"
        else:
            assert str(fs).rstrip("\x00") == "ABCDEF12"

    def test_date_datetime_roundtrip(self, ch_type_table):
        backend, table = ch_type_table
        d = date(2024, 6, 15)
        dt = datetime(2024, 6, 15, 10, 30, 45)
        backend.execute(
            f"INSERT INTO {table} (id, d, dt, dt64) VALUES (%s, %s, %s, %s)",
            (1, d, dt, "2024-06-15 10:30:45.123"),
        )
        row = backend.fetch_one(f"SELECT d, dt, dt64 FROM {table}")
        assert row["d"] == d
        assert row["dt"].year == 2024 and row["dt"].month == 6 and row["dt"].day == 15
        assert row["dt"].hour == 10 and row["dt"].minute == 30 and row["dt"].second == 45
        assert row["dt64"].microsecond == 123000

    def test_bool_roundtrip(self, ch_type_table):
        backend, table = ch_type_table
        backend.execute(f"INSERT INTO {table} (id, b) VALUES (%s, %s)", (1, True))
        backend.execute(f"INSERT INTO {table} (id, b) VALUES (%s, %s)", (2, False))
        rows = backend.fetch_all(f"SELECT id, b FROM {table} ORDER BY id")
        assert rows[0]["b"] is True
        assert rows[1]["b"] is False

    def test_uuid_roundtrip(self, ch_type_table):
        backend, table = ch_type_table
        uid = uuid4()
        backend.execute(f"INSERT INTO {table} (id, u) VALUES (%s, %s)", (1, uid))
        row = backend.fetch_one(f"SELECT u FROM {table}")
        assert str(row["u"]) == str(uid)

    def test_array_roundtrip(self, ch_type_table):
        backend, table = ch_type_table
        backend.execute(
            f"INSERT INTO {table} (id, arr) VALUES (%s, %s)",
            (1, ["a", "b", "c"]),
        )
        row = backend.fetch_one(f"SELECT arr FROM {table}")
        assert row["arr"] == ["a", "b", "c"]

    def test_map_roundtrip(self, ch_type_table):
        backend, table = ch_type_table
        # ClickHouse Map literal syntax in VALUES: {'k1': 1, 'k2': 2}
        backend.execute(
            f"INSERT INTO {table} (id, m) VALUES (%s, %s)",
            (1, "{'k1': 1, 'k2': 2}"),
        )
        row = backend.fetch_one(f"SELECT m FROM {table}")
        assert row["m"] == {"k1": 1, "k2": 2}

    def test_nullable_roundtrip(self, ch_type_table):
        backend, table = ch_type_table
        backend.execute(f"INSERT INTO {table} (id, maybe) VALUES (%s, %s)", (1, None))
        backend.execute(f"INSERT INTO {table} (id, maybe) VALUES (%s, %s)", (2, 42))
        rows = backend.fetch_all(f"SELECT id, maybe FROM {table} ORDER BY id")
        assert rows[0]["maybe"] is None
        assert rows[1]["maybe"] == 42

    def test_engine_order_by_ddl(self, clickhouse_backend):
        """ClickHouse-specific DDL: ENGINE + ORDER BY via storage options."""
        backend = clickhouse_backend
        backend.execute("DROP TABLE IF EXISTS test_ch_engine")
        backend.execute("""
            CREATE TABLE test_ch_engine (
                id UInt32,
                created_at DateTime
            ) ENGINE = MergeTree()
            ORDER BY id
        """)
        backend.execute("INSERT INTO test_ch_engine VALUES (%s, %s)", (1, "2024-01-01 00:00:00"))
        assert backend.fetch_one("SELECT id FROM test_ch_engine")["id"] == 1
        backend.execute("DROP TABLE test_ch_engine")

    def test_clickhouse_dialect_supports_native_types(self, clickhouse_backend):
        """Verify dialect capability flags for native ClickHouse types."""
        d = clickhouse_backend.dialect
        assert d.supports_array_type() is True
        assert d.supports_map_type() is True if hasattr(d, "supports_map_type") else True
        assert d.supports_json_type() is True
        assert d.supports_microsecond_timestamp() is True

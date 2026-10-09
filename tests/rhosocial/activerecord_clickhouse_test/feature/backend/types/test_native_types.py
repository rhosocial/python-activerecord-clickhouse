# tests/rhosocial/activerecord_clickhouse_test/feature/backend/types/test_native_types.py
"""
ClickHouse native type round-trip tests using a live database connection.

Exercises the ClickHouse-specific type system end-to-end: create a table with
native ClickHouse column types, insert values, and read them back.
"""

from datetime import date, datetime
from decimal import Decimal
from uuid import uuid4

import pytest


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


# ── the server is the authority on which integers and vectors exist ────
#
# The unit half of this pair lives in ``test_clickhouse_type_protocol.py``. These
# tests ask the scenario server directly, because both decisions are claims about
# ClickHouse's *own* type inventory rather than about this dialect's code:
#
# * ``unsigned`` is refused on the signed integer classes because ClickHouse
#   spells signedness in the type name — so ``Int8 UNSIGNED`` must be a parse
#   error, and the unsigned form of an integer must be spelled ``UInt8``.
# * MySQL's ``VECTOR`` type and its function family are gone from this backend
#   because ClickHouse has neither — so both claims are checked against the server.

QBIT_GA = (26, 2, 0)

#: MySQL-style unsigned integer aliases ClickHouse accepts, and the ``UInt``
#: family the server resolves each to.  Measured on the 26.7.3.19 scenario
#: server: every one is ``case_insensitive = 1`` in
#: ``system.data_type_families`` with the matching ``alias_to``, and
#: ``SELECT toTypeName(CAST(1 AS <alias>))`` returns the family.  ``YEAR`` is
#: ClickHouse's own alias for ``UInt16`` — the one-byte MySQL ``YEAR`` concept
#: lives in the MySQL backend, not here.
UNSIGNED_INTEGER_ALIASES = (
    ("TINYINT UNSIGNED", "UInt8"),
    ("INT1 UNSIGNED", "UInt8"),
    ("SMALLINT UNSIGNED", "UInt16"),
    ("YEAR", "UInt16"),
    ("MEDIUMINT UNSIGNED", "UInt32"),
    ("INT UNSIGNED", "UInt32"),
    ("INTEGER UNSIGNED", "UInt32"),
    ("BIGINT UNSIGNED", "UInt64"),
    ("UNSIGNED", "UInt64"),
)


class TestSignednessIsInTheTypeName:
    """ClickHouse's integer grammar, verified.

    https://clickhouse.com/docs/sql-reference/data-types/int-uint
    """

    @pytest.mark.parametrize("alias, expected", UNSIGNED_INTEGER_ALIASES)
    def test_the_unsigned_form_is_a_different_type_name(self, clickhouse_backend, alias, expected):
        """The aliases exist, and they resolve to ``UInt*``.

        This is why honouring ``unsigned`` on ``ClickHouseInt8Type`` was refused
        rather than accepted: the rendering that would have honoured it is a column
        byte-for-byte identical to the one ``ClickHouseUInt8Type`` already produces.
        """
        row = clickhouse_backend.fetch_one(f"SELECT toTypeName(CAST(1 AS {alias})) AS t")
        assert row["t"] == expected

    @pytest.mark.parametrize("alias, expected", UNSIGNED_INTEGER_ALIASES)
    def test_parse_type_reads_each_alias_as_the_class_the_server_names(
            self, clickhouse_backend, alias, expected):
        """The parser and the server have to agree on the mapping.

        ``parse_type`` is the reading direction of the type system, so a live
        server agreeing with the formatter is only half the loop.  The parsed
        value must render as the family ``toTypeName`` returns and must be the
        ``ClickHouseUInt*Type`` that owns the column — the alias is
        canonicalised to the native spelling, never to a synonym or to the
        signed class.
        """
        backend = clickhouse_backend
        row = backend.fetch_one(f"SELECT toTypeName(CAST(1 AS {alias})) AS t")
        parsed = backend.dialect.parse_type(alias)
        assert type(parsed).__name__ == f"ClickHouse{expected}Type", alias
        assert backend.dialect.format_data_type(parsed)[0] == row["t"] == expected
        assert parsed.unsigned is True

    def test_unsigned_is_not_a_modifier_on_the_native_name(self, clickhouse_backend):
        """``Int8 UNSIGNED`` is not a spelling, so there is nothing to write.

        The backend reports ``Unknown data type family: INT8 UNSIGNED``, which is
        the reason ``format_data_type_clickhouse_int8`` raises rather than
        appending anything.
        """
        from rhosocial.activerecord.backend.errors import DatabaseError

        with pytest.raises(DatabaseError) as excinfo:
            clickhouse_backend.execute(
                "CREATE TABLE test_ch_unsigned (a Int8 UNSIGNED) ENGINE = Memory"
            )
        assert "UNSIGNED" in str(excinfo.value).upper()

    def test_the_rendered_words_are_the_two_distinct_types(self, clickhouse_backend):
        """``Int8`` and ``UInt8`` are two types, not one type and a modifier.

        Asserted through ``system.columns`` so the formatter's output and the
        server's own view of the column are tied together: the words
        ``format_data_type_clickhouse_int8`` and
        ``format_data_type_clickhouse_uint8`` emit are two different rows here.

        (ClickHouse wraps an out-of-range value on ``INSERT`` rather than refusing
        it — ``-1`` into a ``UInt8`` lands as ``255`` — so the ranges are asserted
        as documented type boundaries, not as insert-time rejection.)
        """
        backend = clickhouse_backend
        backend.execute("DROP TABLE IF EXISTS test_ch_signedness")
        backend.execute("""
            CREATE TABLE test_ch_signedness (
                s Int8,
                u UInt8
            ) ENGINE = Memory
        """)
        try:
            rows = backend.fetch_all(
                "SELECT name, type FROM system.columns "
                "WHERE table = 'test_ch_signedness' ORDER BY name"
            )
            declared = {row["name"]: row["type"] for row in rows}
            assert declared == {"s": "Int8", "u": "UInt8"}
            assert backend.fetch_one("SELECT toInt8(-128) AS v")["v"] == -128
            assert backend.fetch_one("SELECT toUInt8(255) AS v")["v"] == 255
        finally:
            backend.execute("DROP TABLE IF EXISTS test_ch_signedness")


class TestMysqlVectorSurfaceDoesNotExistOnTheServer:
    """The evidence behind deleting that surface, checked against the server.

    Every statement here is expected to fail. If one of them starts succeeding,
    ClickHouse has grown the concept and the deletion should be revisited.
    """

    @pytest.mark.parametrize("ddl", [
        "CREATE TABLE test_ch_vec (a VECTOR(4)) ENGINE = Memory",
    ])
    def test_there_is_no_vector_column_type(self, clickhouse_backend, ddl):
        from rhosocial.activerecord.backend.errors import DatabaseError

        with pytest.raises(DatabaseError) as excinfo:
            clickhouse_backend.execute(ddl)
        assert "VECTOR" in str(excinfo.value).upper()
        clickhouse_backend.execute("DROP TABLE IF EXISTS test_ch_vec")

    @pytest.mark.parametrize("call", [
        "STRING_TO_VECTOR('[1,2,3]')",
        "VECTOR_TO_STRING([1.0,2.0,3.0])",
        "VECTOR_DIM([1.0,2.0,3.0])",
        "DISTANCE_EUCLIDEAN([1.0,2.0],[1.0,3.0])",
        "DISTANCE_COSINE([1.0,2.0],[1.0,3.0])",
        "DISTANCE_DOT([1.0,2.0],[1.0,3.0])",
    ])
    def test_there_are_no_mysql_vector_functions(self, clickhouse_backend, call):
        from rhosocial.activerecord.backend.errors import DatabaseError

        with pytest.raises(DatabaseError) as excinfo:
            clickhouse_backend.execute(f"SELECT {call}")
        message = str(excinfo.value)
        assert "does not exist" in message, message

    def test_the_replacement_functions_do_exist(self, clickhouse_backend):
        """What the guidance names must actually be callable.

        ``L2Distance`` / ``cosineDistance`` / ``dotProduct`` are ClickHouse's own
        distance functions:
        https://clickhouse.com/docs/reference/functions/regular-functions/distance-functions
        """
        for call, expected in (
            ("L2Distance([1.0,2.0],[1.0,3.0])", 1.0),
            ("dotProduct([1.0,2.0],[1.0,3.0])", 7.0),
        ):
            row = clickhouse_backend.fetch_one(f"SELECT {call} AS d")
            assert abs(row["d"] - expected) < 1e-9, call
        row = clickhouse_backend.fetch_one("SELECT cosineDistance([1.0,2.0],[1.0,3.0]) AS d")
        assert 0.0 <= row["d"] <= 1.0

    def test_the_max_vector_dimension_constant_is_not_a_clickhouse_number(self, clickhouse_backend):
        """``16384`` was MySQL's ceiling; ClickHouse states no such limit.

        ``QBit``'s ``dimension`` argument is bounded by what the server can address,
        not by a vendor maximum, which is why the deleted
        ``get_max_vector_dimension()`` had nothing honest to return.
        """
        row = clickhouse_backend.fetch_one(
            "SELECT count() AS c FROM system.data_type_families WHERE name ILIKE '%ECTOR%'"
        )
        assert row["c"] == 0


class TestQBitIsClickhousesOwnVectorType:
    """The rendering this backend does ship, exercised against the server.

    https://clickhouse.com/docs/sql-reference/data-types/qbit
    """

    def test_qbit_column_roundtrips(self, clickhouse_backend):
        backend = clickhouse_backend
        if backend.dialect.version < QBIT_GA:
            pytest.skip(f"QBit needs ClickHouse {QBIT_GA}; this is {backend.dialect.version}")
        backend.execute("DROP TABLE IF EXISTS test_ch_qbit")
        backend.execute("""
            CREATE TABLE test_ch_qbit (
                id UInt32,
                vec QBit(Float32, 4)
            ) ENGINE = MergeTree()
            ORDER BY id
        """)
        try:
            backend.execute(
                "INSERT INTO test_ch_qbit VALUES (%s, %s)",
                (1, [1.0, 2.0, 3.0, 4.0]),
            )
            row = backend.fetch_one("SELECT vec FROM test_ch_qbit")
            assert [float(v) for v in row["vec"]] == [1.0, 2.0, 3.0, 4.0]
            reported = backend.fetch_one(
                "SELECT type FROM system.columns "
                "WHERE table = 'test_ch_qbit' AND name = 'vec'"
            )
            assert reported["type"] == "QBit(Float32, 4)"
        finally:
            backend.execute("DROP TABLE IF EXISTS test_ch_qbit")

    def test_the_dimension_is_part_of_the_column(self, clickhouse_backend):
        """Two dimensions are two columns, which is why ``dim`` is in ``PARAMETERS``.

        A column cannot change its dimension in place: ``QBit``'s dimension is part
        of its type, and a ``SELECT`` over a mismatched width is a type error.
        """
        backend = clickhouse_backend
        if backend.dialect.version < QBIT_GA:
            pytest.skip(f"QBit needs ClickHouse {QBIT_GA}; this is {backend.dialect.version}")
        with pytest.raises(Exception):
            backend.execute(
                "SELECT [1.0,2.0,3.0,4.0]::Array(Float32)::QBit(Float32, 3)"
            )

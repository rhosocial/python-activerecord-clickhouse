# tests/rhosocial/activerecord_clickhouse_test/feature/backend/adapters/test_neutral_type_adapters.py
"""DB-free contract tests for the ClickHouse neutral-type adapters.

Every adapter is exercised through its public ``to_database`` /
``from_database`` pair only; no ClickHouse server is contacted. The wire
forms under test are the ones documented in
``rhosocial.activerecord.backend.impl.clickhouse.adapters``:

    Geometry   -> String (WKT text)
    Vector     -> Array(Float32) (Python list)
    BitString  -> String ("0"/"1" text)
    Range      -> String (JSON text)
    Multirange -> String (JSON array text)
    MacAddress -> String (canonical colon text)
"""

import datetime
import json

import pytest

from rhosocial.activerecord.backend.adapters import (
    BitString,
    Geometry,
    MacAddress,
    Multirange,
    Point,
    Range,
    Vector,
)
from rhosocial.activerecord.backend.errors import TypeConversionError
from rhosocial.activerecord.backend.impl.clickhouse.adapters import (
    ClickHouseBitStringAdapter,
    ClickHouseGeometryAdapter,
    ClickHouseMacAddressAdapter,
    ClickHouseRangeAdapter,
    ClickHouseVectorAdapter,
)
from rhosocial.activerecord.backend.impl.clickhouse.backend.backend import (
    ClickHouseBackend,
)
from rhosocial.activerecord.backend.impl.clickhouse.config import (
    ClickHouseConnectionConfig,
)


NEUTRAL_ADAPTER_CLASSES = (
    ClickHouseBitStringAdapter,
    ClickHouseGeometryAdapter,
    ClickHouseMacAddressAdapter,
    ClickHouseRangeAdapter,
    ClickHouseVectorAdapter,
)


class TestGeometryAdapter:
    def test_wkt_round_trip(self):
        adapter = ClickHouseGeometryAdapter()
        geometry = Point(1.5, -2)

        encoded = adapter.to_database(geometry, str)
        assert encoded == "POINT (1.5 -2.0)"

        decoded = adapter.from_database(encoded, Geometry)
        assert decoded == geometry

    def test_wkt_accepts_compact_form_on_read(self):
        adapter = ClickHouseGeometryAdapter()
        assert adapter.from_database("POINT(1 2)", Geometry) == Point(1, 2)

    def test_invalid_input_is_wrapped(self):
        adapter = ClickHouseGeometryAdapter()
        with pytest.raises(TypeConversionError) as excinfo:
            adapter.to_database(42, str)
        assert "Cannot convert int to Geometry" in str(excinfo.value)

    def test_unparseable_wkt_is_wrapped(self):
        adapter = ClickHouseGeometryAdapter()
        with pytest.raises(TypeConversionError):
            adapter.from_database("NOT A GEOMETRY", Geometry)


class TestVectorAdapter:
    def test_list_round_trip(self):
        adapter = ClickHouseVectorAdapter()
        vector = Vector([0.25, 1, -3])

        encoded = adapter.to_database(vector, list)
        assert isinstance(encoded, list)
        assert encoded == [0.25, 1.0, -3.0]

        decoded = adapter.from_database(encoded, Vector)
        assert decoded == vector

    def test_plain_sequence_is_coerced(self):
        adapter = ClickHouseVectorAdapter()
        assert adapter.to_database((1, 2), list) == [1.0, 2.0]

    def test_non_sequence_is_wrapped(self):
        adapter = ClickHouseVectorAdapter()
        with pytest.raises(TypeConversionError):
            adapter.to_database("not a vector", list)

    def test_scalar_decode_is_wrapped(self):
        adapter = ClickHouseVectorAdapter()
        with pytest.raises(TypeConversionError):
            adapter.from_database(3.14, Vector)


class TestBitStringAdapter:
    def test_bit_text_round_trip_keeps_leading_zeros(self):
        adapter = ClickHouseBitStringAdapter()
        bits = BitString.from_bits("001011")

        encoded = adapter.to_database(bits, str)
        assert encoded == "001011"

        decoded = adapter.from_database(encoded, BitString)
        assert decoded == bits

    def test_bytes_decode_uses_whole_byte_length(self):
        adapter = ClickHouseBitStringAdapter()
        assert adapter.from_database(b"\xf0", BitString).bit_length == 8

    def test_non_binary_text_is_wrapped(self):
        adapter = ClickHouseBitStringAdapter()
        with pytest.raises(TypeConversionError):
            adapter.from_database("10201", BitString)


class TestRangeAdapter:
    def test_range_json_round_trip(self):
        adapter = ClickHouseRangeAdapter()
        value = Range(1, 5, "[)")

        encoded = adapter.to_database(value, str)
        assert json.loads(encoded) == value.to_json_value()

        decoded = adapter.from_database(encoded, Range)
        assert decoded == value

    def test_datetime_range_round_trip(self):
        adapter = ClickHouseRangeAdapter()
        value = Range(
            datetime.datetime(2024, 1, 1, 8, 0),
            datetime.datetime(2024, 1, 2, 8, 0),
            "[)",
        )
        decoded = adapter.from_database(adapter.to_database(value, str), Range)
        assert decoded == value

    def test_multirange_json_round_trip(self):
        adapter = ClickHouseRangeAdapter()
        value = Multirange((Range(1, 5), Range(7, 9)))

        encoded = adapter.to_database(value, str)
        decoded = adapter.from_database(encoded, Multirange)
        assert decoded == value

    def test_mismatched_target_is_wrapped(self):
        adapter = ClickHouseRangeAdapter()
        with pytest.raises(TypeConversionError):
            adapter.to_database(Range(1, 5), Multirange)

    def test_unknown_element_type_is_wrapped(self):
        adapter = ClickHouseRangeAdapter()
        payload = {
            "lower": 1,
            "upper": 5,
            "bounds": "[)",
            "empty": False,
            "element_type": "bogus",
        }
        with pytest.raises(TypeConversionError):
            adapter.from_database(json.dumps(payload), Range)


class TestMacAddressAdapter:
    def test_canonical_text_round_trip(self):
        adapter = ClickHouseMacAddressAdapter()
        mac = MacAddress.parse("08:00:2B:01:02:03")

        encoded = adapter.to_database(mac, str)
        assert encoded == "08:00:2b:01:02:03"

        decoded = adapter.from_database(encoded, MacAddress)
        assert decoded == mac

    def test_octets_decode(self):
        adapter = ClickHouseMacAddressAdapter()
        assert adapter.from_database(b"\x08\x00\x2b\x01\x02\x03", MacAddress) == (
            MacAddress.parse("08:00:2b:01:02:03")
        )

    def test_bad_text_is_wrapped(self):
        adapter = ClickHouseMacAddressAdapter()
        with pytest.raises(TypeConversionError):
            adapter.from_database("not-a-mac", MacAddress)


def test_inventory_contains_neutral_adapters():
    backend = ClickHouseBackend(
        connection_config=ClickHouseConnectionConfig(host="127.0.0.1", port=8123)
    )
    inventory = backend.get_type_adapters()

    for adapter_cls in NEUTRAL_ADAPTER_CLASSES:
        assert any(isinstance(adapter, adapter_cls) for adapter in inventory), (
            f"{adapter_cls.__name__} missing from get_type_adapters()"
        )

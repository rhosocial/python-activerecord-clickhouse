# tests/rhosocial/activerecord_clickhouse_test/feature/backend/test_set_vector_adapters.py
"""
Unit tests for ClickHouse SET and VECTOR type adapters.

This module tests the internal helper methods of ClickHouseSetAdapter and ClickHouseVectorAdapter
to ensure proper code coverage for refactored methods.
"""

import pytest
import struct

from rhosocial.activerecord.backend.impl.clickhouse.adapters import (
    ClickHouseSetAdapter,
    ClickHouseVectorAdapter,
)


class TestClickHouseSetAdapterDecodeFromInt:
    """Tests for ClickHouseSetAdapter._decode_set_from_int method."""

    def test_decode_single_bit(self):
        """Test decoding single bit set."""
        adapter = ClickHouseSetAdapter(allowed_values=["a", "b", "c"])
        # Bit 0 = 'a' (value 1)
        result = adapter._decode_set_from_int(1, set, ["a", "b", "c"])
        assert result == {"a"}

    def test_decode_multiple_bits(self):
        """Test decoding multiple bits set."""
        adapter = ClickHouseSetAdapter(allowed_values=["red", "green", "blue"])
        # Bit 0 = 'red' (1), Bit 1 = 'green' (2), Bit 2 = 'blue' (4)
        # Value 3 = red + green
        result = adapter._decode_set_from_int(3, set, ["red", "green", "blue"])
        assert result == {"red", "green"}

    def test_decode_all_bits(self):
        """Test decoding all bits set."""
        adapter = ClickHouseSetAdapter(allowed_values=["a", "b", "c"])
        # Value 7 = all bits set (1 + 2 + 4)
        result = adapter._decode_set_from_int(7, set, ["a", "b", "c"])
        assert result == {"a", "b", "c"}

    def test_decode_returns_frozenset(self):
        """Test that target_type=frozenset returns frozenset."""
        adapter = ClickHouseSetAdapter(allowed_values=["x", "y"])
        result = adapter._decode_set_from_int(3, frozenset, ["x", "y"])
        assert isinstance(result, frozenset)
        assert result == frozenset({"x", "y"})

    def test_decode_zero_value(self):
        """Test decoding zero (empty set)."""
        adapter = ClickHouseSetAdapter(allowed_values=["a", "b", "c"])
        result = adapter._decode_set_from_int(0, set, ["a", "b", "c"])
        assert result == set()

    def test_decode_without_allowed_values_raises_error(self):
        """Test that decoding without allowed_values raises ValueError."""
        adapter = ClickHouseSetAdapter()
        with pytest.raises(ValueError, match="Cannot decode SET from integer without allowed_values"):
            adapter._decode_set_from_int(1, set, None)


class TestClickHouseSetAdapterDecodeFromString:
    """Tests for ClickHouseSetAdapter._decode_set_from_string method."""

    def test_decode_single_value(self):
        """Test decoding single value string."""
        adapter = ClickHouseSetAdapter()
        result = adapter._decode_set_from_string("red", set)
        assert result == {"red"}

    def test_decode_multiple_values(self):
        """Test decoding comma-separated values."""
        adapter = ClickHouseSetAdapter()
        result = adapter._decode_set_from_string("red,green,blue", set)
        assert result == {"red", "green", "blue"}

    def test_decode_empty_string(self):
        """Test decoding empty string returns empty set."""
        adapter = ClickHouseSetAdapter()
        result = adapter._decode_set_from_string("", set)
        assert result == set()

    def test_decode_returns_frozenset(self):
        """Test that target_type=frozenset returns frozenset."""
        adapter = ClickHouseSetAdapter()
        result = adapter._decode_set_from_string("a,b", frozenset)
        assert isinstance(result, frozenset)
        assert result == frozenset({"a", "b"})


class TestClickHouseVectorAdapterDecodeFromBytes:
    """Tests for ClickHouseVectorAdapter._decode_vector_from_bytes method."""

    def test_decode_utf8_string_bytes(self):
        """Test decoding UTF-8 encoded string format."""
        adapter = ClickHouseVectorAdapter()
        # UTF-8 encoded string format
        result = adapter._decode_vector_from_bytes(b"[1.0,2.0,3.0]")
        assert result == [1.0, 2.0, 3.0]

    def test_decode_binary_format(self):
        """Test decoding packed binary format (IEEE 754 float32)."""
        adapter = ClickHouseVectorAdapter()
        # Pack 3 float32 values in little-endian
        binary_data = struct.pack("<3f", 1.0, 2.0, 3.0)
        result = adapter._decode_vector_from_bytes(binary_data)
        assert len(result) == 3
        assert abs(result[0] - 1.0) < 1e-6
        assert abs(result[1] - 2.0) < 1e-6
        assert abs(result[2] - 3.0) < 1e-6

    def test_decode_binary_invalid_length_raises_error(self):
        """Test that invalid binary length raises ValueError."""
        adapter = ClickHouseVectorAdapter()
        # 5 bytes is not a multiple of 4, and contains invalid UTF-8 sequences
        # Use bytes that cannot be decoded as UTF-8
        invalid_data = b"\xff\xfe\xfd\xfc\xfb"  # Invalid UTF-8, 5 bytes
        with pytest.raises(ValueError, match="Invalid VECTOR binary length"):
            adapter._decode_vector_from_bytes(invalid_data)


class TestClickHouseVectorAdapterDecodeFromString:
    """Tests for ClickHouseVectorAdapter._decode_vector_from_string method."""

    def test_decode_bracketed_format(self):
        """Test decoding standard bracketed format."""
        adapter = ClickHouseVectorAdapter()
        result = adapter._decode_vector_from_string("[1.5,2.5,3.5]")
        assert result == [1.5, 2.5, 3.5]

    def test_decode_single_value(self):
        """Test decoding single value."""
        adapter = ClickHouseVectorAdapter()
        result = adapter._decode_vector_from_string("[42.0]")
        assert result == [42.0]

    def test_decode_empty_brackets(self):
        """Test decoding empty brackets returns empty list."""
        adapter = ClickHouseVectorAdapter()
        result = adapter._decode_vector_from_string("[]")
        assert result == []

    def test_decode_with_spaces(self):
        """Test decoding with whitespace."""
        adapter = ClickHouseVectorAdapter()
        result = adapter._decode_vector_from_string("[ 1.0 , 2.0 , 3.0 ]")
        assert result == [1.0, 2.0, 3.0]

    def test_decode_without_brackets(self):
        """Test decoding format without brackets."""
        adapter = ClickHouseVectorAdapter()
        result = adapter._decode_vector_from_string("1.0,2.0,3.0")
        assert result == [1.0, 2.0, 3.0]

    def test_decode_invalid_value_raises_error(self):
        """Test that invalid value raises ValueError."""
        adapter = ClickHouseVectorAdapter()
        with pytest.raises(ValueError, match="Cannot parse VECTOR value"):
            adapter._decode_vector_from_string("[1.0,invalid,3.0]")


class TestClickHouseSetAdapterFromDatabaseIntegration:
    """Integration tests for ClickHouseSetAdapter.from_database using helper methods."""

    def test_from_database_int_calls_decode_from_int(self):
        """Test that from_database with int calls _decode_set_from_int."""
        adapter = ClickHouseSetAdapter(allowed_values=["a", "b", "c"])
        # Value 5 = bit 0 + bit 2 = 'a' + 'c'
        result = adapter.from_database(5, set)
        assert result == {"a", "c"}

    def test_from_database_string_calls_decode_from_string(self):
        """Test that from_database with str calls _decode_set_from_string."""
        adapter = ClickHouseSetAdapter()
        result = adapter.from_database("a,b,c", set)
        assert result == {"a", "b", "c"}


class TestClickHouseVectorAdapterFromDatabaseIntegration:
    """Integration tests for ClickHouseVectorAdapter.from_database using helper methods."""

    def test_from_database_bytes_calls_decode_from_bytes(self):
        """Test that from_database with bytes calls _decode_vector_from_bytes."""
        adapter = ClickHouseVectorAdapter()
        result = adapter.from_database(b"[1.0,2.0]", list)
        assert result == [1.0, 2.0]

    def test_from_database_string_calls_decode_from_string(self):
        """Test that from_database with str calls _decode_vector_from_string."""
        adapter = ClickHouseVectorAdapter()
        result = adapter.from_database("[1.5,2.5,3.5]", list)
        assert result == [1.5, 2.5, 3.5]

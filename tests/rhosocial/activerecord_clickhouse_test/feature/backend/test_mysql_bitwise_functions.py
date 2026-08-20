# tests/rhosocial/activerecord_clickhouse_test/feature/backend/test_clickhouse_bitwise_functions.py
"""
Tests for ClickHouse-specific bitwise functions.

Functions: bit_and, bit_or, bit_xor, bit_count, bit_get_bit,
           bit_shift_left, bit_shift_right

Note: bit_and, bit_or, bit_xor, bit_get_bit, bit_shift_left, bit_shift_right
are implemented using native ClickHouse operators (&, |, ^, <<, >>) since the
function versions (BIT_AND, etc.) are aggregate functions that require
GROUP BY context.
"""

from rhosocial.activerecord.backend.expression import Column
from rhosocial.activerecord.backend.impl.clickhouse.dialect import ClickHouseDialect
from rhosocial.activerecord.backend.impl.clickhouse.functions.bitwise import (
    bit_and,
    bit_or,
    bit_xor,
    bit_count,
    bit_get_bit,
    bit_shift_left,
    bit_shift_right,
)


class TestClickHouseBitwiseFunctions:
    """Tests for ClickHouse bitwise functions."""

    def test_bit_and_single_column(self, clickhouse_dialect: ClickHouseDialect):
        """Test bit_and() with a single column returns the column itself."""
        result = bit_and(clickhouse_dialect, Column(clickhouse_dialect, "flags"))
        sql, _ = result.to_sql()
        # Single column returns the column (no operator needed)
        assert "`flags`" in sql

    def test_bit_and_multiple_columns(self, clickhouse_dialect: ClickHouseDialect):
        """Test bit_and() with multiple columns."""
        result = bit_and(
            clickhouse_dialect,
            Column(clickhouse_dialect, "a"),
            Column(clickhouse_dialect, "b"),
            Column(clickhouse_dialect, "c"),
        )
        sql, _ = result.to_sql()
        assert "`a`" in sql
        assert "`b`" in sql
        assert "`c`" in sql
        assert " & " in sql

    def test_bit_and_with_literal(self, clickhouse_dialect: ClickHouseDialect):
        """Test bit_and() with literal value."""
        result = bit_and(clickhouse_dialect, 255)
        sql, _ = result.to_sql()
        assert "%s" in sql

    def test_bit_or_single_column(self, clickhouse_dialect: ClickHouseDialect):
        """Test bit_or() with a single column returns the column itself."""
        result = bit_or(clickhouse_dialect, Column(clickhouse_dialect, "flags"))
        sql, _ = result.to_sql()
        # Single column returns the column (no operator needed)
        assert "`flags`" in sql

    def test_bit_or_multiple_columns(self, clickhouse_dialect: ClickHouseDialect):
        """Test bit_or() with multiple columns."""
        result = bit_or(
            clickhouse_dialect,
            Column(clickhouse_dialect, "a"),
            Column(clickhouse_dialect, "b"),
        )
        sql, _ = result.to_sql()
        assert "`a`" in sql
        assert "`b`" in sql
        assert " | " in sql

    def test_bit_or_with_literal(self, clickhouse_dialect: ClickHouseDialect):
        """Test bit_or() with literal value."""
        result = bit_or(clickhouse_dialect, 0xFF)
        sql, _ = result.to_sql()
        assert "%s" in sql

    def test_bit_xor_single_column(self, clickhouse_dialect: ClickHouseDialect):
        """Test bit_xor() with a single column returns the column itself."""
        result = bit_xor(clickhouse_dialect, Column(clickhouse_dialect, "flags"))
        sql, _ = result.to_sql()
        # Single column returns the column (no operator needed)
        assert "`flags`" in sql

    def test_bit_xor_multiple_columns(self, clickhouse_dialect: ClickHouseDialect):
        """Test bit_xor() with multiple columns."""
        result = bit_xor(
            clickhouse_dialect,
            Column(clickhouse_dialect, "a"),
            Column(clickhouse_dialect, "b"),
        )
        sql, _ = result.to_sql()
        assert "`a`" in sql
        assert "`b`" in sql
        assert " ^ " in sql

    def test_bit_xor_with_literal(self, clickhouse_dialect: ClickHouseDialect):
        """Test bit_xor() with literal value."""
        result = bit_xor(clickhouse_dialect, 0xAA)
        sql, _ = result.to_sql()
        assert "%s" in sql

    def test_bit_count_column(self, clickhouse_dialect: ClickHouseDialect):
        """Test bit_count() with a column."""
        result = bit_count(clickhouse_dialect, Column(clickhouse_dialect, "value"))
        sql, _ = result.to_sql()
        assert "BIT_COUNT(" in sql
        assert "`value`" in sql

    def test_bit_count_literal(self, clickhouse_dialect: ClickHouseDialect):
        """Test bit_count() with a literal value."""
        result = bit_count(clickhouse_dialect, 255)
        sql, _ = result.to_sql()
        assert "BIT_COUNT(" in sql
        assert "%s" in sql

    def test_bit_count_binary(self, clickhouse_dialect: ClickHouseDialect):
        """Test bit_count() with a binary value."""
        result = bit_count(clickhouse_dialect, 0b10101010)
        sql, _ = result.to_sql()
        assert "BIT_COUNT(" in sql
        assert "%s" in sql

    def test_bit_get_bit_column_and_literal(self, clickhouse_dialect: ClickHouseDialect):
        """Test bit_get_bit() with column and literal.
        Implemented as ((value >> bit) & 1).
        """
        result = bit_get_bit(clickhouse_dialect, Column(clickhouse_dialect, "value"), 0)
        sql, _ = result.to_sql()
        assert "`value`" in sql
        assert ">>" in sql
        assert "&" in sql
        assert "%s" in sql

    def test_bit_get_bit_both_columns(self, clickhouse_dialect: ClickHouseDialect):
        """Test bit_get_bit() with both arguments as columns."""
        result = bit_get_bit(
            clickhouse_dialect,
            Column(clickhouse_dialect, "value"),
            Column(clickhouse_dialect, "bit_pos"),
        )
        sql, _ = result.to_sql()
        assert "`value`" in sql
        assert "`bit_pos`" in sql
        assert ">>" in sql
        assert "&" in sql

    def test_bit_shift_left_column_by_literal(self, clickhouse_dialect: ClickHouseDialect):
        """Test bit_shift_left() with column and literal."""
        result = bit_shift_left(clickhouse_dialect, Column(clickhouse_dialect, "value"), 1)
        sql, _ = result.to_sql()
        assert "`value`" in sql
        assert "<<" in sql
        assert "%s" in sql

    def test_bit_shift_left_both_columns(self, clickhouse_dialect: ClickHouseDialect):
        """Test bit_shift_left() with both arguments as columns."""
        result = bit_shift_left(
            clickhouse_dialect,
            Column(clickhouse_dialect, "value"),
            Column(clickhouse_dialect, "shift"),
        )
        sql, _ = result.to_sql()
        assert "`value`" in sql
        assert "`shift`" in sql
        assert "<<" in sql

    def test_bit_shift_right_column_by_literal(self, clickhouse_dialect: ClickHouseDialect):
        """Test bit_shift_right() with column and literal."""
        result = bit_shift_right(clickhouse_dialect, Column(clickhouse_dialect, "value"), 2)
        sql, _ = result.to_sql()
        assert "`value`" in sql
        assert ">>" in sql
        assert "%s" in sql

    def test_bit_shift_right_both_columns(self, clickhouse_dialect: ClickHouseDialect):
        """Test bit_shift_right() with both arguments as columns."""
        result = bit_shift_right(
            clickhouse_dialect,
            Column(clickhouse_dialect, "value"),
            Column(clickhouse_dialect, "shift"),
        )
        sql, _ = result.to_sql()
        assert "`value`" in sql
        assert "`shift`" in sql
        assert ">>" in sql

    def test_bit_shift_left_with_literal_base(self, clickhouse_dialect: ClickHouseDialect):
        """Test bit_shift_left() with literal base value."""
        result = bit_shift_left(clickhouse_dialect, 1, 8)
        sql, _ = result.to_sql()
        assert "<<" in sql
        assert "%s" in sql

    def test_bit_shift_right_with_literal_base(self, clickhouse_dialect: ClickHouseDialect):
        """Test bit_shift_right() with literal base value."""
        result = bit_shift_right(clickhouse_dialect, 256, 4)
        sql, _ = result.to_sql()
        assert ">>" in sql
        assert "%s" in sql

    def test_bit_count_with_string_integer(self, clickhouse_dialect: ClickHouseDialect):
        """Test bit_count() with string integer value."""
        result = bit_count(clickhouse_dialect, "255")
        sql, _ = result.to_sql()
        assert "BIT_COUNT(" in sql
        # Non-numeric strings should be treated as column names
        assert "`255`" in sql

    def test_bit_get_bit_with_string_literal(self, clickhouse_dialect: ClickHouseDialect):
        """Test bit_get_bit() with string literal for bit position."""
        result = bit_get_bit(clickhouse_dialect, Column(clickhouse_dialect, "value"), "0")
        sql, _ = result.to_sql()
        # String "0" should be treated as column name since it's not a number literal
        assert "`value`" in sql
        assert "`0`" in sql

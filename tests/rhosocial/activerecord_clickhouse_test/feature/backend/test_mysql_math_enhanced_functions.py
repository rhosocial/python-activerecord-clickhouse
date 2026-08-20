# tests/rhosocial/activerecord_clickhouse_test/feature/backend/test_clickhouse_math_enhanced_functions.py
"""
Tests for ClickHouse-specific enhanced math functions.

These include additional mathematical functions beyond the basic math module.
"""

from rhosocial.activerecord.backend.expression import Column
from rhosocial.activerecord.backend.impl.clickhouse.dialect import ClickHouseDialect
from rhosocial.activerecord.backend.impl.clickhouse.functions.math_enhanced import (
    round_,
    pow,
    power,
    sqrt,
    mod,
    ceil,
    floor,
    trunc,
    max_,
    min_,
    avg,
)


class TestClickHouseMathEnhancedFunctions:
    """Tests for ClickHouse enhanced math functions."""

    def test_round__default(self, clickhouse_dialect: ClickHouseDialect):
        """Test round_() with default precision."""
        result = round_(clickhouse_dialect, Column(clickhouse_dialect, "value"))
        sql, _ = result.to_sql()
        assert "ROUND(" in sql
        assert "`value`" in sql

    def test_round__with_precision(self, clickhouse_dialect: ClickHouseDialect):
        """Test round_() with precision."""
        result = round_(clickhouse_dialect, Column(clickhouse_dialect, "price"), 2)
        sql, _ = result.to_sql()
        assert "ROUND(" in sql

    def test_round__with_literal(self, clickhouse_dialect: ClickHouseDialect):
        """Test round_() with literal value."""
        result = round_(clickhouse_dialect, 3.14159, 2)
        sql, _ = result.to_sql()
        assert "ROUND(" in sql

    def test_pow(self, clickhouse_dialect: ClickHouseDialect):
        """Test pow() function."""
        result = pow(clickhouse_dialect, Column(clickhouse_dialect, "base"), 2)
        sql, _ = result.to_sql()
        assert "POW(" in sql

    def test_pow_both_columns(self, clickhouse_dialect: ClickHouseDialect):
        """Test pow() with both column references."""
        result = pow(clickhouse_dialect, Column(clickhouse_dialect, "x"), Column(clickhouse_dialect, "y"))
        sql, _ = result.to_sql()
        assert "POW(" in sql

    def test_power(self, clickhouse_dialect: ClickHouseDialect):
        """Test power() function (alias for POW)."""
        result = power(clickhouse_dialect, 2, 3)
        sql, _ = result.to_sql()
        assert "POWER(" in sql

    def test_sqrt(self, clickhouse_dialect: ClickHouseDialect):
        """Test sqrt() function."""
        result = sqrt(clickhouse_dialect, Column(clickhouse_dialect, "value"))
        sql, _ = result.to_sql()
        assert "SQRT(" in sql
        assert "`value`" in sql

    def test_sqrt_with_literal(self, clickhouse_dialect: ClickHouseDialect):
        """Test sqrt() with literal value."""
        result = sqrt(clickhouse_dialect, 16)
        sql, _ = result.to_sql()
        assert "SQRT(" in sql

    def test_mod(self, clickhouse_dialect: ClickHouseDialect):
        """Test mod() function."""
        result = mod(clickhouse_dialect, Column(clickhouse_dialect, "total"), 10)
        sql, _ = result.to_sql()
        assert "MOD(" in sql

    def test_mod_both_columns(self, clickhouse_dialect: ClickHouseDialect):
        """Test mod() with both column references."""
        result = mod(clickhouse_dialect, Column(clickhouse_dialect, "dividend"), Column(clickhouse_dialect, "divisor"))
        sql, _ = result.to_sql()
        assert "MOD(" in sql

    def test_ceil(self, clickhouse_dialect: ClickHouseDialect):
        """Test ceil() function."""
        result = ceil(clickhouse_dialect, Column(clickhouse_dialect, "value"))
        sql, _ = result.to_sql()
        assert "CEIL(" in sql
        assert "`value`" in sql

    def test_ceil_with_literal(self, clickhouse_dialect: ClickHouseDialect):
        """Test ceil() with literal value."""
        result = ceil(clickhouse_dialect, 3.14)
        sql, _ = result.to_sql()
        assert "CEIL(" in sql

    def test_floor(self, clickhouse_dialect: ClickHouseDialect):
        """Test floor() function."""
        result = floor(clickhouse_dialect, Column(clickhouse_dialect, "value"))
        sql, _ = result.to_sql()
        assert "FLOOR(" in sql
        assert "`value`" in sql

    def test_floor_with_literal(self, clickhouse_dialect: ClickHouseDialect):
        """Test floor() with literal value."""
        result = floor(clickhouse_dialect, 3.14)
        sql, _ = result.to_sql()
        assert "FLOOR(" in sql

    def test_trunc(self, clickhouse_dialect: ClickHouseDialect):
        """Test trunc() function (becomes TRUNCATE in ClickHouse)."""
        result = trunc(clickhouse_dialect, Column(clickhouse_dialect, "value"))
        sql, _ = result.to_sql()
        assert "TRUNCATE(" in sql
        assert "`value`" in sql

    def test_trunc_with_literal(self, clickhouse_dialect: ClickHouseDialect):
        """Test trunc() with literal value."""
        result = trunc(clickhouse_dialect, 3.14)
        sql, _ = result.to_sql()
        assert "TRUNCATE(" in sql

    def test_trunc_with_precision(self, clickhouse_dialect: ClickHouseDialect):
        """Test trunc() with precision."""
        result = trunc(clickhouse_dialect, 3.14159, 2)
        sql, _ = result.to_sql()
        assert "TRUNCATE(" in sql

    def test_max__two_args(self, clickhouse_dialect: ClickHouseDialect):
        """Test max_() with two arguments (uses GREATEST)."""
        result = max_(clickhouse_dialect, Column(clickhouse_dialect, "a"), Column(clickhouse_dialect, "b"))
        sql, _ = result.to_sql()
        assert "GREATEST(" in sql

    def test_max__multiple_args(self, clickhouse_dialect: ClickHouseDialect):
        """Test max_() with multiple arguments (uses GREATEST)."""
        result = max_(clickhouse_dialect, Column(clickhouse_dialect, "a"), Column(clickhouse_dialect, "b"), Column(clickhouse_dialect, "c"))
        sql, _ = result.to_sql()
        assert "GREATEST(" in sql

    def test_max__with_literals(self, clickhouse_dialect: ClickHouseDialect):
        """Test max_() with literal values (uses GREATEST)."""
        result = max_(clickhouse_dialect, 1, 2, 3)
        sql, _ = result.to_sql()
        assert "GREATEST(" in sql

    def test_max__single_arg(self, clickhouse_dialect: ClickHouseDialect):
        """Test max_() with single column argument (uses MAX aggregate)."""
        result = max_(clickhouse_dialect, Column(clickhouse_dialect, "value"))
        sql, _ = result.to_sql()
        assert "MAX(" in sql

    def test_min__two_args(self, clickhouse_dialect: ClickHouseDialect):
        """Test min_() with two arguments (uses LEAST)."""
        result = min_(clickhouse_dialect, Column(clickhouse_dialect, "a"), Column(clickhouse_dialect, "b"))
        sql, _ = result.to_sql()
        assert "LEAST(" in sql

    def test_min__multiple_args(self, clickhouse_dialect: ClickHouseDialect):
        """Test min_() with multiple arguments (uses LEAST)."""
        result = min_(clickhouse_dialect, Column(clickhouse_dialect, "a"), Column(clickhouse_dialect, "b"), Column(clickhouse_dialect, "c"))
        sql, _ = result.to_sql()
        assert "LEAST(" in sql

    def test_min__with_literals(self, clickhouse_dialect: ClickHouseDialect):
        """Test min_() with literal values (uses LEAST)."""
        result = min_(clickhouse_dialect, 1, 2, 3)
        sql, _ = result.to_sql()
        assert "LEAST(" in sql

    def test_min__single_arg(self, clickhouse_dialect: ClickHouseDialect):
        """Test min_() with single column argument (uses MIN aggregate)."""
        result = min_(clickhouse_dialect, Column(clickhouse_dialect, "value"))
        sql, _ = result.to_sql()
        assert "MIN(" in sql

    def test_avg(self, clickhouse_dialect: ClickHouseDialect):
        """Test avg() aggregate function."""
        result = avg(clickhouse_dialect, Column(clickhouse_dialect, "price"))
        sql, _ = result.to_sql()
        assert "AVG(" in sql
        assert "`price`" in sql

    def test_avg_with_literal(self, clickhouse_dialect: ClickHouseDialect):
        """Test avg() with literal value."""
        result = avg(clickhouse_dialect, 100)
        sql, _ = result.to_sql()
        assert "AVG(" in sql

    def test_round__with_string_integer(self, clickhouse_dialect: ClickHouseDialect):
        """Test round_() with string integer value."""
        result = round_(clickhouse_dialect, "123", 2)
        sql, _ = result.to_sql()
        assert "ROUND(" in sql

    def test_round__with_string_float(self, clickhouse_dialect: ClickHouseDialect):
        """Test round_() with string float value."""
        result = round_(clickhouse_dialect, "3.14159", 2)
        sql, _ = result.to_sql()
        assert "ROUND(" in sql

    def test_round__with_string_column_name(self, clickhouse_dialect: ClickHouseDialect):
        """Test round_() with non-numeric string treated as column."""
        result = round_(clickhouse_dialect, "column_name", 2)
        sql, _ = result.to_sql()
        assert "ROUND(" in sql
        assert "`column_name`" in sql

    def test_pow_with_string_integer(self, clickhouse_dialect: ClickHouseDialect):
        """Test pow() with string integer exponent."""
        result = pow(clickhouse_dialect, Column(clickhouse_dialect, "base"), "2")
        sql, _ = result.to_sql()
        assert "POW(" in sql

    def test_sqrt_with_string_integer(self, clickhouse_dialect: ClickHouseDialect):
        """Test sqrt() with string integer value."""
        result = sqrt(clickhouse_dialect, "16")
        sql, _ = result.to_sql()
        assert "SQRT(" in sql

    def test_mod_with_string_divisor(self, clickhouse_dialect: ClickHouseDialect):
        """Test mod() with string divisor."""
        result = mod(clickhouse_dialect, Column(clickhouse_dialect, "total"), "10")
        sql, _ = result.to_sql()
        assert "MOD(" in sql

    def test_max__with_string_literals(self, clickhouse_dialect: ClickHouseDialect):
        """Test max_() with non-numeric string values (treated as columns in GREATEST)."""
        result = max_(clickhouse_dialect, "a", "b", "c")
        sql, _ = result.to_sql()
        assert "GREATEST(" in sql
        # Non-numeric strings should be treated as column names and quoted with backticks
        assert "`a`" in sql

    def test_min__with_string_literals(self, clickhouse_dialect: ClickHouseDialect):
        """Test min_() with non-numeric string values (treated as columns in LEAST)."""
        result = min_(clickhouse_dialect, "a", "b", "c")
        sql, _ = result.to_sql()
        assert "LEAST(" in sql
        # Non-numeric strings should be treated as column names and quoted with backticks
        assert "`a`" in sql

    def test_avg_with_string_literal(self, clickhouse_dialect: ClickHouseDialect):
        """Test avg() with string numeric value."""
        result = avg(clickhouse_dialect, "100")
        sql, _ = result.to_sql()
        assert "AVG(" in sql

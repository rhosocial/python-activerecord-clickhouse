# tests/rhosocial/activerecord_clickhouse_test/feature/backend/test_dialect_function_support.py
"""
Test SQLFunctionSupport protocol implementation for ClickHouse dialect.

This module tests the supports_functions() method and version-dependent
function availability detection in ClickHouseDialect.
"""

from rhosocial.activerecord.backend.impl.clickhouse.dialect import ClickHouseDialect


class TestClickHouseFunctionSupportBasic:
    """Basic tests for ClickHouse function support detection."""

    def test_supports_functions_returns_dict(self):
        """Test that supports_functions returns a dictionary."""
        dialect = ClickHouseDialect((8, 0, 0))
        result = dialect.supports_functions()
        assert isinstance(result, dict)
        assert len(result) > 0

    def test_supports_functions_all_values_are_bool(self):
        """Test that all values in the returned dict are booleans."""
        dialect = ClickHouseDialect((8, 0, 0))
        result = dialect.supports_functions()
        for func_name, supported in result.items():
            assert isinstance(supported, bool), f"Value for {func_name} is not bool"

    def test_core_functions_always_supported(self):
        """Test that core functions are marked as supported."""
        dialect = ClickHouseDialect((8, 0, 0))
        result = dialect.supports_functions()
        core_functions = ["count", "sum_", "avg", "min_", "max_", "coalesce", "nullif"]
        for func in core_functions:
            assert func in result, f"Core function {func} not in result"
            assert result[func] is True, f"Core function {func} should be supported"

    def test_sqlxml_constructors_are_not_plain_functions(self):
        """Test that standard SQL/XML constructors are not plain functions."""
        dialect = ClickHouseDialect((8, 0, 0))
        result = dialect.supports_functions()
        sqlxml_constructors = [
            "xmlparse",
            "xmlserialize",
            "xmlelement",
            "xmlattributes",
            "xmlforest",
            "xmlconcat",
            "xmlcomment",
            "xmlpi",
            "xmlroot",
            "xmlagg",
            "xmlquery",
            "xmlexists",
            "xmltable",
        ]
        for func in sqlxml_constructors:
            assert func not in result


class TestClickHouseFunctionSupportVersionDependent:
    """Tests for version-dependent function support.

    ClickHouse-specific function wrappers (JSON_*, ST_*, match_against,
    find_in_set, bit_shift_*, etc.) are NOT provided by this backend.
    Core SQL functions are supported on all versions.
    """

    def test_clickhouse_specific_functions_not_reported(self):
        """MySQL-derived function wrappers are not reported as supported.

        Note: ``json_extract`` is a core generic function (uses dialect's
        format method to generate correct SQL), so it IS reported. MySQL-only
        wrappers like ``bit_and``, ``find_in_set`` are absent.
        """
        dialect = ClickHouseDialect(version=(26, 7, 3))
        result = dialect.supports_functions()

        # Core JSON functions are reported (they use the dialect mixin)
        assert "json_extract" in result

        # MySQL-only wrappers from the deleted functions/ module are absent
        mysql_derived = [
            "st_distance",
            "st_geom_from_text",
            "st_within",
            "st_contains",
            "st_intersects",
            "st_as_text",
            "st_as_geojson",
            "match_against",
            "find_in_set",
            "elt",
            "field",
            "bit_and",
            "bit_or",
            "bit_xor",
            "bit_count",
            "bit_get_bit",
            "bit_shift_left",
            "bit_shift_right",
        ]
        for func in mysql_derived:
            assert func not in result, f"{func} should not be reported"

    def test_core_functions_available_all_versions(self):
        """Core math/aggregate functions are available in all ClickHouse versions."""
        dialect = ClickHouseDialect((26, 7, 3))
        result = dialect.supports_functions()

        # Functions present in the core expression.functions module
        core_functions = [
            "round_",
            "power",
            "sqrt",
            "mod",
            "ceil",
            "floor",
            "max_",
            "min_",
            "avg",
        ]
        for func in core_functions:
            assert result.get(func) is True, f"{func} should be supported"

    def test_aggregate_and_scalar_core_functions(self):
        """Core aggregate/scalar functions are reported."""
        dialect = ClickHouseDialect((26, 7, 3))
        result = dialect.supports_functions()
        for func in ["count", "sum_", "avg", "min_", "max_", "coalesce", "nullif"]:
            assert result.get(func) is True, f"{func} should be supported"


class TestClickHouseFunctionSupportPrivateMethod:
    """Tests for the private _is_clickhouse_function_supported method."""

    def test_unknown_function_returns_true(self):
        """Test that unknown functions return True (no restriction)."""
        dialect = ClickHouseDialect((8, 0, 0))
        result = dialect._is_clickhouse_function_supported("unknown_function_xyz")
        assert result is True

    def test_core_math_function_below_minimum(self):
        """Test that a core function with no version gate returns True."""
        dialect = ClickHouseDialect(version=(1, 0, 0))
        result = dialect._is_clickhouse_function_supported("round_")
        assert result is True


class TestClickHouseFunctionSupportIntegration:
    """Integration tests for function support detection."""

    def test_function_dict_contains_core_functions(self):
        """Test that the result contains core functions (not MySQL wrappers)."""
        dialect = ClickHouseDialect((8, 0, 0))
        result = dialect.supports_functions()

        assert any(func in result for func in ["count", "sum_", "avg"])
        # MySQL-derived wrappers are absent
        assert "st_distance" not in result
        assert "find_in_set" not in result

    def test_function_support_stable_across_versions(self):
        """Core function support does not change across ClickHouse versions."""
        old_dialect = ClickHouseDialect(version=(5, 6, 0))
        new_dialect = ClickHouseDialect(version=(26, 0, 0))

        old_result = old_dialect.supports_functions()
        new_result = new_dialect.supports_functions()

        for func in ["count", "sum_", "avg", "coalesce"]:
            assert old_result.get(func) is True
            assert new_result.get(func) is True

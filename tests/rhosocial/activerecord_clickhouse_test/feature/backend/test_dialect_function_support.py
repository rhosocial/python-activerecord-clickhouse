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
    """Tests for version-dependent function support."""

    def test_json_functions_require_clickhouse_5_7_8(self):
        """Test that JSON functions require ClickHouse 5.7.8+."""
        json_functions = [
            "json_extract",
            "json_unquote",
            "json_object",
            "json_array",
            "json_contains",
            "json_set",
            "json_remove",
            "json_type",
            "json_valid",
            "json_search",
        ]

        dialect_old = ClickHouseDialect(version=(5, 7, 7))
        result_old = dialect_old.supports_functions()
        for func in json_functions:
            assert result_old.get(func) is False

        dialect_new = ClickHouseDialect(version=(5, 7, 8))
        result_new = dialect_new.supports_functions()
        for func in json_functions:
            assert result_new.get(func) is True

    def test_spatial_functions_require_clickhouse_5_7(self):
        """Test that spatial functions require ClickHouse 5.7+."""
        spatial_functions = [
            "st_geom_from_text",
            "st_geom_from_wkb",
            "st_as_text",
            "st_distance",
            "st_within",
            "st_contains",
            "st_intersects",
        ]

        dialect_old = ClickHouseDialect(version=(5, 6, 99))
        result_old = dialect_old.supports_functions()
        for func in spatial_functions:
            assert result_old.get(func) is False

        dialect_new = ClickHouseDialect(version=(5, 7, 0))
        result_new = dialect_new.supports_functions()
        for func in spatial_functions:
            assert result_new.get(func) is True

    def test_st_as_geojson_requires_clickhouse_5_7_5(self):
        """Test that st_as_geojson requires ClickHouse 5.7.5+."""
        dialect_old = ClickHouseDialect(version=(5, 7, 4))
        result_old = dialect_old.supports_functions()
        assert result_old.get("st_as_geojson") is False

        dialect_new = ClickHouseDialect(version=(5, 7, 5))
        result_new = dialect_new.supports_functions()
        assert result_new.get("st_as_geojson") is True

    def test_always_available_functions(self):
        """Test functions that are available in all ClickHouse versions."""
        dialect = ClickHouseDialect((8, 0, 0))
        result = dialect.supports_functions()

        always_available = [
            "match_against",
            "find_in_set",
            "elt",
            "field",
            "round_",
            "pow",
            "power",
            "sqrt",
            "mod",
            "ceil",
            "floor",
            "trunc",
            "max_",
            "min_",
            "avg",
            "bit_and",
            "bit_or",
            "bit_xor",
            "bit_count",
        ]
        for func in always_available:
            assert result.get(func) is True, f"{func} should be always available"

    def test_bit_shift_functions_require_clickhouse_8_0(self):
        """Test that bit shift functions require ClickHouse 8.0+."""
        dialect_old = ClickHouseDialect(version=(7, 99, 99))
        result_old = dialect_old.supports_functions()
        assert result_old.get("bit_shift_left") is False
        assert result_old.get("bit_shift_right") is False
        assert result_old.get("bit_get_bit") is False

        dialect_new = ClickHouseDialect(version=(8, 0, 0))
        result_new = dialect_new.supports_functions()
        assert result_new.get("bit_shift_left") is True
        assert result_new.get("bit_shift_right") is True
        assert result_new.get("bit_get_bit") is True


class TestClickHouseFunctionSupportPrivateMethod:
    """Tests for the private _is_clickhouse_function_supported method."""

    def test_unknown_function_returns_true(self):
        """Test that unknown functions return True (no restriction)."""
        dialect = ClickHouseDialect((8, 0, 0))
        result = dialect._is_clickhouse_function_supported("unknown_function_xyz")
        assert result is True

    def test_version_restricted_function_below_minimum(self):
        """Test that version-restricted function returns False below minimum."""
        dialect = ClickHouseDialect(version=(5, 7, 7))
        result = dialect._is_clickhouse_function_supported("json_extract")
        assert result is False

    def test_version_restricted_function_at_minimum(self):
        """Test that version-restricted function returns True at minimum."""
        dialect = ClickHouseDialect(version=(5, 7, 8))
        result = dialect._is_clickhouse_function_supported("json_extract")
        assert result is True

    def test_version_restricted_function_above_minimum(self):
        """Test that version-restricted function returns True above minimum."""
        dialect = ClickHouseDialect(version=(8, 0, 0))
        result = dialect._is_clickhouse_function_supported("json_extract")
        assert result is True


class TestClickHouseFunctionSupportIntegration:
    """Integration tests for function support detection."""

    def test_function_dict_contains_both_core_and_backend_functions(self):
        """Test that the result contains both core and ClickHouse-specific functions."""
        dialect = ClickHouseDialect((8, 0, 0))
        result = dialect.supports_functions()

        assert any(func in result for func in ["count", "sum_", "avg"])
        assert any(func in result for func in ["json_extract", "st_distance", "find_in_set"])

    def test_function_support_changes_with_version(self):
        """Test that function support changes across different versions."""
        old_dialect = ClickHouseDialect(version=(5, 6, 0))
        new_dialect = ClickHouseDialect(version=(8, 0, 0))

        old_result = old_dialect.supports_functions()
        new_result = new_dialect.supports_functions()

        assert old_result.get("json_extract") is False
        assert new_result.get("json_extract") is True

        assert old_result.get("st_geom_from_text") is False
        assert new_result.get("st_geom_from_text") is True

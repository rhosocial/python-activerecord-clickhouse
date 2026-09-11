# tests/rhosocial/activerecord_clickhouse_test/feature/backend/functions/test_json_functions.py
"""
ClickHouse JSON function support tests.

This module tests ClickHouse-specific JSON function functionality including:
- Function version detection (26.0.0+)
- JSONExtract formatting (JSON_EXTRACT equivalent)
- JSONExtractString formatting (JSON_UNQUOTE equivalent)
- map formatting (JSON_OBJECT equivalent)
- array literal formatting (JSON_ARRAY equivalent)
- isNotNull(JSONExtract(...)) formatting (JSON_CONTAINS equivalent)
- mapUpdate formatting (JSON_SET equivalent)
- mapRemove formatting (JSON_REMOVE equivalent)
- JSONType formatting
- JSON_VALID formatting
- JSONExtractString + LIKE formatting (JSON_SEARCH equivalent)
"""

from rhosocial.activerecord.backend.impl.clickhouse.dialect import ClickHouseDialect
from rhosocial.activerecord.backend.impl.clickhouse.expression.json import (
    ClickHouseJSONArrayExpression,
    ClickHouseJSONContainsExpression,
    ClickHouseJSONObjectExpression,
    ClickHouseJSONRemoveExpression,
    ClickHouseJSONSearchExpression,
    ClickHouseJSONSetExpression,
    ClickHouseJSONTypeExpression,
    ClickHouseJSONUnquoteExpression,
    ClickHouseJSONValidExpression,
    ClickHouseJSONExtractExpression,
)


class TestJSONFunctionProtocol:
    """Test JSON function protocol implementation."""

    def test_supports_json_function_basic(self):
        """Test basic JSON function support (26.0.0+)."""
        dialect_25 = ClickHouseDialect(version=(25, 9, 0))
        assert not dialect_25.supports_json_function("JSONExtract")

        dialect_26 = ClickHouseDialect(version=(26, 0, 0))
        assert dialect_26.supports_json_function("JSONExtract")

        dialect_267 = ClickHouseDialect(version=(26, 7, 3))
        assert dialect_267.supports_json_function("JSONExtract")

    def test_supports_json_function_json_value(self):
        """Test JSON_VALUE support (26.0.0+)."""
        dialect_25 = ClickHouseDialect(version=(25, 9, 0))
        assert not dialect_25.supports_json_function("JSON_VALUE")

        dialect_26 = ClickHouseDialect(version=(26, 0, 0))
        assert dialect_26.supports_json_function("JSON_VALUE")

    def test_supports_json_function_json_type(self):
        """Test JSONType support (26.0.0+)."""
        dialect_25 = ClickHouseDialect(version=(25, 9, 0))
        assert not dialect_25.supports_json_function("JSONType")

        dialect_26 = ClickHouseDialect(version=(26, 0, 0))
        assert dialect_26.supports_json_function("JSONType")

    def test_supports_json_type_always_supported(self):
        """Test supports_json_type always returns True for ClickHouse."""
        dialect_old = ClickHouseDialect(version=(22, 1, 0))
        assert dialect_old.supports_json_type()

        dialect_26 = ClickHouseDialect(version=(26, 0, 0))
        assert dialect_26.supports_json_type()

    def test_supports_json_table_never_supported(self):
        """Test JSON_TABLE is never supported by ClickHouse."""
        dialect_old = ClickHouseDialect(version=(22, 1, 0))
        assert not dialect_old.supports_json_table()

        dialect_26 = ClickHouseDialect(version=(26, 0, 0))
        assert not dialect_26.supports_json_table()

    def test_format_json_extract_single_path(self):
        """Test JSONExtract with single path."""
        dialect = ClickHouseDialect(version=(26, 7, 3))
        expr = ClickHouseJSONExtractExpression(dialect, "data", "$.name")

        sql, params = dialect.format_json_extract(expr)

        assert sql == "JSONExtract(data, %s)"
        assert params == ("$.name",)

    def test_format_json_extract_multiple_paths(self):
        """Test JSONExtract with multiple paths."""
        dialect = ClickHouseDialect(version=(26, 7, 3))
        expr = ClickHouseJSONExtractExpression(dialect, "data", "$.name")
        expr.paths = ["$.age", "$.city"]

        sql, params = dialect.format_json_extract(expr)

        assert sql == "JSONExtract(data, %s, %s, %s)"
        assert params == ("$.name", "$.age", "$.city")

    def test_format_json_unquote(self):
        """Test JSONExtractString function."""
        dialect = ClickHouseDialect(version=(26, 7, 3))
        expr = ClickHouseJSONUnquoteExpression(dialect, "data")

        sql, params = dialect.format_json_unquote(expr)

        assert sql == "JSONExtractString(data)"
        assert params == ()

    def test_format_json_object_empty(self):
        """Test map with no arguments."""
        dialect = ClickHouseDialect(version=(26, 7, 3))
        expr = ClickHouseJSONObjectExpression(dialect)

        sql, params = dialect.format_json_object(expr)

        assert sql == "map()"
        assert params == ()

    def test_format_json_object_single_pair(self):
        """Test map with single key-value pair."""
        dialect = ClickHouseDialect(version=(26, 7, 3))
        expr = ClickHouseJSONObjectExpression(dialect, [("name", "John")])

        sql, params = dialect.format_json_object(expr)

        assert sql == "map(%s, %s)"
        assert params == ("name", "John")

    def test_format_json_object_multiple_pairs(self):
        """Test map with multiple key-value pairs."""
        dialect = ClickHouseDialect(version=(26, 7, 3))
        expr = ClickHouseJSONObjectExpression(
            dialect, [("name", "John"), ("age", 30), ("city", "NYC")]
        )

        sql, params = dialect.format_json_object(expr)

        assert sql == "map(%s, %s, %s, %s, %s, %s)"
        assert params == ("name", "John", "age", 30, "city", "NYC")

    def test_format_json_array_empty(self):
        """Test array literal with no values."""
        dialect = ClickHouseDialect(version=(26, 7, 3))
        expr = ClickHouseJSONArrayExpression(dialect, [])

        sql, params = dialect.format_json_array(expr)

        assert sql == "[]"
        assert params == ()

    def test_format_json_array_single_value(self):
        """Test array literal with single value."""
        dialect = ClickHouseDialect(version=(26, 7, 3))
        expr = ClickHouseJSONArrayExpression(dialect, [1])

        sql, params = dialect.format_json_array(expr)

        assert sql == "[%s]"
        assert params == (1,)

    def test_format_json_array_multiple_values(self):
        """Test array literal with multiple values."""
        dialect = ClickHouseDialect(version=(26, 7, 3))
        expr = ClickHouseJSONArrayExpression(dialect, [1, "hello", None, True])

        sql, params = dialect.format_json_array(expr)

        assert sql == "[%s, %s, %s, %s]"
        assert params == (1, "hello", None, True)

    def test_format_json_contains_no_path(self):
        """Test isNotNull(JSONExtract(...)) without path."""
        dialect = ClickHouseDialect(version=(26, 7, 3))
        expr = ClickHouseJSONContainsExpression(dialect, "data", '{"name": "John"}')

        sql, params = dialect.format_json_contains(expr)

        assert sql == "isNotNull(JSONExtract(data, %s))"
        assert params == ('{"name": "John"}',)

    def test_format_json_contains_with_path(self):
        """Test isNotNull(JSONExtract(...)) with path."""
        dialect = ClickHouseDialect(version=(26, 7, 3))
        expr = ClickHouseJSONContainsExpression(
            dialect, "data", '"John"', "$.name"
        )

        sql, params = dialect.format_json_contains(expr)

        assert sql == "isNotNull(JSONExtract(data, %s, %s))"
        assert params == ('"John"', "$.name")

    def test_format_json_set_single_pair(self):
        """Test mapUpdate with single path-value pair."""
        dialect = ClickHouseDialect(version=(26, 7, 3))
        expr = ClickHouseJSONSetExpression(dialect, "data", "$.name", "John")

        sql, params = dialect.format_json_set(expr)

        assert sql == "assumeNotNull(mapUpdate(JSONExtract(data, 'Map(String, String)'), map(%s, %s)))"
        assert params == ("$.name", "John")

    def test_format_json_set_multiple_pairs(self):
        """Test mapUpdate with multiple path-value pairs."""
        dialect = ClickHouseDialect(version=(26, 7, 3))
        expr = ClickHouseJSONSetExpression(
            dialect, "data", "$.name", "John",
            path_value_pairs=[("$.age", 30), ("$.city", "NYC")]
        )

        sql, params = dialect.format_json_set(expr)

        assert sql == (
            "assumeNotNull(mapUpdate(JSONExtract(data, 'Map(String, String)'), "
            "map(%s, %s, %s, %s, %s, %s)))"
        )
        assert params == ("$.name", "John", "$.age", 30, "$.city", "NYC")

    def test_format_json_remove_single_path(self):
        """Test mapRemove with single path."""
        dialect = ClickHouseDialect(version=(26, 7, 3))
        expr = ClickHouseJSONRemoveExpression(dialect, "data", "$.temp")

        sql, params = dialect.format_json_remove(expr)

        assert sql == "mapRemove(JSONExtract(data, 'Map(String, String)'), %s)"
        assert params == ("$.temp",)

    def test_format_json_remove_multiple_paths(self):
        """Test mapRemove with multiple paths."""
        dialect = ClickHouseDialect(version=(26, 7, 3))
        expr = ClickHouseJSONRemoveExpression(
            dialect, "data", "$.temp", paths=["$.cache", "$.old"]
        )

        sql, params = dialect.format_json_remove(expr)

        assert sql == "mapRemove(JSONExtract(data, 'Map(String, String)'), %s, %s, %s)"
        assert params == ("$.temp", "$.cache", "$.old")

    def test_format_json_type(self):
        """Test JSONType function."""
        dialect = ClickHouseDialect(version=(26, 7, 3))
        expr = ClickHouseJSONTypeExpression(dialect, "data")

        sql, params = dialect.format_json_type(expr)

        assert sql == "JSONType(data)"
        assert params == ()

    def test_format_json_valid(self):
        """Test JSON_VALID function."""
        dialect = ClickHouseDialect(version=(26, 7, 3))
        expr = ClickHouseJSONValidExpression(dialect, "data")

        sql, params = dialect.format_json_valid(expr)

        assert sql == "JSON_VALID(data)"
        assert params == ()

    def test_format_json_search_one(self):
        """Test JSONExtractString + LIKE with 'one' mode."""
        dialect = ClickHouseDialect(version=(26, 7, 3))
        expr = ClickHouseJSONSearchExpression(dialect, "data", "John", all=False)

        sql, params = dialect.format_json_search(expr)

        assert sql == "JSONExtractString(data) LIKE %s AND 'one' = 'one'"
        assert params == ("John",)

    def test_format_json_search_all(self):
        """Test JSONExtractString + LIKE with 'all' mode."""
        dialect = ClickHouseDialect(version=(26, 7, 3))
        expr = ClickHouseJSONSearchExpression(dialect, "data", "John", all=True)

        sql, params = dialect.format_json_search(expr)

        assert sql == "JSONExtractString(data) LIKE %s AND 'all' = 'one'"
        assert params == ("John",)

    def test_format_json_search_with_path(self):
        """Test JSONExtractString + LIKE with path."""
        dialect = ClickHouseDialect(version=(26, 7, 3))
        expr = ClickHouseJSONSearchExpression(
            dialect, "data", "John", path="$.users", all=True
        )

        sql, params = dialect.format_json_search(expr)

        assert sql == "JSONExtractString(data, %s) LIKE %s AND 'all' = 'one'"
        assert params == ("$.users", "John")

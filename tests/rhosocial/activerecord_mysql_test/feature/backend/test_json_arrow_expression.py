# tests/rhosocial/activerecord_clickhouse_test/feature/backend/test_json_arrow_expression.py
"""Tests for ClickHouse JSON arrow (-> / ->>) and function-based expressions.

These are pure SQL-rendering tests (no live ClickHouse server) exercising the
``ClickHouseJSONFunctionMixin.format_json_arrow_expression`` and
``format_json_function_expression`` branches added in the connection
serialization PR.
"""

import pytest

from rhosocial.activerecord.backend.expression import Column
from rhosocial.activerecord.backend.expression.advanced_functions import (
    JSONExpression,
    JSONPathMode,
)
from rhosocial.activerecord.backend.impl.clickhouse.dialect import ClickHouseDialect


@pytest.fixture
def dialect():
    return ClickHouseDialect(version=(8, 0, 0))


class TestArrowExpression:
    def test_arrow_column_identifier(self, dialect):
        expr = JSONExpression(dialect, "data", "$.name", "->")
        sql, params = expr.to_sql()
        assert sql == "`data`->'$.name'"
        assert params == ()

    def test_arrow_operator_identifier(self, dialect):
        expr = JSONExpression(dialect, "data", "$.name", "->>")
        sql, params = expr.to_sql()
        assert sql == "`data`->>'$.name'"
        assert params == ()

    def test_arrow_with_nested_column_expression(self, dialect):
        col = Column(dialect, "payload")
        expr = JSONExpression(dialect, col, "$.a.b", "->")
        sql, params = expr.to_sql()
        assert sql == "`payload`->'$.a.b'"
        assert params == ()

    def test_arrow_with_cast_types(self, dialect):
        expr = JSONExpression(dialect, "data", "$.age", "->>", mode=JSONPathMode.ARROW).cast("UNSIGNED")
        sql, params = expr.to_sql()
        assert sql == "CAST(`data`->>'$.age' AS UNSIGNED)"
        assert params == ()

    def test_arrow_with_alias(self, dialect):
        expr = JSONExpression(dialect, "data", "$.name", "->", alias="nm")
        sql, params = expr.to_sql()
        assert sql == "`data`->'$.name' AS `nm`"
        assert params == ()

    def test_arrow_forced_mode_renders_arrow(self):
        old = ClickHouseDialect(version=(5, 7, 0))
        expr = JSONExpression(old, "data", "$.name", "->", mode=JSONPathMode.ARROW)
        sql, params = expr.to_sql()
        assert sql == "`data`->'$.name'"
        assert params == ()

    def test_arrow_other_operator_uses_placeholder(self, dialect):
        expr = JSONExpression(dialect, "data", "$.name", "=")
        sql, params = expr.to_sql()
        assert sql == "(`data` = %s)"
        assert params == ("$.name",)

    def test_arrow_other_operator_with_column_expression(self, dialect):
        col = Column(dialect, "payload")
        expr = JSONExpression(dialect, col, "someval", "@>")
        sql, params = expr.to_sql()
        assert sql == "(`payload` @> %s)"
        assert params == ("someval",)


class TestFunctionExpression:
    def test_function_extract(self, dialect):
        expr = JSONExpression(dialect, "data", "$.name", "->", mode=JSONPathMode.FUNCTION)
        sql, params = expr.to_sql()
        assert sql == "JSON_EXTRACT(`data`, '$.name')"
        assert params == ()

    def test_function_unquote(self, dialect):
        expr = JSONExpression(dialect, "data", "$.name", "->>", mode=JSONPathMode.FUNCTION)
        sql, params = expr.to_sql()
        assert sql == "JSON_UNQUOTE(JSON_EXTRACT(`data`, '$.name'))"
        assert params == ()

    def test_function_other_operator(self, dialect):
        expr = JSONExpression(dialect, "data", "$.name", "@>", mode=JSONPathMode.FUNCTION)
        sql, params = expr.to_sql()
        assert sql == "`data` @> '$.name'"
        assert params == ()

    def test_function_with_column_expression(self, dialect):
        col = Column(dialect, "payload")
        expr = JSONExpression(dialect, col, "$.a", "->", mode=JSONPathMode.FUNCTION)
        sql, params = expr.to_sql()
        assert sql == "JSON_EXTRACT(`payload`, '$.a')"
        assert params == ()

    def test_function_with_cast_types(self, dialect):
        expr = JSONExpression(dialect, "data", "$.age", "->>", mode=JSONPathMode.FUNCTION).cast("SIGNED")
        sql, params = expr.to_sql()
        assert sql == "CAST(JSON_UNQUOTE(JSON_EXTRACT(`data`, '$.age')) AS SIGNED)"
        assert params == ()

    def test_function_with_alias(self, dialect):
        expr = JSONExpression(dialect, "data", "$.name", "->", mode=JSONPathMode.FUNCTION, alias="nm")
        sql, params = expr.to_sql()
        assert sql == "JSON_EXTRACT(`data`, '$.name') AS `nm`"
        assert params == ()


class TestModeDispatch:
    def test_auto_uses_arrow_when_supported(self, dialect):
        expr = JSONExpression(dialect, "data", "$.name", "->")
        sql, _ = expr.to_sql()
        assert "JSON_EXTRACT" not in sql
        assert "->" in sql

    def test_auto_falls_back_to_function_when_unsupported(self):
        old = ClickHouseDialect(version=(5, 7, 0))
        expr = JSONExpression(old, "data", "$.name", "->")
        sql, params = expr.to_sql()
        assert sql == "JSON_EXTRACT(`data`, '$.name')"
        assert params == ()

    def test_string_mode_coercion(self, dialect):
        expr = JSONExpression(dialect, "data", "$.name", "->", mode="function")
        sql, _ = expr.to_sql()
        assert sql == "JSON_EXTRACT(`data`, '$.name')"

    def test_escaped_path_backslash(self, dialect):
        expr = JSONExpression(dialect, "data", "$.a\\b", "->")
        sql, _ = expr.to_sql()
        assert sql == r"`data`->'$.a\\b'"

    def test_escaped_path_single_quote(self, dialect):
        expr = JSONExpression(dialect, "data", "$.a'b", "->")
        sql, _ = expr.to_sql()
        assert sql == "`data`->'$.a''b'"


class TestJSONCapabilityVersions:
    def test_supports_json_type_version_boundary(self):
        assert ClickHouseDialect(version=(5, 6, 0)).supports_json_type() is False
        assert ClickHouseDialect(version=(5, 7, 8)).supports_json_type() is True

    def test_supports_json_merge_patch_version_boundary(self):
        assert ClickHouseDialect(version=(8, 0, 2)).supports_json_merge_patch() is False
        assert ClickHouseDialect(version=(8, 0, 3)).supports_json_merge_patch() is True

    def test_supports_json_table_version_boundary(self):
        assert ClickHouseDialect(version=(8, 0, 3)).supports_json_table() is False
        assert ClickHouseDialect(version=(8, 0, 4)).supports_json_table() is True

    def test_supports_json_function_known_and_unknown(self):
        assert ClickHouseDialect(version=(8, 0, 2)).supports_json_function("JSON_MERGE_PATCH") is False
        assert ClickHouseDialect(version=(8, 0, 4)).supports_json_function("JSON_TABLE") is True
        assert ClickHouseDialect(version=(5, 7, 0)).supports_json_function("CUSTOM_FN") is False
        assert ClickHouseDialect(version=(5, 7, 8)).supports_json_function("CUSTOM_FN") is True

    def test_supports_json_arrow_operators(self):
        assert ClickHouseDialect(version=(5, 7, 8)).supports_json_arrow_operators() is False
        assert ClickHouseDialect(version=(5, 7, 9)).supports_json_arrow_operators() is True
        assert ClickHouseDialect(version=(8, 0, 0)).get_json_access_operator() == "->"

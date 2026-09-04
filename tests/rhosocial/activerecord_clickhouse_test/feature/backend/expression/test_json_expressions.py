# tests/rhosocial/activerecord_clickhouse_test/feature/backend/expression/test_json_expressions.py
"""
Tests for ClickHouse JSON expression classes.

This module tests the following expression classes:
- ClickHouseJSONExtractExpression
- ClickHouseJSONObjectExpression
- ClickHouseJSONArrayExpression
- ClickHouseJSONContainsExpression
"""

from rhosocial.activerecord.backend.impl.clickhouse.dialect import ClickHouseDialect
from rhosocial.activerecord.backend.impl.clickhouse.expression import (
    ClickHouseJSONExtractExpression,
    ClickHouseJSONObjectExpression,
    ClickHouseJSONArrayExpression,
    ClickHouseJSONContainsExpression,
)


class TestClickHouseJSONExtractExpression:
    """Test ClickHouseJSONExtractExpression class."""

    def test_json_extract_basic(self):
        """Test basic JSON extraction."""
        dialect = ClickHouseDialect(version=(8, 0, 0))

        expr = ClickHouseJSONExtractExpression(dialect, "data", "$.name")
        sql, params = expr.to_sql()

        assert "JSONExtract" in sql
        assert "data" in sql
        assert "$.name" in params

    def test_json_extract_with_alias(self):
        """Test JSON extraction with alias."""
        dialect = ClickHouseDialect(version=(8, 0, 0))

        expr = ClickHouseJSONExtractExpression(dialect, "data", "$.name").as_("extracted_name")
        sql, params = expr.to_sql()

        assert "JSONExtract" in sql
        assert "AS `extracted_name`" in sql

    def test_json_extract_array_path(self):
        """Test JSON extraction with array path."""
        dialect = ClickHouseDialect(version=(8, 0, 0))

        expr = ClickHouseJSONExtractExpression(dialect, "data", "$[0]")
        sql, params = expr.to_sql()

        assert "JSONExtract" in sql
        assert "$[0]" in params


class TestClickHouseJSONObjectExpression:
    """Test ClickHouseJSONObjectExpression class."""

    def test_json_object_basic(self):
        """Test basic JSON object creation."""
        dialect = ClickHouseDialect(version=(8, 0, 0))

        expr = ClickHouseJSONObjectExpression(dialect, data={"name": "John", "age": 30})
        sql, params = expr.to_sql()

        assert "map" in sql
        assert "name" in params
        assert "age" in params

    def test_json_object_with_kwargs(self):
        """Test JSON object creation with keyword arguments."""
        dialect = ClickHouseDialect(version=(8, 0, 0))

        expr = ClickHouseJSONObjectExpression(dialect, name="John", age=30).as_("obj")
        sql, params = expr.to_sql()

        assert "map" in sql
        assert "AS `obj`" in sql


class TestClickHouseJSONArrayExpression:
    """Test ClickHouseJSONArrayExpression class."""

    def test_json_array_basic(self):
        """Test basic JSON array creation."""
        dialect = ClickHouseDialect(version=(8, 0, 0))

        expr = ClickHouseJSONArrayExpression(dialect, values=[1, 2, 3])
        sql, params = expr.to_sql()

        assert "[" in sql
        assert params[0] == 1

    def test_json_array_with_args(self):
        """Test JSON array with positional arguments."""
        dialect = ClickHouseDialect(version=(8, 0, 0))

        expr = ClickHouseJSONArrayExpression(dialect, 1, 2, 3)
        sql, params = expr.to_sql()

        assert "[" in sql
        assert len(params) == 3

    def test_json_array_with_alias(self):
        """Test JSON array with alias."""
        dialect = ClickHouseDialect(version=(8, 0, 0))

        expr = ClickHouseJSONArrayExpression(dialect, ["a", "b"]).as_("arr")
        sql, params = expr.to_sql()

        assert "[" in sql
        assert "AS `arr`" in sql


class TestClickHouseJSONContainsExpression:
    """Test ClickHouseJSONContainsExpression class."""

    def test_json_contains_basic(self):
        """Test basic JSON contains check."""
        dialect = ClickHouseDialect(version=(8, 0, 0))

        expr = ClickHouseJSONContainsExpression(dialect, "data", "John", "$.name")
        sql, params = expr.to_sql()

        assert "isNotNull" in sql
        assert "data" in sql
        assert "John" in params

    def test_json_contains_with_alias(self):
        """Test JSON contains with alias."""
        dialect = ClickHouseDialect(version=(8, 0, 0))

        expr = ClickHouseJSONContainsExpression(dialect, "data", "value", "$.key").as_("contains")
        sql, params = expr.to_sql()

        assert "isNotNull" in sql
        assert "AS `contains`" in sql

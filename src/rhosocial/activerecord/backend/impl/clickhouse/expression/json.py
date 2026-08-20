# src/rhosocial/activerecord/backend/impl/clickhouse/expression/json.py
"""
ClickHouse-specific JSON expression functions.

This module provides expression classes for ClickHouse JSON functions:
- ClickHouseJSONExtractExpression
- ClickHouseJSONObjectExpression
- ClickHouseJSONArrayExpression
- ClickHouseJSONContainsExpression
"""

from typing import TYPE_CHECKING, Any, List, Optional

from rhosocial.activerecord.backend.expression.bases import SQLQueryAndParams, SQLValueExpression
from rhosocial.activerecord.backend.expression.mixins import (
    AliasableMixin,
    ComparisonMixin,
)

if TYPE_CHECKING:
    from rhosocial.activerecord.backend.dialect import SQLDialectBase


class ClickHouseJSONExtractExpression(AliasableMixin, ComparisonMixin, SQLValueExpression):
    """ClickHouse JSON_EXTRACT expression.

    Extracts a value from a JSON document using a path.

    Example:
        >>> expr = ClickHouseJSONExtractExpression(dialect, 'data', '$.name')
    """

    def __init__(
        self,
        dialect: "SQLDialectBase",
        json_column: str,
        path: str,
    ):
        super().__init__(dialect)
        self.json_column = json_column
        self.path = path
        self.alias = None

    def to_sql(self) -> "SQLQueryAndParams":
        sql, params = self.dialect.format_json_extract(self.json_column, self.path)
        if self.alias:
            sql = f"{sql} AS {self.dialect.format_identifier(self.alias)}"
        return sql, params


class ClickHouseJSONObjectExpression(AliasableMixin, SQLValueExpression):
    """ClickHouse JSON_OBJECT expression.

    Creates a JSON object from key-value pairs.

    Example:
        >>> expr = ClickHouseJSONObjectExpression(dialect, {'name': 'Alice', 'age': 30})
        OR
        >>> expr = ClickHouseJSONObjectExpression(dialect, ('name', 'Alice'), ('age', 30))
    """

    def __init__(
        self,
        dialect: "SQLDialectBase",
        data: Any = None,
        **kwargs: Any,
    ):
        super().__init__(dialect)
        if data is not None and kwargs:
            pairs = self._convert_to_pairs(data) + self._convert_to_pairs(kwargs)
        elif data is not None:
            pairs = self._convert_to_pairs(data)
        elif kwargs:
            pairs = self._convert_to_pairs(kwargs)
        else:
            pairs = []
        self.pairs = pairs
        self.alias = None

    def _convert_to_pairs(self, data: Any) -> List[tuple]:
        """Convert dict or iterable to list of key-value tuples."""
        if isinstance(data, dict):
            return [(k, v) for k, v in data.items()]
        return list(data)

    def to_sql(self) -> "SQLQueryAndParams":
        sql, params = self.dialect.format_json_object(self.pairs)
        if self.alias:
            sql = f"{sql} AS {self.dialect.format_identifier(self.alias)}"
        return sql, params


class ClickHouseJSONArrayExpression(AliasableMixin, SQLValueExpression):
    """ClickHouse JSON_ARRAY expression.

    Creates a JSON array from values.

    Example:
        >>> expr = ClickHouseJSONArrayExpression(dialect, [1, 2, 3])
        OR
        >>> expr = ClickHouseJSONArrayExpression(dialect, 1, 2, 3)
    """

    def __init__(
        self,
        dialect: "SQLDialectBase",
        values: Any = None,
        *args: Any,
    ):
        super().__init__(dialect)
        if values is not None and args:
            self.values = [values] + list(args)
        elif values is not None:
            self.values = values if isinstance(values, list) else [values]
        elif args:
            self.values = list(args)
        else:
            self.values = []
        self.alias = None

    def to_sql(self) -> "SQLQueryAndParams":
        sql, params = self.dialect.format_json_array(self.values)
        if self.alias:
            sql = f"{sql} AS {self.dialect.format_identifier(self.alias)}"
        return sql, params


class ClickHouseJSONContainsExpression(AliasableMixin, ComparisonMixin, SQLValueExpression):
    """ClickHouse JSON_CONTAINS expression.

    Checks if a JSON document contains a specific value.

    Example:
        >>> expr = ClickHouseJSONContainsExpression(dialect, 'data', 'urgent', '$.tags')
    """

    def __init__(
        self,
        dialect: "SQLDialectBase",
        json_column: str,
        value: str,
        path: Optional[str] = None,
    ):
        super().__init__(dialect)
        self.json_column = json_column
        self.value = value
        self.path = path
        self.alias = None

    def to_sql(self) -> "SQLQueryAndParams":
        sql, params = self.dialect.format_json_contains(self.json_column, self.value, self.path)
        if self.alias:
            sql = f"{sql} AS {self.dialect.format_identifier(self.alias)}"
        return sql, params


__all__ = [
    "ClickHouseJSONExtractExpression",
    "ClickHouseJSONObjectExpression",
    "ClickHouseJSONArrayExpression",
    "ClickHouseJSONContainsExpression",
]

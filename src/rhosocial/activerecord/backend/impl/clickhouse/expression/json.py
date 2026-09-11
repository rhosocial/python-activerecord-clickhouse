# src/rhosocial/activerecord/backend/impl/clickhouse/expression/json.py
"""
ClickHouse-specific JSON expression functions.

This module provides expression classes for ClickHouse JSON functions:
- ClickHouseJSONExtractExpression
- ClickHouseJSONObjectExpression
- ClickHouseJSONArrayExpression
- ClickHouseJSONContainsExpression
- ClickHouseJSONUnquoteExpression
- ClickHouseJSONSetExpression
- ClickHouseJSONRemoveExpression
- ClickHouseJSONTypeExpression
- ClickHouseJSONValidExpression
- ClickHouseJSONSearchExpression
"""

from typing import TYPE_CHECKING, Any, Dict, List, Optional

from rhosocial.activerecord.backend.expression.bases import SQLValueExpression
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
        *,
        alias: Optional[str] = None,
    ):
        super().__init__(dialect)
        self.json_column = json_column
        self.path = path
        self.alias = alias

    @property
    def format_method(self) -> str:
        """The dialect formatting method that renders this expression."""
        return "format_json_extract"


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
        *,
        alias: Optional[str] = None,
        **kwargs: Any,
    ):
        super().__init__(dialect)
        self.data = data  # keep raw for get_params() introspection
        self.kwargs: Dict[str, Any] = dict(kwargs)
        if data is not None and kwargs:
            pairs = self._convert_to_pairs(data) + self._convert_to_pairs(kwargs)
        elif data is not None:
            pairs = self._convert_to_pairs(data)
        elif kwargs:
            pairs = self._convert_to_pairs(kwargs)
        else:
            pairs = []
        self.pairs = pairs
        self.alias = alias

    def _convert_to_pairs(self, data: Any) -> List[tuple]:
        """Convert dict or iterable to list of key-value tuples."""
        if isinstance(data, dict):
            return [(k, v) for k, v in data.items()]
        return list(data)

    @property
    def format_method(self) -> str:
        """The dialect formatting method that renders this expression."""
        return "format_json_object"


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
        alias: Optional[str] = None,
    ):
        super().__init__(dialect)
        self._raw_values = values  # keep raw for get_params() introspection
        self.args = list(args)  # keep raw for get_params() introspection
        if values is not None and args:
            self.values = [values] + list(args)
        elif values is not None:
            self.values = values if isinstance(values, list) else [values]
        elif args:
            self.values = list(args)
        else:
            self.values = []
        self.alias = alias

    def get_params(self) -> Dict[str, Any]:
        """Return the raw constructor arguments.

        The ``values`` parameter is normalized into ``self.values`` during
        construction; returning the raw form keeps the round-trip
        (serialize -> deserialize) from double-applying the positional args.
        """
        return {"values": self._raw_values, "args": self.args, "alias": self.alias}

    @property
    def format_method(self) -> str:
        """The dialect formatting method that renders this expression."""
        return "format_json_array"


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
        *,
        alias: Optional[str] = None,
    ):
        super().__init__(dialect)
        self.json_column = json_column
        self.value = value
        self.path = path
        self.alias = alias

    @property
    def format_method(self) -> str:
        """The dialect formatting method that renders this expression."""
        return "format_json_contains"


class ClickHouseJSONUnquoteExpression(AliasableMixin, SQLValueExpression):
    """ClickHouse JSON_UNQUOTE expression.

    Unquotes a JSON value.

    Example:
        >>> expr = ClickHouseJSONUnquoteExpression(dialect, 'data')
    """

    def __init__(
        self,
        dialect: "SQLDialectBase",
        json_val: str,
        *,
        alias: Optional[str] = None,
    ):
        super().__init__(dialect)
        self.json_val = json_val
        self.alias = alias

    @property
    def format_method(self) -> str:
        """The dialect formatting method that renders this expression."""
        return "format_json_unquote"


class ClickHouseJSONSetExpression(AliasableMixin, SQLValueExpression):
    """ClickHouse JSON_SET expression.

    Sets a value in a JSON document.

    Example:
        >>> expr = ClickHouseJSONSetExpression(dialect, 'data', '$.name', 'John')
    """

    def __init__(
        self,
        dialect: "SQLDialectBase",
        json_column: str,
        path: str,
        value: Any,
        *,
        path_value_pairs: Optional[List[tuple]] = None,
        alias: Optional[str] = None,
    ):
        super().__init__(dialect)
        self.json_column = json_column
        self.path = path
        self.value = value
        self.path_value_pairs = path_value_pairs or []
        self.alias = alias

    @property
    def format_method(self) -> str:
        """The dialect formatting method that renders this expression."""
        return "format_json_set"


class ClickHouseJSONRemoveExpression(AliasableMixin, SQLValueExpression):
    """ClickHouse JSON_REMOVE expression.

    Removes a value from a JSON document.

    Example:
        >>> expr = ClickHouseJSONRemoveExpression(dialect, 'data', '$.temp')
    """

    def __init__(
        self,
        dialect: "SQLDialectBase",
        json_column: str,
        path: str,
        *,
        paths: Optional[List[str]] = None,
        alias: Optional[str] = None,
    ):
        super().__init__(dialect)
        self.json_column = json_column
        self.path = path
        self.paths = paths or []
        self.alias = alias

    @property
    def format_method(self) -> str:
        """The dialect formatting method that renders this expression."""
        return "format_json_remove"


class ClickHouseJSONTypeExpression(AliasableMixin, SQLValueExpression):
    """ClickHouse JSON_TYPE expression.

    Returns the type of a JSON value.

    Example:
        >>> expr = ClickHouseJSONTypeExpression(dialect, 'data')
    """

    def __init__(
        self,
        dialect: "SQLDialectBase",
        json_val: str,
        *,
        alias: Optional[str] = None,
    ):
        super().__init__(dialect)
        self.json_val = json_val
        self.alias = alias

    @property
    def format_method(self) -> str:
        """The dialect formatting method that renders this expression."""
        return "format_json_type"


class ClickHouseJSONValidExpression(AliasableMixin, ComparisonMixin, SQLValueExpression):
    """ClickHouse JSON_VALID expression.

    Checks if a value is valid JSON.

    Example:
        >>> expr = ClickHouseJSONValidExpression(dialect, 'data')
    """

    def __init__(
        self,
        dialect: "SQLDialectBase",
        json_val: str,
        *,
        alias: Optional[str] = None,
    ):
        super().__init__(dialect)
        self.json_val = json_val
        self.alias = alias

    @property
    def format_method(self) -> str:
        """The dialect formatting method that renders this expression."""
        return "format_json_valid"


class ClickHouseJSONSearchExpression(AliasableMixin, SQLValueExpression):
    """ClickHouse JSON_SEARCH expression.

    Searches for a string in a JSON document.

    Example:
        >>> expr = ClickHouseJSONSearchExpression(dialect, 'data', 'John')
    """

    def __init__(
        self,
        dialect: "SQLDialectBase",
        json_column: str,
        search_str: str,
        *,
        path: Optional[str] = None,
        all: bool = False,
        alias: Optional[str] = None,
    ):
        super().__init__(dialect)
        self.json_column = json_column
        self.search_str = search_str
        self.path = path
        self.all = all
        self.alias = alias

    @property
    def format_method(self) -> str:
        """The dialect formatting method that renders this expression."""
        return "format_json_search"


__all__ = [
    "ClickHouseJSONExtractExpression",
    "ClickHouseJSONObjectExpression",
    "ClickHouseJSONArrayExpression",
    "ClickHouseJSONContainsExpression",
    "ClickHouseJSONUnquoteExpression",
    "ClickHouseJSONSetExpression",
    "ClickHouseJSONRemoveExpression",
    "ClickHouseJSONTypeExpression",
    "ClickHouseJSONValidExpression",
    "ClickHouseJSONSearchExpression",
]

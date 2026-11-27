# src/rhosocial/activerecord/backend/impl/clickhouse/mixins/json.py
from typing import TYPE_CHECKING, Any, List, Optional, Tuple, Union

from rhosocial.activerecord.backend.dialect.exceptions import UnsupportedFeatureError
from rhosocial.activerecord.backend.expression.bases import BaseExpression

if TYPE_CHECKING:
    from rhosocial.activerecord.backend.impl.clickhouse.expression.json import (
        ClickHouseJSONArrayExpression,
        ClickHouseJSONContainsExpression,
        ClickHouseJSONExtractExpression,
        ClickHouseJSONObjectExpression,
        ClickHouseJSONRemoveExpression,
        ClickHouseJSONSearchExpression,
        ClickHouseJSONSetExpression,
        ClickHouseJSONTypeExpression,
        ClickHouseJSONUnquoteExpression,
        ClickHouseJSONValidExpression,
    )
    from rhosocial.activerecord.backend.impl.clickhouse.expression.json_table import (
        ClickHouseJSONTableExpression,
    )


if TYPE_CHECKING:
    from rhosocial.activerecord.backend.expression.advanced_functions import (
        JSONDocumentValue,
        JSONTextValue,
    )

    #: Core has one class per JSON operator, and this dialect renders either
    #: from the same code path -- so the parameter is a union, not one of the
    #: two. ``JSONTextValue`` subclasses ``JSONDocumentValue`` so a
    #: path chain can keep going after ``->>``; that inheritance is about
    #: accessors, not about ``->>`` yielding a document.
    JSONPathNode = Union[JSONDocumentValue, JSONTextValue]


def _simple_json_path_parts(path: str) -> Optional[List[str]]:
    """Keys of a simple ``$.a.b`` path, or ``None`` for a complex path.

    A path is simple when it starts with ``$`` and names only dotted keys;
    array indexing, wildcards, filters and braces need ``JSON_VALUE`` instead.
    The decision and the split are one character scan, not SQL-text rewriting.
    """
    if not path or path[0] != "$":
        return None
    for char in path:
        if char in "{[*(":
            return None
    parts: List[str] = []
    current: List[str] = []
    for char in path:
        if char == ".":
            if current:
                parts.append("".join(current))
                current = []
        elif char != "$":
            current.append(char)
    if current:
        parts.append("".join(current))
    return parts


class ClickHouseJSONFunctionMixin:
    """ClickHouse JSON function implementation using native ClickHouse functions."""

    def supports_json_type(self) -> bool:
        return self.version_at_least((26, 0, 0))

    def supports_json_merge_patch(self) -> bool:
        return self.version_at_least((26, 0, 0))

    def supports_json_table(self) -> bool:
        return False

    def supports_json_arrow_operators(self) -> bool:
        """ClickHouse does not support the MySQL-style ``->`` / ``->>`` operators."""
        return False

    def format_json_function_expression(self, expr: "JSONPathNode") -> Tuple[str, tuple]:
        """Format a JSON path expression using native ClickHouse functions.

        ``->``  (JSON value) maps to ``JSONExtractRaw(col, ...parts...)``
        ``->>`` (as text)    maps to ``JSONExtractString(col, ...parts...)``

        Simple dotted paths (``$.a.b``) are split into key arguments; complex
        paths (arrays, wildcards, filters) fall back to ``JSON_VALUE``.
        """
        # ``column`` is declared as an expression or a bare name; which one it
        # is is a type question, so it is asked with isinstance rather than
        # probing for a ``to_sql`` attribute.
        if isinstance(expr.column, BaseExpression):
            col_sql, col_params = expr.column.to_sql()
        else:
            col_sql, col_params = self.format_identifier(str(expr.column)), ()

        escaped_path = self.escape_sql_string(expr.path)
        simple_parts = _simple_json_path_parts(expr.path)

        if expr.operation == "->":
            if simple_parts is not None:
                args = "".join(f", '{self.escape_sql_string(p)}'" for p in simple_parts)
                sql = f"JSONExtractRaw({col_sql}{args})"
            else:
                sql = f"JSON_VALUE({col_sql}, '{escaped_path}')"
        elif expr.operation == "->>":
            if simple_parts is not None:
                args = "".join(f", '{self.escape_sql_string(p)}'" for p in simple_parts)
                sql = f"JSONExtractString({col_sql}{args})"
            else:
                sql = f"JSON_VALUE({col_sql}, '{escaped_path}')"
        else:
            sql = f"{col_sql} {expr.operation} '{escaped_path}'"

        params = col_params

        if expr.alias:
            sql = f"{sql} AS {self.format_identifier(expr.alias)}"

        return sql, params

    def format_json_extract_expression(
        self, expr: "ClickHouseJSONExtractExpression"
    ) -> Tuple[str, tuple]:
        """Format JSONExtract function."""
        all_paths = [expr.path]
        if expr.paths:
            all_paths.extend(expr.paths)
        ph = self.get_parameter_placeholder()
        placeholders = ", ".join([ph for _ in all_paths])
        sql = f"JSONExtract({expr.json_column}, {placeholders})"
        if expr.alias:
            sql = f"{sql} AS {self.format_identifier(expr.alias)}"
        return sql, tuple(all_paths)

    def format_json_unquote_expression(
        self, expr: "ClickHouseJSONUnquoteExpression"
    ) -> Tuple[str, tuple]:
        sql = f"JSONExtractString({expr.json_val})"
        if expr.alias:
            sql = f"{sql} AS {self.format_identifier(expr.alias)}"
        return sql, ()

    def format_json_object_expression(
        self, expr: "ClickHouseJSONObjectExpression"
    ) -> Tuple[str, tuple]:
        """Format map function (ClickHouse equivalent of JSON_OBJECT)."""
        pairs = expr.pairs
        if not pairs:
            sql = "map()"
            if expr.alias:
                sql = f"{sql} AS {self.format_identifier(expr.alias)}"
            return sql, ()

        ph = self.get_parameter_placeholder()
        parts = []
        params: List[Any] = []

        for key, value in pairs:
            parts.append(ph)
            parts.append(ph)
            params.append(key)
            params.append(value)

        sql = f"map({', '.join(parts)})"
        if expr.alias:
            sql = f"{sql} AS {self.format_identifier(expr.alias)}"
        return sql, tuple(params)

    def format_json_array_expression(
        self, expr: "ClickHouseJSONArrayExpression"
    ) -> Tuple[str, tuple]:
        """Format ClickHouse array literal (equivalent to JSON_ARRAY)."""
        values = expr.values
        if not values:
            return "[]", ()
        ph = self.get_parameter_placeholder()
        placeholders = ", ".join([ph for _ in values])
        sql = f"[{placeholders}]"
        if expr.alias:
            sql = f"{sql} AS {self.format_identifier(expr.alias)}"
        return sql, tuple(values)

    def format_json_contains_expression(
        self, expr: "ClickHouseJSONContainsExpression"
    ) -> Tuple[str, tuple]:
        """Format JSON_CONTAINS approximation for ClickHouse.

        ClickHouse has no direct JSON_CONTAINS equivalent. This uses
        isNotNull(JSONExtract(...)) to check if a path exists, which is a
        reasonable approximation for path-based existence checks.
        """
        ph = self.get_parameter_placeholder()
        path = expr.path
        if path:
            sql = f"isNotNull(JSONExtract({expr.json_column}, {ph}, {ph}))"
            params = (expr.value, path)
        else:
            sql = f"isNotNull(JSONExtract({expr.json_column}, {ph}))"
            params = (expr.value,)
        if expr.alias:
            sql = f"{sql} AS {self.format_identifier(expr.alias)}"
        return sql, params

    def format_json_set_expression(self, expr: "ClickHouseJSONSetExpression") -> Tuple[str, tuple]:
        """Format JSON_SET approximation for ClickHouse.

        ClickHouse has no direct JSON_SET equivalent. This uses mapUpdate
        on a Map-typed JSON extraction as an approximation.
        """
        all_pairs = [(expr.path, expr.value)]
        if expr.path_value_pairs:
            all_pairs.extend(expr.path_value_pairs)

        ph = self.get_parameter_placeholder()
        parts = []
        params: List[Any] = []

        for p, v in all_pairs:
            parts.append(ph)
            parts.append(ph)
            params.append(p)
            params.append(v)

        map_expr = f"map({', '.join(parts)})"
        sql = f"assumeNotNull(mapUpdate(JSONExtract({expr.json_column}, 'Map(String, String)'), {map_expr}))"
        if expr.alias:
            sql = f"{sql} AS {self.format_identifier(expr.alias)}"
        return sql, tuple(params)

    def format_json_remove_expression(
        self, expr: "ClickHouseJSONRemoveExpression"
    ) -> Tuple[str, tuple]:
        """Format JSON_REMOVE approximation for ClickHouse.

        ClickHouse has no direct JSON_REMOVE equivalent. This uses mapRemove
        on a Map-typed JSON extraction as an approximation.
        """
        all_paths = [expr.path]
        if expr.paths:
            all_paths.extend(expr.paths)
        ph = self.get_parameter_placeholder()
        placeholders = ", ".join([ph for _ in all_paths])
        sql = f"mapRemove(JSONExtract({expr.json_column}, 'Map(String, String)'), {placeholders})"
        if expr.alias:
            sql = f"{sql} AS {self.format_identifier(expr.alias)}"
        return sql, tuple(all_paths)

    def format_json_type_expression(
        self, expr: "ClickHouseJSONTypeExpression"
    ) -> Tuple[str, tuple]:
        sql = f"JSONType({expr.json_val})"
        if expr.alias:
            sql = f"{sql} AS {self.format_identifier(expr.alias)}"
        return sql, ()

    def format_json_valid_expression(
        self, expr: "ClickHouseJSONValidExpression"
    ) -> Tuple[str, tuple]:
        sql = f"JSON_VALID({expr.json_val})"
        if expr.alias:
            sql = f"{sql} AS {self.format_identifier(expr.alias)}"
        return sql, ()

    def format_json_search_expression(
        self, expr: "ClickHouseJSONSearchExpression"
    ) -> Tuple[str, tuple]:
        """Format JSON_SEARCH approximation for ClickHouse.

        ClickHouse has no direct JSON_SEARCH equivalent. This uses
        JSONExtractString + LIKE as a basic text search approximation.
        """
        one_or_all = "'all'" if expr.all else "'one'"
        ph = self.get_parameter_placeholder()
        path = expr.path
        if path:
            sql = f"JSONExtractString({expr.json_column}, {ph}) LIKE {ph} AND {one_or_all} = 'one'"
            params = (path, expr.search_str)
        else:
            sql = f"JSONExtractString({expr.json_column}) LIKE {ph} AND {one_or_all} = 'one'"
            params = (expr.search_str,)
        if expr.alias:
            sql = f"{sql} AS {self.format_identifier(expr.alias)}"
        return sql, params

    def format_json_table_expression(
        self, expr: "ClickHouseJSONTableExpression"
    ) -> Tuple[str, tuple]:
        """JSON_TABLE is not supported by ClickHouse."""
        raise UnsupportedFeatureError(
            self.name,
            "JSON_TABLE",
            suggestion="Use JSONExtract/JSONExtractKeys with arrayJoin or subqueries instead.",
        )

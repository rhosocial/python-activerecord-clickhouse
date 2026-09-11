# src/rhosocial/activerecord/backend/impl/clickhouse/mixins/json.py
from typing import Any, List, Optional, Tuple, TYPE_CHECKING

from rhosocial.activerecord.backend.dialect.exceptions import UnsupportedFeatureError
from rhosocial.activerecord.backend.expression import bases

if TYPE_CHECKING:
    from rhosocial.activerecord.backend.expression.advanced_functions import JSONExpression


class ClickHouseJSONFunctionMixin:
    """ClickHouse JSON function implementation using native ClickHouse functions."""

    _JSON_FUNCTION_VERSIONS = {
        "JSONType": (26, 0, 0),
        "JSONValid": (26, 0, 0),
        "JSONExtract": (26, 0, 0),
        "JSONExtractString": (26, 0, 0),
        "JSON_QUERY": (26, 0, 0),
        "JSON_VALUE": (26, 0, 0),
    }

    def supports_json_type(self) -> bool:
        return self.version >= (26, 0, 0)

    def supports_json_merge_patch(self) -> bool:
        return self.version >= (26, 0, 0)

    def supports_json_table(self) -> bool:
        return False

    def supports_json_arrow_operators(self) -> bool:
        """ClickHouse does not support the MySQL-style ``->`` / ``->>`` operators."""
        return False

    def format_json_function_expression(self, expr: "JSONExpression") -> Tuple[str, Tuple]:
        """Format a JSON path expression using native ClickHouse functions.

        ``->``  (JSON value) maps to ``JSONExtractRaw(col, ...parts...)``
        ``->>`` (as text)    maps to ``JSONExtractString(col, ...parts...)``

        Simple dotted paths (``$.a.b``) are split into key arguments; complex
        paths (arrays, wildcards, filters) fall back to ``JSON_VALUE``.
        """
        if isinstance(expr.column, bases.BaseExpression):
            col_sql, col_params = expr.column.to_sql()
        else:
            col_sql, col_params = self.format_identifier(str(expr.column)), ()

        escaped_path = self._escape_sql_string(expr.path)
        is_simple = (
            expr.path.startswith("$")
            and "{" not in expr.path
            and "[" not in expr.path
            and "*" not in expr.path
            and "(" not in expr.path
        )

        if expr.operation == "->":
            if is_simple:
                parts = [p for p in expr.path.lstrip("$.").split(".") if p]
                args = "".join(f", '{self._escape_sql_string(p)}'" for p in parts)
                sql = f"JSONExtractRaw({col_sql}{args})"
            else:
                sql = f"JSON_VALUE({col_sql}, '{escaped_path}')"
        elif expr.operation == "->>":
            if is_simple:
                parts = [p for p in expr.path.lstrip("$.").split(".") if p]
                args = "".join(f", '{self._escape_sql_string(p)}'" for p in parts)
                sql = f"JSONExtractString({col_sql}{args})"
            else:
                sql = f"JSON_VALUE({col_sql}, '{escaped_path}')"
        else:
            sql = f"{col_sql} {expr.operation} '{escaped_path}'"

        params = col_params

        if expr.cast_types:
            for target_type in expr.cast_types:
                sql, params = self.format_cast_expression(sql, target_type, params, None)

        if expr.alias:
            sql = f"{sql} AS {self.format_identifier(expr.alias)}"

        return sql, params

    def supports_json_function(self, function_name: str) -> bool:
        if function_name in self._JSON_FUNCTION_VERSIONS:
            return self.version >= self._JSON_FUNCTION_VERSIONS[function_name]
        return self.version >= (26, 0, 0)

    def format_json_extract(self, expr) -> Tuple[str, tuple]:
        """Format JSONExtract function."""
        all_paths = [expr.path]
        if hasattr(expr, "paths") and expr.paths:
            all_paths.extend(expr.paths)
        ph = self.get_parameter_placeholder()
        placeholders = ", ".join([ph for _ in all_paths])
        return f"JSONExtract({expr.json_column}, {placeholders})", tuple(all_paths)

    def format_json_unquote(self, expr) -> Tuple[str, tuple]:
        return f"JSONExtractString({expr.json_val})", ()

    def format_json_object(self, expr) -> Tuple[str, tuple]:
        """Format map function (ClickHouse equivalent of JSON_OBJECT)."""
        pairs = getattr(expr, "pairs", [])
        if not pairs:
            return "map()", ()

        ph = self.get_parameter_placeholder()
        parts = []
        params: List[Any] = []

        for key, value in pairs:
            parts.append(ph)
            parts.append(ph)
            params.append(key)
            params.append(value)

        return f"map({', '.join(parts)})", tuple(params)

    def format_json_array(self, expr) -> Tuple[str, tuple]:
        """Format ClickHouse array literal (equivalent to JSON_ARRAY)."""
        values = getattr(expr, "values", [])
        if not values:
            return "[]", ()
        ph = self.get_parameter_placeholder()
        placeholders = ", ".join([ph for _ in values])
        return f"[{placeholders}]", tuple(values)

    def format_json_contains(self, expr) -> Tuple[str, tuple]:
        """Format JSON_CONTAINS approximation for ClickHouse.

        ClickHouse has no direct JSON_CONTAINS equivalent. This uses
        isNotNull(JSONExtract(...)) to check if a path exists, which is a
        reasonable approximation for path-based existence checks.
        """
        ph = self.get_parameter_placeholder()
        path = getattr(expr, "path", None)
        if path:
            return f"isNotNull(JSONExtract({expr.json_column}, {ph}, {ph}))", (expr.value, path)
        return f"isNotNull(JSONExtract({expr.json_column}, {ph}))", (expr.value,)

    def format_json_set(self, expr) -> Tuple[str, tuple]:
        """Format JSON_SET approximation for ClickHouse.

        ClickHouse has no direct JSON_SET equivalent. This uses mapUpdate
        on a Map-typed JSON extraction as an approximation.
        """
        all_pairs = [(expr.path, expr.value)]
        if hasattr(expr, "path_value_pairs") and expr.path_value_pairs:
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
        return sql, tuple(params)

    def format_json_remove(self, expr) -> Tuple[str, tuple]:
        """Format JSON_REMOVE approximation for ClickHouse.

        ClickHouse has no direct JSON_REMOVE equivalent. This uses mapRemove
        on a Map-typed JSON extraction as an approximation.
        """
        all_paths = [expr.path]
        if hasattr(expr, "paths") and expr.paths:
            all_paths.extend(expr.paths)
        ph = self.get_parameter_placeholder()
        placeholders = ", ".join([ph for _ in all_paths])
        return f"mapRemove(JSONExtract({expr.json_column}, 'Map(String, String)'), {placeholders})", tuple(all_paths)

    def format_json_type(self, expr) -> Tuple[str, tuple]:
        return f"JSONType({expr.json_val})", ()

    def format_json_valid(self, expr) -> Tuple[str, tuple]:
        return f"JSON_VALID({expr.json_val})", ()

    def format_json_search(self, expr) -> Tuple[str, tuple]:
        """Format JSON_SEARCH approximation for ClickHouse.

        ClickHouse has no direct JSON_SEARCH equivalent. This uses
        JSONExtractString + LIKE as a basic text search approximation.
        """
        one_or_all = "'all'" if getattr(expr, "all", False) else "'one'"
        ph = self.get_parameter_placeholder()
        path = getattr(expr, "path", None)
        if path:
            return f"JSONExtractString({expr.json_column}, {ph}) LIKE {ph} AND {one_or_all} = 'one'", (path, expr.search_str)
        return f"JSONExtractString({expr.json_column}) LIKE {ph} AND {one_or_all} = 'one'", (expr.search_str,)

    def format_json_table_expression(self, expr) -> Tuple[str, tuple]:
        """JSON_TABLE is not supported by ClickHouse."""
        raise UnsupportedFeatureError(
            self.name,
            "JSON_TABLE",
            suggestion="Use JSONExtract/JSONExtractKeys with arrayJoin or subqueries instead.",
        )
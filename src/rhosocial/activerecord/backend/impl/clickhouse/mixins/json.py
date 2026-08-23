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

    def format_json_extract(self, json_doc: str, path: str, paths: Optional[List[str]] = None) -> Tuple[str, tuple]:
        """Format JSONExtract function."""
        all_paths = [path]
        if paths:
            all_paths.extend(paths)
        path_placeholders = ", ".join(["%s" for _ in all_paths])
        return f"JSONExtract({json_doc}, {path_placeholders})", tuple(all_paths)

    def format_json_unquote(self, json_val: str) -> Tuple[str, tuple]:
        return f"JSONExtractString({json_val})", ()

    def format_json_object(self, key_value_pairs: List[Tuple[str, Any]]) -> Tuple[str, tuple]:
        """Format map function (ClickHouse equivalent of JSON_OBJECT)."""
        if not key_value_pairs:
            return "map()", ()

        parts = []
        params: List[Any] = []

        for key, value in key_value_pairs:
            parts.append("%s")
            parts.append("%s")
            params.append(key)
            params.append(value)

        return f"map({', '.join(parts)})", tuple(params)

    def format_json_array(self, values: List[Any]) -> Tuple[str, tuple]:
        """Format ClickHouse array literal (equivalent of JSON_ARRAY)."""
        if not values:
            return "[]", ()
        placeholders = ", ".join(["%s" for _ in values])
        return f"[{placeholders}]", tuple(values)

    def format_json_contains(self, target: str, candidate: str, path: Optional[str] = None) -> Tuple[str, tuple]:
        """Format JSON_CONTAINS approximation for ClickHouse.

        ClickHouse has no direct JSON_CONTAINS equivalent. This uses
        isNotNull(JSONExtract(...)) to check if a path exists, which is a
        reasonable approximation for path-based existence checks.
        """
        if path:
            return f"isNotNull(JSONExtract({target}, %s, %s))", (candidate, path)
        return f"isNotNull(JSONExtract({target}, %s))", (candidate,)

    def format_json_set(
        self, json_doc: str, path: str, value: Any, path_value_pairs: Optional[List[Tuple[str, Any]]] = None
    ) -> Tuple[str, tuple]:
        """Format JSON_SET approximation for ClickHouse.

        ClickHouse has no direct JSON_SET equivalent. This uses mapUpdate
        on a Map-typed JSON extraction as an approximation.
        """
        all_pairs = [(path, value)]
        if path_value_pairs:
            all_pairs.extend(path_value_pairs)

        parts = []
        params: List[Any] = []

        for p, v in all_pairs:
            parts.append("%s")
            parts.append("%s")
            params.append(p)
            params.append(v)

        map_expr = f"map({', '.join(parts)})"
        sql = f"assumeNotNull(mapUpdate(JSONExtract({json_doc}, 'Map(String, String)'), {map_expr}))"
        return sql, tuple(params)

    def format_json_remove(self, json_doc: str, path: str, paths: Optional[List[str]] = None) -> Tuple[str, tuple]:
        """Format JSON_REMOVE approximation for ClickHouse.

        ClickHouse has no direct JSON_REMOVE equivalent. This uses mapRemove
        on a Map-typed JSON extraction as an approximation.
        """
        all_paths = [path]
        if paths:
            all_paths.extend(paths)
        path_placeholders = ", ".join(["%s" for _ in all_paths])
        return f"mapRemove(JSONExtract({json_doc}, 'Map(String, String)'), {path_placeholders})", tuple(all_paths)

    def format_json_type(self, json_val: str) -> Tuple[str, tuple]:
        return f"JSONType({json_val})", ()

    def format_json_valid(self, json_val: str) -> Tuple[str, tuple]:
        return f"JSON_VALID({json_val})", ()

    def format_json_search(
        self, json_doc: str, search_str: str, path: Optional[str] = None, all: bool = False
    ) -> Tuple[str, tuple]:
        """Format JSON_SEARCH approximation for ClickHouse.

        ClickHouse has no direct JSON_SEARCH equivalent. This uses
        JSONExtractString + LIKE as a basic text search approximation.
        """
        one_or_all = "'all'" if all else "'one'"
        if path:
            return f"JSONExtractString({json_doc}, %s) LIKE %s AND {one_or_all} = 'one'", (path, search_str)
        return f"JSONExtractString({json_doc}) LIKE %s AND {one_or_all} = 'one'", (search_str,)

    def format_json_table_expression(self, expr) -> Tuple[str, tuple]:
        """JSON_TABLE is not supported by ClickHouse."""
        raise UnsupportedFeatureError(
            self.name,
            "JSON_TABLE",
            suggestion="Use JSONExtract/JSONExtractKeys with arrayJoin or subqueries instead.",
        )
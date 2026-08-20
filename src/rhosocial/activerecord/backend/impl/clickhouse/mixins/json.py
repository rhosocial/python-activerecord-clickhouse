# src/rhosocial/activerecord/backend/impl/clickhouse/mixins/json.py
from typing import Any, List, Optional, Tuple, TYPE_CHECKING

from rhosocial.activerecord.backend.expression import bases

if TYPE_CHECKING:
    from rhosocial.activerecord.backend.expression.advanced_functions import JSONExpression


class ClickHouseJSONFunctionMixin:
    """ClickHouse JSON function implementation."""

    _JSON_FUNCTION_VERSIONS = {
        "JSON_TABLE": (8, 0, 4),
        "JSON_VALUE": (8, 0, 21),
        "JSON_SCHEMA_VALID": (8, 0, 17),
        "JSON_MERGE_PATCH": (8, 0, 3),
    }

    def supports_json_type(self) -> bool:
        return self.version >= (5, 7, 8)

    def supports_json_merge_patch(self) -> bool:
        return self.version >= (8, 0, 3)

    def supports_json_table(self) -> bool:
        return self.version >= (8, 0, 4)

    def supports_json_function(self, function_name: str) -> bool:
        if function_name in self._JSON_FUNCTION_VERSIONS:
            return self.version >= self._JSON_FUNCTION_VERSIONS[function_name]
        return self.version >= (5, 7, 8)

    def format_json_extract(self, json_doc: str, path: str, paths: Optional[List[str]] = None) -> Tuple[str, tuple]:
        """Format JSON_EXTRACT function."""
        all_paths = [path]
        if paths:
            all_paths.extend(paths)
        path_placeholders = ", ".join(["%s" for _ in all_paths])
        return f"JSON_EXTRACT({json_doc}, {path_placeholders})", tuple(all_paths)

    def format_json_unquote(self, json_val: str) -> Tuple[str, tuple]:
        return f"JSON_UNQUOTE({json_val})", ()

    def format_json_object(self, key_value_pairs: List[Tuple[str, Any]]) -> Tuple[str, tuple]:
        """Format JSON_OBJECT function."""
        if not key_value_pairs:
            return "JSON_OBJECT()", ()

        parts = []
        params: List[Any] = []

        for key, value in key_value_pairs:
            parts.append("%s")
            parts.append("%s")
            params.append(key)
            params.append(value)

        return f"JSON_OBJECT({', '.join(parts)})", tuple(params)

    def format_json_array(self, values: List[Any]) -> Tuple[str, tuple]:
        """Format JSON_ARRAY function."""
        if not values:
            return "JSON_ARRAY()", ()
        placeholders = ", ".join(["%s" for _ in values])
        return f"JSON_ARRAY({placeholders})", tuple(values)

    def format_json_contains(self, target: str, candidate: str, path: Optional[str] = None) -> Tuple[str, tuple]:
        """Format JSON_CONTAINS function."""
        if path:
            return f"JSON_CONTAINS({target}, %s, %s)", (candidate, path)
        return f"JSON_CONTAINS({target}, %s)", (candidate,)

    def format_json_set(
        self, json_doc: str, path: str, value: Any, path_value_pairs: Optional[List[Tuple[str, Any]]] = None
    ) -> Tuple[str, tuple]:
        """Format JSON_SET function."""
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

        return f"JSON_SET({json_doc}, {', '.join(parts)})", tuple(params)

    def format_json_remove(self, json_doc: str, path: str, paths: Optional[List[str]] = None) -> Tuple[str, tuple]:
        """Format JSON_REMOVE function."""
        all_paths = [path]
        if paths:
            all_paths.extend(paths)
        path_placeholders = ", ".join(["%s" for _ in all_paths])
        return f"JSON_REMOVE({json_doc}, {path_placeholders})", tuple(all_paths)

    def format_json_type(self, json_val: str) -> Tuple[str, tuple]:
        return f"JSON_TYPE({json_val})", ()

    def format_json_valid(self, json_val: str) -> Tuple[str, tuple]:
        return f"JSON_VALID({json_val})", ()

    def format_json_search(
        self, json_doc: str, search_str: str, path: Optional[str] = None, all: bool = False
    ) -> Tuple[str, tuple]:
        """Format JSON_SEARCH function."""
        one_or_all = "'all'" if all else "'one'"
        if path:
            return f"JSON_SEARCH({json_doc}, {one_or_all}, %s, NULL, %s)", (search_str, path)
        return f"JSON_SEARCH({json_doc}, {one_or_all}, %s)", (search_str,)

    def format_json_arrow_expression(self, expr: "JSONExpression") -> Tuple[str, Tuple]:
        """Format JSON expression using arrow operators for ClickHouse.

        ClickHouse's -> and ->> operators require:
        1. The JSON path as a string literal, not a parameter placeholder
        2. No parentheses around the expression
        """
        if isinstance(expr.column, bases.BaseExpression):
            col_sql, col_params = expr.column.to_sql()
        else:
            col_sql, col_params = self.format_identifier(str(expr.column)), ()

        if expr.operation in ("->", "->>"):
            escaped_path = self._escape_sql_string(expr.path)
            sql = f"{col_sql}{expr.operation}'{escaped_path}'"
            params = col_params
        else:
            sql = f"({col_sql} {expr.operation} {self.get_parameter_placeholder()})"
            params = col_params + (expr.path,)

        if expr.cast_types:
            for target_type in expr.cast_types:
                sql, params = self.format_cast_expression(sql, target_type, params, None)

        if expr.alias:
            sql = f"{sql} AS {self.format_identifier(expr.alias)}"

        return sql, params

    def format_json_function_expression(self, expr: "JSONExpression") -> Tuple[str, Tuple]:
        """Format JSON expression using function-based equivalents for ClickHouse.

        ClickHouse supports JSON_EXTRACT and JSON_UNQUOTE, and also supports
        the native arrow operators.  Both paths are available.
        This is the function-based path, usable via JSONPathMode.FUNCTION.
        """
        if isinstance(expr.column, bases.BaseExpression):
            col_sql, col_params = expr.column.to_sql()
        else:
            col_sql, col_params = self.format_identifier(str(expr.column)), ()

        escaped_path = self._escape_sql_string(expr.path)

        if expr.operation == "->":
            sql = f"JSON_EXTRACT({col_sql}, '{escaped_path}')"
            params = col_params
        elif expr.operation == "->>":
            sql = f"JSON_UNQUOTE(JSON_EXTRACT({col_sql}, '{escaped_path}'))"
            params = col_params
        else:
            sql = f"{col_sql} {expr.operation} '{escaped_path}'"
            params = col_params

        if expr.cast_types:
            for target_type in expr.cast_types:
                sql, params = self.format_cast_expression(sql, target_type, params, None)

        if expr.alias:
            sql = f"{sql} AS {self.format_identifier(expr.alias)}"

        return sql, params

    def format_json_table_expression(self, expr) -> Tuple[str, tuple]:
        """Format JSON_TABLE expression."""
        expr.validate(strict=self.strict_validation)

        parts = ["JSON_TABLE("]
        parts.append(expr.json_doc)
        parts.append(",")
        parts.append(f"'{expr.path}'")
        parts.append(" COLUMNS (")

        column_parts = []
        for col in expr.columns:
            if col.ordinality:
                column_parts.append(f"{self.format_identifier(col.name)} FOR ORDINALITY")
            elif col.exists:
                column_parts.append(f"{self.format_identifier(col.name)} {col.type} EXISTS PATH '{col.path}'")
            else:
                col_def = f"{self.format_identifier(col.name)} {col.type}"
                if col.path:
                    col_def += f" PATH '{col.path}'"
                if col.error_handling:
                    if col.error_handling.upper() == "DEFAULT":
                        col_def += f" DEFAULT {col.default_value} ON ERROR"
                    else:
                        col_def += f" {col.error_handling.upper()} ON ERROR"
                column_parts.append(col_def)

        for nested in expr.nested_paths:
            nested_def = f"NESTED PATH '{nested.path}' COLUMNS ("
            nested_cols = []
            for col in nested.columns:
                if col.ordinality:
                    nested_cols.append(f"{self.format_identifier(col.name)} FOR ORDINALITY")
                else:
                    nested_cols.append(f"{self.format_identifier(col.name)} {col.type} PATH '{col.path}'")
            nested_def += ", ".join(nested_cols) + ")"
            if nested.alias:
                nested_def = f"{nested.alias} AS " + nested_def
            column_parts.append(nested_def)

        parts.append(", ".join(column_parts))
        parts.append("))")

        if expr.alias:
            parts.append(f" AS {expr.alias}")

        return "".join(parts), ()

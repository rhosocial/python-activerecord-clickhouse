# src/rhosocial/activerecord/backend/impl/clickhouse/mixins/json_duality_view.py
from typing import TYPE_CHECKING, Tuple

if TYPE_CHECKING:
    from rhosocial.activerecord.backend.impl.clickhouse.expression.json_duality_view import (
        CreateJsonDualityViewExpression,
        DropJsonDualityViewExpression,
    )


class ClickHouseJsonDualityViewMixin:
    """ClickHouse JSON Duality View implementation (ClickHouse 9.7+)."""

    def supports_json_duality_view(self) -> bool:
        return self.version >= (9, 7, 0)

    def supports_json_duality_view_dml(self) -> bool:
        return self.version >= (9, 7, 0)

    def format_create_json_duality_view_statement(self, expr: "CreateJsonDualityViewExpression") -> Tuple[str, tuple]:
        """Format CREATE JSON RELATIONAL DUALITY VIEW statement."""
        parts = []
        if expr.replace:
            parts.append("CREATE OR REPLACE JSON RELATIONAL DUALITY VIEW")
        else:
            parts.append("CREATE JSON RELATIONAL DUALITY VIEW")
        parts.append(f"`{expr.view_name}`")
        parts.append("AS")

        select_clause = self.format_duality_object_select(expr.root_spec)
        parts.append(select_clause)

        return " ".join(parts), ()

    def format_drop_json_duality_view_statement(self, expr: "DropJsonDualityViewExpression") -> Tuple[str, tuple]:
        """Format DROP VIEW for a JSON Duality View."""
        if expr.if_exists:
            return f"DROP VIEW IF EXISTS `{expr.view_name}`", ()
        return f"DROP VIEW `{expr.view_name}`", ()

    def format_duality_object_select(self, spec) -> str:
        """Format the SELECT JSON_DUALITY_OBJECT(...) FROM table clause."""
        obj_body = self.format_duality_object_body(spec)
        table_ref = f"`{spec.from_table}`"
        if spec.from_alias:
            table_ref += f" `{spec.from_alias}`"
        return f"SELECT {obj_body} FROM {table_ref}"

    def format_duality_object_body(self, spec) -> str:
        """Format JSON_DUALITY_OBJECT( WITH(...) 'key': col, ... )."""
        inner_parts = []

        if spec.tags:
            tag_names = ",".join(t.value for t in spec.tags)
            inner_parts.append(f"WITH({tag_names})")

        for col in spec.columns:
            inner_parts.append(f"'{col.json_key}': {col.column_expr}")

        for nested in spec.nested:
            nested_subquery = self.format_nested_duality(nested)
            inner_parts.append(f"'{nested.json_key}': ({nested_subquery})")

        if spec.tags:
            with_part = inner_parts[0]
            field_parts = inner_parts[1:]
            fields_str = ", ".join(field_parts)
            return f"JSON_DUALITY_OBJECT({with_part} {fields_str})"
        else:
            fields_str = ", ".join(inner_parts)
            return f"JSON_DUALITY_OBJECT({fields_str})"

    def format_nested_duality(self, nested) -> str:
        """Format a nested JSON_ARRAYAGG(JSON_DUALITY_OBJECT(...)) subquery."""
        sub_spec = nested.subquery
        obj_body = self.format_duality_object_body(sub_spec)
        table_ref = f"`{sub_spec.from_table}`"
        if sub_spec.from_alias:
            table_ref += f" `{sub_spec.from_alias}`"
        sql = f"SELECT JSON_ARRAYAGG({obj_body}) FROM {table_ref}"
        if sub_spec.join_condition:
            sql += f" WHERE {sub_spec.join_condition}"
        return sql

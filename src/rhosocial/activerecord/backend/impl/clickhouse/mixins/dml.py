# src/rhosocial/activerecord/backend/impl/clickhouse/mixins/dml.py
from typing import TYPE_CHECKING, Tuple

if TYPE_CHECKING:
    from rhosocial.activerecord.backend.expression.statements import OnConflictClause
    from rhosocial.activerecord.backend.impl.clickhouse.expression.load_data import (
        ClickHouseLoadDataExpression,
    )


class ClickHouseDMLOperationMixin:
    """ClickHouse DML operations mixin."""

    def supports_insert_ignore(self) -> bool:
        return True

    def supports_replace_into(self) -> bool:
        return True

    def supports_load_data(self) -> bool:
        return True

    def format_load_data_statement(self, expr: "ClickHouseLoadDataExpression") -> Tuple[str, tuple]:
        """Format LOAD DATA INFILE statement."""
        expr.validate(strict=self.strict_validation)

        parts = ["LOAD DATA"]

        if expr.options.local:
            parts.append("LOCAL")

        parts.append("INFILE")

        file_path_escaped = expr.file_path.replace("\\", "\\\\").replace("'", "\\'")
        parts.append(f"'{file_path_escaped}'")

        if expr.options.replace:
            parts.append("REPLACE")
        elif expr.options.ignore:
            parts.append("IGNORE")

        parts.append("INTO TABLE")
        parts.append(self.format_identifier(expr.table))

        if expr.options.character_set:
            parts.append(f"CHARACTER SET {expr.options.character_set}")

        field_parts = []
        if expr.options.fields_terminated_by is not None:
            field_parts.append(f"TERMINATED BY '{expr.options.fields_terminated_by}'")
        if expr.options.fields_enclosed_by is not None:
            field_parts.append(f"ENCLOSED BY '{expr.options.fields_enclosed_by}'")
        if expr.options.fields_escaped_by is not None:
            field_parts.append(f"ESCAPED BY '{expr.options.fields_escaped_by}'")
        if field_parts:
            parts.append("FIELDS")
            parts.append(" ".join(field_parts))

        line_parts = []
        if expr.options.lines_starting_by is not None:
            line_parts.append(f"STARTING BY '{expr.options.lines_starting_by}'")
        if expr.options.lines_terminated_by is not None:
            line_parts.append(f"TERMINATED BY '{expr.options.lines_terminated_by}'")
        if line_parts:
            parts.append("LINES")
            parts.append(" ".join(line_parts))

        if expr.options.ignore_lines is not None:
            parts.append(f"IGNORE {expr.options.ignore_lines} LINES")

        if expr.options.column_list:
            columns = ", ".join(self.format_identifier(c) for c in expr.options.column_list)
            parts.append(f"({columns})")

        if expr.options.set_assignments:
            set_parts = []
            for col, val in expr.options.set_assignments.items():
                set_parts.append(f"{self.format_identifier(col)} = {val}")
            parts.append("SET " + ", ".join(set_parts))

        return " ".join(parts), ()

    def format_on_conflict_clause(self, expr: "OnConflictClause") -> Tuple[str, tuple]:
        """Format ON DUPLICATE KEY UPDATE for ClickHouse."""
        all_params = []
        parts = ["ON DUPLICATE KEY UPDATE"]

        update_parts = []
        if expr.update_assignments:
            for col_name, value_expr in expr.update_assignments.items():
                col_sql = self.format_identifier(col_name)
                if hasattr(value_expr, "to_sql"):
                    val_sql, val_params = value_expr.to_sql()
                    all_params.extend(val_params)
                else:
                    val_sql = str(value_expr)
                update_parts.append(f"{col_sql} = {val_sql}")

        if update_parts:
            parts.append(" ".join(update_parts))
        else:
            parts.append(f"{self.format_identifier('id')} = {self.format_identifier('id')}")

        return " ".join(parts), tuple(all_params)

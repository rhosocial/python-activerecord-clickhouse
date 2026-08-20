# src/rhosocial/activerecord/backend/impl/clickhouse/mixins/column.py
from typing import Tuple, TYPE_CHECKING

if TYPE_CHECKING:
    from rhosocial.activerecord.backend.expression.statements.ddl_alter import (
        ModifyColumn,
        ChangeColumn,
    )


class ClickHouseModifyColumnMixin:
    """ClickHouse MODIFY COLUMN and CHANGE COLUMN mixin."""

    def supports_modify_column(self) -> bool:
        return True

    def supports_change_column(self) -> bool:
        return True

    def format_modify_column_action(self, action: "ModifyColumn") -> Tuple[str, tuple]:
        """Format MODIFY COLUMN action for ALTER TABLE."""
        col_sql, col_params = self.format_column_definition(action.column)
        sql = f"MODIFY COLUMN {col_sql}"
        if action.after_column:
            sql += f" AFTER {self.format_identifier(action.after_column)}"
        elif action.first:
            sql += " FIRST"
        return sql, col_params

    def format_change_column_action(self, action: "ChangeColumn") -> Tuple[str, tuple]:
        """Format CHANGE COLUMN action for ALTER TABLE."""
        col_sql, col_params = self.format_column_definition(action.column)
        sql = f"CHANGE COLUMN {self.format_identifier(action.old_name)} {col_sql}"
        if action.after_column:
            sql += f" AFTER {self.format_identifier(action.after_column)}"
        elif action.first:
            sql += " FIRST"
        return sql, col_params

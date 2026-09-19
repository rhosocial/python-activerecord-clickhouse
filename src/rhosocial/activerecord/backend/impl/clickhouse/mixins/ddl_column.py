# src/rhosocial/activerecord/backend/impl/clickhouse/mixins/ddl_column.py
from typing import Any, Dict, List, Tuple, TYPE_CHECKING

from rhosocial.activerecord.backend.dialect.exceptions import UnsupportedFeatureError

if TYPE_CHECKING:
    from rhosocial.activerecord.backend.expression.statements.ddl_table import (
        TableConstraint,
    )


class ClickHouseDDLColumnMixin:
    """ClickHouse DDL column action formatting."""

    def supports_add_column_if_not_exists(self) -> bool:
        """ClickHouse supports ADD COLUMN IF NOT EXISTS."""
        return True

    def supports_drop_column_if_exists(self) -> bool:
        """ClickHouse supports DROP COLUMN IF EXISTS."""
        return True

    def supports_drop_constraint_if_exists(self) -> bool:
        """Whether DROP CONSTRAINT IF EXISTS is supported."""
        return False

    def supports_generated_columns(self) -> bool:
        """Whether generated columns are supported (alias for protocol)."""
        return False

    def format_add_table_constraint_action(self, action: Any) -> Tuple[str, tuple]:
        raise UnsupportedFeatureError(
            self.name, "ADD CONSTRAINT",
            suggestion="ClickHouse does not support table constraints."
        )

    def format_add_column_action(self, action) -> Tuple[str, tuple]:
        column_sql, column_params = self.format_column_definition(action.column)
        parts = []
        if getattr(action, "if_not_exists", None) is True:
            parts.append("ADD COLUMN IF NOT EXISTS")
        else:
            parts.append("ADD COLUMN")
        parts.append(column_sql)
        after = action.dialect_options.get("after")
        if after:
            parts.append(f"AFTER {self.format_identifier(after)}")
        return " ".join(parts), column_params

    def format_alter_column_action(self, action) -> Tuple[str, tuple]:
        """Format ALTER TABLE ... ALTER COLUMN {SET DEFAULT | DROP DEFAULT}.

        ClickHouse 8.0 syntax is ``ALTER TABLE t ALTER [COLUMN] col {SET DEFAULT
        literal | DROP DEFAULT}``. Unlike the generic SQL-standard renderer,
        ClickHouse requires a literal for SET DEFAULT (no parenthesised
        expressions / parameters), so we inline the value.
        """
        operation = getattr(action.operation, "value", None) or str(action.operation)
        col_name = self.format_identifier(action.column_name)

        if operation == "DROP DEFAULT":
            return f"ALTER COLUMN {col_name} DROP DEFAULT", ()

        if operation == "SET DEFAULT":
            new_value = getattr(action, "new_value", None)
            if isinstance(new_value, str):
                escaped = self._escape_sql_string(new_value)
                return f"ALTER COLUMN {col_name} SET DEFAULT '{escaped}'", ()
            if isinstance(new_value, bool):
                return f"ALTER COLUMN {col_name} SET DEFAULT {1 if new_value else 0}", ()
            if new_value is None:
                raise ValueError("SET DEFAULT requires a default value")
            if isinstance(new_value, (int, float)):
                return f"ALTER COLUMN {col_name} SET DEFAULT {new_value}", ()
            if hasattr(new_value, "to_sql"):
                value_sql, value_params = new_value.to_sql()
                return f"ALTER COLUMN {col_name} SET DEFAULT {value_sql}", tuple(value_params)
            return f"ALTER COLUMN {col_name} SET DEFAULT {new_value}", ()

        return super().format_alter_column_action(action)

    def format_table_constraint(
        self,
        t_const: "TableConstraint"
    ) -> Tuple[str, tuple]:
        """Format a table-level constraint.

        ClickHouse supports only PRIMARY KEY among table-level constraints;
        UNIQUE and FOREIGN KEY constraints are not supported.
        """
        from rhosocial.activerecord.backend.expression.statements.ddl_table import (
            TableConstraintType,
        )
        parts = []
        params: List[Any] = []

        if t_const.constraint_type == TableConstraintType.PRIMARY_KEY:
            if t_const.columns:
                cols_str = ', '.join(self.format_identifier(c) for c in t_const.columns)
                parts.append(f"PRIMARY KEY ({cols_str})")
        elif t_const.constraint_type == TableConstraintType.UNIQUE:
            raise UnsupportedFeatureError(
                self.name, "UNIQUE table constraint",
                suggestion="ClickHouse does not support UNIQUE constraints."
            )
        elif t_const.constraint_type == TableConstraintType.FOREIGN_KEY:
            raise UnsupportedFeatureError(
                self.name, "FOREIGN KEY constraint",
                suggestion="ClickHouse does not support FOREIGN KEY constraints."
            )

        return ' '.join(parts), tuple(params)

    def format_storage_options(self, storage_options: Dict[str, Any]) -> str:
        """
        Format storage options for ClickHouse.

        Args:
            storage_options: Dict with keys like 'ENGINE', 'ORDER BY', 'PARTITION BY'

        Returns:
            Formatted storage options string (e.g., "ENGINE = MergeTree() ORDER BY id")
        """
        parts = []
        for key, value in storage_options.items():
            if isinstance(value, str):
                parts.append(f"{key} = {value}")
            else:
                parts.append(f"{key} = {value}")
        return ' '.join(parts)

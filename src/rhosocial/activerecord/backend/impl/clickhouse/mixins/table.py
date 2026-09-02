# src/rhosocial/activerecord/backend/impl/clickhouse/mixins/table.py
from typing import Any, Dict, List, TYPE_CHECKING, Tuple
import re

if TYPE_CHECKING:
    from rhosocial.activerecord.backend.expression.statements.ddl_table import CreateTableExpression


class ClickHouseTableMixin:
    """ClickHouse table DDL implementation."""

    @staticmethod
    def _validate_data_type(data_type: str) -> bool:
        """Validate data type string, allowing single quotes for ClickHouse ENUM types."""
        return bool(re.fullmatch(r"[A-Za-z0-9\s\(\),\']+", data_type))

    def supports_table_like_syntax(self) -> bool:
        return True

    def supports_inline_index(self) -> bool:
        return True

    def supports_storage_engine_option(self) -> bool:
        return True

    def supports_charset_option(self) -> bool:
        return True

    def format_create_table_statement(self, expr) -> Tuple[str, tuple]:
        """Format CREATE TABLE statement for ClickHouse."""
        if "like_table" in expr.dialect_options:
            return self.format_create_table_like(expr)


        all_params: List[Any] = []

        parts = ["CREATE TABLE"]
        if expr.temporary:
            parts.append("TEMPORARY")
        if expr.if_not_exists:
            parts.append("IF NOT EXISTS")
        parts.append(expr.table.to_sql()[0])

        column_parts = []
        for col_def in expr.columns:
            col_sql, col_params = self.format_column_definition(col_def)
            column_parts.append(col_sql)
            all_params.extend(col_params)

        for t_const in expr.table_constraints:
            const_sql, const_params = self.format_table_constraint(t_const)
            column_parts.append(const_sql)
            all_params.extend(const_params)

        for idx_def in expr.indexes:
            idx_sql = self.format_inline_index(idx_def)
            column_parts.append(idx_sql)

        parts.append(f"({', '.join(column_parts)})")

        if expr.storage_options:
            storage_sql = self.format_storage_options(expr.storage_options)
            if storage_sql:
                parts.append(storage_sql)

        if "comment" in expr.dialect_options:
            escaped_comment = self._escape_sql_string(expr.dialect_options["comment"])
            parts.append(f"COMMENT '{escaped_comment}'")

        return " ".join(parts), tuple(all_params)

    def format_create_table_like(self, expr: "CreateTableExpression") -> Tuple[str, tuple]:
        """Format CREATE TABLE ... LIKE statement."""
        like_table = expr.dialect_options["like_table"]

        parts = ["CREATE TABLE"]
        if expr.temporary:
            parts.append("TEMPORARY")
        if expr.if_not_exists:
            parts.append("IF NOT EXISTS")
        parts.append(expr.table.to_sql()[0])

        if isinstance(like_table, tuple):
            schema, table = like_table
            like_table_str = f"{self.format_identifier(schema)}.{self.format_identifier(table)}"
        else:
            like_table_str = self.format_identifier(like_table)

        parts.append(f"LIKE {like_table_str}")
        return " ".join(parts), ()

    def format_column_definition(self, col_def, ColumnConstraintType=None) -> Tuple[str, List[Any]]:
        """Format a single column definition with ClickHouse-specific syntax."""
        if ColumnConstraintType is None:
            from rhosocial.activerecord.backend.expression.statements import ColumnConstraintType
        type_sql, type_params = col_def.data_type.to_sql(self)
        parts = [self.format_identifier(col_def.name), type_sql]
        params: List[Any] = list(type_params)

        for constraint in col_def.constraints:
            suffix, cp = self.format_column_constraint(constraint)
            constraint_text = suffix.strip()
            if constraint_text:
                parts.append(constraint_text)
            params.extend(list(cp))
            if constraint.is_auto_increment:
                from rhosocial.activerecord.backend.dialect.exceptions import UnsupportedFeatureError
                raise UnsupportedFeatureError(
                    self.name, "AUTO_INCREMENT column",
                    suggestion="ClickHouse does not support AUTO_INCREMENT; use UUID or an explicit value."
                )

        if col_def.comment:
            escaped_comment = self._escape_sql_string(col_def.comment)
            parts.append(f"COMMENT '{escaped_comment}'")

        return " ".join(parts), params

    def format_table_constraint(self, t_const, TableConstraintType=None) -> Tuple[str, List[Any]]:
        """Format a table-level constraint."""
        if TableConstraintType is None:
            from rhosocial.activerecord.backend.expression.statements import TableConstraintType
        parts = []
        params: List[Any] = []

        if t_const.name:
            parts.append(f"CONSTRAINT {self.format_identifier(t_const.name)}")

        if t_const.constraint_type == TableConstraintType.PRIMARY_KEY:
            if t_const.columns:
                cols_str = ", ".join(self.format_identifier(c) for c in t_const.columns)
                parts.append(f"PRIMARY KEY ({cols_str})")
        elif t_const.constraint_type == TableConstraintType.UNIQUE:
            from rhosocial.activerecord.backend.dialect.exceptions import UnsupportedFeatureError
            raise UnsupportedFeatureError(
                self.name, "UNIQUE table constraint",
                suggestion="ClickHouse does not support UNIQUE constraints."
            )
        elif t_const.constraint_type == TableConstraintType.FOREIGN_KEY:
            from rhosocial.activerecord.backend.dialect.exceptions import UnsupportedFeatureError
            raise UnsupportedFeatureError(
                self.name, "FOREIGN KEY constraint",
                suggestion="ClickHouse does not support FOREIGN KEY constraints."
            )

        return " ".join(parts), params

    def format_inline_index(self, idx_def) -> str:
        """Format an inline INDEX definition within CREATE TABLE (ClickHouse-specific)."""
        parts = []
        if idx_def.unique:
            from rhosocial.activerecord.backend.dialect.exceptions import UnsupportedFeatureError
            raise UnsupportedFeatureError(
                self.name, "UNIQUE index",
                suggestion="ClickHouse cannot enforce unique indexes."
            )
        parts.append("INDEX")
        parts.append(self.format_identifier(idx_def.name))
        cols_str = ", ".join(self.format_identifier(c) for c in idx_def.columns)
        parts.append(f"({cols_str})")
        # ClickHouse requires TYPE clause for inline indexes; default to minmax
        idx_type = idx_def.type if idx_def.type else "minmax"
        parts.append(f"TYPE {idx_type}")
        return " ".join(parts)

    def format_storage_options(self, storage_options: Dict[str, Any]) -> str:
        """Format ClickHouse table storage options.

        ClickHouse syntax: ``ENGINE = MergeTree()``, ``ORDER BY id``,
        ``PARTITION BY toYYYYMM(created_at)`` — values are NOT quoted.
        """
        parts = []
        for key, value in storage_options.items():
            parts.append(f"{key} = {value}")
        return " ".join(parts)


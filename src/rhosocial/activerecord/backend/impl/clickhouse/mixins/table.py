# src/rhosocial/activerecord/backend/impl/clickhouse/mixins/table.py
from typing import Any, List, Tuple, TYPE_CHECKING
import re

if TYPE_CHECKING:
    from rhosocial.activerecord.backend.expression.statements.ddl_table import (
        ColumnDefinition,
        CreateTableExpression,
        CreateTableLikeExpression,
        StorageOptionsExpression,
        IndexDefinition,
        TableConstraint,
    )


class ClickHouseTableMixin:
    """ClickHouse table DDL implementation."""

    @staticmethod
    def _validate_data_type(data_type: str) -> bool:
        """Validate data type string, allowing single quotes for ClickHouse ENUM types."""
        return bool(re.fullmatch(r"[A-Za-z0-9\s\(\),\']+", data_type))

    def supports_create_table_like(self) -> bool:
        return True

    def supports_inline_index(self) -> bool:
        return True

    def supports_storage_engine_option(self) -> bool:
        return True

    def supports_charset_option(self) -> bool:
        return True

    def format_create_table_statement(self, expr: "CreateTableExpression") -> Tuple[str, tuple]:
        """Format CREATE TABLE statement for ClickHouse."""
        all_params: List[Any] = []

        parts = ["CREATE"]
        if expr.temporary:
            parts.append("TEMPORARY")
        parts.append("TABLE")
        if expr.if_not_exists:
            parts.append("IF NOT EXISTS")
        parts.append(self.format_identifier(expr.table_name))

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
            idx_sql, idx_params = self.format_inline_index(idx_def)
            if idx_sql:
                column_parts.append(idx_sql)

        parts.append(f"({', '.join(column_parts)})")

        if expr.storage_options:
            storage_sql, storage_params = self._format_table_storage_options(expr.storage_options)
            if storage_sql:
                parts.append(storage_sql)
                all_params.extend(storage_params)

        if "comment" in expr.dialect_options:
            escaped_comment = self._escape_sql_string(expr.dialect_options["comment"])
            parts.append(f"COMMENT '{escaped_comment}'")

        if expr.partition is not None:
            partition_sql, partition_params = expr.partition.to_sql()
            if partition_sql:
                parts.append(partition_sql.strip())
                all_params.extend(partition_params)

        return " ".join(parts), tuple(all_params)

    def _format_table_storage_options(self, storage_options: Any) -> Tuple[str, tuple]:
        """Render storage options from either a mapping or a StorageOptionsExpression."""
        if isinstance(storage_options, dict):
            return self.format_table_engine_clauses(storage_options)
        return storage_options.to_sql()

    def format_create_table_like_statement(
        self, expr: "CreateTableLikeExpression"
    ) -> Tuple[str, tuple]:
        """Format ClickHouse ``CREATE TABLE ... AS <source>``.

        ClickHouse has no ``LIKE`` keyword.  Copying a table's structure uses
        ``CREATE TABLE target AS source`` (or ``CREATE TABLE target CLONE AS
        source`` to also copy data).  The capability probe
        :meth:`supports_create_table_like` still reports ``True`` because the
        underlying capability exists; only the keyword differs.
        """
        from rhosocial.activerecord.backend.dialect.exceptions import UnsupportedFeatureError

        if not self.supports_create_table_like():
            raise UnsupportedFeatureError(self.name, "CREATE TABLE ... AS <source>")

        parts = ["CREATE"]
        if expr.temporary:
            parts.append("TEMPORARY")
        parts.append("TABLE")
        if expr.if_not_exists:
            parts.append("IF NOT EXISTS")
        parts.append(expr.table.to_sql()[0])
        parts.append(f"AS {expr.like_table.to_sql()[0]}")
        return " ".join(parts), ()

    def format_column_definition(self, col_def: "ColumnDefinition") -> Tuple[str, tuple]:
        """Format a single column definition with ClickHouse-specific syntax."""
        type_sql, type_params = col_def.data_type.to_sql()
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

        return " ".join(parts), tuple(params)

    def format_table_constraint(self, t_const: "TableConstraint") -> Tuple[str, tuple]:
        """Format a table-level constraint."""
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

        return " ".join(parts), tuple(params)

    def format_inline_index(self, idx_def: "IndexDefinition") -> Tuple[str, tuple]:
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
        return " ".join(parts), ()

    def format_storage_options(self, expr: "StorageOptionsExpression") -> Tuple[str, tuple]:
        """Format ClickHouse table storage options.

        Delegates to ``format_table_engine_clauses`` using the expression's
        options mapping.  Values are rendered verbatim (not quoted) because
        ClickHouse storage option values are SQL fragments (engine names,
        column lists, etc.).
        """
        return self.format_table_engine_clauses(expr.options)

    def supports_if_not_exists_table(self) -> bool:
        """Whether CREATE TABLE IF NOT EXISTS is supported."""
        return True

    def supports_if_exists_table(self) -> bool:
        """Whether DROP TABLE IF EXISTS is supported."""
        return True

    def supports_temporary_table(self) -> bool:
        """Whether CREATE TEMPORARY TABLE is supported."""
        return True

    def supports_rename_table(self) -> bool:
        """Whether RENAME TABLE is supported."""
        return True

    def supports_rename_column(self) -> bool:
        """Whether RENAME COLUMN is supported."""
        return True

    def supports_ilike(self) -> bool:
        """ClickHouse supports ILIKE operator."""
        return True


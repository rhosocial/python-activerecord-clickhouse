# src/rhosocial/activerecord/backend/impl/clickhouse/mixins/dml.py
from typing import Any, List, Tuple, TYPE_CHECKING

from rhosocial.activerecord.backend.dialect.exceptions import UnsupportedFeatureError

if TYPE_CHECKING:
    from rhosocial.activerecord.backend.expression.statements import InsertExpression


class ClickHouseDMLOperationMixin:
    """ClickHouse DML operations mixin.

    ClickHouse does not support INSERT IGNORE, REPLACE INTO, LOAD DATA,
    or ON DUPLICATE KEY UPDATE. All supports_* methods return False and
    format methods raise UnsupportedFeatureError.
    """

    def supports_insert_ignore(self) -> bool:
        return False

    def supports_replace_into(self) -> bool:
        return False

    def supports_load_data(self) -> bool:
        return False

    def format_load_data_statement(self, expr: Any) -> Tuple[str, tuple]:
        raise UnsupportedFeatureError(
            self.name, "LOAD DATA",
            suggestion="ClickHouse does not support LOAD DATA INFILE; use INSERT or clickhouse-client --query."
        )

    def format_on_conflict_clause(self, expr: Any) -> Tuple[str, tuple]:
        raise UnsupportedFeatureError(
            self.name, "ON DUPLICATE KEY UPDATE",
            suggestion=(
                "ClickHouse does not support ON DUPLICATE KEY UPDATE; "
                "use INSERT with ReplacingMergeTree or other merge mechanisms."
            ),
        )

    def format_insert_statement(self, expr: "InsertExpression") -> Tuple[str, tuple]:
        """Format a ClickHouse INSERT statement.

        ClickHouse does not support INSERT IGNORE / REPLACE INTO / ON CONFLICT;
        those dialect options raise UnsupportedFeatureError. INSERT ... RETURNING
        is supported.
        """
        if self.strict_validation:
            expr.validate(strict=True)

        if expr.dialect_options.get("replace", False):
            raise UnsupportedFeatureError(
                self.name, "REPLACE INTO",
                suggestion="ClickHouse does not support REPLACE INTO."
            )
        if expr.dialect_options.get("ignore", False):
            raise UnsupportedFeatureError(
                self.name, "INSERT IGNORE",
                suggestion="ClickHouse does not support INSERT IGNORE."
            )
        if expr.on_conflict:
            raise UnsupportedFeatureError(
                self.name, "ON CONFLICT / ON DUPLICATE KEY",
                suggestion="ClickHouse does not support upsert conflict clauses."
            )

        all_params: List[Any] = []
        table_sql, table_params = expr.into.to_sql()
        all_params.extend(table_params)

        parts = ["INSERT INTO", table_sql]

        if expr.columns:
            columns_sql = "(" + ", ".join([self.format_identifier(c) for c in expr.columns]) + ")"
            parts.append(columns_sql)

        from rhosocial.activerecord.backend.expression.statements import (
            DefaultValuesSource,
            SelectSource,
            ValuesSource,
        )

        if isinstance(expr.source, DefaultValuesSource):
            parts.append("DEFAULT VALUES")
        elif isinstance(expr.source, ValuesSource):
            all_rows_sql = []
            for row in expr.source.values_list:
                row_sql, row_params = [], []
                for val in row:
                    s, p = val.to_sql()
                    row_sql.append(s)
                    row_params.extend(p)
                all_rows_sql.append(f"({', '.join(row_sql)})")
                all_params.extend(row_params)
            parts.append("VALUES " + ", ".join(all_rows_sql))
        elif isinstance(expr.source, SelectSource):
            s_sql, s_params = expr.source.select_query.to_sql()
            parts.append(s_sql)
            all_params.extend(s_params)

        sql = " ".join(parts)

        if expr.returning:
            returning_sql, returning_params = self.format_returning_clause(expr.returning)
            sql += f" {returning_sql}"
            all_params.extend(returning_params)

        return sql, tuple(all_params)
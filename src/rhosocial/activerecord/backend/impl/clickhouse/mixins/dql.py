# src/rhosocial/activerecord/backend/impl/clickhouse/mixins/dql.py
from typing import Any, List, Optional, Tuple, TYPE_CHECKING

if TYPE_CHECKING:
    from rhosocial.activerecord.backend.expression.core import Column


class ClickHouseDQLMixin:
    """ClickHouse DQL (Data Query Language) formatting."""

    def supports_fetch_with_ties(self) -> bool:
        """ClickHouse does not support FETCH ... WITH TIES."""
        return False

    def supports_nulls_first_last(self) -> bool:
        """ClickHouse does not support explicit NULLS FIRST/LAST ordering."""
        return False

    def format_column(self, expr: "Column") -> Tuple[str, tuple]:
        """Format column reference for ClickHouse.

        ClickHouse uses database-qualified references (db.table.column) rather
        than schema-qualified ones, so schema_name is silently ignored
        here. Database qualification is handled separately through
        cross-database query support.
        """
        if expr.table:
            col_sql = f"{self.format_identifier(expr.table, expr.table_need_quote)}.{self.format_identifier(expr.name, expr.name_need_quote)}"
        else:
            col_sql = self.format_identifier(expr.name, expr.name_need_quote)

        if expr.alias:
            col_sql = f"{col_sql} AS {self.format_identifier(expr.alias, expr.alias_need_quote)}"

        return col_sql, ()

    def format_limit_offset(
        self, limit: Optional[int] = None, offset: Optional[int] = None
    ) -> Tuple[Optional[str], List[Any]]:
        """
        Format LIMIT and OFFSET clause for ClickHouse.

        ClickHouse requires LIMIT when using OFFSET.
        """
        params = []
        sql_parts = []

        if limit is not None:
            sql_parts.append(f"LIMIT {self.p()}")
            params.append(limit)

        if offset is not None:
            if limit is None:
                sql_parts.append(f"LIMIT {self.p()}")
                params.append(18446744073709551615)  # ClickHouse maximum value for BIGINT UNSIGNED
            sql_parts.append(f"OFFSET {self.p()}")
            params.append(offset)

        if not sql_parts:
            return None, []

        return " ".join(sql_parts), params

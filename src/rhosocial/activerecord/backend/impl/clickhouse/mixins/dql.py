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
        from rhosocial.activerecord.backend.dialect.protocols import SchemaSupport

        if isinstance(self, SchemaSupport):
            self.validate_schema_name(expr)

        if expr.schema_name and not expr.table:
            # A column reference cannot be qualified without a table. The core
            # dialect raises here; ClickHouse qualifies by *database* rather
            # than schema, so a schema on a bare column is meaningless rather
            # than dangerous. Warn instead of raising so one model definition
            # can still target both PostgreSQL and ClickHouse.
            _warn_qualification_dropped(self.name, expr, "ClickHouse")
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


def _warn_qualification_dropped(dialect_name: str, expr, label: str) -> None:
    """Warn that a supplied ``schema_name`` cannot be rendered on a bare column."""
    import warnings

    warnings.warn(
        f"{label}: dropping schema_name={expr.schema_name!r} from column "
        f"{expr.name!r} because no table was given; a column reference needs "
        "a table to be qualified",
        UserWarning,
        stacklevel=3,
    )

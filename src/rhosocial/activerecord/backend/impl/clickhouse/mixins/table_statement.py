# src/rhosocial/activerecord/backend/impl/clickhouse/mixins/table_statement.py
from typing import List, TYPE_CHECKING, Tuple

if TYPE_CHECKING:  # pragma: no cover
    from rhosocial.activerecord.backend.impl.clickhouse.expression.table_statement import (
        ClickHouseTableExpression,
        ClickHouseValuesExpression,
    )


def _format_table_limit(parts: List[str], order_by, limit, offset, format_identifier):
    """Append ORDER BY / LIMIT / OFFSET to a TABLE / VALUES statement."""
    if order_by:
        cols = ", ".join(format_identifier(c) for c in order_by)
        parts.append(f"ORDER BY {cols}")
    if limit is not None:
        parts.append(f"LIMIT {int(limit)}")
    if offset is not None:
        parts.append(f"OFFSET {int(offset)}")


class ClickHouseTableStatementMixin:
    """ClickHouse TABLE statement and VALUES constructor support.

    ``TABLE table`` (8.0.19+) is a shortcut for ``SELECT * FROM table``.
    ``VALUES ROW(...), ...`` (8.0.19+) is a table value constructor.
    """

    def supports_table_statement(self) -> bool:
        """ClickHouse 8.0.19+ supports the TABLE statement."""
        return getattr(self, "version", None) is not None and self.version >= (8, 0, 19)

    def supports_values_table_constructor(self) -> bool:
        """ClickHouse 8.0.19+ supports VALUES as a table value constructor."""
        return getattr(self, "version", None) is not None and self.version >= (8, 0, 19)

    def format_table_statement(self, expr: "ClickHouseTableExpression") -> Tuple[str, tuple]:
        """Format ``TABLE <table> [ORDER BY ...] [LIMIT ...]``."""
        expr.validate(strict=self.strict_validation)
        parts = ["TABLE", self.format_identifier(expr.table_name)]
        _format_table_limit(parts, expr.order_by, expr.limit, expr.offset, self.format_identifier)
        return " ".join(parts), ()

    def format_values_statement(self, expr: "ClickHouseValuesExpression") -> Tuple[str, tuple]:
        """Format ``VALUES ROW(...), ... [ORDER BY ...] [LIMIT ...]``."""
        expr.validate(strict=self.strict_validation)
        params = []
        row_parts = []
        for row in expr.rows:
            cell_parts = []
            for value in row:
                if hasattr(value, "to_sql"):
                    sql, p = value.to_sql()
                    cell_parts.append(sql)
                    params.extend(p)
                else:
                    cell_parts.append(self.get_parameter_placeholder())
                    params.append(value)
            row_parts.append(f"({', '.join(cell_parts)})")
        parts = ["VALUES", ", ".join(row_parts)]
        _format_table_limit(parts, expr.order_by, expr.limit, expr.offset, self.format_identifier)
        return " ".join(parts), tuple(params)
# src/rhosocial/activerecord/backend/impl/clickhouse/mixins/explain.py
from typing import Tuple, TYPE_CHECKING

if TYPE_CHECKING:
    from rhosocial.activerecord.backend.expression.statements import ExplainExpression


class ClickHouseExplainMixin:
    """ClickHouse EXPLAIN statement support."""

    def supports_explain_analyze(self) -> bool:
        """Whether EXPLAIN ANALYZE is supported.

        Accepted syntax-wise from ClickHouse 26.7; older maintained lines
        (25.8 LTS, 26.3 LTS) reject the ANALYZE keyword.
        """
        return self.version >= (26, 7, 0)

    def supports_explain_format(self, format_type: str) -> bool:
        """Check if specific EXPLAIN format is supported.

        ClickHouse supports TEXT, JSON, TREE, and TABULAR formats.
        """
        format_type_upper = format_type.upper()
        if format_type_upper in ("TEXT", "JSON", "TREE", "TABULAR", "TSV", "TSVRaw", "CSV"):
            return True
        return False

    def format_explain_statement(self, explain_expr: "ExplainExpression") -> tuple:
        """Build the ClickHouse EXPLAIN SQL string and return (sql, params).

        ClickHouse syntax variants:
        - ``EXPLAIN <stmt>``
        - ``EXPLAIN <stmt> FORMAT=TEXT|JSON|TABULAR|TSV|CSV``
        - ``EXPLAIN ANALYZE <stmt>``
        - ``EXPLAIN PIPELINE <stmt>``
        """
        from rhosocial.activerecord.backend.expression.statements import ExplainType

        statement_sql, statement_params = explain_expr.statement.to_sql()
        options = explain_expr.options
        parts = ["EXPLAIN"]

        if options is not None:
            if options.analyze:
                parts.append("ANALYZE")

            if options.format is not None:
                fmt_name = options.format.name if hasattr(options.format, "name") else str(options.format)
                parts.append(f"FORMAT={fmt_name.upper()}")
            elif options.type is not None and options.type == ExplainType.QUERY_PLAN:
                pass

        return f"{' '.join(parts)} {statement_sql}", statement_params

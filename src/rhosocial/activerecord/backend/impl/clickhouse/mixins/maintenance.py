# src/rhosocial/activerecord/backend/impl/clickhouse/mixins/maintenance.py
from typing import TYPE_CHECKING, Tuple

from rhosocial.activerecord.backend.dialect.exceptions import UnsupportedFeatureError

if TYPE_CHECKING:  # pragma: no cover
    pass


def _format_table_name(dialect, table):
    if isinstance(table, tuple):
        schema, name = table
        return f"{dialect.format_identifier(schema)}.{dialect.format_identifier(name)}"
    return dialect.format_identifier(table)


class ClickHouseMaintenanceMixin:
    """ClickHouse whole-table maintenance statement support.

    Implements ANALYZE / CHECK / CHECKSUM / OPTIMIZE / REPAIR TABLE,
    distinct from the partition-level variants in ClickHousePartitionMixin.
    """

    def supports_analyze_table(self) -> bool:
        return True

    def supports_check_table(self) -> bool:
        return True

    def supports_checksum_table(self) -> bool:
        return True

    def supports_optimize_table(self) -> bool:
        return True

    def supports_repair_table(self) -> bool:
        return True

    def format_table_maintenance_statement(self, expr) -> Tuple[str, tuple]:
        """Format a whole-table maintenance statement (analyze/check/...)."""
        expr.validate(strict=self.strict_validation)
        operation = expr.operation
        support_method = f"supports_{operation.lower()}_table"
        if not hasattr(self, support_method) or not getattr(self, support_method)():
            feature = f"{operation} TABLE"
            raise UnsupportedFeatureError(self.name, feature)

        parts = [f"{operation} TABLE"]

        if hasattr(expr, "no_write_to_binlog") and expr.no_write_to_binlog.value:
            parts.append(expr.no_write_to_binlog.value)

        table_parts = [_format_table_name(self, t) for t in expr.tables]
        parts.append(", ".join(table_parts))

        if operation == "CHECK" and getattr(expr, "options", None):
            parts.append(" ".join(option.value for option in expr.options))
        elif operation == "CHECKSUM" and getattr(expr, "option", None):
            parts.append(expr.option.value)
        elif operation == "REPAIR" and getattr(expr, "options", None):
            parts.append(" ".join(option.value for option in expr.options))

        return " ".join(parts), ()
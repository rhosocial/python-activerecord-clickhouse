# src/rhosocial/activerecord/backend/impl/clickhouse/mixins/maintenance.py
from typing import Any, Tuple

from rhosocial.activerecord.backend.dialect.exceptions import UnsupportedFeatureError


def format_table_name(dialect, table):
    """Format a possibly schema-qualified table name."""
    if isinstance(table, tuple):
        schema, name = table
        return f"{dialect.format_identifier(schema)}.{dialect.format_identifier(name)}"
    return dialect.format_identifier(table)


_fmt_table = format_table_name


class ClickHouseMaintenanceMixin:
    """ClickHouse does not support the MySQL whole-table maintenance
    statement set (``ANALYZE`` / ``CHECK`` / ``CHECKSUM`` / ``REPAIR TABLE``).

    ClickHouse provides ``OPTIMIZE TABLE ... FINAL`` natively through the
    table-engine layer (see :class:`ClickHouseTableEngineMixin`), not this
    MySQL-style maintenance mixin. The MySQL ``NO_WRITE_TO_BINLOG`` modifier
    has no ClickHouse equivalent. All methods here fail fast; use
    ``SYSTEM`` commands or the table-engine OPTIMIZE path instead.
    """

    def supports_analyze_table(self) -> bool:
        return False

    def supports_check_table(self) -> bool:
        return False

    def supports_checksum_table(self) -> bool:
        return False

    def supports_optimize_table(self) -> bool:
        return False

    def supports_repair_table(self) -> bool:
        return False

    def format_table_maintenance_statement(self, expr: Any) -> Tuple[str, tuple]:
        raise UnsupportedFeatureError(
            self.name, "MySQL whole-table maintenance (ANALYZE/CHECK/CHECKSUM/REPAIR)",
            suggestion="Use ClickHouse OPTIMIZE TABLE ... FINAL or SYSTEM commands instead.",
        )

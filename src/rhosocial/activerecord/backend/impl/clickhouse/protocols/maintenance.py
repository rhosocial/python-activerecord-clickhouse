# src/rhosocial/activerecord/backend/impl/clickhouse/protocols/maintenance.py
"""ClickHouse whole-table maintenance protocol.

Split out of the former single-module ``clickhouse/protocols.py``; one
concern per module so the protocol surface stays legible.
"""

from typing import Protocol, runtime_checkable, Tuple, TYPE_CHECKING

@runtime_checkable
class ClickHouseMaintenanceSupport(Protocol):
    """ClickHouse whole-table maintenance statements support protocol.

    Feature Source: ClickHouse native

    Covers ANALYZE / CHECK / CHECKSUM / OPTIMIZE / REPAIR TABLE (whole-table,
    distinct from the partition-level variants).

    Official Documentation:
    - Table maintenance: https://dev.clickhouse.com/doc/refman/8.0/en/table-maintenance-sql.html
    """

    def supports_analyze_table(self) -> bool:
        """Whether ANALYZE TABLE is supported."""
        ...

    def supports_check_table(self) -> bool:
        """Whether CHECK TABLE is supported."""
        ...

    def supports_checksum_table(self) -> bool:
        """Whether CHECKSUM TABLE is supported."""
        ...

    def supports_optimize_table(self) -> bool:
        """Whether OPTIMIZE TABLE is supported."""
        ...

    def supports_repair_table(self) -> bool:
        """Whether REPAIR TABLE is supported."""
        ...

    def format_table_maintenance_statement(self, expr) -> Tuple[str, tuple]:
        """Format a whole-table maintenance statement."""
        ...

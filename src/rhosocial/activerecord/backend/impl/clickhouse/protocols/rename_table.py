# src/rhosocial/activerecord/backend/impl/clickhouse/protocols/rename_table.py
"""ClickHouse RENAME TABLE protocol.

Split out of the former single-module ``clickhouse/protocols.py``; one
concern per module so the protocol surface stays legible.
"""

from typing import Protocol, runtime_checkable, Tuple, TYPE_CHECKING

if TYPE_CHECKING:  # pragma: no cover
    from rhosocial.activerecord.backend.impl.clickhouse.expression.rename_table import (
        ClickHouseRenameTableExpression,
    )

@runtime_checkable
class ClickHouseRenameTableSupport(Protocol):
    """ClickHouse RENAME TABLE support protocol.

    Feature Source: ClickHouse 5.0+

    ClickHouse supports atomic multi-table renames in a single statement:

        RENAME TABLE t1 TO t2 [, t3 TO t4, ...]

    Official Documentation:
    - RENAME TABLE: https://dev.clickhouse.com/doc/refman/8.0/en/rename-table.html
    """

    def supports_rename_table(self) -> bool:
        """Whether RENAME TABLE is supported."""
        ...

    def supports_multi_table_rename(self) -> bool:
        """Whether multiple rename pairs in one statement are supported."""
        ...

    def format_rename_table_statement(self, expr: "ClickHouseRenameTableExpression") -> Tuple[str, tuple]:
        """Format a ClickHouse RENAME TABLE statement."""
        ...

# src/rhosocial/activerecord/backend/impl/clickhouse/protocols/modify_column.py
"""ClickHouse MODIFY COLUMN / CHANGE COLUMN protocol.

Split out of the former single-module ``clickhouse/protocols.py``; one
concern per module so the protocol surface stays legible.
"""

from typing import Protocol, runtime_checkable, Tuple, TYPE_CHECKING

if TYPE_CHECKING:  # pragma: no cover
    from rhosocial.activerecord.backend.expression.statements.ddl_alter import (
        ChangeColumn,
        ModifyColumn,
    )

@runtime_checkable
class ClickHouseModifyColumnSupport(Protocol):
    """ClickHouse MODIFY COLUMN and CHANGE COLUMN protocol.

    Feature Source: ClickHouse native (not SQL standard)

    ClickHouse ALTER TABLE features beyond SQL standard:
    - MODIFY COLUMN: Redefine a column with new specification (name unchanged)
    - CHANGE COLUMN: Rename and redefine a column in one operation
    - FIRST/AFTER: Column positioning within the table

    Official Documentation:
    - ALTER TABLE: https://dev.clickhouse.com/doc/refman/8.0/en/alter-table.html

    Version Requirements:
    - MODIFY COLUMN: All ClickHouse versions
    - CHANGE COLUMN: All ClickHouse versions
    """

    def supports_modify_column(self) -> bool:
        """Whether MODIFY COLUMN is supported."""
        ...

    def supports_change_column(self) -> bool:
        """Whether CHANGE COLUMN is supported."""
        ...

    def format_modify_column_action(self, action: "ModifyColumn") -> Tuple[str, tuple]:
        """Format MODIFY COLUMN action for ALTER TABLE.

        Args:
            action: ModifyColumn action instance

        Returns:
            Tuple of (SQL string, parameters tuple)
        """
        ...

    def format_change_column_action(self, action: "ChangeColumn") -> Tuple[str, tuple]:
        """Format CHANGE COLUMN action for ALTER TABLE.

        Args:
            action: ChangeColumn action instance

        Returns:
            Tuple of (SQL string, parameters tuple)
        """
        ...

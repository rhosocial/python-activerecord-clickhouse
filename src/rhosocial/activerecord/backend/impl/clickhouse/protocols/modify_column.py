# src/rhosocial/activerecord/backend/impl/clickhouse/protocols/modify_column.py
"""ClickHouse MODIFY COLUMN / CHANGE COLUMN protocol.

Split out of the former single-module ``clickhouse/protocols.py``; one
concern per module so the protocol surface stays legible.
"""

from typing import Protocol, runtime_checkable, Tuple, TYPE_CHECKING

if TYPE_CHECKING:  # pragma: no cover
    from rhosocial.activerecord.backend.expression.statements import (
        ChangeColumnAction as ChangeColumn,
        ModifyColumnAction as ModifyColumn,
    )

@runtime_checkable
class ClickHouseModifyColumnSupport(Protocol):
    """Column modification surface of the ClickHouse dialect.

    Feature Source: ClickHouse native (not SQL standard)

    ClickHouse's ``ALTER TABLE ... COLUMN`` actions are ``MODIFY COLUMN``
    (type/default/codec/TTL change) and ``RENAME COLUMN name TO new_name``.
    There is no MySQL-style ``CHANGE COLUMN`` that renames and redefines in
    one clause, so the probe for it must answer False and the formatter must
    fail fast. ``FIRST`` / ``AFTER`` is an ``ADD COLUMN`` position clause; it
    is not part of the portable ``ModifyColumnAction`` rendering.

    Official documentation:
    https://clickhouse.com/docs/sql-reference/statements/alter/column

    Version Requirements:
    - MODIFY COLUMN: available on all supported ClickHouse versions
    - CHANGE COLUMN: does not exist in ClickHouse
    """

    def supports_modify_column(self) -> bool:
        """Whether MODIFY COLUMN is supported."""
        ...

    def supports_change_column(self) -> bool:
        """Whether CHANGE COLUMN is supported (False in ClickHouse)."""
        ...

    def format_modify_column_action(self, expr: "ModifyColumn") -> Tuple[str, tuple]:
        """Format MODIFY COLUMN action for ALTER TABLE.

        Args:
            expr: ModifyColumn action instance

        Returns:
            Tuple of (SQL string, parameters tuple)
        """
        ...

    def format_change_column_action(self, expr: "ChangeColumn") -> Tuple[str, tuple]:
        """Fail fast: ClickHouse has no CHANGE COLUMN clause.

        Args:
            expr: ChangeColumn action instance

        Returns:
            Never returns; raises UnsupportedFeatureError.
        """
        ...

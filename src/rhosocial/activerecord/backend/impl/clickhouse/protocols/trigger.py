# src/rhosocial/activerecord/backend/impl/clickhouse/protocols/trigger.py
"""ClickHouse trigger DDL protocol.

Split out of the former single-module ``clickhouse/protocols.py``; one
concern per module so the protocol surface stays legible.
"""

from typing import Protocol, runtime_checkable, Tuple, TYPE_CHECKING

if TYPE_CHECKING:  # pragma: no cover
    from rhosocial.activerecord.backend.expression.statements.ddl_trigger import (
        CreateTriggerExpression,
        DropTriggerExpression,
    )

@runtime_checkable
class ClickHouseTriggerSupport(Protocol):
    """ClickHouse trigger DDL protocol.

    Feature Source: Native support (no extension required)

    ClickHouse triggers:
    - BEFORE/AFTER: Timing
    - INSERT/UPDATE/DELETE: Event
    - FOR EACH ROW: Level (only row-level triggers supported)
    - NEW/OLD: Row references

    Official Documentation:
    - CREATE TRIGGER: https://dev.clickhouse.com/doc/refman/8.0/en/create-trigger.html

    Version Requirements:
    - Triggers: ClickHouse 5.0.2+
    - Trigger IF EXISTS: ClickHouse 8.0.4+
    """

    def supports_trigger(self) -> bool:
        """Whether triggers are supported."""
        ...

    def supports_trigger_if_not_exists(self) -> bool:
        """Whether CREATE TRIGGER IF NOT EXISTS is supported (ClickHouse 8.0.4+)."""
        ...

    def supports_instead_of_trigger(self) -> bool:
        """Whether INSTEAD OF triggers are supported.

        ClickHouse does NOT support INSTEAD OF triggers (only BEFORE/AFTER).
        This method always returns False for ClickHouse.
        """
        ...

    def supports_statement_trigger(self) -> bool:
        """Whether statement-level triggers are supported.

        ClickHouse only supports row-level triggers (FOR EACH ROW).
        This method always returns False for ClickHouse.
        """
        ...

    def supports_trigger_referencing(self) -> bool:
        """Whether trigger referencing (NEW/OLD) is supported.

        ClickHouse supports NEW and OLD row references in triggers.
        """
        ...

    def supports_trigger_when(self) -> bool:
        """Whether WHEN condition on triggers is supported.

        ClickHouse does NOT support WHEN condition on triggers.
        This method always returns False for ClickHouse.
        """
        ...

    def format_create_trigger_statement(self, expr: "CreateTriggerExpression") -> Tuple[str, tuple]:
        """Format CREATE TRIGGER statement.

        Args:
            expr: CreateTriggerExpression instance

        Returns:
            Tuple of (SQL string, parameters tuple)
        """
        ...

    def format_drop_trigger_statement(self, expr: "DropTriggerExpression") -> Tuple[str, tuple]:
        """Format DROP TRIGGER statement.

        Args:
            expr: DropTriggerExpression instance

        Returns:
            Tuple of (SQL string, parameters tuple)
        """
        ...

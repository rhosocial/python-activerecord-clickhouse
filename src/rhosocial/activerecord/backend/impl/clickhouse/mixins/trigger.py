# src/rhosocial/activerecord/backend/impl/clickhouse/mixins/trigger.py
from typing import TYPE_CHECKING, Tuple

if TYPE_CHECKING:
    from rhosocial.activerecord.backend.expression.statements.ddl_trigger import (
        CreateTriggerExpression,
        DropTriggerExpression,
    )


class ClickHouseTriggerMixin:
    """ClickHouse trigger DDL implementation."""

    def supports_trigger(self) -> bool:
        """ClickHouse supports triggers since 5.0.2."""
        return self.version >= (5, 0, 2)

    def supports_instead_of_trigger(self) -> bool:
        """ClickHouse does NOT support INSTEAD OF triggers."""
        return False

    def supports_statement_trigger(self) -> bool:
        """ClickHouse does NOT support FOR EACH STATEMENT triggers."""
        return False

    def supports_trigger_referencing(self) -> bool:
        """ClickHouse does NOT support REFERENCING clause."""
        return False

    def supports_trigger_when(self) -> bool:
        """ClickHouse does NOT support WHEN condition."""
        return False

    def supports_trigger_if_not_exists(self) -> bool:
        """ClickHouse 5.7+ supports IF NOT EXISTS."""
        return self.version >= (5, 7, 0)

    def format_create_trigger_statement(self, expr: "CreateTriggerExpression") -> Tuple[str, tuple]:
        """Format CREATE TRIGGER statement (ClickHouse syntax)."""
        from rhosocial.activerecord.backend.dialect.exceptions import UnsupportedFeatureError

        if not self.supports_trigger():
            raise UnsupportedFeatureError(self.name, "triggers")

        if expr.timing.value == "INSTEAD OF":
            raise UnsupportedFeatureError(self.name, "INSTEAD OF triggers (ClickHouse does not support this feature)")

        if expr.level and expr.level.value == "FOR EACH STATEMENT":
            raise UnsupportedFeatureError(self.name, "FOR EACH STATEMENT triggers (ClickHouse only supports FOR EACH ROW)")

        if expr.condition:
            raise UnsupportedFeatureError(self.name, "WHEN condition in triggers (ClickHouse does not support this feature)")

        if expr.referencing:
            raise UnsupportedFeatureError(
                self.name, "REFERENCING clause in triggers (ClickHouse does not support this feature)"
            )

        if len(expr.events) > 1:
            raise UnsupportedFeatureError(self.name, "multiple trigger events (ClickHouse only supports single event)")

        if expr.update_columns:
            raise UnsupportedFeatureError(self.name, "UPDATE OF column_list (ClickHouse does not support this syntax)")

        parts = ["CREATE TRIGGER"]

        if expr.if_not_exists and self.supports_trigger_if_not_exists():
            parts.append("IF NOT EXISTS")

        parts.append(self.format_identifier(expr.trigger_name))
        parts.append(expr.timing.value)

        if expr.events:
            parts.append(expr.events[0].value)

        parts.append("ON")
        parts.append(self.format_identifier(expr.table_name))
        parts.append("FOR EACH ROW")

        if expr.function_name:
            parts.append("CALL")
            parts.append(self.format_identifier(expr.function_name))

        return " ".join(parts), ()

    def format_drop_trigger_statement(self, expr: "DropTriggerExpression") -> Tuple[str, tuple]:
        """Format DROP TRIGGER statement (ClickHouse syntax)."""
        from rhosocial.activerecord.backend.dialect.exceptions import UnsupportedFeatureError

        if not self.supports_trigger():
            raise UnsupportedFeatureError(self.name, "triggers")

        parts = ["DROP TRIGGER"]

        if expr.if_exists:
            parts.append("IF EXISTS")

        parts.append(self.format_identifier(expr.trigger_name))

        return " ".join(parts), ()

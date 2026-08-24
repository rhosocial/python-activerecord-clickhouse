# src/rhosocial/activerecord/backend/impl/clickhouse/mixins/trigger.py
from typing import Any, Tuple

from rhosocial.activerecord.backend.dialect.exceptions import UnsupportedFeatureError


class ClickHouseTriggerMixin:
    """ClickHouse does not support triggers.

    All ``supports_*`` methods return ``False`` and ``format_*`` methods raise
    :class:`UnsupportedFeatureError`. ClickHouse has no trigger subsystem;
    the trigger-related capability is also overridden inline in
    :class:`ClickHouseDialect`.
    """

    def supports_trigger(self) -> bool:
        return False

    def supports_instead_of_trigger(self) -> bool:
        return False

    def supports_statement_trigger(self) -> bool:
        return False

    def supports_trigger_referencing(self) -> bool:
        return False

    def supports_trigger_when(self) -> bool:
        return False

    def supports_trigger_if_not_exists(self) -> bool:
        return False

    def format_create_trigger_statement(self, expr: Any) -> Tuple[str, tuple]:
        raise UnsupportedFeatureError(
            self.name, "triggers",
            suggestion="ClickHouse does not support triggers.",
        )

    def format_drop_trigger_statement(self, expr: Any) -> Tuple[str, tuple]:
        raise UnsupportedFeatureError(
            self.name, "triggers",
            suggestion="ClickHouse does not support triggers.",
        )

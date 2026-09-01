# src/rhosocial/activerecord/backend/impl/clickhouse/mixins/routine.py
from typing import Any, Tuple

from rhosocial.activerecord.backend.dialect.mixins.routine import RoutineSupportMixin
from rhosocial.activerecord.backend.dialect.exceptions import UnsupportedFeatureError




class ClickHouseRoutineMixin(RoutineSupportMixin):
    """ClickHouse does not support SQL stored procedures or stored functions.

    ClickHouse has no ``CREATE PROCEDURE`` / ``CREATE FUNCTION`` (stored)
    / ``CALL`` SQL-standard routine subsystem. ``CALL`` is not supported.
    All methods fail fast. (ClickHouse user-defined functions are created
    via ``CREATE FUNCTION ... AS`` SQL UDFs or executable UDFs, handled
    separately and not by this MySQL-style routine mixin.)
    """

    def supports_procedure(self) -> bool:
        return False

    def supports_stored_function(self) -> bool:
        return False

    def supports_call(self) -> bool:
        return False

    def format_create_procedure_statement(self, expr: Any) -> Tuple[str, tuple]:
        raise UnsupportedFeatureError(
            self.name, "stored procedures",
            suggestion="ClickHouse has no CREATE PROCEDURE / CALL.",
        )

    def format_drop_procedure_statement(self, expr: Any) -> Tuple[str, tuple]:
        raise UnsupportedFeatureError(
            self.name, "stored procedures",
            suggestion="ClickHouse has no DROP PROCEDURE.",
        )

    def format_create_function_statement(self, expr: Any) -> Tuple[str, tuple]:
        raise UnsupportedFeatureError(
            self.name, "stored functions",
            suggestion="Use ClickHouse CREATE FUNCTION name AS lambda(...) for UDFs.",
        )

    def format_drop_function_statement(self, expr: Any) -> Tuple[str, tuple]:
        raise UnsupportedFeatureError(
            self.name, "stored functions",
            suggestion="Use ClickHouse DROP FUNCTION for UDFs, not this MySQL-style routine mixin.",
        )

    def format_call_statement(self, expr: Any) -> Tuple[str, tuple]:
        raise UnsupportedFeatureError(
            self.name, "CALL",
            suggestion="ClickHouse has no CALL statement / stored procedures.",
        )

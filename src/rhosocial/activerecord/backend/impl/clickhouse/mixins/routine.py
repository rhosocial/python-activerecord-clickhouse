# src/rhosocial/activerecord/backend/impl/clickhouse/mixins/routine.py
from typing import TYPE_CHECKING, Tuple

from rhosocial.activerecord.backend.dialect.exceptions import UnsupportedFeatureError

if TYPE_CHECKING:
    from rhosocial.activerecord.backend.impl.clickhouse.expression.routine import (
        ClickHouseCallStatement,
        ClickHouseCreateFunctionStatement,
        ClickHouseCreateProcedureStatement,
        ClickHouseDropFunctionStatement,
        ClickHouseDropProcedureStatement,
    )


class ClickHouseRoutineMixin:
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

    def format_create_procedure_statement(
        self, expr: "ClickHouseCreateProcedureStatement"
    ) -> Tuple[str, tuple]:
        raise UnsupportedFeatureError(
            self.name,
            "stored procedures",
            suggestion="ClickHouse has no CREATE PROCEDURE / CALL.",
        )

    def format_drop_procedure_statement(
        self, expr: "ClickHouseDropProcedureStatement"
    ) -> Tuple[str, tuple]:
        raise UnsupportedFeatureError(
            self.name,
            "stored procedures",
            suggestion="ClickHouse has no DROP PROCEDURE.",
        )

    def format_create_function_statement(
        self, expr: "ClickHouseCreateFunctionStatement"
    ) -> Tuple[str, tuple]:
        raise UnsupportedFeatureError(
            self.name,
            "stored functions",
            suggestion="Use ClickHouse CREATE FUNCTION name AS lambda(...) for UDFs.",
        )

    def format_drop_function_statement(
        self, expr: "ClickHouseDropFunctionStatement"
    ) -> Tuple[str, tuple]:
        raise UnsupportedFeatureError(
            self.name,
            "stored functions",
            suggestion="Use ClickHouse DROP FUNCTION for UDFs, not this MySQL-style routine mixin.",
        )

    def format_call_statement(self, expr: "ClickHouseCallStatement") -> Tuple[str, tuple]:
        raise UnsupportedFeatureError(
            self.name,
            "CALL",
            suggestion="ClickHouse has no CALL statement / stored procedures.",
        )

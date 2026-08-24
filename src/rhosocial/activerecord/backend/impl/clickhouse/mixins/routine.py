# src/rhosocial/activerecord/backend/impl/clickhouse/mixins/routine.py
from typing import Any, Tuple

from rhosocial.activerecord.backend.dialect.exceptions import UnsupportedFeatureError


def _format_param(dialect, param) -> str:
    """Format a stored-routine parameter definition.

    A param may be a plain string (``IN name TYPE``), a tuple
    ``(mode, name, type)``, or ``(name, type)``.
    """
    if isinstance(param, tuple):
        if len(param) == 3:
            mode, name, type_sql = param
            return f"{mode} {dialect.format_identifier(name)} {type_sql}"
        if len(param) == 2:
            name, type_sql = param
            return f"{dialect.format_identifier(name)} {type_sql}"
        raise ValueError(f"Invalid parameter definition: {param!r}")
    return str(param)


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

# src/rhosocial/activerecord/backend/impl/clickhouse/protocols/routine.py
"""ClickHouse stored routine protocol.

Split out of the former single-module ``clickhouse/protocols.py``; one
concern per module so the protocol surface stays legible.
"""

from typing import Protocol, runtime_checkable, Tuple, TYPE_CHECKING

if TYPE_CHECKING:  # pragma: no cover
    from rhosocial.activerecord.backend.impl.clickhouse.expression.routine import (
        ClickHouseCallExpression,
        ClickHouseCreateFunctionExpression,
        ClickHouseCreateProcedureExpression,
        ClickHouseDropFunctionExpression,
        ClickHouseDropProcedureExpression,
    )

@runtime_checkable
class ClickHouseRoutineSupport(Protocol):
    """ClickHouse stored routine support protocol.

    Feature Source: ClickHouse 5.0+

    Covers CREATE/DROP PROCEDURE, CREATE/DROP FUNCTION (stored), and CALL.

    Official Documentation:
    - Stored routines: https://dev.clickhouse.com/doc/refman/8.0/en/stored-programs-views.html
    - CALL: https://dev.clickhouse.com/doc/refman/8.0/en/call.html
    """

    def supports_procedure(self) -> bool:
        """Whether stored procedures are supported."""
        ...

    def supports_stored_function(self) -> bool:
        """Whether stored functions are supported."""
        ...

    def supports_call(self) -> bool:
        """Whether CALL is supported."""
        ...

    def format_create_procedure_statement(self, expr: "ClickHouseCreateProcedureExpression") -> Tuple[str, tuple]:
        """Format CREATE PROCEDURE."""
        ...

    def format_drop_procedure_statement(self, expr: "ClickHouseDropProcedureExpression") -> Tuple[str, tuple]:
        """Format DROP PROCEDURE."""
        ...

    def format_create_function_statement(self, expr: "ClickHouseCreateFunctionExpression") -> Tuple[str, tuple]:
        """Format CREATE FUNCTION (stored function)."""
        ...

    def format_drop_function_statement(self, expr: "ClickHouseDropFunctionExpression") -> Tuple[str, tuple]:
        """Format DROP FUNCTION."""
        ...

    def format_call_statement(self, expr: "ClickHouseCallExpression") -> Tuple[str, tuple]:
        """Format CALL."""
        ...

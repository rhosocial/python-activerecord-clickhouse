# src/rhosocial/activerecord/backend/impl/clickhouse/expression/routine.py
"""ClickHouse stored routine expressions.

ClickHouse supports:

    CREATE PROCEDURE name ([params]) body
    DROP PROCEDURE [IF EXISTS] name
    CREATE FUNCTION name ([params]) RETURNS type ... (stored function)
    DROP FUNCTION [IF EXISTS] name
    CALL name([args])

Note: ``CREATE FUNCTION ... SONAME 'library.so'`` creates a loadable (UDF)
function and is intentionally NOT represented here because it is an
installation-time administrative action (see admin expressions instead).

The routine is named by a schema object carrying its own ``catalog_name``. There
is no ``(database, name)`` tuple input and no rendering here: the expression
holds the identity and the dialect renders it.
"""

from typing import Any, Optional, Sequence, TYPE_CHECKING

from rhosocial.activerecord.backend.expression.bases import BaseExpression
from rhosocial.activerecord.backend.expression.objects import RoutineObject

if TYPE_CHECKING:  # pragma: no cover
    from rhosocial.activerecord.backend.dialect import SQLDialectBase


class ClickHouseRoutineExpression(BaseExpression):
    """Base class for stored routine DDL / invocation statements.

    Attributes:
        routine: The routine being named -- a :class:`Function` or
            :class:`Procedure` carrying its own ``catalog_name``. The
            expression never renders it; the dialect does, through the
            routine's own ``to_sql()``.
        params: Parameter definitions list.
        body: Routine body SQL text (for CREATE statements).

    Raises:
        TypeError: ``routine`` is not a routine object (see :meth:`validate`).
    """

    def __init__(
        self,
        dialect: "SQLDialectBase",
        routine: RoutineObject,
        *,
        params: Optional[Sequence[Any]] = None,
        body: Optional[str] = None,
    ):
        super().__init__(dialect)
        self.routine: RoutineObject = routine
        self.params: list = list(params or [])
        self.body: Optional[str] = body
        self.validate()

    def validate(self, strict: bool = True) -> None:
        """Validate the routine identity.

        Raises:
            TypeError: ``routine`` is not a routine object. A ``str`` or a
                ``(database, name)`` tuple is refused: both only say *which*
                routine, never *what kind*, and neither can carry the
                database without the caller unpacking it by hand.
        """
        if not strict:
            return
        if not isinstance(self.routine, RoutineObject):
            raise TypeError(
                "routine must be a Function or Procedure object carrying its own "
                f"catalog_name, got {type(self.routine).__name__}"
            )


class ClickHouseCreateProcedureExpression(ClickHouseRoutineExpression):
    """Represent ``CREATE PROCEDURE``."""

    @property
    def format_method(self) -> str:
        return "format_create_procedure_statement"


class ClickHouseDropProcedureExpression(ClickHouseRoutineExpression):
    """Represent ``DROP PROCEDURE [IF EXISTS]``."""

    def __init__(
        self,
        dialect: "SQLDialectBase",
        routine: RoutineObject,
        *,
        if_exists: bool = False,
    ):
        super().__init__(dialect, routine)
        self.if_exists: bool = if_exists

    @property
    def format_method(self) -> str:
        return "format_drop_procedure_statement"


class ClickHouseCreateFunctionExpression(ClickHouseRoutineExpression):
    """Represent ``CREATE FUNCTION`` (stored function)."""

    def __init__(
        self,
        dialect: "SQLDialectBase",
        routine: RoutineObject,
        *,
        returns: str,
        params: Optional[Sequence[Any]] = None,
        body: Optional[str] = None,
        deterministic: bool = False,
    ):
        super().__init__(
            dialect,
            routine,
            params=params,
            body=body,
        )
        self.returns: str = returns
        self.deterministic: bool = deterministic

    @property
    def format_method(self) -> str:
        return "format_create_function_statement"


class ClickHouseDropFunctionExpression(ClickHouseRoutineExpression):
    """Represent ``DROP FUNCTION [IF EXISTS]`` (stored function)."""

    def __init__(
        self,
        dialect: "SQLDialectBase",
        routine: RoutineObject,
        *,
        if_exists: bool = False,
    ):
        super().__init__(dialect, routine)
        self.if_exists: bool = if_exists

    @property
    def format_method(self) -> str:
        return "format_drop_function_statement"


class ClickHouseCallExpression(BaseExpression):
    """Represent ``CALL procedure_name([args])``.

    Attributes:
        routine: The stored procedure being called, carrying its own
            ``catalog_name``.
        args: Positional argument list.

    Raises:
        TypeError: ``routine`` is not a :class:`Procedure` object.
    """

    def __init__(
        self,
        dialect: "SQLDialectBase",
        routine: RoutineObject,
        args: Optional[Sequence[Any]] = None,
    ):
        super().__init__(dialect)
        self.routine: RoutineObject = routine
        self.args: list = list(args or [])
        self.validate()

    def validate(self, strict: bool = True) -> None:
        """Validate the procedure identity.

        Raises:
            TypeError: ``routine`` is not a routine object.
        """
        if not strict:
            return
        if not isinstance(self.routine, RoutineObject):
            raise TypeError(
                "CALL requires a Function or Procedure object carrying its own "
                f"catalog_name, got {type(self.routine).__name__}"
            )

    @property
    def format_method(self) -> str:
        return "format_call_statement"

# src/rhosocial/activerecord/backend/impl/clickhouse/functions/enum_set.py
"""
ClickHouse SET and Enum type function factories.

Functions: find_in_set, elt, field
"""

from typing import Union, Any, TYPE_CHECKING

from rhosocial.activerecord.backend.expression import bases, core

if TYPE_CHECKING:  # pragma: no cover
    from rhosocial.activerecord.backend.dialect import SQLDialectBase
    from .dialect import ClickHouseDialect


def _convert_to_expression(
    dialect: "SQLDialectBase",
    expr: Union[str, "bases.BaseExpression"],
    handle_numeric_literals: bool = True,
) -> "bases.BaseExpression":
    """
    Helper function to convert an input value to an appropriate BaseExpression.

    Args:
        dialect: The SQL dialect instance
        expr: The expression to convert
        handle_numeric_literals: Whether to treat numeric values as literals

    Returns:
        A BaseExpression instance
    """
    if isinstance(expr, bases.BaseExpression):
        return expr
    elif handle_numeric_literals and isinstance(expr, (int, float)):
        return core.Literal(dialect, expr)
    else:
        return core.Column(dialect, expr)


def find_in_set(
    dialect: "ClickHouseDialect",
    value: str,
    set_column: Union[str, "bases.BaseExpression"],
) -> "core.FunctionCall":
    """
    Creates a FIND_IN_SET function call.

    Finds the position of a value in a SET column.

    Args:
        dialect: The ClickHouse dialect instance
        value: Value to find
        set_column: SET column name or expression

    Returns:
        A FunctionCall instance representing FIND_IN_SET

    Version: All ClickHouse versions
    """
    value_expr = core.Literal(dialect, value)
    col_expr = _convert_to_expression(dialect, set_column)
    return core.FunctionCall(dialect, "FIND_IN_SET", value_expr, col_expr)


def elt(
    dialect: "ClickHouseDialect",
    index: int,
    *values: str,
) -> "core.FunctionCall":
    """
    Creates an ELT function call.

    Returns the N-th element from a list of strings.

    Args:
        dialect: The ClickHouse dialect instance
        index: 1-based index of the element to return
        *values: List of string values

    Returns:
        A FunctionCall instance representing ELT

    Version: All ClickHouse versions
    """
    index_expr = core.Literal(dialect, index)
    args = [index_expr]
    for v in values:
        args.append(core.Literal(dialect, v))
    return core.FunctionCall(dialect, "ELT", *args)


def field(
    dialect: "ClickHouseDialect",
    value: Any,
    *values: Any,
) -> "core.FunctionCall":
    """
    Creates a FIELD function call.

    Returns the index (position) of value in the list of values.
    Returns 0 if not found.

    Args:
        dialect: The ClickHouse dialect instance
        value: Value to search for
        *values: List of values to search in

    Returns:
        A FunctionCall instance representing FIELD

    Version: All ClickHouse versions
    """
    value_expr = _convert_to_expression(dialect, value)
    args = [value_expr]
    for v in values:
        args.append(_convert_to_expression(dialect, v))
    return core.FunctionCall(dialect, "FIELD", *args)


__all__ = [
    "find_in_set",
    "elt",
    "field",
]

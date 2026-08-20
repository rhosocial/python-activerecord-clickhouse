# src/rhosocial/activerecord/backend/impl/clickhouse/functions/bitwise.py
"""
ClickHouse Bitwise function factories.

Functions: bit_and, bit_or, bit_xor, bit_count, bit_get_bit,
           bit_shift_left, bit_shift_right

Note: ClickHouse 9.6 does not support BIT_GET_BIT, BIT_SHIFT_LEFT, BIT_SHIFT_RIGHT
as functions. These are implemented using native bitwise operators.

.. warning::
    This module was copied from the MySQL backend template and contains
    MySQL-style SQL functions/show commands. ClickHouse uses different
    function names (e.g. ``JSONExtract*``) and a different SHOW command
    subset. May generate non-ClickHouse SQL; verify before use.
"""

from typing import Union, TYPE_CHECKING

from rhosocial.activerecord.backend.expression import bases, core
from rhosocial.activerecord.backend.expression.operators import BinaryArithmeticExpression

if TYPE_CHECKING:  # pragma: no cover
    from rhosocial.activerecord.backend.dialect import SQLDialectBase
    from .dialect import ClickHouseDialect


def _convert_to_expression(
    dialect: "SQLDialectBase",
    expr: Union[str, int, float, "bases.BaseExpression"],
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


def bit_and(
    dialect: "ClickHouseDialect",
    value: Union[str, int, "bases.BaseExpression"],
    *values: Union[str, int, "bases.BaseExpression"],
) -> "bases.BaseExpression":
    """
    Returns the bitwise AND of values.

    Note: ClickHouse's BIT_AND() is an aggregate function. For scalar bitwise AND,
    this function returns (value & values[0] & values[1] ...).

    Args:
        dialect: The ClickHouse dialect instance
        value: First value
        *values: Additional values to AND

    Returns:
        An expression representing bitwise AND

    Version: ClickHouse 5.0.12+ (aggregate), native operators available in all versions
    """
    result = _convert_to_expression(dialect, value)
    for v in values:
        v_expr = _convert_to_expression(dialect, v)
        result = BinaryArithmeticExpression(dialect, "&", result, v_expr)
    return result


def bit_or(
    dialect: "ClickHouseDialect",
    value: Union[str, int, "bases.BaseExpression"],
    *values: Union[str, int, "bases.BaseExpression"],
) -> "bases.BaseExpression":
    """
    Returns the bitwise OR of values.

    Note: ClickHouse's BIT_OR() is an aggregate function. For scalar bitwise OR,
    this function returns (value | values[0] | values[1] ...).

    Args:
        dialect: The ClickHouse dialect instance
        value: First value
        *values: Additional values to OR

    Returns:
        An expression representing bitwise OR

    Version: ClickHouse 5.0.12+ (aggregate), native operators available in all versions
    """
    result = _convert_to_expression(dialect, value)
    for v in values:
        v_expr = _convert_to_expression(dialect, v)
        result = BinaryArithmeticExpression(dialect, "|", result, v_expr)
    return result


def bit_xor(
    dialect: "ClickHouseDialect",
    value: Union[str, int, "bases.BaseExpression"],
    *values: Union[str, int, "bases.BaseExpression"],
) -> "bases.BaseExpression":
    """
    Returns the bitwise XOR of values.

    Note: ClickHouse's BIT_XOR() is an aggregate function. For scalar bitwise XOR,
    this function returns (value ^ values[0] ^ values[1] ...).

    Args:
        dialect: The ClickHouse dialect instance
        value: First value
        *values: Additional values to XOR

    Returns:
        An expression representing bitwise XOR

    Version: ClickHouse 5.0.12+ (aggregate), native operators available in all versions
    """
    result = _convert_to_expression(dialect, value)
    for v in values:
        v_expr = _convert_to_expression(dialect, v)
        result = BinaryArithmeticExpression(dialect, "^", result, v_expr)
    return result


def bit_count(
    dialect: "ClickHouseDialect",
    value: Union[str, int, "bases.BaseExpression"],
) -> "core.FunctionCall":
    """
    Returns the number of bits set to 1 in the binary representation.

    Args:
        dialect: The ClickHouse dialect instance
        value: Column or expression to count bits

    Returns:
        A FunctionCall instance representing BIT_COUNT(expr)

    Version: ClickHouse 5.0.12+
    """
    value_expr = _convert_to_expression(dialect, value)
    return core.FunctionCall(dialect, "BIT_COUNT", value_expr)


def bit_get_bit(
    dialect: "ClickHouseDialect",
    value: Union[str, int, "bases.BaseExpression"],
    bit: Union[str, int, "bases.BaseExpression"],
) -> "bases.BaseExpression":
    """
    Returns the value of a specific bit (0 or 1).

    Note: ClickHouse does not have a BIT_GET_BIT function in all versions.
    This is implemented as ((value >> bit) & 1).

    Args:
        dialect: The ClickHouse dialect instance
        value: The value to get the bit from
        bit: The bit position (0-indexed)

    Returns:
        An expression representing the bit value (0 or 1)

    Version: Native operators available in all ClickHouse versions
    """
    value_expr = _convert_to_expression(dialect, value)
    bit_expr = _convert_to_expression(dialect, bit)
    # (value >> bit) & 1
    shifted = BinaryArithmeticExpression(dialect, ">>", value_expr, bit_expr)
    return BinaryArithmeticExpression(dialect, "&", shifted, core.Literal(dialect, 1))


def bit_shift_left(
    dialect: "ClickHouseDialect",
    value: Union[str, int, "bases.BaseExpression"],
    count: Union[str, int, "bases.BaseExpression"],
) -> "bases.BaseExpression":
    """
    Returns the value left-shifted by count bits.

    Note: ClickHouse does not have BIT_SHIFT_LEFT function in all versions.
    This is implemented using the native << operator.

    Args:
        dialect: The ClickHouse dialect instance
        value: The value to shift
        count: Number of positions to shift

    Returns:
        An expression representing the left-shifted value

    Version: Native operators available in all ClickHouse versions
    """
    value_expr = _convert_to_expression(dialect, value)
    count_expr = _convert_to_expression(dialect, count)
    return BinaryArithmeticExpression(dialect, "<<", value_expr, count_expr)


def bit_shift_right(
    dialect: "ClickHouseDialect",
    value: Union[str, int, "bases.BaseExpression"],
    count: Union[str, int, "bases.BaseExpression"],
) -> "bases.BaseExpression":
    """
    Returns the value right-shifted by count bits.

    Note: ClickHouse does not have BIT_SHIFT_RIGHT function in all versions.
    This is implemented using the native >> operator.

    Args:
        dialect: The ClickHouse dialect instance
        value: The value to shift
        count: Number of positions to shift

    Returns:
        An expression representing the right-shifted value

    Version: Native operators available in all ClickHouse versions
    """
    value_expr = _convert_to_expression(dialect, value)
    count_expr = _convert_to_expression(dialect, count)
    return BinaryArithmeticExpression(dialect, ">>", value_expr, count_expr)


__all__ = [
    "bit_and",
    "bit_or",
    "bit_xor",
    "bit_count",
    "bit_get_bit",
    "bit_shift_left",
    "bit_shift_right",
]

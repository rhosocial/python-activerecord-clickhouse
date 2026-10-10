# src/rhosocial/activerecord/backend/impl/clickhouse/mixins/trim.py
"""ClickHouse's TRIM spelling: the direction is the function name.

ClickHouse parses the ANSI ``TRIM([LEADING|TRAILING|BOTH] [chars] FROM s)``
form too, but only when the character set is spelled out --
``TRIM(BOTH FROM s)`` (no characters) is a syntax error measured on the public
playground: ``Syntax error: failed at position ... Expected FROM``. The shared
default renderer emits exactly that form for the whitespace case, so it is not
safe here. ClickHouse's own function form takes the characters optionally:

    BOTH     -> ``trimBoth(x[, chars])``   (alias ``trim``)
    LEADING  -> ``trimLeft(x[, chars])``   (alias ``ltrim``)
    TRAILING -> ``trimRight(x[, chars])``  (alias ``rtrim``)

so the mapping is a substitution of the function name plus the operand order
(the target first, the optional character set second). The three names carry
the direction the ANSI keyword carries, which is why no direction operand
survives into the rendered SQL. Everything else about the node -- the operand
parameters in order and the optional alias -- is the default's.

The functions arrived in v20.1.0 (``trimBoth`` / ``trimLeft`` / ``trimRight``);
earlier releases need the ANSI form, and this mixin does not attempt to gate on
the server version because the dialect has no mechanism for it.
"""
from typing import Tuple, TYPE_CHECKING

if TYPE_CHECKING:  # pragma: no cover
    from ...expression.advanced_functions import TrimExpression


class ClickHouseTrimMixin:
    """Mixin rendering the TRIM family as ClickHouse's trimBoth/Left/Right."""

    _TRIM_FUNCTIONS = {"BOTH": "trimBoth", "LEADING": "trimLeft", "TRAILING": "trimRight"}

    def format_trim_expression(self, expr: "TrimExpression") -> Tuple[str, Tuple]:
        """Format a TRIM node in ClickHouse's form.

        Args:
            expr: Trim expression exposing ``expr``, ``chars``, ``direction``
                and an optional ``alias``.

        Returns:
            Tuple of (SQL string, parameters tuple), carrying the operands'
            parameters in order.

        Raises:
            ValueError: ``expr.direction`` is not one of the three the node
                allows.
        """
        target_sql, target_params = expr.expr.to_sql()
        function = self._TRIM_FUNCTIONS.get(expr.direction)
        if function is None:
            raise ValueError(
                f"Unsupported trim direction {expr.direction!r}; expected one of "
                f"{sorted(self._TRIM_FUNCTIONS)}"
            )
        if expr.chars is not None:
            chars_sql, chars_params = expr.chars.to_sql()
            sql = f"{function}({target_sql}, {chars_sql})"
            params = tuple(target_params) + tuple(chars_params)
        else:
            sql = f"{function}({target_sql})"
            params = tuple(target_params)
        if expr.alias:
            sql = f"{sql} AS {self.format_identifier(expr.alias)}"
        return sql, params

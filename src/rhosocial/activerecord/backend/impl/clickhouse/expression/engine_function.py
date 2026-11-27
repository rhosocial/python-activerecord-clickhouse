# src/rhosocial/activerecord/backend/impl/clickhouse/expression/engine_function.py
"""A typed node for ClickHouse's case-sensitive engine functions.

ClickHouse spells several built-ins in camelCase (``groupUniqArray``,
``toTypeName``, ``currentUser``) and matches combinator suffixes against the
name exactly as written. The generic function formatter upper-cases names, so
these calls need a node that preserves the spelling instead of handing raw SQL
text to the driver. The operands remain expression nodes: each renders itself
and binds its own parameters.
"""

from typing import TYPE_CHECKING, Optional, Tuple

from rhosocial.activerecord.backend.expression.bases import SQLValue
from rhosocial.activerecord.backend.expression.mixins import AliasableMixin

if TYPE_CHECKING:
    from rhosocial.activerecord.backend.dialect import SQLDialectBase


class ClickHouseEngineFunctionExpression(AliasableMixin, SQLValue):
    """``name(operand, ...)`` with the engine's own spelling, optionally aliased."""

    def __init__(
        self,
        dialect: "SQLDialectBase",
        name: str,
        *operands,
        alias: Optional[str] = None,
    ) -> None:
        super().__init__(dialect)
        if not isinstance(name, str) or not name.strip():
            raise ValueError("name must be a non-empty string")
        self.name = name
        self.operands: Tuple = operands
        self.alias = alias

    @property
    def format_method(self) -> str:
        return "format_clickhouse_engine_function_expression"


__all__ = ["ClickHouseEngineFunctionExpression"]

# src/rhosocial/activerecord/backend/impl/clickhouse/expression/optimizer_hint.py
"""ClickHouse optimizer hint expressions.

Supports per-statement optimizer hints using the /*+ ... */ syntax,
including SET_VAR hints for controlling optimizer switches like
the hypergraph optimizer (ClickHouse 9.7+).
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import List, TYPE_CHECKING

from rhosocial.activerecord.backend.expression.bases import BaseExpression

if TYPE_CHECKING:
    from rhosocial.activerecord.backend.dialect.base import SQLDialectBase


class OptimizerHintType(Enum):
    """Types of ClickHouse optimizer hints."""

    SET_VAR = "SET_VAR"


@dataclass
class SetVarHint:
    """A SET_VAR optimizer hint."""

    variable: str
    value: str


class ClickHouseOptimizerHintExpression(BaseExpression):
    """Expression for ClickHouse optimizer hints (/*+ ... */ syntax).

    Usage:
        hint = ClickHouseOptimizerHintExpression(dialect, [
            SetVarHint("optimizer_switch", "hypergraph_optimizer=on")
        ])
        sql, params = hint.to_sql()
        # => ("/*+ SET_VAR(optimizer_switch='hypergraph_optimizer=on') */", ())
    """

    def __init__(self, dialect: "SQLDialectBase", hints: List[SetVarHint]):
        super().__init__(dialect)
        self.hints = hints

    def to_sql(self):
        return self.dialect.format_optimizer_hint(self)

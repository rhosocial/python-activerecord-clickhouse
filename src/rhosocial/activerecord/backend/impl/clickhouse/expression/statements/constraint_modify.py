# src/rhosocial/activerecord/backend/impl/clickhouse/expression/statements/constraint_modify.py
"""ClickHouse ``ALTER TABLE ... MODIFY CONSTRAINT`` statement.

ClickHouse redefines an existing ``CHECK`` / ``ASSUME`` constraint in place
with the ``MODIFY`` verb -- measured on 26.7.3.19::

    ALTER TABLE probe_t MODIFY CONSTRAINT ck CHECK c > 100
    -- accepted; system.constraints re-reads expression = 'c > 100'

    ALTER TABLE probe_t MODIFY CONSTRAINT ak ASSUME c > 0
    -- accepted

``ALTER CONSTRAINT`` is a syntax error (``Expected COLUMN``), which is why this
is not routed through the core ``ALTER CONSTRAINT`` vocabulary. Core has no node
for ClickHouse's ``MODIFY CONSTRAINT`` production, so this class is owned by
this backend and never re-exported from core.

The constructor collects parameters and validates nothing; the dialect
formatter owns the kind vocabulary, the probe, the inline-only condition rule
and every refusal.
"""

from __future__ import annotations

from typing import Any, Optional

from rhosocial.activerecord.backend.expression.bases.bases import BaseExpression

__all__ = ["ClickHouseModifyConstraintStatement"]

#: The two constraint kinds ClickHouse's table-constraint grammar accepts.
MODIFY_CONSTRAINT_KINDS = ("CHECK", "ASSUME")


class ClickHouseModifyConstraintStatement(BaseExpression):
    """``ALTER TABLE <t> MODIFY CONSTRAINT <name> CHECK|ASSUME <condition>``.

    Args:
        dialect: The dialect this statement is bound to; ``None`` is accepted
            and the tree can be rendered later through ``to_sql(dialect)``.
        table: Target table name.
        name: Name of the existing constraint to redefine.
        kind: ``"CHECK"`` or ``"ASSUME"``. The formatter validates the word.
        condition: The new condition, as an expression node (core
            ``SQLPredicate`` nodes render inline). A bind-carrying condition is
            refused because DDL has no bind parameters.
        schema: Optional database name, rendered in ClickHouse's catalog slot.
    """

    def __init__(
        self,
        dialect: Optional[Any],
        table: str,
        name: str,
        kind: str,
        condition: Any,
        *,
        schema: Optional[str] = None,
    ):
        super().__init__(dialect)
        self.table = table
        self.name = name
        self.kind = kind
        self.condition = condition
        self.schema = schema

    @property
    def format_method(self) -> str:
        """The dialect formatting method that renders this statement."""
        return "format_clickhouse_modify_constraint_statement"

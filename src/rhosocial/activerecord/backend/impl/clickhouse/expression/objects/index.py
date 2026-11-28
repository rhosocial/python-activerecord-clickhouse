# src/rhosocial/activerecord/backend/impl/clickhouse/expression/objects/index.py
"""ClickHouse data-skipping index definition (the inline ``CREATE TABLE`` node).

The inline form is ``INDEX <name> (<columns>) TYPE <type> GRANULARITY <n>``.
The standalone ``ALTER TABLE ... ADD/DROP INDEX`` statements live in
:mod:`..statements.index`; they deliberately carry their own body fields rather
than reusing this inline-only rendering.

Official reference (data-skipping indexes):
https://clickhouse.com/docs/sql-reference/statements/alter/skipping-index
"""

from __future__ import annotations

from typing import Any, List, Optional

from rhosocial.activerecord.backend.expression.statements.ddl_table import IndexDefinition


__all__ = ["ClickHouseIndexDefinition"]


class ClickHouseIndexDefinition(IndexDefinition):
    """A ClickHouse data-skipping index.

    Rendered inline in CREATE TABLE as
    ``INDEX <name> (<columns>) TYPE <type> GRANULARITY <n>``. Skip-index types
    (``minmax``, ``set``, ``bloom_filter``, ...) and granularity are structural
    ClickHouse concepts, hence a dedicated ``IndexDefinition`` subclass — which
    also lets the ActiveRecord ownership gate recognise it as ClickHouse-owned.
    """

    def __init__(
        self,
        dialect: Any,
        name: str,
        columns: List[str],
        *,
        type: Optional[str] = None,
        granularity: int = 1,
    ):
        super().__init__(
            dialect,
            name=name,
            columns=columns,
            type=type,
        )
        self.granularity = granularity

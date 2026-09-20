# src/rhosocial/activerecord/backend/impl/clickhouse/expression/alter_column.py
"""ClickHouse-specific ALTER TABLE column actions.

ClickHouse's ``ADD COLUMN`` accepts a positional clause that has no generic
equivalent:

* ``AFTER <column>`` — place the new column immediately after ``column``.

It lives on ``ClickHouseAddColumn`` (deriving the generic ``AddColumn``) and
is rendered by the ClickHouse ``format_add_column_action`` override.
ClickHouse does **not** share it with any other backend.
"""

from typing import Optional, TYPE_CHECKING

from rhosocial.activerecord.backend.expression.statements import (
    AddColumn,
    ColumnDefinition,
)

if TYPE_CHECKING:  # pragma: no cover
    from rhosocial.activerecord.backend.dialect import SQLDialectBase


__all__ = [
    "ClickHouseAddColumn",
]


class ClickHouseAddColumn(AddColumn):
    """A ClickHouse ``ADD COLUMN`` action extending the generic one.

    Adds the ClickHouse-only ``after`` positional clause.
    """

    def __init__(
        self,
        dialect: "SQLDialectBase",
        column: ColumnDefinition,
        *,
        if_not_exists: Optional[bool] = None,
        after: Optional[str] = None,
    ):
        super().__init__(dialect, column, if_not_exists=if_not_exists)
        self.after = after

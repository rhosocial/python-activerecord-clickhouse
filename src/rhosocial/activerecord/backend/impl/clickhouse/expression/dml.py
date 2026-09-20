# src/rhosocial/activerecord/backend/impl/clickhouse/expression/dml.py
"""ClickHouse-specific DML expression classes."""

from typing import TYPE_CHECKING

from rhosocial.activerecord.backend.expression.statements import InsertExpression

if TYPE_CHECKING:  # pragma: no cover
    from rhosocial.activerecord.backend.dialect import SQLDialectBase


class ClickHouseInsertExpression(InsertExpression):
    """A ClickHouse INSERT statement extending the generic one.

    ClickHouse does not support REPLACE INTO / INSERT IGNORE, but the generic
    expression previously accepted these flags through ``dialect_options`` so
    that the ClickHouse formatter could reject them explicitly. They are carried
    as typed fields here instead.
    """

    def __init__(
        self,
        dialect: "SQLDialectBase",
        into,
        source,
        columns=None,
        *,
        on_conflict=None,
        returning=None,
        replace: bool = False,
        ignore: bool = False,
    ):
        super().__init__(
            dialect,
            into=into,
            source=source,
            columns=columns,
            on_conflict=on_conflict,
            returning=returning,
        )
        self.replace = replace
        self.ignore = ignore


__all__ = [
    "ClickHouseInsertExpression",
]

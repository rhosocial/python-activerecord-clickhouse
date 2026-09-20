# src/rhosocial/activerecord/backend/impl/clickhouse/expression/column.py
"""ClickHouse-specific column definition expressions.

ClickHouse extends the standard column definition with per-column clauses that
have no generic equivalent:

* ``CODEC(<codec>, ...)`` — column compression codec.
* ``MATERIALIZED <expr>`` — materialized (computed-on-insert) column.
* ``ALIAS <expr>`` — alias column (computed on read).
* ``TTL <expr>`` — per-column time-to-live.

The ``expr`` values are ``BaseExpression`` instances so their dialect is
propagated. These live on ``ClickHouseColumnDefinition`` (deriving the generic
``ColumnDefinition``) and are rendered by the ClickHouse
``format_column_definition`` override; they are declared through
``ClickHouseColumnOptions`` (deriving the generic ``ColumnOptions``).
"""

from typing import Optional, Sequence, TYPE_CHECKING

from rhosocial.activerecord.backend.expression.bases import BaseExpression
from rhosocial.activerecord.backend.expression.statements import ColumnDefinition
from rhosocial.activerecord.base.ddl.options import ColumnOptions

if TYPE_CHECKING:  # pragma: no cover
    from rhosocial.activerecord.backend.dialect import SQLDialectBase


__all__ = [
    "ClickHouseColumnDefinition",
    "ClickHouseColumnOptions",
]


class ClickHouseColumnDefinition(ColumnDefinition):
    """A ClickHouse column definition extending the generic one.

    Adds ClickHouse-only typed attributes: ``codec``, ``materialized``,
    ``alias`` and ``ttl``.
    """

    def __init__(
        self,
        dialect: "SQLDialectBase",
        name: str,
        data_type,
        constraints=None,
        comment: Optional[str] = None,
        generated_expression=None,
        identity: Optional[str] = None,
        identity_start: Optional[int] = None,
        identity_increment: Optional[int] = None,
        identity_clause=None,
        *,
        codec: Optional[Sequence[str]] = None,
        materialized: Optional[BaseExpression] = None,
        alias: Optional[BaseExpression] = None,
        ttl: Optional[BaseExpression] = None,
    ):
        super().__init__(
            dialect,
            name,
            data_type,
            constraints=constraints,
            comment=comment,
            generated_expression=generated_expression,
            identity=identity,
            identity_start=identity_start,
            identity_increment=identity_increment,
            identity_clause=identity_clause,
        )
        if materialized is not None and not isinstance(materialized, BaseExpression):
            raise TypeError("materialized must be a BaseExpression")
        if alias is not None and not isinstance(alias, BaseExpression):
            raise TypeError("alias must be a BaseExpression")
        if ttl is not None and not isinstance(ttl, BaseExpression):
            raise TypeError("ttl must be a BaseExpression")
        self.codec = list(codec) if codec else None
        self.materialized = materialized
        self.alias = alias
        self.ttl = ttl


class ClickHouseColumnOptions(ColumnOptions):
    """ClickHouse per-column options declaration."""

    def __init__(
        self,
        *,
        identity_start: Optional[int] = None,
        identity_increment: Optional[int] = None,
        codec: Optional[Sequence[str]] = None,
        materialized: Optional[BaseExpression] = None,
        alias: Optional[BaseExpression] = None,
        ttl: Optional[BaseExpression] = None,
    ):
        super().__init__(
            identity_start=identity_start,
            identity_increment=identity_increment,
        )
        if materialized is not None and not isinstance(materialized, BaseExpression):
            raise TypeError("materialized must be a BaseExpression")
        if alias is not None and not isinstance(alias, BaseExpression):
            raise TypeError("alias must be a BaseExpression")
        if ttl is not None and not isinstance(ttl, BaseExpression):
            raise TypeError("ttl must be a BaseExpression")
        self.codec = list(codec) if codec else None
        self.materialized = materialized
        self.alias = alias
        self.ttl = ttl

    def column_definition_class(self):
        """Build a ``ClickHouseColumnDefinition`` for these options."""
        return ClickHouseColumnDefinition

    def apply_to(self, column) -> None:
        """Transfer the ClickHouse-only fields onto the column definition."""
        if not isinstance(column, ClickHouseColumnDefinition):
            raise TypeError(
                "ClickHouseColumnOptions.apply_to requires a ClickHouseColumnDefinition, "
                f"got {type(column).__name__}"
            )
        column.codec = self.codec
        column.materialized = self.materialized
        column.alias = self.alias
        column.ttl = self.ttl

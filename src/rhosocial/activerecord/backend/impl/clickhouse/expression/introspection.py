# src/rhosocial/activerecord/backend/impl/clickhouse/expression/introspection.py
"""ClickHouse backend-specific introspection expressions.

The core introspection protocol has statements for tables, columns, indexes,
views and triggers. ClickHouse has two more facts worth asking its own catalog
about, and no core statement shape for either:

* a table's parts, grouped into partitions (``system.parts``);
* the storage definition a table was created with (``system.tables``).

Each node carries only its parameters, as every other expression in this
backend does (expression-dialect §16.2): the dialect writes the statement, the
introspector constructs and executes it. The formatters live in
``..mixins.introspection``, beside the core introspection formatters they share
their building blocks with.

The parameter is named ``database`` rather than ``schema`` on purpose:
ClickHouse has no schema layer, and its top-level namespace is a database. See
``..introspection.types`` for the full statement of that naming rule.
"""

from typing import TYPE_CHECKING

from rhosocial.activerecord.backend.expression.bases import BaseExpression

if TYPE_CHECKING:  # pragma: no cover
    from rhosocial.activerecord.backend.dialect import SQLDialectBase


__all__ = [
    "ClickHouseTableEngineQuery",
    "ClickHouseTablePartitionsQuery",
]


class ClickHouseTablePartitionsQuery(BaseExpression):
    """Active parts of one table, aggregated per ``partition_id``."""

    def __init__(self, dialect: "SQLDialectBase", database: str, table: str):
        super().__init__(dialect)
        self.database = database
        self.table = table

    @property
    def format_method(self) -> str:
        """The dialect formatting method that renders this expression."""
        return "format_clickhouse_table_partitions_query"


class ClickHouseTableEngineQuery(BaseExpression):
    """The storage definition of one table, from ``system.tables``."""

    def __init__(self, dialect: "SQLDialectBase", database: str, table: str):
        super().__init__(dialect)
        self.database = database
        self.table = table

    @property
    def format_method(self) -> str:
        """The dialect formatting method that renders this expression."""
        return "format_clickhouse_table_engine_query"

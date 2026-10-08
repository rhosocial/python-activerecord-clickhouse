# src/rhosocial/activerecord/backend/impl/clickhouse/protocols/table_statement.py
"""ClickHouse TABLE statement / VALUES constructor protocol.

Split out of the former single-module ``clickhouse/protocols.py``; one
concern per module so the protocol surface stays legible.
"""

from typing import Protocol, runtime_checkable, Tuple, TYPE_CHECKING

if TYPE_CHECKING:  # pragma: no cover
    from rhosocial.activerecord.backend.impl.clickhouse.expression.table_statement import (
        ClickHouseTableExpression,
        ClickHouseValuesExpression,
    )

@runtime_checkable
class ClickHouseTableStatementSupport(Protocol):
    """ClickHouse TABLE statement / VALUES constructor support protocol.

    Feature Source: ClickHouse 8.0.19+

    Official Documentation:
    - TABLE statement: https://dev.clickhouse.com/doc/refman/8.0/en/table.html
    - VALUES statement: https://dev.clickhouse.com/doc/refman/8.0/en/values.html
    """

    def supports_table_statement(self) -> bool:
        """Whether the TABLE statement is supported."""
        ...

    def supports_values_table_constructor(self) -> bool:
        """Whether VALUES as a table value constructor is supported."""
        ...

    def format_table_statement(self, expr: "ClickHouseTableExpression") -> Tuple[str, tuple]:
        """Format a TABLE statement."""
        ...

    def format_values_statement(self, expr: "ClickHouseValuesExpression") -> Tuple[str, tuple]:
        """Format a VALUES table value constructor."""
        ...

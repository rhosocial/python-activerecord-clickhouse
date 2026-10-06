# src/rhosocial/activerecord/backend/impl/clickhouse/protocols/optimizer_hint.py
"""ClickHouse optimizer hint protocol.

Split out of the former single-module ``clickhouse/protocols.py``; one
concern per module so the protocol surface stays legible.
"""

from typing import Protocol, runtime_checkable, Tuple, TYPE_CHECKING

if TYPE_CHECKING:  # pragma: no cover
    from rhosocial.activerecord.backend.impl.clickhouse.expression.optimizer_hint import (
        ClickHouseOptimizerHintExpression,
    )

@runtime_checkable
class ClickHouseOptimizerHintSupport(Protocol):
    """ClickHouse optimizer hint protocol.

    Feature Source: ClickHouse 5.7+ (hint syntax), ClickHouse 9.7+ (hypergraph optimizer)

    Supports per-statement optimizer hints using /*+ ... */ syntax,
    including SET_VAR hints for controlling optimizer switches.

    Official Documentation:
    - Optimizer Hints: https://dev.clickhouse.com/doc/refman/8.0/en/optimizer-hints.html
    - SET_VAR: https://dev.clickhouse.com/doc/refman/8.0/en/optimizer-hints.html#optimizer-hints-set-var

    Version Requirements:
    - Optimizer hints: ClickHouse 5.7+
    - SET_VAR hint: ClickHouse 8.0+
    - Hypergraph optimizer: ClickHouse 9.7+ (Community Edition)
    """

    def supports_optimizer_hint(self) -> bool:
        """Whether optimizer hints (/*+ ... */) are supported."""
        ...

    def supports_hypergraph_optimizer(self) -> bool:
        """Whether the hypergraph optimizer is available (ClickHouse 9.7+)."""
        ...

    def format_optimizer_hint(self, expr: "ClickHouseOptimizerHintExpression") -> Tuple[str, tuple]:
        """Format optimizer hint expression.

        Args:
            expr: ClickHouseOptimizerHintExpression instance

        Returns:
            Tuple of (SQL hint string, parameters tuple)
        """
        ...

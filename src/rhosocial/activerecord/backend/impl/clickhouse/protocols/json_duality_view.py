# src/rhosocial/activerecord/backend/impl/clickhouse/protocols/json_duality_view.py
"""ClickHouse JSON Duality View protocol.

Split out of the former single-module ``clickhouse/protocols.py``; one
concern per module so the protocol surface stays legible.
"""

from typing import TYPE_CHECKING, Any, Protocol, Tuple, runtime_checkable

if TYPE_CHECKING:  # pragma: no cover
    from rhosocial.activerecord.backend.impl.clickhouse.expression.statements import (
        ClickHouseCreateJsonDualityViewStatement,
        ClickHouseDropJsonDualityViewStatement,
    )


@runtime_checkable
class ClickHouseJsonDualityViewSupport(Protocol):
    """ClickHouse JSON Duality View protocol -- a switch that answers no.

    The protocol exists so a caller can *ask*; the answer is always no.
    ClickHouse has no duality views at any version, and there is nothing to
    name a version for: ``CREATE`` enumerates the objects it can make on
    refusal, and a duality view is not on the list -- the three measurements
    are recorded in ``expression/json_duality_view.py``. What the server has
    for reacting to a row is ``CREATE FUNCTION ... AS`` plus a MATERIALIZED
    VIEW; for relational JSON, the ``JSON`` type with ``JSONExtract*``.
    """

    def supports_json_duality_view(self) -> bool:
        """Whether JSON Duality Views are supported -- always ``False`` here."""
        ...

    def supports_json_duality_view_dml(self) -> bool:
        """Whether DML on JSON Duality Views is supported -- always ``False`` here."""
        ...

    def format_clickhouse_create_json_duality_view_statement(
        self, expr: "ClickHouseCreateJsonDualityViewStatement"
    ) -> Tuple[str, tuple]:
        """Format CREATE JSON RELATIONAL DUALITY VIEW statement.

        Args:
            expr: ClickHouseCreateJsonDualityViewStatement instance

        Returns:
            Tuple of (SQL string, parameters tuple)
        """
        ...

    def format_clickhouse_drop_json_duality_view_statement(
        self, expr: "ClickHouseDropJsonDualityViewStatement"
    ) -> Tuple[str, tuple]:
        """Format DROP VIEW statement for a JSON Duality View."""
        ...

    def _refuse_duality_object_select(self, expr: Any) -> str:
        """Format SELECT JSON_DUALITY_OBJECT(...) FROM table clause."""
        ...

    def _refuse_duality_object_body(self, expr: Any) -> str:
        """Format JSON_DUALITY_OBJECT(...) body."""
        ...

    def _refuse_nested_duality(self, expr: Any) -> str:
        """Format nested JSON_ARRAYAGG(JSON_DUALITY_OBJECT(...)) subquery."""
        ...

# src/rhosocial/activerecord/backend/impl/clickhouse/protocols/json_duality_view.py
"""ClickHouse JSON Duality View protocol.

Split out of the former single-module ``clickhouse/protocols.py``; one
concern per module so the protocol surface stays legible.
"""

from typing import Any, Protocol, runtime_checkable, Tuple, TYPE_CHECKING

if TYPE_CHECKING:  # pragma: no cover
    from rhosocial.activerecord.backend.impl.clickhouse.expression.json_duality_view import (
        CreateJsonDualityViewExpression,
        DropJsonDualityViewExpression,
    )

@runtime_checkable
class ClickHouseJsonDualityViewSupport(Protocol):
    """ClickHouse JSON Duality View protocol (ClickHouse 9.7+).

    Feature Source: ClickHouse 9.7.0 (2026-04-21)

    JSON Duality Views provide a document-relational duality layer:
    - CREATE JSON RELATIONAL DUALITY VIEW with JSON_DUALITY_OBJECT
    - WITH(INSERT,UPDATE,DELETE) annotations per object level
    - DML via single JSON `data` column
    - Optimistic locking via _metadata.etag on UPDATE

    Official Documentation:
    - JSON Duality Views: https://dev.clickhouse.com/doc/refman/9.7/en/json-duality-views.html

    Version Requirements:
    - JSON Duality Views: ClickHouse 9.7.0+
    """

    def supports_json_duality_view(self) -> bool:
        """Whether JSON Duality Views are supported (ClickHouse 9.7+)."""
        ...

    def supports_json_duality_view_dml(self) -> bool:
        """Whether DML on JSON Duality Views is supported (ClickHouse 9.7+)."""
        ...

    def format_create_json_duality_view_statement(self, expr: "CreateJsonDualityViewExpression") -> Tuple[str, tuple]:
        """Format CREATE JSON RELATIONAL DUALITY VIEW statement.

        Args:
            expr: CreateJsonDualityViewExpression instance

        Returns:
            Tuple of (SQL string, parameters tuple)
        """
        ...

    def format_drop_json_duality_view_statement(self, expr: "DropJsonDualityViewExpression") -> Tuple[str, tuple]:
        """Format DROP VIEW statement for a JSON Duality View."""
        ...

    def format_duality_object_select(self, spec: Any) -> str:
        """Format SELECT JSON_DUALITY_OBJECT(...) FROM table clause."""
        ...

    def format_duality_object_body(self, spec: Any) -> str:
        """Format JSON_DUALITY_OBJECT(...) body."""
        ...

    def format_nested_duality(self, nested: Any) -> str:
        """Format nested JSON_ARRAYAGG(JSON_DUALITY_OBJECT(...)) subquery."""
        ...

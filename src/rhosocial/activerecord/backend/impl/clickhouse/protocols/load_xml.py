# src/rhosocial/activerecord/backend/impl/clickhouse/protocols/load_xml.py
"""ClickHouse LOAD XML statement protocol.

Split out of the former single-module ``clickhouse/protocols.py``; one
concern per module so the protocol surface stays legible.
"""

from typing import Protocol, runtime_checkable, Tuple, TYPE_CHECKING

if TYPE_CHECKING:  # pragma: no cover
    from rhosocial.activerecord.backend.impl.clickhouse.expression.load_xml import (
        ClickHouseLoadXMLEXpression,
    )

@runtime_checkable
class ClickHouseLoadXMLSupport(Protocol):
    """ClickHouse LOAD XML statement support protocol.

    Feature Source: ClickHouse 5.0+

    Official Documentation:
    - LOAD XML: https://dev.clickhouse.com/doc/refman/8.0/en/load-xml.html
    """

    def supports_load_xml(self) -> bool:
        """Whether LOAD XML is supported."""
        ...

    def format_load_xml_statement(self, expr: "ClickHouseLoadXMLEXpression") -> Tuple[str, tuple]:
        """Format a LOAD XML statement."""
        ...

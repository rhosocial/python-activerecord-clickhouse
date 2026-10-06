# src/rhosocial/activerecord/backend/impl/clickhouse/protocols/set_type.py
"""ClickHouse SET type protocol.

Split out of the former single-module ``clickhouse/protocols.py``; one
concern per module so the protocol surface stays legible.
"""

from typing import Protocol, runtime_checkable, Tuple, TYPE_CHECKING

@runtime_checkable
class ClickHouseSetTypeSupport(Protocol):
    """ClickHouse SET type protocol.

    Feature Source: ClickHouse native (not SQL standard)

    ClickHouse SET features:
    - String object with zero or more values from predefined list
    - Stored as integer (bit flags) internally
    - Maximum 64 members
    - Supports FIND_IN_SET, LIKE operations
    - Automatically sorted on storage

    Official Documentation:
    - SET Type: https://dev.clickhouse.com/doc/refman/8.0/en/set.html

    Version Requirements:
    - All ClickHouse versions
    """

    def supports_set_type(self) -> bool:
        """Whether SET type is supported."""
        ...

    def format_set_literal(self, expr) -> Tuple[str, tuple]:
        """Format SET type literal."""
        ...

    def format_find_in_set(self, expr) -> Tuple[str, tuple]:
        """Format FIND_IN_SET function call."""
        ...

    def format_set_contains(self, expr) -> Tuple[str, tuple]:
        """Format SET contains check expression."""
        ...

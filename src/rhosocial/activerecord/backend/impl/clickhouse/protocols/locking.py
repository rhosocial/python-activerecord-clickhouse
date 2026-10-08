# src/rhosocial/activerecord/backend/impl/clickhouse/protocols/locking.py
"""ClickHouse row-level locking protocol.

Split out of the former single-module ``clickhouse/protocols.py``; one
concern per module so the protocol surface stays legible.
"""

from typing import Any, Protocol, runtime_checkable, Tuple, TYPE_CHECKING

from rhosocial.activerecord.backend.dialect.protocols import LockingSupport


@runtime_checkable
class ClickHouseLockingSupport(LockingSupport, Protocol):
    """ClickHouse row-level locking protocol.

    Feature Source: ClickHouse native (FOR UPDATE all versions, FOR SHARE ClickHouse 8.0+)

    ClickHouse locking features beyond SQL standard:
    - FOR SHARE: Shared lock (ClickHouse 8.0+, replaces LOCK IN SHARE MODE)
    - NOWAIT: Fail immediately if rows are locked (ClickHouse 8.0+)
    - SKIP LOCKED: Skip locked rows (ClickHouse 8.0+)

    Note: ClickHouse does NOT support PostgreSQL's FOR NO KEY UPDATE or
    FOR KEY SHARE lock strengths.

    Official Documentation:
    - SELECT ... FOR UPDATE: https://dev.clickhouse.com/doc/refman/8.0/en/innodb-locking-reads.html
    - LOCK IN SHARE MODE: https://dev.clickhouse.com/doc/refman/8.0/en/innodb-locking-reads.html

    Version Requirements:
    - FOR UPDATE: All ClickHouse versions
    - FOR SHARE (replacing LOCK IN SHARE MODE): ClickHouse 8.0+
    - NOWAIT: ClickHouse 8.0+
    - SKIP LOCKED: ClickHouse 8.0+
    """

    def supports_for_share(self) -> bool:
        """Whether FOR SHARE clause is supported (ClickHouse 8.0+)."""
        ...

    def supports_for_update_nowait(self) -> bool:
        """Whether FOR UPDATE NOWAIT is supported (ClickHouse 8.0+)."""
        ...

    def supports_for_update_skip_locked(self) -> bool:
        """Whether FOR UPDATE SKIP LOCKED is supported (ClickHouse 8.0+)."""
        ...

    def format_for_update_clause(self, clause: Any) -> Tuple[str, tuple]:
        """Format ClickHouse-specific FOR UPDATE clause.

        Args:
            clause: ForUpdateClause instance

        Returns:
            Tuple of (SQL string, parameters tuple)
        """
        ...

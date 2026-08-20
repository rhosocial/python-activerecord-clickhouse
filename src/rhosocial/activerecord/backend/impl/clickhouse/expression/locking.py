# src/rhosocial/activerecord/backend/impl/clickhouse/expression/locking.py
"""
ClickHouse-specific row-level locking expressions.

ClickHouse supports row-level locking with FOR UPDATE and FOR SHARE:
- FOR UPDATE: Exclusive lock (write lock), blocks other FOR UPDATE and FOR SHARE
- FOR SHARE: Shared lock (read lock), allows other FOR SHARE but blocks FOR UPDATE

ClickHouse 8.0+ additionally supports:
- FOR SHARE NOWAIT: Fail immediately if rows are locked
- FOR UPDATE NOWAIT: Fail immediately if rows are locked
- FOR UPDATE SKIP LOCKED: Skip locked rows instead of waiting
- FOR SHARE SKIP LOCKED: Skip locked rows instead of waiting

Note: ClickHouse 8.0 deprecated LOCK IN SHARE MODE in favor of FOR SHARE,
but both syntaxes are supported.
"""

from enum import Enum
from typing import Any, Dict, List, Optional, Union, TYPE_CHECKING

from rhosocial.activerecord.backend.expression.query_parts import ForUpdateClause
from rhosocial.activerecord.backend.expression import bases

if TYPE_CHECKING:
    from rhosocial.activerecord.backend.dialect import SQLDialectBase


class ClickHouseLockStrength(Enum):
    """
    Enumeration of ClickHouse row-level lock strength options.

    ClickHouse supports two lock strengths for row-level locking:

    - UPDATE: Exclusive lock (FOR UPDATE), blocks all other locks
    - SHARE: Shared lock (FOR SHARE), allows other shared locks

    Version requirements (ClickHouse):
    - FOR UPDATE: All versions
    - FOR SHARE: ClickHouse 8.0+ (previously LOCK IN SHARE MODE)
    """

    UPDATE = "FOR UPDATE"  # Exclusive lock (strongest)
    SHARE = "FOR SHARE"  # Shared lock (ClickHouse 8.0+)


class ClickHouseForUpdateClause(ForUpdateClause):
    """
    ClickHouse-specific FOR UPDATE clause with lock strength support.

    Extends the standard ForUpdateClause with ClickHouse's row-level
    locking capabilities.

    ClickHouse supports:
    - FOR UPDATE: Exclusive lock on selected rows
    - FOR SHARE: Shared lock on selected rows (ClickHouse 8.0+)
    - NOWAIT: Fail immediately if rows are locked (ClickHouse 8.0+)
    - SKIP LOCKED: Skip locked rows instead of waiting (ClickHouse 8.0+)

    Note: ClickHouse does NOT support PostgreSQL's FOR NO KEY UPDATE
    or FOR KEY SHARE lock strengths.

    Example Usage:
        # Basic FOR UPDATE (same as parent class)
        for_update = ClickHouseForUpdateClause(dialect)

        # FOR SHARE (ClickHouse 8.0+)
        for_update = ClickHouseForUpdateClause(dialect, strength=ClickHouseLockStrength.SHARE)

        # FOR SHARE with NOWAIT (ClickHouse 8.0+)
        for_update = ClickHouseForUpdateClause(
            dialect,
            strength=ClickHouseLockStrength.SHARE,
            nowait=True
        )

        # FOR UPDATE with SKIP LOCKED (ClickHouse 8.0+)
        for_update = ClickHouseForUpdateClause(
            dialect,
            strength=ClickHouseLockStrength.UPDATE,
            skip_locked=True
        )
    """

    def __init__(
        self,
        dialect: "SQLDialectBase",
        strength: Optional[ClickHouseLockStrength] = None,
        of_columns: Optional[List[Union[str, "bases.BaseExpression"]]] = None,
        nowait: bool = False,
        skip_locked: bool = False,
        dialect_options: Optional[Dict[str, Any]] = None,
    ):
        """
        Initialize ClickHouse FOR UPDATE clause.

        Args:
            dialect: The SQL dialect to use for formatting
            strength: Lock strength (defaults to UPDATE for backward compatibility)
            of_columns: Columns to apply the lock to
            nowait: If True, fail immediately if rows are locked (ClickHouse 8.0+)
            skip_locked: If True, skip locked rows instead of waiting (ClickHouse 8.0+)
            dialect_options: Additional dialect-specific options
        """
        super().__init__(
            dialect,
            of_columns=of_columns,
            nowait=nowait,
            skip_locked=skip_locked,
            dialect_options=dialect_options,
        )
        # Default to UPDATE for backward compatibility
        self.strength = strength if strength is not None else ClickHouseLockStrength.UPDATE

    def to_sql(self) -> "bases.SQLQueryAndParams":
        """
        Generate the SQL representation of the ClickHouse FOR UPDATE clause.

        Delegates to the dialect's format_for_update_clause method
        to follow the Expression-Dialect separation pattern.

        Returns:
            Tuple containing:
            - SQL string fragment for the FOR UPDATE clause
            - Tuple of parameter values for prepared statements
        """
        return self.dialect.format_for_update_clause(self)

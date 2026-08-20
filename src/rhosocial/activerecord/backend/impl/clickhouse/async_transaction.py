# src/rhosocial/activerecord/backend/impl/clickhouse/async_transaction.py
"""
Asynchronous transaction management for ClickHouse backend.

This module provides async transaction management capabilities for ClickHouse.
ClickHouse requires SET TRANSACTION ISOLATION LEVEL to be executed before
START TRANSACTION as separate statements. This class overrides _do_begin()
to handle this sequencing properly.
"""

import logging
from typing import TYPE_CHECKING, Optional

from rhosocial.activerecord.backend.transaction import (
    AsyncTransactionManager,
)

from .mixins import ClickHouseTransactionMixin

if TYPE_CHECKING:
    from .backend import AsyncClickHouseBackend


class AsyncClickHouseTransactionManager(ClickHouseTransactionMixin, AsyncTransactionManager):
    """Asynchronous transaction manager for ClickHouse backend.

    ClickHouse requires SET TRANSACTION ISOLATION LEVEL to be executed before
    START TRANSACTION when a specific isolation level is needed. This class
    overrides _do_begin() to handle this sequencing.

    The format_begin_transaction() in ClickHouseDialect returns only "START TRANSACTION",
    while this class handles the SET TRANSACTION step separately.

    Non-I/O methods (isolation_level, _build_set_isolation_sql, _ISOLATION_LEVELS)
    are inherited from ClickHouseTransactionMixin.
    """

    def __init__(
        self,
        backend: "AsyncClickHouseBackend",
        logger: Optional[logging.Logger] = None,
    ) -> None:
        """Initialize async ClickHouse transaction manager.

        Args:
            backend: AsyncClickHouseBackend instance.
            logger: Optional logger instance.
        """
        super().__init__(backend, logger)
        # Note: _isolation_level defaults to None (use database default).
        # ClickHouse's default isolation level is REPEATABLE READ, but we only
        # send SET TRANSACTION when user explicitly specifies a level.

    async def _do_begin(self) -> None:
        """Begin a new transaction with ClickHouse-specific sequencing.

        ClickHouse requires:
        1. SET TRANSACTION ISOLATION LEVEL (if needed, before START)
        2. START TRANSACTION [READ ONLY]

        Each statement is executed separately via backend.execute().
        """
        # Step 1: Set isolation level if needed
        if self._isolation_level is not None:
            sql, params = self._build_set_isolation_sql(self._isolation_level)
            self.log(logging.DEBUG, f"Executing: {sql}")
            await self._backend.execute(sql, params)

        # Step 2: Execute START TRANSACTION
        sql, params = self._build_begin_sql()
        self.log(logging.DEBUG, f"Executing: {sql}")
        await self._backend.execute(sql, params)

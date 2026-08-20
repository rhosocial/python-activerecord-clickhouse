# src/rhosocial/activerecord/backend/impl/clickhouse/mixins/concurrency.py
import logging
from typing import Optional

from rhosocial.activerecord.backend.protocols import ConcurrencyHint


class ClickHouseConcurrencyMixin:
    """Mixin providing ClickHouse-specific concurrency hint."""

    _concurrency_hint: Optional[ConcurrencyHint] = None

    def connect(self):
        """Establish connection to ClickHouse and fetch concurrency hint."""
        super().connect()
        self._fetch_concurrency_hint()

    def _fetch_concurrency_hint(self) -> None:
        """Fetch max concurrent queries from ClickHouse and compute concurrency hint."""
        try:
            cursor = self._connection.cursor()
            cursor.execute("SELECT value FROM system.settings WHERE name = 'max_concurrent_queries'")
            row = cursor.fetchone()
            cursor.close()

            if row:
                max_connections = int(row[0])
                pool_size = getattr(self.config, "pool_size", 5) or 5
                limit = min(max_connections, pool_size)
                self._concurrency_hint = ConcurrencyHint(
                    max_concurrency=limit,
                    reason=f"min(max_concurrent_queries={max_connections}, pool_size={pool_size})",
                )
                self.log(
                    logging.DEBUG,
                    f"Concurrency hint: max_concurrency={limit}, max_concurrent_queries={max_connections}, pool_size={pool_size}",  # noqa: E501
                )
        except Exception as e:
            self.log(logging.WARNING, f"Failed to fetch concurrency hint: {e}")
            self._concurrency_hint = None

    def get_concurrency_hint(self) -> Optional[ConcurrencyHint]:
        return self._concurrency_hint


class AsyncClickHouseConcurrencyMixin:
    """Async mixin providing ClickHouse-specific concurrency hint."""

    _concurrency_hint: Optional[ConcurrencyHint] = None

    async def connect(self):
        """Establish connection to ClickHouse and fetch concurrency hint."""
        await super().connect()
        await self._fetch_concurrency_hint()

    async def _fetch_concurrency_hint(self) -> None:
        """Fetch max_concurrent_queries from ClickHouse server and compute concurrency hint."""
        try:
            cursor = await self._connection.cursor(dictionary=True)
            await cursor.execute("SELECT value FROM system.settings WHERE name = 'max_concurrent_queries'")
            row = await cursor.fetchone()
            await cursor.close()

            if row:
                max_connections = int(row["value"])
                pool_size = getattr(self.config, "pool_size", 5) or 5
                limit = min(max_connections, pool_size)
                self._concurrency_hint = ConcurrencyHint(
                    max_concurrency=limit,
                    reason=f"min(max_concurrent_queries={max_connections}, pool_size={pool_size})",
                )
                self.log(
                    logging.DEBUG,
                    f"Concurrency hint: max_concurrency={limit}, max_concurrent_queries={max_connections}, pool_size={pool_size}",  # noqa: E501
                )
        except Exception as e:
            self.log(logging.WARNING, f"Failed to fetch concurrency hint: {e}")
            self._concurrency_hint = None

    def get_concurrency_hint(self) -> Optional[ConcurrencyHint]:
        return self._concurrency_hint

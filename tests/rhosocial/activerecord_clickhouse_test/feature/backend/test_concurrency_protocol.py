# tests/rhosocial/activerecord_clickhouse_test/feature/backend/test_concurrency_protocol.py
"""
Test for ConcurrencyAware protocol implementation in ClickHouse backend.

This test verifies that ClickHouseBackend correctly implements the ConcurrencyAware
protocol by fetching max_connections during connect and returning the appropriate
concurrency hint.
"""

import pytest

from rhosocial.activerecord.backend.protocols import ConcurrencyAware, ConcurrencyHint


class TestClickHouseConcurrencyAware:
    """Test ConcurrencyAware protocol implementation for ClickHouse backend."""

    def test_clickhouse_backend_implements_protocol(self, clickhouse_backend_single):
        """Test that ClickHouseBackend implements ConcurrencyAware protocol."""
        assert isinstance(clickhouse_backend_single, ConcurrencyAware)

    def test_clickhouse_get_concurrency_hint(self, clickhouse_backend_single):
        """Test ClickHouseBackend returns correct concurrency hint."""
        hint = clickhouse_backend_single.get_concurrency_hint()

        assert hint is not None
        assert isinstance(hint, ConcurrencyHint)
        assert hint.max_concurrency is not None
        assert hint.max_concurrency > 0
        assert "max_connections" in hint.reason
        assert "pool_size" in hint.reason

    def test_clickhouse_concurrency_hint_value(self, clickhouse_backend_single):
        """Test concurrency hint value is bounded by pool_size."""
        pool_size = clickhouse_backend_single.config.pool_size or 5
        hint = clickhouse_backend_single.get_concurrency_hint()

        assert hint.max_concurrency <= pool_size
        assert hint.max_concurrency > 0

    def test_clickhouse_concurrency_hint_not_none_after_connect(self, clickhouse_backend_single):
        """Test that concurrency hint is populated after connect."""
        assert clickhouse_backend_single._connection is not None
        assert clickhouse_backend_single.get_concurrency_hint() is not None


class TestAsyncClickHouseConcurrencyAware:
    """Test ConcurrencyAware protocol implementation for async ClickHouse backend."""

    @pytest.mark.asyncio
    async def test_async_clickhouse_backend_implements_protocol(self, async_clickhouse_backend_single):
        """Test that AsyncClickHouseBackend implements ConcurrencyAware protocol."""
        assert isinstance(async_clickhouse_backend_single, ConcurrencyAware)

    @pytest.mark.asyncio
    async def test_async_clickhouse_get_concurrency_hint(self, async_clickhouse_backend_single):
        """Test AsyncClickHouseBackend returns correct concurrency hint."""
        hint = async_clickhouse_backend_single.get_concurrency_hint()

        assert hint is not None
        assert isinstance(hint, ConcurrencyHint)
        assert hint.max_concurrency is not None
        assert hint.max_concurrency > 0
        assert "max_connections" in hint.reason
        assert "pool_size" in hint.reason

    @pytest.mark.asyncio
    async def test_async_clickhouse_concurrency_hint_value(self, async_clickhouse_backend_single):
        """Test async concurrency hint value is bounded by pool_size."""
        pool_size = async_clickhouse_backend_single.config.pool_size or 5
        hint = async_clickhouse_backend_single.get_concurrency_hint()

        assert hint.max_concurrency <= pool_size
        assert hint.max_concurrency > 0

    @pytest.mark.asyncio
    async def test_async_clickhouse_concurrency_hint_not_none_after_connect(self, async_clickhouse_backend_single):
        """Test that async concurrency hint is populated after connect."""
        assert async_clickhouse_backend_single._connection is not None
        assert async_clickhouse_backend_single.get_concurrency_hint() is not None

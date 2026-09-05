# tests/rhosocial/activerecord_clickhouse_test/feature/backend/concurrency/test_concurrency_protocol.py
"""Tests for the ConcurrencyAware protocol implementation in the ClickHouse backend.

Verifies that :class:`ClickHouseBackend` implements the ``ConcurrencyAware``
protocol and returns a concurrency hint derived from the server's
``max_concurrent_queries`` setting. When the query is not permitted the hint
falls back to ``None``, so the protocol tests accept either outcome.
"""

from rhosocial.activerecord.backend.protocols import ConcurrencyAware, ConcurrencyHint


class TestClickHouseConcurrencyAware:
    """ConcurrencyAware protocol conformance for the ClickHouse backend."""

    def test_clickhouse_backend_implements_protocol(self, clickhouse_backend_single):
        """The backend must declare the ConcurrencyAware protocol."""
        assert isinstance(clickhouse_backend_single, ConcurrencyAware), (
            "ClickHouseBackend must implement ConcurrencyAware"
        )

    def test_clickhouse_get_concurrency_hint(self, clickhouse_backend_single):
        """A concurrency hint is returned after connect (or None when unavailable)."""
        hint = clickhouse_backend_single.get_concurrency_hint()
        assert hint is None or isinstance(hint, ConcurrencyHint), (
            "hint must be None or a ConcurrencyHint"
        )
        if hint is not None:
            assert hint.max_concurrency is None or hint.max_concurrency > 0, (
                "max_concurrency must be positive when set"
            )

    def test_clickhouse_concurrency_hint_reason(self, clickhouse_backend_single):
        """The hint reason names the constraint source when a hint is present."""
        hint = clickhouse_backend_single.get_concurrency_hint()
        if hint is not None:
            assert "max_concurrent_queries" in hint.reason or "pool_size" in hint.reason, (
                "hint reason must name max_concurrent_queries/pool_size"
            )
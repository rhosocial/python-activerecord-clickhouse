# src/rhosocial/activerecord/backend/impl/clickhouse/async_backend.py
"""
Stub: AsyncClickHouseBackend is not available.

clickhouse-connect (the ClickHouse driver used by this backend) is a synchronous-only
library. No asynchronous backend is provided. Use ClickHouseBackend (sync) instead.
"""

raise ImportError(
    "AsyncClickHouseBackend is not available in rhosocial-activerecord-clickhouse. "
    "clickhouse-connect is a synchronous-only library. "
    "Use ClickHouseBackend (sync) instead."
)
# src/rhosocial/activerecord/backend/impl/clickhouse/async_backend.py
"""AsyncClickHouseBackend placeholder.

clickhouse-connect (the ClickHouse driver used by this backend) is a
synchronous-only library, so no asynchronous backend is provided.

This module keeps a minimal placeholder class so that existing imports
(testsuite providers, CLI helpers) continue to load, but any attempt to
instantiate it fails fast.
"""


class AsyncClickHouseBackend:
    """Placeholder: asynchronous ClickHouse backend is not supported.

    clickhouse-connect is a synchronous-only library, so async execution is
    not available for ClickHouse. Use :class:`ClickHouseBackend` instead.
    """

    def __init__(self, *args, **kwargs):
        raise NotImplementedError(
            "AsyncClickHouseBackend is not available in rhosocial-activerecord-clickhouse. "
            "clickhouse-connect is a synchronous-only library. "
            "Use ClickHouseBackend (sync) instead."
        )

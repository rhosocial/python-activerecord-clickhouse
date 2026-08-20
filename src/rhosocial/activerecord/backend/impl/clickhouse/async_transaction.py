# src/rhosocial/activerecord/backend/impl/clickhouse/async_transaction.py
"""AsyncClickHouseTransactionManager placeholder.

clickhouse-connect (the ClickHouse driver used by this backend) is a
synchronous-only library and ClickHouse does not support ACID transactions,
so no asynchronous transaction manager is provided.

This module keeps a minimal placeholder class so that existing imports
continue to load, but any attempt to instantiate it fails fast.
"""


class AsyncClickHouseTransactionManager:
    """Placeholder: asynchronous ClickHouse transactions are not supported."""

    def __init__(self, *args, **kwargs):
        raise NotImplementedError(
            "AsyncClickHouseTransactionManager is not available in "
            "rhosocial-activerecord-clickhouse. ClickHouse does not support "
            "ACID transactions and clickhouse-connect is sync-only."
        )

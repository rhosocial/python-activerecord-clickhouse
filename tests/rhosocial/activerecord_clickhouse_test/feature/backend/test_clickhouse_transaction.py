# tests/rhosocial/activerecord_clickhouse_test/feature/backend/test_clickhouse_transaction.py
"""
ClickHouse transaction behavior tests.

ClickHouse does not support ACID transactions. The ``transaction()`` context
manager degrades to a no-op so that generic operations (e.g. ``bulk_create``)
work, but ``begin()`` / ``commit()`` / ``rollback()`` still fail fast.
"""

import pytest

from rhosocial.activerecord.backend.errors import TransactionError
from rhosocial.activerecord.backend.dialect.exceptions import UnsupportedFeatureError


class TestClickHouseTransactionsUnsupported:
    """ClickHouse transactions must fail fast."""

    @pytest.fixture
    def test_table(self, clickhouse_backend):
        backend = clickhouse_backend
        backend.execute("DROP TABLE IF EXISTS test_tx_unsupported")
        backend.execute("""
            CREATE TABLE test_tx_unsupported (
                id UInt32,
                name String
            ) ENGINE = MergeTree()
            ORDER BY id
        """)
        yield "test_tx_unsupported"
        backend.execute("DROP TABLE IF EXISTS test_tx_unsupported")

    def test_transaction_context_manager_is_noop(self, clickhouse_backend, test_table):
        """The context manager degrades to a no-op (no exception)."""
        # The context manager silently succeeds to keep generic operations
        # (e.g. bulk_create) working.
        with clickhouse_backend.transaction():
            pass

    def test_begin_transaction_fails(self, clickhouse_backend):
        """Calling transaction_manager.begin() must fail."""
        with pytest.raises((TransactionError, UnsupportedFeatureError)):
            clickhouse_backend.transaction_manager.begin()

    def test_commit_without_transaction_fails(self, clickhouse_backend):
        """Committing without an active transaction must fail."""
        with pytest.raises((TransactionError, UnsupportedFeatureError)):
            clickhouse_backend.transaction_manager.commit()

    def test_rollback_without_transaction_fails(self, clickhouse_backend):
        """Rolling back without an active transaction must fail."""
        with pytest.raises((TransactionError, UnsupportedFeatureError)):
            clickhouse_backend.transaction_manager.rollback()

    def test_dialect_reports_transactions_unsupported(self, clickhouse_backend):
        """Dialect capability flags for transactions are False."""
        d = clickhouse_backend.dialect
        assert d.supports_transaction_mode() is False
        assert d.supports_savepoint() is False
        assert d.supports_read_only_transaction() is False
        assert d.supports_deferrable_transaction() is False

    def test_dialect_transaction_sql_raises(self, clickhouse_backend):
        """Transaction SQL generation must raise UnsupportedFeatureError."""
        d = clickhouse_backend.dialect
        with pytest.raises(UnsupportedFeatureError):
            from rhosocial.activerecord.backend.expression import BeginTransactionExpression
            d.format_begin_transaction(BeginTransactionExpression(d))

    def test_normal_operations_still_work(self, clickhouse_backend, test_table):
        """Non-transactional DML works normally."""
        backend = clickhouse_backend
        backend.execute(
            f"INSERT INTO {test_table} (id, name) VALUES (%s, %s)",
            (1, "normal"),
        )
        rows = backend.fetch_all(f"SELECT name FROM {test_table}")
        assert len(rows) == 1
        assert rows[0]["name"] == "normal"

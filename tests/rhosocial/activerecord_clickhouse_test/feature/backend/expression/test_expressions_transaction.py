# tests/rhosocial/activerecord_test/feature/backend/clickhouse/test_expressions_transaction.py
"""Tests for ClickHouse transaction expression classes.

ClickHouse Transaction Behavior:
- Isolation level must be set BEFORE START TRANSACTION using SET TRANSACTION
- START TRANSACTION can include READ ONLY / READ WRITE modes
- The dialect's format_begin_transaction() only returns START TRANSACTION
- SetTransactionExpression is used for isolation level settings
"""

import pytest
from rhosocial.activerecord.backend.expression.transaction import (
    BeginTransactionExpression,
    CommitTransactionExpression,
    RollbackTransactionExpression,
    SavepointExpression,
    ReleaseSavepointExpression,
    SetTransactionExpression,
)
from rhosocial.activerecord.backend.transaction import IsolationLevel


class TestClickHouseBeginTransactionExpression:
    """Tests for ClickHouse BeginTransactionExpression.

    Note: ClickHouse does not support isolation level in START TRANSACTION.
    The dialect's supports_isolation_level_in_begin() returns False.
    Use SetTransactionExpression to set isolation level before START TRANSACTION.
    """

    def test_basic_begin(self, clickhouse_dialect):
        """Test basic START TRANSACTION."""
        expr = BeginTransactionExpression(clickhouse_dialect)
        sql, params = expr.to_sql()
        assert sql == "START TRANSACTION"
        assert params == ()

    def test_begin_with_isolation_level_returns_only_start(self, clickhouse_dialect):
        """Test that isolation level is NOT included in START TRANSACTION.

        ClickHouse requires SET TRANSACTION ISOLATION LEVEL to be executed
        separately before START TRANSACTION. The dialect's format_begin_transaction()
        only returns the START TRANSACTION statement.
        """
        expr = BeginTransactionExpression(clickhouse_dialect)
        expr.isolation_level(IsolationLevel.SERIALIZABLE)
        sql, params = expr.to_sql()
        # ClickHouse dialect does NOT include isolation level in START TRANSACTION
        assert sql == "START TRANSACTION"
        assert params == ()
        # Verify dialect capability
        assert not clickhouse_dialect.supports_isolation_level_in_begin()

    def test_begin_read_only(self, clickhouse_dialect):
        """Test START TRANSACTION READ ONLY."""
        expr = BeginTransactionExpression(clickhouse_dialect)
        expr.read_only()
        sql, params = expr.to_sql()
        assert sql == "START TRANSACTION READ ONLY"
        assert params == ()

    def test_begin_read_write(self, clickhouse_dialect):
        """Test START TRANSACTION READ WRITE."""
        expr = BeginTransactionExpression(clickhouse_dialect)
        expr.read_write()
        sql, params = expr.to_sql()
        assert sql == "START TRANSACTION"
        assert params == ()

    def test_begin_with_isolation_and_read_only(self, clickhouse_dialect):
        """Test START TRANSACTION with isolation level and READ ONLY.

        The isolation level is ignored by the dialect in START TRANSACTION.
        Use SetTransactionExpression for isolation level, then BeginTransactionExpression
        for READ ONLY mode.
        """
        expr = BeginTransactionExpression(clickhouse_dialect)
        expr.isolation_level(IsolationLevel.READ_COMMITTED).read_only()
        sql, params = expr.to_sql()
        # Only READ ONLY mode is included, isolation level is NOT
        assert sql == "START TRANSACTION READ ONLY"
        assert params == ()

    @pytest.mark.parametrize(
        "level",
        [
            IsolationLevel.READ_UNCOMMITTED,
            IsolationLevel.READ_COMMITTED,
            IsolationLevel.REPEATABLE_READ,
            IsolationLevel.SERIALIZABLE,
        ],
    )
    def test_begin_with_isolation_returns_start_transaction(self, clickhouse_dialect, level):
        """Test that START TRANSACTION does not include isolation level.

        ClickHouse requires separate SET TRANSACTION ISOLATION LEVEL statement.
        """
        expr = BeginTransactionExpression(clickhouse_dialect)
        expr.isolation_level(level)
        sql, params = expr.to_sql()
        # ClickHouse dialect does NOT include isolation level
        assert sql == "START TRANSACTION"
        assert params == ()


class TestClickHouseSetTransactionExpression:
    """Tests for ClickHouse SetTransactionExpression.

    ClickHouse uses SET TRANSACTION ISOLATION LEVEL before START TRANSACTION
    to set the isolation level for the next transaction.
    """

    def test_set_isolation_level(self, clickhouse_dialect):
        """Test SET TRANSACTION ISOLATION LEVEL."""
        expr = SetTransactionExpression(clickhouse_dialect)
        expr.isolation_level(IsolationLevel.SERIALIZABLE)
        sql, params = expr.to_sql()
        assert sql == "SET TRANSACTION ISOLATION LEVEL SERIALIZABLE"
        assert params == ()

    @pytest.mark.parametrize(
        "level,expected_name",
        [
            (IsolationLevel.READ_UNCOMMITTED, "READ UNCOMMITTED"),
            (IsolationLevel.READ_COMMITTED, "READ COMMITTED"),
            (IsolationLevel.REPEATABLE_READ, "REPEATABLE READ"),
            (IsolationLevel.SERIALIZABLE, "SERIALIZABLE"),
        ],
    )
    def test_all_isolation_levels(self, clickhouse_dialect, level, expected_name):
        """Test all isolation levels in SET TRANSACTION."""
        expr = SetTransactionExpression(clickhouse_dialect)
        expr.isolation_level(level)
        sql, params = expr.to_sql()
        assert expected_name in sql
        assert params == ()

    def test_set_read_only(self, clickhouse_dialect):
        """Test SET TRANSACTION READ ONLY."""
        expr = SetTransactionExpression(clickhouse_dialect)
        expr.read_only()
        sql, params = expr.to_sql()
        assert sql == "SET TRANSACTION READ ONLY"
        assert params == ()

    def test_set_read_write(self, clickhouse_dialect):
        """Test SET TRANSACTION READ WRITE."""
        expr = SetTransactionExpression(clickhouse_dialect)
        expr.read_write()
        sql, params = expr.to_sql()
        assert sql == "SET TRANSACTION READ WRITE"
        assert params == ()


class TestClickHouseCommitRollback:
    """Tests for ClickHouse COMMIT and ROLLBACK."""

    def test_commit(self, clickhouse_dialect):
        """Test COMMIT statement."""
        expr = CommitTransactionExpression(clickhouse_dialect)
        sql, params = expr.to_sql()
        assert sql == "COMMIT"
        assert params == ()

    def test_rollback(self, clickhouse_dialect):
        """Test ROLLBACK statement."""
        expr = RollbackTransactionExpression(clickhouse_dialect)
        sql, params = expr.to_sql()
        assert sql == "ROLLBACK"
        assert params == ()

    def test_rollback_to_savepoint(self, clickhouse_dialect):
        """Test ROLLBACK TO SAVEPOINT statement."""
        expr = RollbackTransactionExpression(clickhouse_dialect)
        expr.to_savepoint("my_savepoint")
        sql, params = expr.to_sql()
        assert "ROLLBACK" in sql
        assert "SAVEPOINT" in sql
        assert params == ()


class TestClickHouseSavepoint:
    """Tests for ClickHouse SAVEPOINT operations."""

    def test_savepoint(self, clickhouse_dialect):
        """Test SAVEPOINT statement."""
        expr = SavepointExpression(clickhouse_dialect, "my_savepoint")
        sql, params = expr.to_sql()
        assert "SAVEPOINT" in sql
        assert "my_savepoint" in sql
        assert params == ()

    def test_release_savepoint(self, clickhouse_dialect):
        """Test RELEASE SAVEPOINT statement."""
        expr = ReleaseSavepointExpression(clickhouse_dialect, "my_savepoint")
        sql, params = expr.to_sql()
        assert "RELEASE SAVEPOINT" in sql
        assert "my_savepoint" in sql
        assert params == ()


class TestClickHouseTransactionCapabilities:
    """Tests for ClickHouse transaction capabilities."""

    def test_supports_transaction_mode(self, clickhouse_dialect):
        """Test ClickHouse supports transaction mode."""
        assert clickhouse_dialect.supports_transaction_mode()

    def test_supports_isolation_level_in_begin(self, clickhouse_dialect):
        """Test ClickHouse does not support isolation level in BEGIN."""
        assert not clickhouse_dialect.supports_isolation_level_in_begin()

    def test_supports_read_only_transaction(self, clickhouse_dialect):
        """Test ClickHouse supports READ ONLY transactions (5.6.5+)."""
        assert clickhouse_dialect.supports_read_only_transaction()

    def test_supports_deferrable_transaction(self, clickhouse_dialect):
        """Test ClickHouse does not support DEFERRABLE transactions."""
        assert not clickhouse_dialect.supports_deferrable_transaction()

    def test_supports_savepoint(self, clickhouse_dialect):
        """Test ClickHouse supports savepoints."""
        assert clickhouse_dialect.supports_savepoint()

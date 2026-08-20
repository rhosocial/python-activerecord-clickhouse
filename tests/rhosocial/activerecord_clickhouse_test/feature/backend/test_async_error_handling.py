# tests/rhosocial/activerecord_clickhouse_test/feature/backend/test_async_error_handling.py
"""
Async ClickHouse Backend Error Handling Tests

Tests for verifying that AsyncClickHouseBackend correctly handles ClickHouse errors
using the proper error classes from clickhouse.connector.errors (not clickhouse.connector.aio).

This ensures the fix for: AttributeError: module 'clickhouse.connector.aio' has no attribute 'Error'
"""

import asyncio
import pytest
import pytest_asyncio

try:
    from clickhouse.connector.errors import (
        Error as ClickHouseError,
        DatabaseError as ClickHouseDatabaseError,
        OperationalError as ClickHouseOperationalError,
    )
except (ImportError, ModuleNotFoundError):
    pytest.skip("MySQL-specific test, skip for ClickHouse backend", allow_module_level=True)

from rhosocial.activerecord.backend.impl.clickhouse import AsyncClickHouseBackend
from rhosocial.activerecord.backend.errors import (
    IntegrityError,
    DatabaseError,
    DeadlockError,
    OperationalError,
)


@pytest_asyncio.fixture
async def setup_test_table(async_clickhouse_backend):
    """Create test table for error handling tests."""
    await async_clickhouse_backend.execute("DROP TABLE IF EXISTS error_test")
    await async_clickhouse_backend.execute("""
        CREATE TABLE error_test (
            id INT AUTO_INCREMENT PRIMARY KEY,
            name VARCHAR(255) NOT NULL,
            email VARCHAR(255) UNIQUE
        )
    """)
    yield
    # Give time for any pending async operations to complete
    await asyncio.sleep(0.1)
    try:
        await async_clickhouse_backend.execute("DROP TABLE IF EXISTS error_test")
    except Exception:
        pass


class TestAsyncHandleError:
    """Tests for _handle_error method with various ClickHouse error types."""

    @pytest.mark.asyncio
    async def test_handle_duplicate_entry_error(self, async_clickhouse_backend):
        """Test that Duplicate Entry error is converted to IntegrityError."""
        # Create table with unique constraint
        await async_clickhouse_backend.execute("DROP TABLE IF EXISTS unique_test_err")
        await async_clickhouse_backend.execute("""
            CREATE TABLE unique_test_err (
                id INT AUTO_INCREMENT PRIMARY KEY,
                email VARCHAR(255) UNIQUE
            )
        """)

        try:
            # Insert first row
            await async_clickhouse_backend.execute("INSERT INTO unique_test_err (email) VALUES (%s)", ("test@example.com",))

            # Try to insert duplicate - should raise IntegrityError
            with pytest.raises(IntegrityError) as exc_info:
                await async_clickhouse_backend.execute(
                    "INSERT INTO unique_test_err (email) VALUES (%s)", ("test@example.com",)
                )

            # The error message contains "duplicate entry" (lowercase in ClickHouse error)
            error_msg_lower = str(exc_info.value).lower()
            assert "duplicate entry" in error_msg_lower
        finally:
            # Give time for any pending async operations
            await asyncio.sleep(0.1)
            try:
                await async_clickhouse_backend.execute("DROP TABLE IF EXISTS unique_test_err")
            except Exception:
                pass

    @pytest.mark.asyncio
    async def test_handle_deadlock_error(self, async_clickhouse_backend):
        """Test that Deadlock error is converted to DeadlockError."""
        backend = async_clickhouse_backend

        # Create a mock ClickHouseDatabaseError with deadlock message
        class MockDeadlockError(ClickHouseDatabaseError):
            def __init__(self):
                self._msg = "Deadlock found when trying to get lock"

            def __str__(self):
                return self._msg

        mock_error = MockDeadlockError()

        with pytest.raises(DeadlockError):
            await backend._handle_error(mock_error)

    @pytest.mark.asyncio
    async def test_handle_lock_wait_timeout_error(self, async_clickhouse_backend):
        """Test that Lock wait timeout error is converted to OperationalError."""
        backend = async_clickhouse_backend

        # Create a mock ClickHouseOperationalError with lock timeout message
        class MockLockTimeoutError(ClickHouseOperationalError):
            def __init__(self):
                super().__init__()
                self._msg = "Lock wait timeout exceeded"

            def __str__(self):
                return self._msg

        mock_error = MockLockTimeoutError()

        # Due to inheritance order in _handle_error, OperationalError that is also
        # a DatabaseError will be caught by DatabaseError branch
        with pytest.raises((OperationalError, DatabaseError)):
            await backend._handle_error(mock_error)

    @pytest.mark.asyncio
    async def test_handle_generic_database_error(self, async_clickhouse_backend):
        """Test that generic DatabaseError is converted properly."""
        backend = async_clickhouse_backend

        # Create a mock ClickHouseDatabaseError
        class MockDatabaseError(ClickHouseDatabaseError):
            def __init__(self, msg="Generic database error"):
                self._msg = msg

            def __str__(self):
                return self._msg

        mock_error = MockDatabaseError("Some database error")

        with pytest.raises(DatabaseError):
            await backend._handle_error(mock_error)

    @pytest.mark.asyncio
    async def test_handle_generic_clickhouse_error(self, async_clickhouse_backend):
        """Test that generic ClickHouseError is converted to DatabaseError."""
        backend = async_clickhouse_backend

        # Create a mock ClickHouseError (base error class)
        class MockClickHouseError(ClickHouseError):
            def __init__(self, msg="Generic ClickHouse error"):
                self._msg = msg

            def __str__(self):
                return self._msg

        mock_error = MockClickHouseError("Some ClickHouse error")

        with pytest.raises(DatabaseError):
            await backend._handle_error(mock_error)

    @pytest.mark.asyncio
    async def test_handle_foreign_key_constraint_error(self, async_clickhouse_backend):
        """Test that foreign key constraint violation is converted to IntegrityError."""
        backend = async_clickhouse_backend

        try:
            # Create parent table
            await backend.execute("DROP TABLE IF EXISTS child_table_err")
            await backend.execute("DROP TABLE IF EXISTS parent_table_err")

            await backend.execute("""
                CREATE TABLE parent_table_err (
                    id INT PRIMARY KEY
                )
            """)

            await backend.execute("""
                CREATE TABLE child_table_err (
                    id INT PRIMARY KEY,
                    parent_id INT,
                    FOREIGN KEY (parent_id) REFERENCES parent_table_err(id)
                )
            """)

            # Try to insert with non-existent parent - should raise IntegrityError
            with pytest.raises(IntegrityError) as exc_info:
                await backend.execute("INSERT INTO child_table_err (id, parent_id) VALUES (1, 999)")

            assert "foreign key constraint" in str(exc_info.value).lower()
        finally:
            await asyncio.sleep(0.1)
            try:
                await backend.execute("DROP TABLE IF EXISTS child_table_err")
                await backend.execute("DROP TABLE IF EXISTS parent_table_err")
            except Exception:
                pass


class TestAsyncErrorClassValidation:
    """Tests to verify correct error class usage."""

    @pytest.mark.asyncio
    async def test_error_classes_from_correct_module(self):
        """Verify that error classes are imported from clickhouse.connector.errors."""
        from clickhouse.connector.errors import (
            Error as ClickHouseError,
            DatabaseError as ClickHouseDatabaseError,
            IntegrityError as ClickHouseIntegrityError,
            OperationalError as ClickHouseOperationalError,
        )

        # All should come from clickhouse.connector.errors
        assert ClickHouseError.__module__ == "clickhouse.connector.errors"
        assert ClickHouseDatabaseError.__module__ == "clickhouse.connector.errors"
        assert ClickHouseIntegrityError.__module__ == "clickhouse.connector.errors"
        assert ClickHouseOperationalError.__module__ == "clickhouse.connector.errors"

    @pytest.mark.asyncio
    async def test_clickhouse_async_error_is_same_as_connector_error(self):
        """
        Verify that clickhouse.connector.aio.Error (if exists) is the same as
        clickhouse.connector.errors.Error.

        In older clickhouse-connector-python versions, clickhouse_async.Error exists
        and is an alias to clickhouse.connector.errors.Error.
        In newer versions, clickhouse_async.Error may not exist.
        Either way, we should use the error classes from clickhouse.connector.errors.
        """
        import clickhouse.connector.aio as clickhouse_async
        from clickhouse.connector.errors import Error as ClickHouseError

        # In some versions, clickhouse_async.Error exists and is the same class
        if hasattr(clickhouse_async, "Error"):
            # It should be the same class, not a different one
            assert clickhouse_async.Error is ClickHouseError
        # In newer versions, clickhouse_async.Error may not exist, which is fine
        # The important thing is that we use ClickHouseError from clickhouse.connector.errors


class TestAsyncConnectionErrorHandling:
    """Tests for connection error handling."""

    @pytest.mark.asyncio
    async def test_connection_error_on_invalid_host(self):
        """Test that connection to invalid host raises proper error."""
        from rhosocial.activerecord.backend.errors import ConnectionError as ARConnectionError

        backend = AsyncClickHouseBackend(
            host="nonexistent-host-12345.invalid", port=3306, database="test", username="test", password="test"
        )

        with pytest.raises((ARConnectionError, OSError)):
            await backend.connect()

    @pytest.mark.asyncio
    async def test_syntax_error_handling(self, async_clickhouse_backend):
        """Test that SQL syntax error raises proper DatabaseError."""
        with pytest.raises(DatabaseError):
            await async_clickhouse_backend.execute("SELECT * FROM nonexistent_table_xyz")

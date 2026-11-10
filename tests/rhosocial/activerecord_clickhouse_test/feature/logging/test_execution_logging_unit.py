# tests/rhosocial/activerecord_clickhouse_test/feature/logging/test_execution_logging_unit.py
"""Database-free coverage for ClickHouse execution logging.

The ClickHouse driver is not needed to import the changed modules, build a
backend, or drive ``execute_many`` against a fake connection. Only the error
classification cases construct real ``clickhouse_connect`` exceptions, so
those skip when the driver is not installed.
"""

import logging
from contextlib import contextmanager

import pytest

from rhosocial.activerecord.backend.errors import DatabaseError, IntegrityError
from rhosocial.activerecord.backend.impl.clickhouse.backend import ClickHouseBackend
from rhosocial.activerecord.backend.impl.clickhouse.cli import info as info_cli
from rhosocial.activerecord.backend.impl.clickhouse.config import ClickHouseConnectionConfig
from rhosocial.activerecord.backend.impl.clickhouse.mixins import (
    ClickHouseBackendMixin,
    ClickHouseTransactionMixin,
)
from rhosocial.activerecord.backend.impl.clickhouse.transaction import (
    ClickHouseTransactionManager,
)
from rhosocial.activerecord.backend.options import ExecutionOptions, StatementType
from rhosocial.activerecord.backend.transaction import IsolationLevel
from rhosocial.activerecord.logging.defaults import get_logger
from rhosocial.activerecord.logging.redaction import SensitiveValue

#: Sync and async ClickHouse backends share this logger; the backend name is
#: derived from the class name, not the module path.
CANONICAL_LOGGER = "rhosocial.activerecord.backend.clickhouse"

#: The CLI module keeps its own module-named logger.
CLI_LOGGER = "rhosocial.activerecord.backend.impl.clickhouse.cli.info"


class _FakeCursor:
    """Minimal DB-API cursor: executes, reports a row count, closes."""

    def __init__(self, execute_error=None):
        self.rowcount = 1
        self.execute_error = execute_error
        self.executed = []
        self.closed = False

    def execute(self, sql, params=None):
        if self.execute_error is not None:
            raise self.execute_error
        self.executed.append((sql, params))

    def fetchone(self):
        return (1,)

    def close(self):
        self.closed = True


class _FakeConnection:
    """Minimal connection whose first cursor serves the probe query.

    ``_get_cursor`` opens a probe cursor to verify the connection is alive and
    then returns a fresh cursor. The fake therefore lets the first cursor
    succeed and makes the second one raise when ``execute_error`` is set.
    """

    def __init__(self, execute_error=None):
        self.execute_error = execute_error
        self.cursors = []

    def cursor(self):
        error = self.execute_error if self.cursors else None
        cursor = _FakeCursor(error)
        self.cursors.append(cursor)
        return cursor

    def close(self):
        pass


class _ListHandler(logging.Handler):
    """Collect records emitted by one logger."""

    def __init__(self, records):
        super().__init__(logging.DEBUG)
        self._records = records

    def emit(self, record):
        self._records.append(record)


@contextmanager
def _capture_logger(logger):
    """Capture records on the logger itself, independent of propagation."""
    records = []
    handler = _ListHandler(records)
    previous_level = logger.level
    logger.addHandler(handler)
    logger.setLevel(logging.DEBUG)
    try:
        yield records
    finally:
        logger.removeHandler(handler)
        logger.setLevel(previous_level)


def _make_backend():
    """Build a backend without opening a connection."""
    return ClickHouseBackend(
        connection_config=ClickHouseConnectionConfig(
            host="localhost",
            database="test_db",
        )
    )


@pytest.fixture
def clickhouse_exceptions():
    """The driver exception types ``_handle_error`` classifies."""
    pytest.importorskip("clickhouse_connect")
    from clickhouse_connect.driver.exceptions import (
        DatabaseError as ClickHouseDatabaseError,
        IntegrityError as ClickHouseIntegrityError,
    )

    return {
        "database": ClickHouseDatabaseError,
        "integrity": ClickHouseIntegrityError,
    }


class TestChangedModulesImport:
    """Importing the changed modules records their import-time lines."""

    def test_changed_modules_are_imported(self):
        assert issubclass(ClickHouseBackend, ClickHouseBackendMixin)
        assert issubclass(ClickHouseTransactionManager, ClickHouseTransactionMixin)
        assert info_cli.logger is get_logger(info_cli.__name__)


class TestBackendLogger:
    def test_backend_uses_canonical_clickhouse_logger(self):
        backend = _make_backend()

        assert backend._get_logger_name() == CANONICAL_LOGGER
        assert backend.logger.name == CANONICAL_LOGGER
        assert isinstance(backend.transaction_manager, ClickHouseTransactionManager)


class TestExecuteMany:
    def test_execute_many_logs_batch_and_unwraps_sensitive_values(self):
        backend = _make_backend()
        backend._connection = _FakeConnection()
        params_list = [(1, "alpha"), (SensitiveValue("secret"), "beta")]

        with _capture_logger(backend.logger) as records:
            result = backend.execute_many("INSERT INTO t VALUES (%s, %s)", params_list)

        assert result.affected_rows == 2
        assert result.duration >= 0
        # The wrapped value reaches the driver unwrapped, never as a wrapper.
        assert backend._connection.cursors[-1].executed == [
            ("INSERT INTO t VALUES (%s, %s)", (1, "alpha")),
            ("INSERT INTO t VALUES (%s, %s)", ("secret", "beta")),
        ]
        assert backend._connection.cursors[-1].closed is True

        debug_messages = [
            record.getMessage()
            for record in records
            if record.name == CANONICAL_LOGGER and record.levelno == logging.DEBUG
        ]
        assert any("parameter_sets: 2" in message for message in debug_messages)

        summaries = [
            record for record in records if getattr(record, "event", None) == "dml.batch"
        ]
        assert summaries
        fields = summaries[-1].activerecord
        assert fields["rows_affected"] == 2
        assert fields["parameter_sets"] == 2

    def test_execute_many_accepts_explicit_options(self):
        backend = _make_backend()
        backend._connection = _FakeConnection()

        result = backend.execute_many(
            "INSERT INTO t VALUES (%s)",
            [(1,), (2,)],
            options=ExecutionOptions(stmt_type=StatementType.DML),
        )

        assert result.affected_rows == 2

    def test_execute_many_error_branch_logs_and_maps_null_error(self, clickhouse_exceptions):
        backend = _make_backend()
        null_error = clickhouse_exceptions["database"](
            "Cannot convert NULL to a non-nullable type"
        )
        backend._connection = _FakeConnection(execute_error=null_error)

        with _capture_logger(backend.logger) as records:
            with pytest.raises(IntegrityError, match="cannot be null"):
                backend.execute_many("INSERT INTO t VALUES (%s)", [(None,)])

        failures = [
            record.getMessage()
            for record in records
            if "Query failed, exception will be re-raised" in record.getMessage()
        ]
        assert failures
        assert backend._connection.cursors[-1].closed is True


class TestHandleError:
    def test_generic_database_error_maps_to_database_error(self, clickhouse_exceptions):
        backend = _make_backend()
        error = clickhouse_exceptions["database"]("Syntax error near FROM")

        with pytest.raises(DatabaseError, match="Syntax error near FROM"):
            backend._handle_error(error)

    def test_null_to_non_nullable_maps_to_integrity_error(self, clickhouse_exceptions):
        backend = _make_backend()
        error = clickhouse_exceptions["database"](
            "Cannot convert NULL to a non-nullable type"
        )

        with pytest.raises(IntegrityError, match="cannot be null"):
            backend._handle_error(error)

    def test_driver_integrity_error_maps_to_integrity_error(self, clickhouse_exceptions):
        backend = _make_backend()
        error = clickhouse_exceptions["integrity"]("Violates unique constraint")

        with pytest.raises(IntegrityError, match="Unique constraint violation"):
            backend._handle_error(error)


class TestIsolationLevelLogging:
    def test_isolation_level_setter_logs_debug(self):
        backend = _make_backend()
        manager = backend.transaction_manager

        with _capture_logger(manager.logger) as records:
            manager.isolation_level = IsolationLevel.READ_COMMITTED

        assert manager.isolation_level is IsolationLevel.READ_COMMITTED
        messages = [
            record.getMessage()
            for record in records
            if record.name == CANONICAL_LOGGER
        ]
        assert any("Setting isolation level to" in message for message in messages)
        assert any("Isolation level set to" in message for message in messages)


class TestCliLogger:
    def test_cli_info_uses_module_logger(self):
        assert isinstance(info_cli.logger, logging.Logger)
        assert info_cli.logger.name == CLI_LOGGER

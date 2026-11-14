# tests/rhosocial/activerecord_clickhouse_test/feature/backend/construct/errors/test_driver_error_mapping.py
"""ClickHouse driver exceptions map to semantic error categories.

Only synthetic driver exceptions are constructed; no ClickHouse server is
touched. The codes come from the ``code`` keyword accepted by
clickhouse-connect 1.7.x ``Error`` classes, mirroring ClickHouse's
ErrorCodes.cpp. The whole module skips when the driver is not installed.
"""

import pytest

clickhouse_errors = pytest.importorskip("clickhouse_connect.driver.exceptions")

from rhosocial.activerecord.backend.errors import (  # noqa: E402
    ConcurrencyError,
    ConnectionError,
    DataError,
    DatabaseError,
    InfrastructureError,
    IntegrityError,
    OperationalError,
    QueryError,
)
from rhosocial.activerecord.backend.impl.clickhouse.backend import (  # noqa: E402
    ClickHouseBackend,
)
from rhosocial.activerecord.backend.impl.clickhouse.config import (  # noqa: E402
    ClickHouseConnectionConfig,
)


@pytest.fixture
def backend():
    """A backend that never connects: mapping is pure classification."""
    return ClickHouseBackend(
        connection_config=ClickHouseConnectionConfig(host="localhost", database="db")
    )


def _translated(backend, error):
    with pytest.raises(DatabaseError) as info:
        backend._handle_error(error)
    return info.value


def test_unique_constraint_maps_to_integrity(backend):
    error = clickhouse_errors.IntegrityError("Violates unique constraint users_email")

    translated = _translated(backend, error)

    assert isinstance(translated, IntegrityError)
    assert isinstance(translated, DataError)
    assert translated.backend == "clickhouse"
    assert translated.operation == "execute"
    assert translated.retryable is False


def test_duplicate_object_code_maps_to_integrity(backend):
    error = clickhouse_errors.DatabaseError(
        "Table db.users already exists",
        code=57,
        name="TABLE_ALREADY_EXISTS",
    )

    translated = _translated(backend, error)

    assert isinstance(translated, IntegrityError)
    assert translated.driver_code == 57


def test_null_to_non_nullable_maps_to_integrity(backend):
    error = clickhouse_errors.DatabaseError(
        "Cannot convert NULL to a non-nullable type",
        code=70,
        name="CANNOT_CONVERT_TYPE",
    )

    translated = _translated(backend, error)

    assert isinstance(translated, IntegrityError)
    assert "cannot be null" in str(translated)
    assert translated.driver_code == 70


def test_timeout_maps_to_transient_operational_error(backend):
    error = clickhouse_errors.OperationalError(
        "Timeout exceeded: max_execution_time",
        code=159,
        name="TIMEOUT_EXCEEDED",
    )

    translated = _translated(backend, error)

    assert isinstance(translated, OperationalError)
    assert isinstance(translated, InfrastructureError)
    assert translated.transient is True
    assert translated.retryable is True
    assert translated.driver_code == 159


def test_concurrency_limit_is_transient_infrastructure(backend):
    error = clickhouse_errors.DatabaseError(
        "Too many simultaneous queries",
        code=202,
        name="TOO_MANY_SIMULTANEOUS_QUERIES",
    )

    translated = _translated(backend, error)

    assert isinstance(translated, OperationalError)
    assert not isinstance(translated, ConcurrencyError)
    assert translated.transient is True
    assert translated.retryable is True


def test_memory_limit_is_transient_infrastructure(backend):
    error = clickhouse_errors.DatabaseError(
        "Memory limit exceeded",
        code=241,
        name="MEMORY_LIMIT_EXCEEDED",
    )

    translated = _translated(backend, error)

    assert isinstance(translated, OperationalError)
    assert translated.transient is True


def test_unknown_table_maps_to_query_error(backend):
    error = clickhouse_errors.DatabaseError(
        "Table db.missing doesn't exist",
        code=60,
        name="UNKNOWN_TABLE",
    )

    translated = _translated(backend, error)

    assert isinstance(translated, QueryError)
    assert translated.driver_code == 60
    assert translated.retryable is False


def test_unknown_column_maps_to_query_error(backend):
    error = clickhouse_errors.DatabaseError(
        "Unknown identifier users.missing",
        code=47,
        name="UNKNOWN_IDENTIFIER",
    )

    translated = _translated(backend, error)

    assert isinstance(translated, QueryError)
    assert translated.driver_code == 47


def test_syntax_error_maps_to_query_error(backend):
    error = clickhouse_errors.DatabaseError(
        "Syntax error near FROM",
        code=62,
        name="SYNTAX_ERROR",
    )

    translated = _translated(backend, error)

    assert isinstance(translated, QueryError)
    assert translated.driver_code == 62


def test_authentication_failure_is_not_retryable(backend):
    error = clickhouse_errors.OperationalError(
        "default: Authentication failed",
        code=516,
        name="AUTHENTICATION_FAILED",
    )

    translated = _translated(backend, error)

    assert isinstance(translated, ConnectionError)
    assert isinstance(translated, InfrastructureError)
    assert translated.transient is False
    assert translated.retryable is False
    assert translated.driver_code == 516


def test_connection_loss_is_transient(backend):
    error = clickhouse_errors.OperationalError("Connection refused by server")

    translated = _translated(backend, error)

    assert isinstance(translated, OperationalError)
    assert translated.transient is True
    assert translated.retryable is True


def test_generic_database_error_falls_back(backend):
    error = clickhouse_errors.DatabaseError("Something odd happened")

    translated = _translated(backend, error)

    assert isinstance(translated, DatabaseError)
    assert not isinstance(
        translated,
        (IntegrityError, QueryError, OperationalError, ConcurrencyError),
    )
    assert translated.operation == "execute"
    assert translated.backend == "clickhouse"


def test_generic_driver_error_falls_back(backend):
    error = clickhouse_errors.Error("Something odd happened")

    translated = _translated(backend, error)

    assert isinstance(translated, DatabaseError)
    assert not isinstance(translated, DataError)


def test_non_driver_exception_is_reraised(backend):
    error = ValueError("local validation only")

    with pytest.raises(ValueError, match="local validation only"):
        backend._handle_error(error)

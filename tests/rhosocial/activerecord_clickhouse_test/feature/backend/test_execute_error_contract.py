# tests/rhosocial/activerecord_clickhouse_test/feature/backend/test_execute_error_contract.py
"""ClickHouse ``execute`` phases follow the core error contract.

``ExecutionMixin.execute`` is patched so the retry loop sees the framework
errors the real pipeline produces, and a fake connection covers the commit and
close phases. No ClickHouse server is contacted; the module skips when the
driver is not installed.

Note: ClickHouse has no deadlock detector, so the "lock wait" case of the
contract becomes a server timeout (``OperationalError(transient=True)``).
"""

import pytest

pytest.importorskip("clickhouse_connect")

from clickhouse_connect.driver.exceptions import (  # noqa: E402
    DatabaseError as ClickHouseDatabaseError,
    OperationalError as ClickHouseOperationalError,
)

from rhosocial.activerecord.backend.base.execution import ExecutionMixin  # noqa: E402
from rhosocial.activerecord.backend.errors import (  # noqa: E402
    ConnectionError,
    OperationalError,
    QueryError,
    TransactionError,
    attach_diagnostics,
)
from rhosocial.activerecord.backend.impl.clickhouse.backend import (  # noqa: E402
    ClickHouseBackend,
)
from rhosocial.activerecord.backend.impl.clickhouse.config import (  # noqa: E402
    ClickHouseConnectionConfig,
)
from rhosocial.activerecord.backend.result import QueryResult  # noqa: E402


class _FakeCursor:
    """DB-API cursor that records calls and can fail on purpose."""

    def __init__(self, *, execute_error=None, close_error=None):
        self.execute_error = execute_error
        self.close_error = close_error
        self.rowcount = 1
        self.lastrowid = None
        self.description = None
        self.executed = []
        self.closed = False

    def execute(self, sql, params=None, settings=None):  # noqa: ARG002
        if self.execute_error is not None:
            raise self.execute_error
        self.executed.append((sql, params))

    def fetchone(self):
        return (1,)

    def close(self):
        self.closed = True
        if self.close_error is not None:
            raise self.close_error


class _FakeConnection:
    """Connection whose first cursor serves the liveness probe.

    ``_get_cursor`` spends one cursor on the probe query and then opens the
    cursor the caller uses, so the configured failures apply from the second
    cursor onward.
    """

    def __init__(self, *, execute_error=None, close_error=None, commit_error=None):
        self.execute_error = execute_error
        self.close_error = close_error
        self.commit_error = commit_error
        self.cursors = []
        self.commits = 0

    def cursor(self):
        first = not self.cursors
        cursor = _FakeCursor(
            execute_error=None if first else self.execute_error,
            close_error=None if first else self.close_error,
        )
        self.cursors.append(cursor)
        return cursor

    def commit(self):
        self.commits += 1
        if self.commit_error is not None:
            raise self.commit_error

    def close(self):
        pass


def _make_backend(*, autocommit: bool = True) -> ClickHouseBackend:
    """Build a backend without opening a connection."""
    return ClickHouseBackend(
        connection_config=ClickHouseConnectionConfig(
            host="localhost",
            database="test_db",
            autocommit=autocommit,
        )
    )


@pytest.fixture
def backend():
    return _make_backend()


@pytest.fixture
def transient_error():
    """A framework error the retry loop is allowed to retry."""
    return attach_diagnostics(
        OperationalError("Timeout exceeded while waiting for server response"),
        operation="execute",
        backend="clickhouse",
        transient=True,
    )


@pytest.fixture
def patched_execution(monkeypatch):
    """Replace the core pipeline so only the retry loop is under test.

    Returns a helper that installs a script of outcomes (error or result).
    """

    def install(outcomes):
        calls = []

        def fake_execute(self, sql, params=None, *, options=None):  # noqa: ARG001
            calls.append(sql)
            outcome = outcomes[min(len(calls) - 1, len(outcomes) - 1)]
            if isinstance(outcome, BaseException):
                raise outcome
            return outcome

        monkeypatch.setattr(ExecutionMixin, "execute", fake_execute)
        return calls

    return install


@pytest.fixture
def reconnects(monkeypatch, backend):
    """Record ``_reconnect`` calls; returns the recording list."""
    recorded = []

    def fake_reconnect():
        recorded.append(True)
        return True

    monkeypatch.setattr(backend, "_reconnect", fake_reconnect)
    return recorded


class TestExecuteRetry:
    """Retries depend on ``error.transient``, not on driver exception types."""

    def test_transient_error_reconnects_then_retries(self, backend, patched_execution, reconnects,
                                                     transient_error):
        calls = patched_execution([transient_error, QueryResult(affected_rows=1, duration=0.0)])

        result = backend.execute("INSERT INTO t VALUES (1)")

        assert result.affected_rows == 1
        assert len(calls) == 2
        assert reconnects == [True]

    def test_non_transient_error_is_not_retried(self, backend, patched_execution, reconnects):
        error = ConnectionError("Authentication failed for user default")
        calls = patched_execution([error])

        with pytest.raises(ConnectionError) as info:
            backend.execute("SELECT 1")

        assert info.value is error
        assert len(calls) == 1
        assert reconnects == []

    def test_transient_connection_error_is_retried(self, backend, patched_execution, reconnects):
        error = attach_diagnostics(
            ConnectionError("Network unreachable"),
            operation="connect",
            backend="clickhouse",
            transient=True,
        )
        calls = patched_execution([error, QueryResult(affected_rows=0, duration=0.0)])

        result = backend.execute("SELECT 1")

        assert result.affected_rows == 0
        assert len(calls) == 2
        assert reconnects == [True]

    def test_retries_exhausted_raise_original_error_unchanged(self, backend, patched_execution,
                                                              reconnects, transient_error):
        calls = patched_execution([transient_error])

        with pytest.raises(OperationalError) as info:
            backend.execute("SELECT 1", max_retries=2)

        assert info.value is transient_error
        assert len(calls) == 3
        assert len(reconnects) == 2

    def test_failed_reconnect_stops_retrying(self, backend, patched_execution, reconnects,
                                             transient_error, monkeypatch):
        calls = patched_execution([transient_error])
        monkeypatch.setattr(backend, "_reconnect", lambda: False)

        with pytest.raises(OperationalError) as info:
            backend.execute("SELECT 1")

        assert info.value is transient_error
        assert len(calls) == 1


class TestAutoCommit:
    """A failed commit is reported, never swallowed."""

    def test_commit_failure_raises_transaction_error(self, monkeypatch):
        commit_error = RuntimeError("commit rejected by server")
        backend = _make_backend(autocommit=False)
        backend._connection = _FakeConnection(commit_error=commit_error)

        with pytest.raises(TransactionError) as info:
            backend.execute("INSERT INTO t VALUES (1)")

        assert "Auto-commit failed" in str(info.value)
        assert info.value.__cause__ is commit_error
        assert backend._connection.commits == 1

    def test_autocommit_enabled_skips_commit(self, backend):
        backend._connection = _FakeConnection()

        result = backend.execute("INSERT INTO t VALUES (1)")

        assert result.affected_rows == 1
        assert backend._connection.commits == 0


class TestExecuteMany:
    """``execute_many`` uses the same taxonomy and commit contract as ``execute``."""

    def test_timeout_maps_to_transient_operational_error(self, backend):
        driver_error = ClickHouseOperationalError(
            "Timeout exceeded while reading from socket",
            code=159,
            name="TIMEOUT_EXCEEDED",
        )
        backend._connection = _FakeConnection(execute_error=driver_error)

        with pytest.raises(OperationalError) as info:
            backend.execute_many("INSERT INTO t VALUES (%s)", [(1,), (2,)])

        assert info.value.transient is True
        assert info.value.driver_code == 159
        assert info.value.backend == "clickhouse"

    def test_commit_failure_raises_transaction_error(self, monkeypatch):
        commit_error = RuntimeError("commit rejected by server")
        backend = _make_backend(autocommit=False)
        backend._connection = _FakeConnection(commit_error=commit_error)

        with pytest.raises(TransactionError) as info:
            backend.execute_many("INSERT INTO t VALUES (%s)", [(1,), (2,)])

        assert "Auto-commit failed" in str(info.value)
        assert info.value.__cause__ is commit_error

    def test_close_failure_does_not_replace_original_error(self, backend):
        syntax_error = ClickHouseDatabaseError(
            "Syntax error near FROM",
            code=62,
            name="SYNTAX_ERROR",
        )
        backend._connection = _FakeConnection(
            execute_error=syntax_error,
            close_error=RuntimeError("cursor close failed"),
        )

        with pytest.raises(QueryError, match="Syntax error near FROM"):
            backend.execute_many("INSERT INTO t VALUES (%s)", [(1,)])

        # The close was attempted, and its failure stayed out of the way.
        assert backend._connection.cursors[-1].closed is True


class TestHandleError:
    """A framework error is translated once, never a second time."""

    def test_framework_error_is_raised_unchanged(self, backend):
        error = attach_diagnostics(
            QueryError("already translated"),
            operation="execute",
            backend="clickhouse",
        )

        with pytest.raises(QueryError) as info:
            backend._handle_error(error)

        assert info.value is error
        assert type(info.value) is QueryError
        assert info.value.operation == "execute"

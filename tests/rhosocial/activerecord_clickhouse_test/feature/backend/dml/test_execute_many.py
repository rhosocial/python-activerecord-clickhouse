# tests/rhosocial/activerecord_clickhouse_test/feature/backend/dml/test_execute_many.py
"""Synchronous ClickHouse backend ``execute_many`` batch semantics.

Verifies total affected-row accounting for a batch INSERT and the noop
behaviour for an empty parameter list, mirroring the shared execute-many
contract across backend repos.
"""

import pytest

from rhosocial.activerecord.backend.options import ExecutionOptions
from rhosocial.activerecord.backend.schema import StatementType


class TestExecuteMany:
    """ClickHouse ``execute_many`` batch behaviour."""

    @pytest.fixture
    def batch_table(self, clickhouse_backend):
        """Create (and later drop) a scratch table for batch inserts."""
        backend = clickhouse_backend
        backend.execute("DROP TABLE IF EXISTS test_execute_many", options=ExecutionOptions(stmt_type=StatementType.DDL))
        backend.execute(
            "CREATE TABLE test_execute_many (name String) ENGINE = Memory",
            options=ExecutionOptions(stmt_type=StatementType.DDL),
        )
        yield "test_execute_many"
        backend.execute("DROP TABLE IF EXISTS test_execute_many", options=ExecutionOptions(stmt_type=StatementType.DDL))

    def test_batch_insert_reports_total_affected_rows(self, clickhouse_backend, batch_table):
        """Batch INSERT should report every affected row and persist them all."""
        sql = f"INSERT INTO {batch_table} (name) VALUES (%s)"
        params_list = [(f"row_{i}",) for i in range(5)]
        result = clickhouse_backend.execute_many(sql, params_list)
        assert result.affected_rows == 5, "batch insert should report all 5 affected rows"

        count = clickhouse_backend.fetch_one(f"SELECT count() AS c FROM {batch_table}")
        assert count is not None and count["c"] == 5, "all 5 rows should be persisted"

    def test_empty_params_list_is_noop(self, clickhouse_backend, batch_table):
        """An empty parameter list should insert nothing and not error."""
        result = clickhouse_backend.execute_many(f"INSERT INTO {batch_table} (name) VALUES (%s)", [])
        assert result is not None, "execute_many should return a QueryResult even for an empty batch"
        assert result.affected_rows == 0, "empty batch should affect no rows"

        count = clickhouse_backend.fetch_one(f"SELECT count() AS c FROM {batch_table}")
        assert count is not None and count["c"] == 0, "no rows should exist after an empty batch"
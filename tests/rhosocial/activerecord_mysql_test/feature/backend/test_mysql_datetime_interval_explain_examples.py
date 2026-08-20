# tests/rhosocial/activerecord_clickhouse_test/feature/backend/test_clickhouse_datetime_interval_explain_examples.py
"""ClickHouse EXPLAIN examples for datetime interval expressions and indexes."""

import pytest
import pytest_asyncio

from rhosocial.activerecord.backend.expression import (
    Column,
    ComparisonPredicate,
    Literal,
    LogicalPredicate,
    QueryExpression,
    TableExpression,
)
from rhosocial.activerecord.backend.expression.functions import (
    date_add,
    date_diff,
    date_sub,
    extract,
)
from rhosocial.activerecord.backend.expression.query_parts import OrderByClause
from rhosocial.activerecord.backend.impl.clickhouse import ClickHouseExplainResult
from rhosocial.activerecord.backend.options import ExecutionOptions
from rhosocial.activerecord.backend.schema import StatementType


_SETUP_SQL = """
    DROP TABLE IF EXISTS explain_temporal_events;

    CREATE TABLE explain_temporal_events (
        id INT NOT NULL AUTO_INCREMENT PRIMARY KEY,
        category VARCHAR(32) NOT NULL,
        created_at DATETIME NOT NULL,
        started_at DATETIME NOT NULL,
        ended_at DATETIME NOT NULL,
        INDEX idx_temporal_created_at (created_at),
        INDEX idx_temporal_started_ended (started_at, ended_at),
        INDEX idx_temporal_category_created (category, created_at)
    ) ENGINE=InnoDB;

    INSERT INTO explain_temporal_events (category, created_at, started_at, ended_at)
    WITH RECURSIVE seq AS (
        SELECT 0 AS n
        UNION ALL
        SELECT n + 1 FROM seq WHERE n < 119
    )
    SELECT
        CASE
            WHEN n IN (55, 58, 62) THEN 'deploy'
            WHEN MOD(n, 3) = 0 THEN 'billing'
            WHEN MOD(n, 3) = 1 THEN 'report'
            ELSE 'maintenance'
        END,
        TIMESTAMP('2026-01-01 00:00:00') + INTERVAL n DAY,
        TIMESTAMP('2026-01-01 00:00:00') + INTERVAL n DAY + INTERVAL 10 MINUTE,
        TIMESTAMP('2026-01-01 00:00:00') + INTERVAL n DAY + INTERVAL 40 MINUTE
    FROM seq;
"""

_CLEANUP_SQL = "DROP TABLE IF EXISTS explain_temporal_events;"
_DQL_OPTIONS = ExecutionOptions(stmt_type=StatementType.DQL)
_INDEX_USAGES = {"index_with_lookup", "covering_index"}


@pytest.fixture(scope="function")
def temporal_indexed_backend(clickhouse_backend_single):
    if not clickhouse_backend_single.dialect.supports_recursive_cte():
        pytest.skip("ClickHouse version does not support recursive CTEs (8.0+)")
    clickhouse_backend_single.executescript(_SETUP_SQL)
    yield clickhouse_backend_single
    try:
        clickhouse_backend_single.executescript(_CLEANUP_SQL)
    except Exception:
        pass


@pytest_asyncio.fixture(scope="function")
async def async_temporal_indexed_backend(async_clickhouse_backend):
    if not async_clickhouse_backend.dialect.supports_recursive_cte():
        pytest.skip("ClickHouse version does not support recursive CTEs (8.0+)")
    await async_clickhouse_backend.executescript(_SETUP_SQL)
    yield async_clickhouse_backend
    try:
        await async_clickhouse_backend.executescript(_CLEANUP_SQL)
    except Exception:
        pass


def _row_keys(result: ClickHouseExplainResult) -> set:
    return {row.key for row in result.rows if row.key}


def _range_filter(dialect, column_name: str, start: str, end: str):
    return LogicalPredicate(
        dialect,
        "AND",
        ComparisonPredicate(dialect, ">=", Column(dialect, column_name), Literal(dialect, start)),
        ComparisonPredicate(dialect, "<", Column(dialect, column_name), Literal(dialect, end)),
    )


def _category_created_filter(dialect):
    return LogicalPredicate(
        dialect,
        "AND",
        ComparisonPredicate(dialect, "=", Column(dialect, "category"), Literal(dialect, "deploy")),
        _range_filter(
            dialect,
            "created_at",
            "2026-02-20 00:00:00",
            "2026-03-10 00:00:00",
        ),
    )


def _datetime_expression_query(dialect):
    return QueryExpression(
        dialect,
        select=[
            Column(dialect, "id"),
            extract(dialect, "year", Column(dialect, "created_at")).as_("created_year"),
            date_add(dialect, Column(dialect, "started_at"), 30, "minute").as_("starts_plus_30m"),
            date_sub(dialect, Column(dialect, "ended_at"), 1, "hour").as_("ended_minus_1h"),
            date_diff(dialect, "minute", Column(dialect, "started_at"), Column(dialect, "ended_at")).as_(
                "duration_minutes"
            ),
        ],
        from_=TableExpression(dialect, "explain_temporal_events"),
        where=_category_created_filter(dialect),
        order_by=OrderByClause(
            dialect,
            [(Column(dialect, "category"), "ASC"), (Column(dialect, "created_at"), "ASC")],
        ),
    )


class TestSyncClickHouseDateTimeIntervalExplainExamples:
    def test_created_at_range_uses_datetime_index(self, temporal_indexed_backend):
        dialect = temporal_indexed_backend.dialect
        result = temporal_indexed_backend.explain(
            QueryExpression(
                dialect,
                select=[Column(dialect, "id"), Column(dialect, "created_at")],
                from_=TableExpression(dialect, "explain_temporal_events"),
                where=_range_filter(
                    dialect,
                    "created_at",
                    "2026-02-20 00:00:00",
                    "2026-03-10 00:00:00",
                ),
            )
        )

        assert isinstance(result, ClickHouseExplainResult)
        assert result.analyze_index_usage() in _INDEX_USAGES
        assert result.is_index_used is True
        assert result.is_full_scan is False
        assert _row_keys(result) & {"idx_temporal_created_at", "idx_temporal_category_created"}

    def test_category_created_range_uses_composite_datetime_index(self, temporal_indexed_backend):
        dialect = temporal_indexed_backend.dialect
        result = temporal_indexed_backend.explain(
            QueryExpression(
                dialect,
                select=[
                    Column(dialect, "id"),
                    Column(dialect, "category"),
                    Column(dialect, "created_at"),
                ],
                from_=TableExpression(dialect, "explain_temporal_events"),
                where=_category_created_filter(dialect),
            )
        )

        assert result.analyze_index_usage() in _INDEX_USAGES
        assert result.is_index_used is True
        assert result.is_full_scan is False
        assert "idx_temporal_category_created" in _row_keys(result)

    def test_covering_datetime_index_query_is_detected(self, temporal_indexed_backend):
        dialect = temporal_indexed_backend.dialect
        result = temporal_indexed_backend.explain(
            QueryExpression(
                dialect,
                select=[Column(dialect, "category"), Column(dialect, "created_at")],
                from_=TableExpression(dialect, "explain_temporal_events"),
                where=_category_created_filter(dialect),
            )
        )

        assert result.analyze_index_usage() in _INDEX_USAGES
        assert result.is_index_used is True
        assert result.is_full_scan is False
        assert "idx_temporal_category_created" in _row_keys(result)

    def test_datetime_interval_expressions_work_with_indexed_filter(self, temporal_indexed_backend):
        dialect = temporal_indexed_backend.dialect
        query = _datetime_expression_query(dialect)

        explain_result = temporal_indexed_backend.explain(query)
        assert explain_result.analyze_index_usage() in _INDEX_USAGES
        assert explain_result.is_index_used is True
        assert "idx_temporal_category_created" in _row_keys(explain_result)

        query_result = temporal_indexed_backend.execute(
            *query.to_sql(),
            options=_DQL_OPTIONS,
        )
        rows = query_result.data

        assert rows is not None
        assert len(rows) == 3
        assert rows[0]["created_year"] == 2026
        assert rows[0]["duration_minutes"] == 30
        assert rows[0]["starts_plus_30m"] is not None
        assert rows[0]["ended_minus_1h"] is not None


class TestAsyncClickHouseDateTimeIntervalExplainExamples:
    @pytest.mark.asyncio
    async def test_category_created_range_uses_composite_datetime_index(self, async_temporal_indexed_backend):
        dialect = async_temporal_indexed_backend.dialect
        result = await async_temporal_indexed_backend.explain(
            QueryExpression(
                dialect,
                select=[
                    Column(dialect, "id"),
                    Column(dialect, "category"),
                    Column(dialect, "created_at"),
                ],
                from_=TableExpression(dialect, "explain_temporal_events"),
                where=_category_created_filter(dialect),
            )
        )

        assert result.is_index_used is True
        assert result.is_full_scan is False
        assert "idx_temporal_category_created" in _row_keys(result)

    @pytest.mark.asyncio
    async def test_datetime_interval_expressions_work_with_indexed_filter(self, async_temporal_indexed_backend):
        dialect = async_temporal_indexed_backend.dialect
        query = _datetime_expression_query(dialect)

        explain_result = await async_temporal_indexed_backend.explain(query)
        assert explain_result.is_index_used is True
        assert "idx_temporal_category_created" in _row_keys(explain_result)

        query_result = await async_temporal_indexed_backend.execute(
            *query.to_sql(),
            options=_DQL_OPTIONS,
        )
        rows = query_result.data

        assert rows is not None
        assert len(rows) == 3
        assert rows[0]["created_year"] == 2026
        assert rows[0]["duration_minutes"] == 30

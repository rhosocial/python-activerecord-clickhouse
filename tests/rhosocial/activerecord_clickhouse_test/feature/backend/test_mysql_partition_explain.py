# tests/rhosocial/activerecord_clickhouse_test/feature/backend/test_clickhouse_partition_explain.py
"""Real ClickHouse EXPLAIN tests for partitioned tables."""

from __future__ import annotations

from datetime import datetime
from typing import Optional

import pytest

from rhosocial.activerecord.backend.expression import (
    Column,
    ColumnDefinition,
    ColumnConstraint,
    ColumnConstraintType,
    CreateTableExpression,
    DropTableExpression,
    IndexDefinition,
    InsertExpression,
    Literal,
    QueryExpression,
    TableExpression,
    ValuesSource,
    WildcardExpression,
)
from rhosocial.activerecord.backend.expression.types import BigIntType, DateTimeType, VarCharType
from rhosocial.activerecord.backend.impl.clickhouse import ClickHouseExplainResult, ClickHouseExplainRow
from rhosocial.activerecord.backend.impl.clickhouse.expression import (
    ClickHousePartitionByRangeColumns,
    ClickHousePartitionDefinition,
    ClickHousePartitionValue,
)


PARTITION_EXPLAIN_TABLE = "ar_clickhouse_partition_explain_events"


def _partition_value(dialect, value):
    return ClickHousePartitionValue(dialect, value)


def _drop_partition_explain_table_expression(dialect):
    return DropTableExpression(dialect=dialect, table=PARTITION_EXPLAIN_TABLE, if_exists=True)


def _create_partition_explain_table_expression(dialect):
    return CreateTableExpression(
        dialect=dialect,
        table=PARTITION_EXPLAIN_TABLE,
        columns=[
            ColumnDefinition("id", BigIntType(), constraints=[ColumnConstraint(ColumnConstraintType.NOT_NULL)]),
            ColumnDefinition("tenant_id", BigIntType(), constraints=[ColumnConstraint(ColumnConstraintType.NOT_NULL)]),
            ColumnDefinition("created_at", DateTimeType(), constraints=[ColumnConstraint(ColumnConstraintType.NOT_NULL)]),
            ColumnDefinition("payload", VarCharType(255)),
        ],
        indexes=[
            IndexDefinition(name="idx_created_at", columns=["created_at"]),
            IndexDefinition(
                name="idx_tenant_created_at",
                columns=["tenant_id", "created_at"],
            ),
            IndexDefinition(name="idx_id", columns=["id"]),
        ],
        partition=ClickHousePartitionByRangeColumns(
            dialect=dialect,
            keys=[Column(dialect, "created_at")],
            partitions=[
                ClickHousePartitionDefinition(
                    name="p2026_01",
                    less_than=[_partition_value(dialect, "2026-02-01")],
                ),
                ClickHousePartitionDefinition(
                    name="p2026_02",
                    less_than=[_partition_value(dialect, "2026-03-01")],
                ),
                ClickHousePartitionDefinition(
                    name="p2026_03",
                    less_than=[_partition_value(dialect, "2026-04-01")],
                ),
            ],
        ),
    )


def _seed_partition_explain_rows_expression(dialect):
    rows = [
        [1, 100, datetime(2026, 1, 15), "jan"],
        [2, 100, datetime(2026, 2, 15), "feb"],
        [3, 200, datetime(2026, 3, 15), "mar"],
    ]
    return InsertExpression(
        dialect=dialect,
        into=PARTITION_EXPLAIN_TABLE,
        columns=["id", "tenant_id", "created_at", "payload"],
        source=ValuesSource(
            dialect,
            [[Literal(dialect, value) for value in row] for row in rows],
        ),
    )


def _partition_range_query_expression(dialect, start, end):
    return QueryExpression(
        dialect,
        select=[WildcardExpression(dialect)],
        from_=TableExpression(dialect, PARTITION_EXPLAIN_TABLE),
        where=(Column(dialect, "created_at") >= Literal(dialect, start))
        & (Column(dialect, "created_at") < Literal(dialect, end)),
    )


def _full_scan_query_expression(dialect):
    return QueryExpression(
        dialect,
        select=[WildcardExpression(dialect)],
        from_=TableExpression(dialect, PARTITION_EXPLAIN_TABLE),
    )


def _drop_partition_explain_table(backend):
    backend.execute(*_drop_partition_explain_table_expression(backend.dialect).to_sql())


async def _async_drop_partition_explain_table(backend):
    await backend.execute(*_drop_partition_explain_table_expression(backend.dialect).to_sql())


def _create_partition_explain_table(backend):
    _drop_partition_explain_table(backend)
    backend.execute(*_create_partition_explain_table_expression(backend.dialect).to_sql())


async def _async_create_partition_explain_table(backend):
    await _async_drop_partition_explain_table(backend)
    await backend.execute(*_create_partition_explain_table_expression(backend.dialect).to_sql())


def _seed_partition_explain_rows(backend):
    backend.execute(*_seed_partition_explain_rows_expression(backend.dialect).to_sql())


async def _async_seed_partition_explain_rows(backend):
    await backend.execute(*_seed_partition_explain_rows_expression(backend.dialect).to_sql())


def _split_partitions(value: Optional[str]) -> list[str]:
    if not value:
        return []
    return [partition.strip() for partition in str(value).split(",") if partition.strip()]


def _collect_explain_partitions(result: ClickHouseExplainResult) -> list[str]:
    partitions: list[str] = []
    for row in result.rows:
        partitions.extend(_split_partitions(row.partitions))
    return partitions


def _assert_explain_result_shape(result: ClickHouseExplainResult):
    assert isinstance(result, ClickHouseExplainResult)
    assert result.rows
    assert all(isinstance(row, ClickHouseExplainRow) for row in result.rows)
    assert all(hasattr(row, "partitions") for row in result.rows)


def _assert_partition_pruning(result: ClickHouseExplainResult, expected_partition: str):
    _assert_explain_result_shape(result)
    partitions = _collect_explain_partitions(result)
    assert expected_partition in partitions


@pytest.fixture
def clickhouse_partition_explain_backend(clickhouse_backend):
    """Create a real partitioned table for EXPLAIN tests."""
    _create_partition_explain_table(clickhouse_backend)
    _seed_partition_explain_rows(clickhouse_backend)
    yield clickhouse_backend
    _drop_partition_explain_table(clickhouse_backend)


@pytest.fixture
async def async_clickhouse_partition_explain_backend(async_clickhouse_backend):
    """Create a real partitioned table for async EXPLAIN tests."""
    await _async_create_partition_explain_table(async_clickhouse_backend)
    await _async_seed_partition_explain_rows(async_clickhouse_backend)
    yield async_clickhouse_backend
    await _async_drop_partition_explain_table(async_clickhouse_backend)


class TestClickHousePartitionExplain:
    """Synchronous EXPLAIN tests for ClickHouse partition pruning."""

    def test_explain_partition_pruning_returns_expected_partition(
        self,
        clickhouse_partition_explain_backend,
    ):
        """Range predicate on partition key should expose the pruned partition."""
        dialect = clickhouse_partition_explain_backend.dialect
        expr = _partition_range_query_expression(
            dialect,
            datetime(2026, 2, 1),
            datetime(2026, 3, 1),
        )

        result = clickhouse_partition_explain_backend.explain(expr)

        _assert_partition_pruning(result, "p2026_02")

    def test_explain_full_scan_exposes_partition_scope_when_available(
        self,
        clickhouse_partition_explain_backend,
    ):
        """Full table scan may report all partitions or NULL depending on ClickHouse version."""
        dialect = clickhouse_partition_explain_backend.dialect
        result = clickhouse_partition_explain_backend.explain(
            _full_scan_query_expression(dialect)
        )

        _assert_explain_result_shape(result)
        partitions = _collect_explain_partitions(result)
        if partitions:
            assert {"p2026_01", "p2026_02"}.issubset(set(partitions))

    def test_explain_row_exposes_partitions_attribute(self, clickhouse_partition_explain_backend):
        """ClickHouseExplainRow should retain the native EXPLAIN partitions field."""
        dialect = clickhouse_partition_explain_backend.dialect
        result = clickhouse_partition_explain_backend.explain(
            _partition_range_query_expression(
                dialect,
                datetime(2026, 1, 1),
                datetime(2026, 2, 1),
            )
        )

        _assert_explain_result_shape(result)
        assert all(
            row.partitions is None or isinstance(row.partitions, str)
            for row in result.rows
        )


class TestAsyncClickHousePartitionExplain:
    """Asynchronous EXPLAIN tests for ClickHouse partition pruning."""

    @pytest.mark.asyncio
    async def test_explain_partition_pruning_returns_expected_partition(
        self,
        async_clickhouse_partition_explain_backend,
    ):
        """Range predicate on partition key should expose the pruned partition."""
        dialect = async_clickhouse_partition_explain_backend.dialect
        expr = _partition_range_query_expression(
            dialect,
            datetime(2026, 2, 1),
            datetime(2026, 3, 1),
        )

        result = await async_clickhouse_partition_explain_backend.explain(expr)

        _assert_partition_pruning(result, "p2026_02")

    @pytest.mark.asyncio
    async def test_explain_full_scan_exposes_partition_scope_when_available(
        self,
        async_clickhouse_partition_explain_backend,
    ):
        """Full table scan may report all partitions or NULL depending on ClickHouse version."""
        dialect = async_clickhouse_partition_explain_backend.dialect
        result = await async_clickhouse_partition_explain_backend.explain(
            _full_scan_query_expression(dialect)
        )

        _assert_explain_result_shape(result)
        partitions = _collect_explain_partitions(result)
        if partitions:
            assert {"p2026_01", "p2026_02"}.issubset(set(partitions))

    @pytest.mark.asyncio
    async def test_explain_row_exposes_partitions_attribute(
        self,
        async_clickhouse_partition_explain_backend,
    ):
        """ClickHouseExplainRow should retain the native EXPLAIN partitions field."""
        dialect = async_clickhouse_partition_explain_backend.dialect
        result = await async_clickhouse_partition_explain_backend.explain(
            _partition_range_query_expression(
                dialect,
                datetime(2026, 1, 1),
                datetime(2026, 2, 1),
            )
        )

        _assert_explain_result_shape(result)
        assert all(
            row.partitions is None or isinstance(row.partitions, str)
            for row in result.rows
        )

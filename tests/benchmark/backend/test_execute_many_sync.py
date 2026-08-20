"""Synchronous ClickHouse direct backend batch benchmarks."""

import pytest

from rhosocial.activerecord.testsuite.benchmark.crud.fixtures.data import make_user_payload

from .workloads import execute_many_insert


@pytest.mark.benchmark
@pytest.mark.benchmark_backend
@pytest.mark.benchmark_sync
@pytest.mark.benchmark_write
def test_clickhouse_backend_execute_many_insert_sync(benchmark, clickhouse_backend_sync_context):
    start = len(clickhouse_backend_sync_context.payloads) + 1
    payloads = [make_user_payload(start + index) for index in range(100)]
    affected_rows = benchmark(execute_many_insert, clickhouse_backend_sync_context, payloads)
    assert affected_rows == len(payloads)

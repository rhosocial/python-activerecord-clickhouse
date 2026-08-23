"""ClickHouse direct backend benchmark fixtures."""

import asyncio
from dataclasses import dataclass
from typing import Any, Callable, List

import pytest

from rhosocial.activerecord.backend.options import ExecutionOptions, InsertOptions
from rhosocial.activerecord.backend.schema import StatementType
from rhosocial.activerecord.testsuite.benchmark.crud.fixtures.data import (
    make_user_payloads,
    payload_count_for_size,
)

from providers.scenarios import get_enabled_scenarios, get_scenario


@dataclass
class BackendBenchmarkContext:
    scenario: str
    size: str
    backend: Any
    payloads: List[dict]
    record_ids: List[Any]
    sql: dict
    params_factory: Callable[..., Any]
    backend_namespace: str
    backend_name: str


DQL_OPTIONS = ExecutionOptions(stmt_type=StatementType.DQL, process_result_set=True)
DML_OPTIONS = ExecutionOptions(stmt_type=StatementType.DML, process_result_set=False)
DDL_OPTIONS = ExecutionOptions(stmt_type=StatementType.DDL)


SCENARIO_PARAMS = list(get_enabled_scenarios().keys()) or [
    pytest.param("default", marks=pytest.mark.skip(reason="No ClickHouse benchmark scenarios found"))
]


def pytest_addoption(parser):
    try:
        parser.addoption(
            "--benchmark-size",
            action="store",
            default="small",
            choices=("small", "medium", "large"),
            help="Data size for ClickHouse backend benchmark scenarios.",
        )
    except ValueError:
        pass


@pytest.fixture(scope="function")
def benchmark_size(request):
    return request.config.getoption("--benchmark-size")


def pytest_configure(config):
    config.addinivalue_line("markers", "benchmark: Mark tests as performance benchmarks")
    config.addinivalue_line("markers", "benchmark_sync: Mark synchronous benchmark tests")
    config.addinivalue_line("markers", "benchmark_async: Mark asynchronous benchmark tests")
    config.addinivalue_line("markers", "benchmark_read: Mark read-oriented benchmark tests")
    config.addinivalue_line("markers", "benchmark_write: Mark write-oriented benchmark tests")
    config.addinivalue_line("markers", "benchmark_backend: Mark backend direct benchmark tests")


@pytest.fixture(scope="function", params=SCENARIO_PARAMS)
def clickhouse_backend_sync_context(request, benchmark_size):
    from rhosocial.activerecord.backend.impl.clickhouse import ClickHouseBackend

    scenario = request.param
    _, config = get_scenario(scenario)
    backend = ClickHouseBackend(connection_config=config)
    _initialize_schema(backend)
    payloads = make_user_payloads(payload_count_for_size(benchmark_size))
    record_ids = _seed_sync(backend, payloads)
    try:
        yield BackendBenchmarkContext(
            scenario=scenario,
            size=benchmark_size,
            backend=backend,
            payloads=payloads,
            record_ids=record_ids,
            sql=_sql_templates(),
            params_factory=_params_factory,
            backend_namespace="rhosocial.activerecord.backend.impl.clickhouse",
            backend_name="clickhouse",
        )
    finally:
        backend.disconnect()


@pytest.fixture(scope="function", params=SCENARIO_PARAMS)
def clickhouse_backend_async_context(request, benchmark_size):
    from rhosocial.activerecord.backend.impl.clickhouse import AsyncClickHouseBackend

    scenario = request.param
    _, config = get_scenario(scenario)
    loop = asyncio.new_event_loop()
    backend = AsyncClickHouseBackend(connection_config=config)
    try:
        loop.run_until_complete(_initialize_schema_async(backend))
        payloads = make_user_payloads(payload_count_for_size(benchmark_size))
        record_ids = loop.run_until_complete(_seed_async(backend, payloads))
        yield (
            BackendBenchmarkContext(
                scenario=scenario,
                size=benchmark_size,
                backend=backend,
                payloads=payloads,
                record_ids=record_ids,
                sql=_sql_templates(),
                params_factory=_params_factory,
                backend_namespace="rhosocial.activerecord.backend.impl.clickhouse",
                backend_name="clickhouse",
            ),
            loop.run_until_complete,
        )
    finally:
        loop.run_until_complete(backend.disconnect())
        loop.close()


def _initialize_schema(backend):
    backend.execute("DROP TABLE IF EXISTS benchmark_users", options=DDL_OPTIONS)
    backend.execute(_schema_sql(), options=DDL_OPTIONS)


async def _initialize_schema_async(backend):
    await backend.execute("DROP TABLE IF EXISTS benchmark_users", options=DDL_OPTIONS)
    await backend.execute(_schema_sql(), options=DDL_OPTIONS)


def _seed_sync(backend, payloads):
    # Seed through the backend insert contract: ClickHouse has no AUTO_INCREMENT
    # and the driver reports no rowcount/lastrowid for raw SQL, so ids are
    # generated client-side (snowflake) by backend.insert().
    record_ids = []
    for payload in payloads:
        result = backend.insert(InsertOptions(table="benchmark_users", data=dict(payload)))
        if result.affected_rows != 1 or result.last_insert_id is None:
            raise AssertionError("failed to seed sync ClickHouse backend benchmark row")
        record_ids.append(result.last_insert_id)
    return record_ids


async def _seed_async(backend, payloads):
    record_ids = []
    for payload in payloads:
        result = await backend.insert(InsertOptions(table="benchmark_users", data=dict(payload)))
        if result.affected_rows != 1 or result.last_insert_id is None:
            raise AssertionError("failed to seed async ClickHouse backend benchmark row")
        record_ids.append(result.last_insert_id)
    return record_ids


def _sql_templates():
    return {
        "insert": """
INSERT INTO benchmark_users (
    username, email, age, balance, notes, is_active, created_at, updated_at
) VALUES (%s, %s, %s, %s, %s, %s, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
""",
        "find_one": "SELECT * FROM benchmark_users WHERE id = %s",
        "update": ("UPDATE benchmark_users SET username = %s, updated_at = CURRENT_TIMESTAMP WHERE id = %s"),
        "delete": "DELETE FROM benchmark_users WHERE id = %s",
    }


def _params_factory(operation, payload):
    if operation != "insert":
        raise ValueError(f"unsupported backend benchmark operation: {operation}")
    return (
        payload["username"],
        payload["email"],
        payload["age"],
        payload["balance"],
        payload["notes"],
        payload["is_active"],
    )


def _schema_sql():
    return """
CREATE TABLE benchmark_users (
    id Int64,
    username String NOT NULL,
    email String NOT NULL,
    age Int32,
    balance Float64 NOT NULL DEFAULT 0.0,
    notes String,
    is_active Bool NOT NULL DEFAULT 1,
    created_at DateTime,
    updated_at DateTime
) ENGINE = MergeTree ORDER BY id SETTINGS enable_block_number_column = 1, enable_block_offset_column = 1
"""

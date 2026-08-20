# tests/rhosocial/activerecord_clickhouse_test/feature/backend/test_clickhouse_partition_operations.py
"""Real ClickHouse partition operation tests."""

from datetime import datetime
from typing import Any, List, Optional, Sequence

import pytest

from rhosocial.activerecord.backend.expression import (
    Column,
    ColumnConstraint,
    ColumnConstraintType,
    ColumnDefinition,
    CreateTableExpression,
    DropTableExpression,
    FunctionCall,
    IndexDefinition,
    InsertExpression,
    Literal,
    LogicalPredicate,
    OrderByClause,
    QueryExpression,
    TableConstraint,
    TableConstraintType,
    TableExpression,
    ValuesSource,
    WildcardExpression,
)
from rhosocial.activerecord.backend.expression.types import BigIntType, DateTimeType, DateType, VarCharType
from rhosocial.activerecord.backend.impl.clickhouse.dialect import ClickHouseDialect
from rhosocial.activerecord.backend.impl.clickhouse import ShowCreateTableExpression
from rhosocial.activerecord.backend.impl.clickhouse.expression import (
    ClickHouseAddPartitionExpression,
    ClickHouseCoalescePartitionExpression,
    ClickHouseDropPartitionExpression,
    ClickHouseExchangePartitionExpression,
    ClickHousePartitionByHash,
    ClickHousePartitionByRange,
    ClickHousePartitionByRangeColumns,
    ClickHousePartitionDefinition,
    ClickHousePartitionMaxValue,
    ClickHousePartitionValue,
    ClickHouseReorganizePartitionExpression,
    ClickHouseSubpartitionClause,
    ClickHouseSubpartitionDefinition,
    ClickHouseSubpartitionStrategy,
    ClickHouseTruncatePartitionExpression,
)


PARTITION_TABLE = "ar_clickhouse_partition_events"


def _drop_table_expression(dialect):
    return DropTableExpression(dialect=dialect, table=PARTITION_TABLE, if_exists=True)


def _base_partition_definitions(dialect: ClickHouseDialect) -> List[ClickHousePartitionDefinition]:
    return [
        ClickHousePartitionDefinition(
            name="p2026_01",
            less_than=[ClickHousePartitionValue(dialect, "2026-02-01")],
        ),
        ClickHousePartitionDefinition(
            name="p2026_02",
            less_than=[ClickHousePartitionValue(dialect, "2026-03-01")],
        ),
    ]


def _create_partitioned_table_expression(dialect):
    return CreateTableExpression(
        dialect=dialect,
        table=PARTITION_TABLE,
        columns=[
            ColumnDefinition("id", BigIntType(), constraints=[ColumnConstraint(ColumnConstraintType.NOT_NULL)]),
            ColumnDefinition("created_at", DateTimeType(), constraints=[ColumnConstraint(ColumnConstraintType.NOT_NULL)]),
            ColumnDefinition("payload", VarCharType(255)),
        ],
        indexes=[
            IndexDefinition(name="idx_created_at", columns=["created_at"]),
            IndexDefinition(name="idx_id", columns=["id"]),
        ],
        partition=ClickHousePartitionByRangeColumns(
            dialect=dialect,
            keys=[Column(dialect, "created_at")],
            partitions=_base_partition_definitions(dialect),
        ),
    )


def _insert_events_expression(dialect, rows):
    return InsertExpression(
        dialect=dialect,
        into=PARTITION_TABLE,
        columns=["id", "created_at", "payload"],
        source=ValuesSource(
            dialect,
            [[Literal(dialect, value) for value in row] for row in rows],
        ),
    )


def _select_payloads_expression(dialect):
    return QueryExpression(
        dialect,
        select=[Column(dialect, "payload")],
        from_=TableExpression(dialect, PARTITION_TABLE),
        order_by=OrderByClause(dialect, [(Column(dialect, "id"), "ASC")]),
    )


def _select_payload_by_id_expression(dialect, row_id):
    return QueryExpression(
        dialect,
        select=[Column(dialect, "payload")],
        from_=TableExpression(dialect, PARTITION_TABLE),
        where=Column(dialect, "id") == Literal(dialect, row_id),
    )


def _partition_names_expression(dialect, table_name=None):
    table_name = table_name or PARTITION_TABLE
    partitions = TableExpression(dialect, "PARTITIONS", schema_name="information_schema")
    return QueryExpression(
        dialect,
        select=[Column(dialect, "PARTITION_NAME", alias="name")],
        from_=partitions,
        where=LogicalPredicate(
            dialect,
            "AND",
            Column(dialect, "TABLE_SCHEMA") == FunctionCall(dialect, "DATABASE"),
            Column(dialect, "TABLE_NAME") == Literal(dialect, table_name),
            Column(dialect, "PARTITION_NAME").is_not_null(),
        ),
        order_by=OrderByClause(dialect, [(Column(dialect, "PARTITION_NAME"), "ASC")]),
    )


def _partition_metadata_expression(dialect):
    partitions = TableExpression(dialect, "PARTITIONS", schema_name="information_schema")
    return QueryExpression(
        dialect,
        select=[
            Column(dialect, "PARTITION_NAME", alias="name"),
            Column(dialect, "PARTITION_METHOD", alias="method"),
            Column(dialect, "PARTITION_EXPRESSION", alias="expression"),
            Column(dialect, "PARTITION_DESCRIPTION", alias="description"),
            Column(dialect, "TABLE_ROWS", alias="table_rows"),
            Column(dialect, "DATA_LENGTH", alias="data_length"),
            Column(dialect, "INDEX_LENGTH", alias="index_length"),
        ],
        from_=partitions,
        where=LogicalPredicate(
            dialect,
            "AND",
            Column(dialect, "TABLE_SCHEMA") == FunctionCall(dialect, "DATABASE"),
            Column(dialect, "TABLE_NAME") == Literal(dialect, PARTITION_TABLE),
            Column(dialect, "PARTITION_NAME").is_not_null(),
        ),
        order_by=OrderByClause(dialect, [(Column(dialect, "PARTITION_NAME"), "ASC")]),
    )


def _add_future_partition_expression(dialect):
    return ClickHouseAddPartitionExpression(
        dialect=dialect,
        table=PARTITION_TABLE,
        partitions=[
            ClickHousePartitionDefinition(
                name="p2026_03",
                less_than=[ClickHousePartitionValue(dialect, "2026-04-01")],
            )
        ],
    )


def _drop_partition_expression(dialect, partition):
    return ClickHouseDropPartitionExpression(dialect, PARTITION_TABLE, [partition])


def _truncate_partition_expression(dialect, partition):
    return ClickHouseTruncatePartitionExpression(dialect, PARTITION_TABLE, [partition])


def _reorganize_partition_expression(dialect):
    return ClickHouseReorganizePartitionExpression(
        dialect=dialect,
        table=PARTITION_TABLE,
        partition="p2026_02",
        into=[
            ClickHousePartitionDefinition(
                name="p2026_02a",
                less_than=[ClickHousePartitionValue(dialect, "2026-02-15")],
            ),
            ClickHousePartitionDefinition(
                name="p2026_02b",
                less_than=[ClickHousePartitionValue(dialect, "2026-03-01")],
            ),
        ],
    )


def _drop_table(backend):
    backend.execute(*_drop_table_expression(backend.dialect).to_sql())


async def _async_drop_table(backend):
    await backend.execute(*_drop_table_expression(backend.dialect).to_sql())


def _create_partitioned_table(backend):
    _drop_table(backend)
    backend.execute(*_create_partitioned_table_expression(backend.dialect).to_sql())


async def _async_create_partitioned_table(backend):
    await _async_drop_table(backend)
    await backend.execute(*_create_partitioned_table_expression(backend.dialect).to_sql())


def _partition_names(backend, table_name=None):
    rows = backend.fetch_all(*_partition_names_expression(backend.dialect, table_name).to_sql())
    return [row["name"] for row in rows]


async def _async_partition_names(backend, table_name=None):
    rows = await backend.fetch_all(*_partition_names_expression(backend.dialect, table_name).to_sql())
    return [row["name"] for row in rows]


def _partition_metadata(backend):
    return backend.fetch_all(*_partition_metadata_expression(backend.dialect).to_sql())


async def _async_partition_metadata(backend):
    return await backend.fetch_all(*_partition_metadata_expression(backend.dialect).to_sql())


def _assert_base_partition_metadata(rows):
    assert [row["name"] for row in rows] == ["p2026_01", "p2026_02"]

    by_name = {row["name"]: row for row in rows}
    for row in rows:
        assert "RANGE" in str(row["method"]).upper()
        assert "created_at" in str(row["expression"]).lower()
        assert "table_rows" in row
        assert "data_length" in row
        assert "index_length" in row

    assert "2026-02-01" in str(by_name["p2026_01"]["description"])
    assert "2026-03-01" in str(by_name["p2026_02"]["description"])


def _show_create_table_sql(backend):
    row = backend.fetch_one(*ShowCreateTableExpression(backend.dialect, PARTITION_TABLE).to_sql())
    return row.get("Create Table") or row.get("create table")


async def _async_show_create_table_sql(backend):
    row = await backend.fetch_one(*ShowCreateTableExpression(backend.dialect, PARTITION_TABLE).to_sql())
    return row.get("Create Table") or row.get("create table")


def _assert_show_create_table_includes_partition_definition(create_sql):
    assert create_sql
    upper_sql = create_sql.upper()
    lower_sql = create_sql.lower()

    assert "PARTITION BY RANGE" in upper_sql
    assert "created_at" in lower_sql
    assert "p2026_01" in create_sql
    assert "p2026_02" in create_sql
    assert "VALUES LESS THAN" in upper_sql
    assert "2026-02-01" in create_sql
    assert "2026-03-01" in create_sql


# --- Negative / edge-case test helpers ---

NEGATIVE_TABLE = "ar_clickhouse_partition_negative"
NEGATIVE_PARTITIONED_TABLE = "ar_clickhouse_partition_negative_part"
NEGATIVE_HASH_TABLE = "ar_clickhouse_partition_negative_hash"


def _base_columns_without_pk():
    return [
        ColumnDefinition("id", BigIntType(), constraints=[ColumnConstraint(ColumnConstraintType.NOT_NULL)]),
        ColumnDefinition("shard_id", BigIntType(), constraints=[ColumnConstraint(ColumnConstraintType.NOT_NULL)]),
        ColumnDefinition("payload", VarCharType(255)),
    ]


def _create_nonpartitioned_table_expression(dialect):
    return CreateTableExpression(
        dialect=dialect,
        table=NEGATIVE_TABLE,
        columns=_base_columns_without_pk(),
    )


def _create_negative_partitioned_table_expression(dialect):
    return CreateTableExpression(
        dialect=dialect,
        table=NEGATIVE_PARTITIONED_TABLE,
        columns=_base_columns_without_pk(),
        partition=ClickHousePartitionByRange(
            dialect=dialect,
            keys=[Column(dialect, "shard_id")],
            partitions=[
                ClickHousePartitionDefinition("p_low", less_than=[ClickHousePartitionValue(dialect, 100)]),
                ClickHousePartitionDefinition("p_mid", less_than=[ClickHousePartitionValue(dialect, 200)]),
            ],
        ),
    )


def _create_negative_hash_table_expression(dialect):
    return CreateTableExpression(
        dialect=dialect,
        table=NEGATIVE_HASH_TABLE,
        columns=_base_columns_without_pk(),
        partition=ClickHousePartitionByHash(
            dialect=dialect,
            keys=[Column(dialect, "shard_id")],
            partitions_count=4,
        ),
    )


def _setup_negative_tables(backend):
    backend.execute(*_drop_named_table_expression(backend.dialect, NEGATIVE_TABLE).to_sql())
    backend.execute(*_drop_named_table_expression(backend.dialect, NEGATIVE_PARTITIONED_TABLE).to_sql())
    backend.execute(*_drop_named_table_expression(backend.dialect, NEGATIVE_HASH_TABLE).to_sql())
    backend.execute(*_create_nonpartitioned_table_expression(backend.dialect).to_sql())
    backend.execute(*_create_negative_partitioned_table_expression(backend.dialect).to_sql())
    backend.execute(*_create_negative_hash_table_expression(backend.dialect).to_sql())


def _teardown_negative_tables(backend):
    for table in (NEGATIVE_HASH_TABLE, NEGATIVE_PARTITIONED_TABLE, NEGATIVE_TABLE):
        backend.execute(*_drop_named_table_expression(backend.dialect, table).to_sql())


async def _async_setup_negative_tables(backend):
    for table in (NEGATIVE_TABLE, NEGATIVE_PARTITIONED_TABLE, NEGATIVE_HASH_TABLE):
        await backend.execute(*_drop_named_table_expression(backend.dialect, table).to_sql())
    await backend.execute(*_create_nonpartitioned_table_expression(backend.dialect).to_sql())
    await backend.execute(*_create_negative_partitioned_table_expression(backend.dialect).to_sql())
    await backend.execute(*_create_negative_hash_table_expression(backend.dialect).to_sql())


async def _async_teardown_negative_tables(backend):
    for table in (NEGATIVE_HASH_TABLE, NEGATIVE_PARTITIONED_TABLE, NEGATIVE_TABLE):
        await backend.execute(*_drop_named_table_expression(backend.dialect, table).to_sql())


PRODUCTION_PARTITION_TABLE = "ar_clickhouse_partition_ops_events"
PRODUCTION_MAXVALUE_TABLE = "ar_clickhouse_partition_ops_events_maxvalue"
PRODUCTION_ARCHIVE_TABLE = "ar_clickhouse_partition_ops_events_archive_2026"
PRODUCTION_PARTITIONS = (
    ("p2026", "2027-01-01 00:00:00.000000"),
    ("p2027_q1", "2027-04-01 00:00:00.000000"),
    ("p2027_04", "2027-05-01 00:00:00.000000"),
    ("p2027_w18", "2027-05-08 00:00:00.000000"),
)


def _drop_named_table_expression(dialect, table_name: str):
    return DropTableExpression(dialect=dialect, table=table_name, if_exists=True)


def _production_columns():
    return [
        ColumnDefinition("id", BigIntType(), constraints=[ColumnConstraint(ColumnConstraintType.NOT_NULL)]),
        ColumnDefinition("created_at", DateTimeType(6), constraints=[ColumnConstraint(ColumnConstraintType.NOT_NULL)]),
        ColumnDefinition("tenant_id", BigIntType(), constraints=[ColumnConstraint(ColumnConstraintType.NOT_NULL)]),
        ColumnDefinition("payload", VarCharType(255), constraints=[ColumnConstraint(ColumnConstraintType.NOT_NULL)]),
    ]


def _production_indexes():
    return [
        IndexDefinition(name="idx_created_at", columns=["created_at"]),
        IndexDefinition(name="idx_tenant_created_at", columns=["tenant_id", "created_at"]),
    ]


def _production_table_constraints():
    return [
        TableConstraint(
            TableConstraintType.PRIMARY_KEY,
            columns=["id", "created_at"],
        ),
    ]


def _partition_definition(dialect, name: str, upper_bound: str):
    return ClickHousePartitionDefinition(
        name=name,
        less_than=[ClickHousePartitionValue(dialect, upper_bound)],
    )


def _create_production_partitioned_table_expression(dialect, partitions):
    return CreateTableExpression(
        dialect=dialect,
        table=PRODUCTION_PARTITION_TABLE,
        columns=_production_columns(),
        indexes=_production_indexes(),
        table_constraints=_production_table_constraints(),
        partition=ClickHousePartitionByRangeColumns(
            dialect=dialect,
            keys=[Column(dialect, "created_at")],
            partitions=[
                _partition_definition(dialect, name, upper_bound)
                for name, upper_bound in partitions
            ],
        ),
    )


def _create_production_archive_table_expression(dialect):
    return CreateTableExpression(
        dialect=dialect,
        table=PRODUCTION_ARCHIVE_TABLE,
        columns=_production_columns(),
        indexes=_production_indexes(),
        table_constraints=_production_table_constraints(),
    )


def _create_production_maxvalue_partitioned_table_expression(dialect):
    return CreateTableExpression(
        dialect=dialect,
        table=PRODUCTION_MAXVALUE_TABLE,
        columns=_production_columns(),
        indexes=_production_indexes(),
        table_constraints=_production_table_constraints(),
        partition=ClickHousePartitionByRangeColumns(
            dialect=dialect,
            keys=[Column(dialect, "created_at")],
            partitions=[
                _partition_definition(dialect, "p2026", "2027-01-01 00:00:00.000000"),
                ClickHousePartitionDefinition(
                    name="pmax",
                    less_than=[ClickHousePartitionMaxValue(dialect)],
                ),
            ],
        ),
    )


def _insert_production_events_into_expression(dialect, table_name: str, rows):
    return InsertExpression(
        dialect=dialect,
        into=table_name,
        columns=["id", "created_at", "tenant_id", "payload"],
        source=ValuesSource(
            dialect,
            [[Literal(dialect, value) for value in row] for row in rows],
        ),
    )


def _insert_production_events_expression(dialect, rows):
    return _insert_production_events_into_expression(dialect, PRODUCTION_PARTITION_TABLE, rows)


def _select_production_payloads_from_expression(
    dialect,
    table_name: str,
    start,
    end,
    *,
    tenant_id: Optional[int] = None,
):
    predicate = (Column(dialect, "created_at") >= Literal(dialect, start)) & (
        Column(dialect, "created_at") < Literal(dialect, end)
    )
    if tenant_id is not None:
        predicate = LogicalPredicate(
            dialect,
            "AND",
            Column(dialect, "tenant_id") == Literal(dialect, tenant_id),
            predicate,
        )
    return QueryExpression(
        dialect,
        select=[Column(dialect, "payload")],
        from_=TableExpression(dialect, table_name),
        where=predicate,
        order_by=OrderByClause(dialect, [(Column(dialect, "id"), "ASC")]),
    )


def _select_production_payloads_expression(dialect, start, end, *, tenant_id: Optional[int] = None):
    return _select_production_payloads_from_expression(
        dialect,
        PRODUCTION_PARTITION_TABLE,
        start,
        end,
        tenant_id=tenant_id,
    )


def _select_production_count_expression(dialect):
    return QueryExpression(
        dialect,
        select=[FunctionCall(dialect, "COUNT", WildcardExpression(dialect)).as_("count")],
        from_=TableExpression(dialect, PRODUCTION_PARTITION_TABLE),
    )


def _select_archive_count_expression(dialect):
    return QueryExpression(
        dialect,
        select=[FunctionCall(dialect, "COUNT", WildcardExpression(dialect)).as_("count")],
        from_=TableExpression(dialect, PRODUCTION_ARCHIVE_TABLE),
    )


def _partition_metadata_expression_for_table(dialect, table_name: str):
    partitions = TableExpression(dialect, "PARTITIONS", schema_name="information_schema")
    return QueryExpression(
        dialect,
        select=[
            Column(dialect, "PARTITION_NAME", alias="name"),
            Column(dialect, "PARTITION_METHOD", alias="method"),
            Column(dialect, "PARTITION_EXPRESSION", alias="expression"),
            Column(dialect, "PARTITION_DESCRIPTION", alias="description"),
            Column(dialect, "TABLE_ROWS", alias="table_rows"),
            Column(dialect, "DATA_LENGTH", alias="data_length"),
            Column(dialect, "INDEX_LENGTH", alias="index_length"),
        ],
        from_=partitions,
        where=LogicalPredicate(
            dialect,
            "AND",
            Column(dialect, "TABLE_SCHEMA") == FunctionCall(dialect, "DATABASE"),
            Column(dialect, "TABLE_NAME") == Literal(dialect, table_name),
            Column(dialect, "PARTITION_NAME").is_not_null(),
        ),
        order_by=OrderByClause(dialect, [(Column(dialect, "PARTITION_NAME"), "ASC")]),
    )


def _production_partition_metadata(backend):
    expr = _partition_metadata_expression_for_table(backend.dialect, PRODUCTION_PARTITION_TABLE)
    return backend.fetch_all(*expr.to_sql())


async def _async_production_partition_metadata(backend):
    expr = _partition_metadata_expression_for_table(backend.dialect, PRODUCTION_PARTITION_TABLE)
    return await backend.fetch_all(*expr.to_sql())


def _add_production_partition_expression(dialect, name: str, upper_bound: str):
    return ClickHouseAddPartitionExpression(
        dialect=dialect,
        table=PRODUCTION_PARTITION_TABLE,
        partitions=[_partition_definition(dialect, name, upper_bound)],
    )


def _reorganize_maxvalue_partition_expression(dialect):
    return ClickHouseReorganizePartitionExpression(
        dialect=dialect,
        table=PRODUCTION_MAXVALUE_TABLE,
        partition="pmax",
        into=[
            _partition_definition(dialect, "p2027", "2028-01-01 00:00:00.000000"),
            ClickHousePartitionDefinition(
                name="pmax",
                less_than=[ClickHousePartitionMaxValue(dialect)],
            ),
        ],
    )


def _production_range_query_for_table_expression(dialect, table_name: str, start, end, *, tenant_id: int):
    return QueryExpression(
        dialect,
        select=[WildcardExpression(dialect)],
        from_=TableExpression(dialect, table_name),
        where=LogicalPredicate(
            dialect,
            "AND",
            Column(dialect, "tenant_id") == Literal(dialect, tenant_id),
            (Column(dialect, "created_at") >= Literal(dialect, start))
            & (Column(dialect, "created_at") < Literal(dialect, end)),
        ),
    )


def _production_range_query_expression(dialect, start, end, *, tenant_id: int):
    return _production_range_query_for_table_expression(
        dialect,
        PRODUCTION_PARTITION_TABLE,
        start,
        end,
        tenant_id=tenant_id,
    )


def _collect_explain_partitions(result) -> List[str]:
    partitions: List[str] = []
    for row in result.rows:
        if row.partitions:
            partitions.extend(part.strip() for part in str(row.partitions).split(","))
    return [partition for partition in partitions if partition]


def _assert_partition_metadata(rows, expected_names: Sequence[str]):
    assert {row["name"] for row in rows} == set(expected_names)
    by_name = {row["name"]: row for row in rows}
    for name in expected_names:
        row = by_name[name]
        assert "RANGE" in str(row["method"]).upper()
        assert "created_at" in str(row["expression"]).lower()
        assert "table_rows" in row
        assert "data_length" in row
        assert "index_length" in row


def _create_production_partitioned_table(backend, partitions):
    for table_name in (PRODUCTION_ARCHIVE_TABLE, PRODUCTION_MAXVALUE_TABLE, PRODUCTION_PARTITION_TABLE):
        backend.execute(*_drop_named_table_expression(backend.dialect, table_name).to_sql())
    backend.execute(
        *_create_production_partitioned_table_expression(backend.dialect, partitions).to_sql()
    )


async def _async_create_production_partitioned_table(backend, partitions):
    for table_name in (PRODUCTION_ARCHIVE_TABLE, PRODUCTION_MAXVALUE_TABLE, PRODUCTION_PARTITION_TABLE):
        expr = _drop_named_table_expression(backend.dialect, table_name)
        await backend.execute(*expr.to_sql())
    expr = _create_production_partitioned_table_expression(backend.dialect, partitions)
    await backend.execute(*expr.to_sql())


def _create_production_maxvalue_partitioned_table(backend):
    for table_name in (PRODUCTION_MAXVALUE_TABLE, PRODUCTION_PARTITION_TABLE):
        backend.execute(*_drop_named_table_expression(backend.dialect, table_name).to_sql())
    backend.execute(*_create_production_maxvalue_partitioned_table_expression(backend.dialect).to_sql())


async def _async_create_production_maxvalue_partitioned_table(backend):
    for table_name in (PRODUCTION_MAXVALUE_TABLE, PRODUCTION_PARTITION_TABLE):
        expr = _drop_named_table_expression(backend.dialect, table_name)
        await backend.execute(*expr.to_sql())
    expr = _create_production_maxvalue_partitioned_table_expression(backend.dialect)
    await backend.execute(*expr.to_sql())


def _drop_production_tables(backend):
    for table_name in (PRODUCTION_ARCHIVE_TABLE, PRODUCTION_MAXVALUE_TABLE, PRODUCTION_PARTITION_TABLE):
        backend.execute(*_drop_named_table_expression(backend.dialect, table_name).to_sql())


async def _async_drop_production_tables(backend):
    for table_name in (PRODUCTION_ARCHIVE_TABLE, PRODUCTION_MAXVALUE_TABLE, PRODUCTION_PARTITION_TABLE):
        expr = _drop_named_table_expression(backend.dialect, table_name)
        await backend.execute(*expr.to_sql())


@pytest.fixture
def clickhouse_partitioned_table(clickhouse_backend):
    """Create a real RANGE-partitioned ClickHouse table."""
    _create_partitioned_table(clickhouse_backend)
    yield PARTITION_TABLE
    _drop_table(clickhouse_backend)


@pytest.fixture
async def async_clickhouse_partitioned_table(async_clickhouse_backend):
    """Create a real RANGE-partitioned ClickHouse table asynchronously."""
    await _async_create_partitioned_table(async_clickhouse_backend)
    yield PARTITION_TABLE
    await _async_drop_table(async_clickhouse_backend)


@pytest.fixture
def clickhouse_production_year_partition_table(clickhouse_backend):
    """Create a production-like table with only the 2026 year partition."""
    _create_production_partitioned_table(clickhouse_backend, [PRODUCTION_PARTITIONS[0]])
    yield PRODUCTION_PARTITION_TABLE
    _drop_production_tables(clickhouse_backend)


@pytest.fixture
async def async_clickhouse_production_year_partition_table(async_clickhouse_backend):
    """Create the async production-like table with only the 2026 year partition."""
    await _async_create_production_partitioned_table(
        async_clickhouse_backend,
        [PRODUCTION_PARTITIONS[0]],
    )
    yield PRODUCTION_PARTITION_TABLE
    await _async_drop_production_tables(async_clickhouse_backend)


@pytest.fixture
def clickhouse_production_partition_table(clickhouse_backend):
    """Create a production-like table with year, quarter, month, and week partitions."""
    _create_production_partitioned_table(clickhouse_backend, PRODUCTION_PARTITIONS)
    yield PRODUCTION_PARTITION_TABLE
    _drop_production_tables(clickhouse_backend)


@pytest.fixture
async def async_clickhouse_production_partition_table(async_clickhouse_backend):
    """Create the async production-like table with multiple future partitions."""
    await _async_create_production_partitioned_table(
        async_clickhouse_backend,
        PRODUCTION_PARTITIONS,
    )
    yield PRODUCTION_PARTITION_TABLE
    await _async_drop_production_tables(async_clickhouse_backend)


@pytest.fixture
def clickhouse_production_maxvalue_partition_table(clickhouse_backend):
    """Create a production-like table with a MAXVALUE catch-all partition."""
    _create_production_maxvalue_partitioned_table(clickhouse_backend)
    yield PRODUCTION_MAXVALUE_TABLE
    _drop_production_tables(clickhouse_backend)


@pytest.fixture
async def async_clickhouse_production_maxvalue_partition_table(async_clickhouse_backend):
    """Create the async production-like table with a MAXVALUE catch-all partition."""
    await _async_create_production_maxvalue_partitioned_table(async_clickhouse_backend)
    yield PRODUCTION_MAXVALUE_TABLE
    await _async_drop_production_tables(async_clickhouse_backend)


class TestClickHousePartitionOperations:
    """Synchronous real backend tests for ClickHouse partition operations."""

    def test_create_range_partitioned_table(self, clickhouse_backend, clickhouse_partitioned_table):
        """information_schema.PARTITIONS should expose created partitions."""
        assert clickhouse_partitioned_table == PARTITION_TABLE
        assert _partition_names(clickhouse_backend) == ["p2026_01", "p2026_02"]

    def test_partition_metadata_contains_strategy_key_and_bounds(self, clickhouse_backend, clickhouse_partitioned_table):
        """information_schema.PARTITIONS should expose strategy, key, and bounds."""
        _assert_base_partition_metadata(_partition_metadata(clickhouse_backend))

    def test_show_create_table_includes_partition_definition(self, clickhouse_backend, clickhouse_partitioned_table):
        """SHOW CREATE TABLE should include the native partition definition."""
        _assert_show_create_table_includes_partition_definition(_show_create_table_sql(clickhouse_backend))

    def test_insert_across_partitions_and_query(self, clickhouse_backend, clickhouse_partitioned_table):
        """Rows inserted across ranges should remain queryable through parent table."""
        insert = _insert_events_expression(
            clickhouse_backend.dialect,
            [
                [1, datetime(2026, 1, 15), "jan"],
                [2, datetime(2026, 2, 15), "feb"],
            ],
        )
        clickhouse_backend.execute(*insert.to_sql())

        rows = clickhouse_backend.fetch_all(*_select_payloads_expression(clickhouse_backend.dialect).to_sql())
        assert [row["payload"] for row in rows] == ["jan", "feb"]

    def test_add_partition_for_future_range(self, clickhouse_backend, clickhouse_partitioned_table):
        """ALTER TABLE ADD PARTITION should allow future range inserts."""
        clickhouse_backend.execute(*_add_future_partition_expression(clickhouse_backend.dialect).to_sql())
        clickhouse_backend.execute(
            *_insert_events_expression(
                clickhouse_backend.dialect,
                [[3, datetime(2026, 3, 15), "mar"]],
            ).to_sql()
        )

        assert _partition_names(clickhouse_backend) == ["p2026_01", "p2026_02", "p2026_03"]
        row = clickhouse_backend.fetch_one(*_select_payload_by_id_expression(clickhouse_backend.dialect, 3).to_sql())
        assert row["payload"] == "mar"

    def test_drop_partition(self, clickhouse_backend, clickhouse_partitioned_table):
        """ALTER TABLE DROP PARTITION should remove the partition and its rows."""
        clickhouse_backend.execute(
            *_insert_events_expression(
                clickhouse_backend.dialect,
                [
                    [1, datetime(2026, 1, 15), "jan"],
                    [2, datetime(2026, 2, 15), "feb"],
                ],
            ).to_sql()
        )
        clickhouse_backend.execute(*_drop_partition_expression(clickhouse_backend.dialect, "p2026_01").to_sql())

        assert _partition_names(clickhouse_backend) == ["p2026_02"]
        rows = clickhouse_backend.fetch_all(*_select_payloads_expression(clickhouse_backend.dialect).to_sql())
        assert [row["payload"] for row in rows] == ["feb"]

    def test_truncate_partition(self, clickhouse_backend, clickhouse_partitioned_table):
        """ALTER TABLE TRUNCATE PARTITION should clear one range only."""
        clickhouse_backend.execute(
            *_insert_events_expression(
                clickhouse_backend.dialect,
                [
                    [1, datetime(2026, 1, 15), "jan"],
                    [2, datetime(2026, 2, 15), "feb"],
                ],
            ).to_sql()
        )
        clickhouse_backend.execute(*_truncate_partition_expression(clickhouse_backend.dialect, "p2026_01").to_sql())

        rows = clickhouse_backend.fetch_all(*_select_payloads_expression(clickhouse_backend.dialect).to_sql())
        assert [row["payload"] for row in rows] == ["feb"]

    def test_reorganize_partition(self, clickhouse_backend, clickhouse_partitioned_table):
        """ALTER TABLE REORGANIZE PARTITION should split an existing range."""
        clickhouse_backend.execute(*_reorganize_partition_expression(clickhouse_backend.dialect).to_sql())

        assert _partition_names(clickhouse_backend) == ["p2026_01", "p2026_02a", "p2026_02b"]


class TestClickHousePartitionOperationsNegative:
    """Negative and edge-case tests for ClickHouse partition maintenance operations.

    Each test sets up its own tables via _setup_negative_tables to guarantee
    a clean baseline regardless of test ordering.
    """

    def test_add_partition_on_nonpartitioned_table_raises_error(self, clickhouse_backend):
        """ALTER TABLE ADD PARTITION should fail on a table without partitioning.

        Raises:
            Exception: ClickHouse rejects ADD PARTITION for non-partitioned tables.
        """
        _setup_negative_tables(clickhouse_backend)
        try:
            with pytest.raises(Exception):
                clickhouse_backend.execute(
                    *ClickHouseAddPartitionExpression(
                        clickhouse_backend.dialect,
                        NEGATIVE_TABLE,
                        [
                            ClickHousePartitionDefinition(
                                "p_extra", less_than=[ClickHousePartitionValue(clickhouse_backend.dialect, 300)]
                            ),
                        ],
                    ).to_sql()
                )
        finally:
            _teardown_negative_tables(clickhouse_backend)

    def test_drop_partition_on_nonpartitioned_table_raises_error(self, clickhouse_backend):
        """ALTER TABLE DROP PARTITION should fail on a table without partitioning.

        Raises:
            Exception: ClickHouse rejects DROP PARTITION for non-partitioned tables.
        """
        _setup_negative_tables(clickhouse_backend)
        try:
            with pytest.raises(Exception):
                clickhouse_backend.execute(
                    *ClickHouseDropPartitionExpression(
                        clickhouse_backend.dialect, NEGATIVE_TABLE, ["p_low"]
                    ).to_sql()
                )
        finally:
            _teardown_negative_tables(clickhouse_backend)

    def test_drop_nonexistent_partition_raises_error(self, clickhouse_backend):
        """ALTER TABLE DROP PARTITION should fail when the partition does not exist.

        Raises:
            Exception: ClickHouse rejects dropping a partition name that does not exist.
        """
        _setup_negative_tables(clickhouse_backend)
        try:
            with pytest.raises(Exception):
                clickhouse_backend.execute(
                    *ClickHouseDropPartitionExpression(
                        clickhouse_backend.dialect, NEGATIVE_PARTITIONED_TABLE, ["p_nonexistent"]
                    ).to_sql()
                )
        finally:
            _teardown_negative_tables(clickhouse_backend)

    def test_add_partition_duplicate_boundary_raises_error(self, clickhouse_backend):
        """ALTER TABLE ADD PARTITION should fail when the range overlaps an existing one.

        ClickHouse RANGE partitions must be strictly increasing. Adding a partition with
        a boundary less than the existing maximum should be rejected.

        Raises:
            Exception: ClickHouse rejects overlapping range boundaries.
        """
        _setup_negative_tables(clickhouse_backend)
        try:
            with pytest.raises(Exception):
                clickhouse_backend.execute(
                    *ClickHouseAddPartitionExpression(
                        clickhouse_backend.dialect,
                        NEGATIVE_PARTITIONED_TABLE,
                        [
                            ClickHousePartitionDefinition(
                                "p_overlap",
                                less_than=[ClickHousePartitionValue(clickhouse_backend.dialect, 150)],
                            ),
                        ],
                    ).to_sql()
                )
        finally:
            _teardown_negative_tables(clickhouse_backend)

    def test_truncate_partition_on_nonpartitioned_table_raises_error(self, clickhouse_backend):
        """ALTER TABLE TRUNCATE PARTITION should fail on a non-partitioned table.

        Raises:
            Exception: ClickHouse rejects TRUNCATE PARTITION for non-partitioned tables.
        """
        _setup_negative_tables(clickhouse_backend)
        try:
            with pytest.raises(Exception):
                clickhouse_backend.execute(
                    *ClickHouseTruncatePartitionExpression(
                        clickhouse_backend.dialect, NEGATIVE_TABLE, ["p_low"]
                    ).to_sql()
                )
        finally:
            _teardown_negative_tables(clickhouse_backend)

    def test_coalesce_partition_on_nonpartitioned_table_raises_error(self, clickhouse_backend):
        """ALTER TABLE COALESCE PARTITION should fail on a non-partitioned table.

        Raises:
            Exception: ClickHouse rejects COALESCE PARTITION for non-partitioned tables.
        """
        _setup_negative_tables(clickhouse_backend)
        try:
            with pytest.raises(Exception):
                clickhouse_backend.execute(
                    *ClickHouseCoalescePartitionExpression(
                        clickhouse_backend.dialect, NEGATIVE_TABLE, 2
                    ).to_sql()
                )
        finally:
            _teardown_negative_tables(clickhouse_backend)

    def test_coalesce_partition_count_exceeds_existing_raises_error(self, clickhouse_backend):
        """ALTER TABLE COALESCE PARTITION should fail when count exceeds existing partitions.

        Raises:
            Exception: ClickHouse rejects COALESCE with N > number of existing HASH partitions.
        """
        _setup_negative_tables(clickhouse_backend)
        try:
            with pytest.raises(Exception):
                clickhouse_backend.execute(
                    *ClickHouseCoalescePartitionExpression(
                        clickhouse_backend.dialect, NEGATIVE_HASH_TABLE, 10
                    ).to_sql()
                )
        finally:
            _teardown_negative_tables(clickhouse_backend)

    def test_reorganize_nonexistent_partition_raises_error(self, clickhouse_backend):
        """ALTER TABLE REORGANIZE PARTITION should fail when the partition does not exist.

        Raises:
            Exception: ClickHouse rejects reorganizing a partition name that does not exist.
        """
        _setup_negative_tables(clickhouse_backend)
        try:
            with pytest.raises(Exception):
                clickhouse_backend.execute(
                    *ClickHouseReorganizePartitionExpression(
                        clickhouse_backend.dialect,
                        NEGATIVE_PARTITIONED_TABLE,
                        partition="p_nonexistent",
                        into=[
                            ClickHousePartitionDefinition(
                                "p_new", less_than=[ClickHousePartitionValue(clickhouse_backend.dialect, 150)]
                            ),
                        ],
                    ).to_sql()
                )
        finally:
            _teardown_negative_tables(clickhouse_backend)

    def test_reorganize_partition_on_nonpartitioned_table_raises_error(self, clickhouse_backend):
        """ALTER TABLE REORGANIZE PARTITION should fail on non-partitioned tables.

        Raises:
            Exception: ClickHouse rejects REORGANIZE PARTITION for non-partitioned tables.
        """
        _setup_negative_tables(clickhouse_backend)
        try:
            with pytest.raises(Exception):
                clickhouse_backend.execute(
                    *ClickHouseReorganizePartitionExpression(
                        clickhouse_backend.dialect,
                        NEGATIVE_TABLE,
                        partition="p_low",
                        into=[
                            ClickHousePartitionDefinition(
                                "p_new", less_than=[ClickHousePartitionValue(clickhouse_backend.dialect, 150)]
                            ),
                        ],
                    ).to_sql()
                )
        finally:
            _teardown_negative_tables(clickhouse_backend)


class TestClickHousePartitionOperationsConcurrency:
    """Concurrency and transaction tests for ClickHouse partition operations.

    These tests verify partition DDL behaviour under concurrent access and
    transactional contexts, which is important because ClickHouse partition DDL
    statements trigger implicit commits.
    """

    def test_partition_ddl_inside_transaction_triggers_implicit_commit(
        self, clickhouse_backend, clickhouse_partitioned_table
    ):
        """ALTER TABLE ADD PARTITION inside a transaction should auto-commit.

        ClickHouse partition DDL statements are not transactional — they trigger
        an implicit commit before and after execution. This test verifies that
        a rollback after ADD PARTITION does not undo the partition change,
        and that the INSERT performed before the DDL is also committed.

        Steps:
            1. BEGIN a transaction
            2. INSERT a row
            3. ADD PARTITION  — triggers implicit commit
            4. ROLLBACK (no effect — transaction was already committed)
            5. Verify partition exists and INSERT survived the rollback

        Raises:
            AssertionError: if partition DDL was rolled back or INSERT was lost.
        """
        clickhouse_backend.execute("BEGIN")
        clickhouse_backend.execute(
            *_insert_events_expression(
                clickhouse_backend.dialect,
                [[1, datetime(2026, 1, 15), "jan"]],
            ).to_sql()
        )
        clickhouse_backend.execute(
            *_add_future_partition_expression(clickhouse_backend.dialect).to_sql()
        )
        clickhouse_backend.execute("ROLLBACK")

        # Partition DDL auto-committed — p2026_03 should still exist
        assert _partition_names(clickhouse_backend) == ["p2026_01", "p2026_02", "p2026_03"]

        # INSERT was also auto-committed by the DDL — row should still exist
        count = clickhouse_backend.fetch_one(
            f"SELECT COUNT(*) AS count FROM {PARTITION_TABLE}"
        )["count"]
        assert count == 1

    def test_concurrent_add_and_drop_partition(self, clickhouse_backend, clickhouse_control_backend):
        """Concurrent ADD and DROP on different connections should not corrupt metadata.

        Uses two independent connections to the same database.

        Steps:
            1. Create a partitioned table with p_low and p_mid
            2. Connection A adds p_high
            3. Connection B drops p_low
            4. Both operations succeed; final metadata has p_mid and p_high
        """
        _setup_negative_tables(clickhouse_backend)

        try:
            clickhouse_control_backend.execute(
                *ClickHouseAddPartitionExpression(
                    clickhouse_control_backend.dialect,
                    NEGATIVE_PARTITIONED_TABLE,
                    [
                        ClickHousePartitionDefinition(
                            "p_high",
                            less_than=[ClickHousePartitionValue(clickhouse_control_backend.dialect, 300)],
                        ),
                    ],
                ).to_sql()
            )
            clickhouse_backend.execute(
                *ClickHouseDropPartitionExpression(
                    clickhouse_backend.dialect, NEGATIVE_PARTITIONED_TABLE, ["p_low"]
                ).to_sql()
            )
            names = _partition_names(clickhouse_backend, NEGATIVE_PARTITIONED_TABLE)
            assert "p_mid" in names
            assert "p_high" in names
            assert "p_low" not in names
        finally:
            _teardown_negative_tables(clickhouse_backend)


class TestAsyncClickHousePartitionOperationsNegative:
    """Asynchronous negative and edge-case tests for ClickHouse partition maintenance operations."""

    @pytest.mark.asyncio
    async def test_add_partition_on_nonpartitioned_table_raises_error(self, async_clickhouse_backend):
        """ALTER TABLE ADD PARTITION should fail on a non-partitioned table (async)."""
        await _async_setup_negative_tables(async_clickhouse_backend)
        try:
            with pytest.raises(Exception):
                await async_clickhouse_backend.execute(
                    *ClickHouseAddPartitionExpression(
                        async_clickhouse_backend.dialect,
                        NEGATIVE_TABLE,
                        [
                            ClickHousePartitionDefinition(
                                "p_extra",
                                less_than=[ClickHousePartitionValue(async_clickhouse_backend.dialect, 300)],
                            ),
                        ],
                    ).to_sql()
                )
        finally:
            await _async_teardown_negative_tables(async_clickhouse_backend)

    @pytest.mark.asyncio
    async def test_drop_nonexistent_partition_raises_error(self, async_clickhouse_backend):
        """ALTER TABLE DROP PARTITION should fail when partition does not exist (async)."""
        await _async_setup_negative_tables(async_clickhouse_backend)
        try:
            with pytest.raises(Exception):
                await async_clickhouse_backend.execute(
                    *ClickHouseDropPartitionExpression(
                        async_clickhouse_backend.dialect, NEGATIVE_PARTITIONED_TABLE, ["p_nonexistent"]
                    ).to_sql()
                )
        finally:
            await _async_teardown_negative_tables(async_clickhouse_backend)

    @pytest.mark.asyncio
    async def test_add_partition_duplicate_boundary_raises_error(self, async_clickhouse_backend):
        """ALTER TABLE ADD PARTITION should fail on overlapping boundary (async)."""
        await _async_setup_negative_tables(async_clickhouse_backend)
        try:
            with pytest.raises(Exception):
                await async_clickhouse_backend.execute(
                    *ClickHouseAddPartitionExpression(
                        async_clickhouse_backend.dialect,
                        NEGATIVE_PARTITIONED_TABLE,
                        [
                            ClickHousePartitionDefinition(
                                "p_overlap",
                                less_than=[ClickHousePartitionValue(async_clickhouse_backend.dialect, 150)],
                            ),
                        ],
                    ).to_sql()
                )
        finally:
            await _async_teardown_negative_tables(async_clickhouse_backend)

    @pytest.mark.asyncio
    async def test_coalesce_partition_count_exceeds_existing_raises_error(self, async_clickhouse_backend):
        """ALTER TABLE COALESCE PARTITION should fail when count exceeds existing (async)."""
        await _async_setup_negative_tables(async_clickhouse_backend)
        try:
            with pytest.raises(Exception):
                await async_clickhouse_backend.execute(
                    *ClickHouseCoalescePartitionExpression(
                        async_clickhouse_backend.dialect, NEGATIVE_HASH_TABLE, 10
                    ).to_sql()
                )
        finally:
            await _async_teardown_negative_tables(async_clickhouse_backend)


class TestAsyncClickHousePartitionOperationsConcurrency:
    """Asynchronous concurrency and transaction tests for ClickHouse partition operations."""

    @pytest.mark.asyncio
    async def test_partition_ddl_triggers_implicit_commit(
        self, async_clickhouse_backend, async_clickhouse_partitioned_table
    ):
        """ALTER TABLE ADD PARTITION inside a transaction should auto-commit (async)."""
        await async_clickhouse_backend.execute("BEGIN")
        await async_clickhouse_backend.execute(
            *_insert_events_expression(
                async_clickhouse_backend.dialect,
                [[1, datetime(2026, 1, 15), "jan"]],
            ).to_sql()
        )
        await async_clickhouse_backend.execute(
            *_add_future_partition_expression(async_clickhouse_backend.dialect).to_sql()
        )
        await async_clickhouse_backend.execute("ROLLBACK")

        names = await _async_partition_names(async_clickhouse_backend)
        assert "p2026_03" in names


# --- Subpartition integration tests ---

SUBPARTITION_TABLE = "ar_clickhouse_partition_subpart"


def _subpartition_columns():
    return [
        ColumnDefinition("id", BigIntType(), constraints=[ColumnConstraint(ColumnConstraintType.NOT_NULL)]),
        ColumnDefinition("created_at", DateType(), constraints=[ColumnConstraint(ColumnConstraintType.NOT_NULL)]),
        ColumnDefinition("region", VarCharType(32), constraints=[ColumnConstraint(ColumnConstraintType.NOT_NULL)]),
        ColumnDefinition("payload", VarCharType(255)),
    ]


def _create_subpartitioned_table_expression(dialect):
    return CreateTableExpression(
        dialect=dialect,
        table=SUBPARTITION_TABLE,
        columns=_subpartition_columns(),
        partition=ClickHousePartitionByRangeColumns(
            dialect=dialect,
            keys=[Column(dialect, "created_at")],
            partitions=[
                ClickHousePartitionDefinition(
                    name="p2026",
                    less_than=[ClickHousePartitionValue(dialect, "2027-01-01")],
                    subpartition_definitions=None,
                ),
                ClickHousePartitionDefinition(
                    name="p2027",
                    less_than=[ClickHousePartitionValue(dialect, "2028-01-01")],
                    subpartition_definitions=None,
                ),
            ],
            subpartition_by=ClickHouseSubpartitionClause(
                dialect=dialect,
                strategy=ClickHouseSubpartitionStrategy.HASH,
                expression=Column(dialect, "id"),
                count=4,
            ),
        ),
    )


def _create_subpartitioned_table(backend):
    backend.execute(*_drop_named_table_expression(backend.dialect, SUBPARTITION_TABLE).to_sql())
    backend.execute(*_create_subpartitioned_table_expression(backend.dialect).to_sql())


async def _async_create_subpartitioned_table(backend):
    await backend.execute(*_drop_named_table_expression(backend.dialect, SUBPARTITION_TABLE).to_sql())
    await backend.execute(*_create_subpartitioned_table_expression(backend.dialect).to_sql())


def _subpartition_metadata(backend):
    partitions = TableExpression(dialect=backend.dialect, name="PARTITIONS", schema_name="information_schema")
    return backend.fetch_all(
        *QueryExpression(
            dialect=backend.dialect,
            select=[
                Column(backend.dialect, "PARTITION_NAME", alias="name"),
                Column(backend.dialect, "SUBPARTITION_NAME", alias="subname"),
                Column(backend.dialect, "SUBPARTITION_METHOD", alias="submethod"),
                Column(backend.dialect, "SUBPARTITION_EXPRESSION", alias="subexpression"),
                Column(backend.dialect, "TABLE_ROWS", alias="table_rows"),
            ],
            from_=partitions,
            where=LogicalPredicate(
                backend.dialect,
                "AND",
                Column(backend.dialect, "TABLE_SCHEMA") == FunctionCall(backend.dialect, "DATABASE"),
                Column(backend.dialect, "TABLE_NAME") == Literal(backend.dialect, SUBPARTITION_TABLE),
            ),
            order_by=OrderByClause(
                backend.dialect,
                [
                    (Column(backend.dialect, "PARTITION_ORDINAL_POSITION"), "ASC"),
                    (Column(backend.dialect, "SUBPARTITION_ORDINAL_POSITION"), "ASC"),
                ],
            ),
        ).to_sql()
    )


async def _async_subpartition_metadata(backend):
    partitions = TableExpression(dialect=backend.dialect, name="PARTITIONS", schema_name="information_schema")
    return await backend.fetch_all(
        *QueryExpression(
            dialect=backend.dialect,
            select=[
                Column(backend.dialect, "PARTITION_NAME", alias="name"),
                Column(backend.dialect, "SUBPARTITION_NAME", alias="subname"),
                Column(backend.dialect, "SUBPARTITION_METHOD", alias="submethod"),
                Column(backend.dialect, "SUBPARTITION_EXPRESSION", alias="subexpression"),
                Column(backend.dialect, "TABLE_ROWS", alias="table_rows"),
            ],
            from_=partitions,
            where=LogicalPredicate(
                backend.dialect,
                "AND",
                Column(backend.dialect, "TABLE_SCHEMA") == FunctionCall(backend.dialect, "DATABASE"),
                Column(backend.dialect, "TABLE_NAME") == Literal(backend.dialect, SUBPARTITION_TABLE),
            ),
            order_by=OrderByClause(
                backend.dialect,
                [
                    (Column(backend.dialect, "PARTITION_ORDINAL_POSITION"), "ASC"),
                    (Column(backend.dialect, "SUBPARTITION_ORDINAL_POSITION"), "ASC"),
                ],
            ),
        ).to_sql()
    )


class TestClickHouseSubpartitionOperations:
    """Synchronous real backend tests for ClickHouse subpartitioning."""

    def test_create_subpartitioned_table_has_subpartition_metadata(self, clickhouse_backend):
        """A table with SUBPARTITION BY should expose subpartition metadata in information_schema."""
        _create_subpartitioned_table(clickhouse_backend)
        try:
            rows = _subpartition_metadata(clickhouse_backend)
            assert len(rows) == 8  # 2 partitions × 4 subpartitions
            parent_partitions = {row["name"] for row in rows}
            assert parent_partitions == {"p2026", "p2027"}
            subpartition_names = [row["subname"] for row in rows if row["subname"]]
            # ClickHouse auto-generates subpartition names (s0..s7) when not specified
            assert len(subpartition_names) == 8
            for row in rows:
                if row["subname"]:
                    assert row["submethod"] is not None
                    assert "HASH" in str(row["submethod"]).upper()
        finally:
            clickhouse_backend.execute(*_drop_named_table_expression(clickhouse_backend.dialect, SUBPARTITION_TABLE).to_sql())

    def test_insert_into_subpartitioned_table_and_query(self, clickhouse_backend):
        """Rows inserted into a subpartitioned table should be queryable through the parent."""
        _create_subpartitioned_table(clickhouse_backend)
        try:
            insert = InsertExpression(
                dialect=clickhouse_backend.dialect,
                into=SUBPARTITION_TABLE,
                columns=["id", "created_at", "region", "payload"],
                source=ValuesSource(
                    clickhouse_backend.dialect,
                    [
                        [Literal(clickhouse_backend.dialect, 1), Literal(clickhouse_backend.dialect, "2026-06-01"),
                         Literal(clickhouse_backend.dialect, "us"), Literal(clickhouse_backend.dialect, "alpha")],
                        [Literal(clickhouse_backend.dialect, 2), Literal(clickhouse_backend.dialect, "2026-06-15"),
                         Literal(clickhouse_backend.dialect, "eu"), Literal(clickhouse_backend.dialect, "beta")],
                        [Literal(clickhouse_backend.dialect, 3), Literal(clickhouse_backend.dialect, "2027-03-01"),
                         Literal(clickhouse_backend.dialect, "ap"), Literal(clickhouse_backend.dialect, "gamma")],
                    ],
                ),
            )
            clickhouse_backend.execute(*insert.to_sql())

            query = QueryExpression(
                dialect=clickhouse_backend.dialect,
                select=[Column(clickhouse_backend.dialect, "payload")],
                from_=TableExpression(clickhouse_backend.dialect, SUBPARTITION_TABLE),
                order_by=OrderByClause(clickhouse_backend.dialect, [(Column(clickhouse_backend.dialect, "id"), "ASC")]),
            )
            rows = clickhouse_backend.fetch_all(*query.to_sql())
            assert [row["payload"] for row in rows] == ["alpha", "beta", "gamma"]
        finally:
            clickhouse_backend.execute(*_drop_named_table_expression(clickhouse_backend.dialect, SUBPARTITION_TABLE).to_sql())


class TestAsyncClickHouseSubpartitionOperations:
    """Asynchronous real backend tests for ClickHouse subpartitioning."""

    @pytest.mark.asyncio
    async def test_create_subpartitioned_table_has_subpartition_metadata(self, async_clickhouse_backend):
        """Subpartitioned table should expose subpartition metadata (async)."""
        await _async_create_subpartitioned_table(async_clickhouse_backend)
        try:
            rows = await _async_subpartition_metadata(async_clickhouse_backend)
            assert len(rows) == 8
            parent_partitions = {row["name"] for row in rows}
            assert parent_partitions == {"p2026", "p2027"}
        finally:
            await async_clickhouse_backend.execute(
                *_drop_named_table_expression(async_clickhouse_backend.dialect, SUBPARTITION_TABLE).to_sql()
            )

    @pytest.mark.asyncio
    async def test_insert_into_subpartitioned_table_and_query(self, async_clickhouse_backend):
        """Rows inserted into subpartitioned table should be queryable (async)."""
        await _async_create_subpartitioned_table(async_clickhouse_backend)
        try:
            insert = InsertExpression(
                dialect=async_clickhouse_backend.dialect,
                into=SUBPARTITION_TABLE,
                columns=["id", "created_at", "region", "payload"],
                source=ValuesSource(
                    async_clickhouse_backend.dialect,
                    [
                        [Literal(async_clickhouse_backend.dialect, 1),
                         Literal(async_clickhouse_backend.dialect, "2026-06-01"),
                         Literal(async_clickhouse_backend.dialect, "us"),
                         Literal(async_clickhouse_backend.dialect, "alpha")],
                    ],
                ),
            )
            await async_clickhouse_backend.execute(*insert.to_sql())
            query = QueryExpression(
                dialect=async_clickhouse_backend.dialect,
                select=[Column(async_clickhouse_backend.dialect, "payload")],
                from_=TableExpression(async_clickhouse_backend.dialect, SUBPARTITION_TABLE),
            )
            rows = await async_clickhouse_backend.fetch_all(*query.to_sql())
            assert [row["payload"] for row in rows] == ["alpha"]
        finally:
            await async_clickhouse_backend.execute(
                *_drop_named_table_expression(async_clickhouse_backend.dialect, SUBPARTITION_TABLE).to_sql()
            )


class TestClickHouseProductionTimePartitionOperations:
    """Synchronous production-style time partition operation scenarios."""

    def test_maxvalue_catch_all_partition_can_be_split_for_future_traffic(
        self,
        clickhouse_backend,
        clickhouse_production_maxvalue_partition_table,
    ):
        """Use MAXVALUE as a catch-all partition and split it later.

                Scenario: operators keep a `pmax` catch-all partition so unexpected future
                timestamps remain writable while alerting metadata still exposes the
                operational debt.

                Steps: create `p2026` plus `pmax`, insert one 2026 row and one far-future
                row, inspect EXPLAIN partition pruning for the future row, then reorganize
                `pmax` into `p2027` plus a new `pmax`.

                Assertions: metadata includes `MAXVALUE`; far-future data routes through
                `pmax` before the split; after reorganization, 2027 data moves to `p2027`
                while future rows beyond 2027 remain queryable through the catch-all.

                Production value: this documents the safer ClickHouse runbook for catch-all
                traffic and the follow-up maintenance path that turns emergency overflow
                into explicit future ranges.
        """
        assert clickhouse_production_maxvalue_partition_table == PRODUCTION_MAXVALUE_TABLE
        metadata = clickhouse_backend.fetch_all(
            *_partition_metadata_expression_for_table(
                clickhouse_backend.dialect,
                PRODUCTION_MAXVALUE_TABLE,
            ).to_sql()
        )
        _assert_partition_metadata(metadata, ["p2026", "pmax"])
        assert any("MAXVALUE" in str(row["description"]).upper() for row in metadata)

        clickhouse_backend.execute(
            *_insert_production_events_into_expression(
                clickhouse_backend.dialect,
                PRODUCTION_MAXVALUE_TABLE,
                [
                    [101, datetime(2026, 6, 1), 10, "regular-year"],
                    [102, datetime(2035, 1, 1), 10, "catch-all"],
                ],
            ).to_sql()
        )
        future_rows = clickhouse_backend.fetch_all(
            *_select_production_payloads_from_expression(
                clickhouse_backend.dialect,
                PRODUCTION_MAXVALUE_TABLE,
                datetime(2030, 1, 1),
                datetime(2040, 1, 1),
                tenant_id=10,
            ).to_sql()
        )
        assert [row["payload"] for row in future_rows] == ["catch-all"]

        result = clickhouse_backend.explain(
            _production_range_query_for_table_expression(
                clickhouse_backend.dialect,
                PRODUCTION_MAXVALUE_TABLE,
                datetime(2030, 1, 1),
                datetime(2040, 1, 1),
                tenant_id=10,
            )
        )
        partitions = set(_collect_explain_partitions(result))
        if partitions:
            assert partitions == {"pmax"}

        clickhouse_backend.execute(*_reorganize_maxvalue_partition_expression(clickhouse_backend.dialect).to_sql())
        metadata = clickhouse_backend.fetch_all(
            *_partition_metadata_expression_for_table(
                clickhouse_backend.dialect,
                PRODUCTION_MAXVALUE_TABLE,
            ).to_sql()
        )
        _assert_partition_metadata(metadata, ["p2026", "p2027", "pmax"])
        clickhouse_backend.execute(
            *_insert_production_events_into_expression(
                clickhouse_backend.dialect,
                PRODUCTION_MAXVALUE_TABLE,
                [[103, datetime(2027, 6, 1), 10, "split-year"]],
            ).to_sql()
        )
        rows = clickhouse_backend.fetch_all(
            *_select_production_payloads_from_expression(
                clickhouse_backend.dialect,
                PRODUCTION_MAXVALUE_TABLE,
                datetime(2027, 1, 1),
                datetime(2040, 1, 1),
                tenant_id=10,
            ).to_sql()
        )
        assert [row["payload"] for row in rows] == ["catch-all", "split-year"]

    def test_initial_year_partition_uses_microsecond_boundaries(
        self,
        clickhouse_backend,
        clickhouse_production_year_partition_table,
    ):
        """Validate the initial annual partition used during table rollout.
        
                Scenario: the production table starts with only the 2026 calendar-year
                partition. The partition key is `created_at DATETIME(6)`, and the
                primary key includes `(id, created_at)` to satisfy ClickHouse partitioned
                unique-key rules.
        
                Steps: create the parent table with only `p2026`, insert the 2026 lower
                bound and the last microsecond before 2027, then try to insert the first
                timestamp of 2027 before a future partition exists.
        
                Assertions: metadata lists only `p2026`; microsecond boundary rows are
                queryable through the parent table; out-of-range future data is rejected
                by the database.
        
                Production value: this proves the annual rollout can cover a complete
                calendar year while exposing a missing future partition as an operational
                failure instead of silently losing data.
        """
        assert clickhouse_production_year_partition_table == PRODUCTION_PARTITION_TABLE
        _assert_partition_metadata(_production_partition_metadata(clickhouse_backend), ["p2026"])

        clickhouse_backend.execute(
            *_insert_production_events_expression(
                clickhouse_backend.dialect,
                [
                    [1, datetime(2026, 1, 1, 0, 0, 0, 0), 10, "year-start"],
                    [2, datetime(2026, 12, 31, 23, 59, 59, 999999), 10, "year-end"],
                ],
            ).to_sql()
        )

        rows = clickhouse_backend.fetch_all(
            *_select_production_payloads_expression(
                clickhouse_backend.dialect,
                datetime(2026, 1, 1),
                datetime(2027, 1, 1),
            ).to_sql()
        )
        assert [row["payload"] for row in rows] == ["year-start", "year-end"]

        with pytest.raises(Exception):
            clickhouse_backend.execute(
                *_insert_production_events_expression(
                    clickhouse_backend.dialect,
                    [[3, datetime(2027, 1, 1, 0, 0, 0, 0), 10, "missing-partition"]],
                ).to_sql()
            )

    def test_precreate_future_partitions_before_traffic_arrives(
        self,
        clickhouse_backend,
        clickhouse_production_year_partition_table,
    ):
        """Pre-create future partitions with mixed operational granularities.
        
                Scenario: operators prepare future partitions before traffic arrives,
                and the future granularity may shift from yearly to quarterly, monthly,
                or weekly partitions.
        
                Steps: start from the initial `p2026` table, add `p2027_q1`,
                `p2027_04`, and `p2027_w18`, then insert rows into each future window.
        
                Assertions: metadata reflects all newly added partitions; future rows
                are accepted; parent-table queries can read the full pre-created range.
        
                Production value: this verifies rolling partition pre-creation so the
                database can cross time boundaries without emergency DDL during traffic.
        """
        for name, upper_bound in PRODUCTION_PARTITIONS[1:]:
            clickhouse_backend.execute(
                *_add_production_partition_expression(
                    clickhouse_backend.dialect,
                    name,
                    upper_bound,
                ).to_sql()
            )

        _assert_partition_metadata(
            _production_partition_metadata(clickhouse_backend),
            [name for name, _ in PRODUCTION_PARTITIONS],
        )
        clickhouse_backend.execute(
            *_insert_production_events_expression(
                clickhouse_backend.dialect,
                [
                    [11, datetime(2027, 2, 15, 8, 0, 0, 123456), 10, "q1"],
                    [12, datetime(2027, 4, 15, 8, 0, 0, 123456), 10, "month"],
                    [13, datetime(2027, 5, 3, 8, 0, 0, 123456), 10, "week"],
                ],
            ).to_sql()
        )

        rows = clickhouse_backend.fetch_all(
            *_select_production_payloads_expression(
                clickhouse_backend.dialect,
                datetime(2027, 1, 1),
                datetime(2027, 5, 8),
            ).to_sql()
        )
        assert [row["payload"] for row in rows] == ["q1", "month", "week"]

    def test_query_continuous_partitions_and_explain_uses_index(
        self,
        clickhouse_backend,
        clickhouse_production_partition_table,
    ):
        """Query a continuous time range and inspect pruning/index candidates.
        
                Scenario: production searches often span several continuous partitions
                while filtering by tenant and time range.
        
                Steps: insert rows across yearly, quarterly, monthly, and weekly
                partitions, query `[2027-02-01, 2027-05-08)` for `tenant_id=10`, and run
                ClickHouse EXPLAIN for the same expression.
        
                Assertions: the query returns only target-tenant rows in the continuous
                range; EXPLAIN reports only the target partitions when partition data is
                available; `possible_keys` or `key` exposes the `(tenant_id, created_at)`
                composite index.
        
                Production value: this demonstrates that partition pruning and business
                indexes work together, and that partitioning does not replace the need
                for query indexes.
        """
        clickhouse_backend.execute(
            *_insert_production_events_expression(
                clickhouse_backend.dialect,
                [
                    [21, datetime(2026, 6, 1), 10, "old-year"],
                    [22, datetime(2027, 2, 15), 10, "q1"],
                    [23, datetime(2027, 4, 15), 10, "month"],
                    [24, datetime(2027, 5, 3), 10, "week"],
                    [25, datetime(2027, 5, 3), 20, "other-tenant"],
                ],
            ).to_sql()
        )

        rows = clickhouse_backend.fetch_all(
            *_select_production_payloads_expression(
                clickhouse_backend.dialect,
                datetime(2027, 2, 1),
                datetime(2027, 5, 8),
                tenant_id=10,
            ).to_sql()
        )
        assert [row["payload"] for row in rows] == ["q1", "month", "week"]

        result = clickhouse_backend.explain(
            _production_range_query_expression(
                clickhouse_backend.dialect,
                datetime(2027, 2, 1),
                datetime(2027, 5, 8),
                tenant_id=10,
            )
        )
        partitions = set(_collect_explain_partitions(result))
        if partitions:
            assert partitions <= {"p2027_q1", "p2027_04", "p2027_w18"}
            assert {"p2027_q1", "p2027_04", "p2027_w18"}.issubset(partitions)
        key_names = {
            key
            for row in result.rows
            for key in (row.key, row.possible_keys)
            if key
        }
        assert any("idx_tenant_created_at" in key for key in key_names)

    def test_exchange_expired_year_partition_for_cold_archive(
        self,
        clickhouse_backend,
        clickhouse_production_partition_table,
    ):
        """Cold-archive an expired year partition with EXCHANGE PARTITION.
        
                Scenario: ClickHouse has no PostgreSQL-style `DETACH PARTITION`; `DROP
                PARTITION` and `TRUNCATE PARTITION` must not be used as cold archival
                operations because they delete or clear data.
        
                Steps: create a structurally identical archive table, insert cold 2026
                data and hot 2027 data, then exchange `p2026` with the archive table.
        
                Assertions: parent metadata still keeps the `p2026` partition; the
                parent table no longer returns cold data but still returns hot data; the
                archive table keeps the exchanged cold data.
        
                Production value: this documents the safe ClickHouse cold-archive path that
                preserves data instead of using destructive partition maintenance.
        """
        if not clickhouse_backend.dialect.supports_exchange_partition():
            pytest.skip("ClickHouse scenario does not support EXCHANGE PARTITION")

        clickhouse_backend.execute(*_create_production_archive_table_expression(clickhouse_backend.dialect).to_sql())
        clickhouse_backend.execute(
            *_insert_production_events_expression(
                clickhouse_backend.dialect,
                [
                    [31, datetime(2026, 6, 1), 10, "cold-year"],
                    [32, datetime(2027, 2, 1), 10, "hot-quarter"],
                ],
            ).to_sql()
        )
        clickhouse_backend.execute(
            *ClickHouseExchangePartitionExpression(
                clickhouse_backend.dialect,
                PRODUCTION_PARTITION_TABLE,
                "p2026",
                PRODUCTION_ARCHIVE_TABLE,
            ).to_sql()
        )

        parent_count = clickhouse_backend.fetch_one(
            *_select_production_count_expression(clickhouse_backend.dialect).to_sql()
        )["count"]
        archive_count = clickhouse_backend.fetch_one(
            *_select_archive_count_expression(clickhouse_backend.dialect).to_sql()
        )["count"]
        assert parent_count == 1
        assert archive_count == 1
        _assert_partition_metadata(
            _production_partition_metadata(clickhouse_backend),
            [name for name, _ in PRODUCTION_PARTITIONS],
        )


class TestAsyncClickHouseProductionTimePartitionOperations:
    """Asynchronous production-style time partition operation scenarios."""

    @pytest.mark.asyncio
    async def test_maxvalue_catch_all_partition_can_be_split_for_future_traffic(
        self,
        async_clickhouse_backend,
        async_clickhouse_production_maxvalue_partition_table,
    ):
        """Use MAXVALUE as a catch-all partition and split it later.

                Scenario: operators keep a `pmax` catch-all partition so unexpected future
                timestamps remain writable while alerting metadata still exposes the
                operational debt.

                Steps: create `p2026` plus `pmax`, insert one 2026 row and one far-future
                row, inspect EXPLAIN partition pruning for the future row, then reorganize
                `pmax` into `p2027` plus a new `pmax`.

                Assertions: metadata includes `MAXVALUE`; far-future data routes through
                `pmax` before the split; after reorganization, 2027 data moves to `p2027`
                while future rows beyond 2027 remain queryable through the catch-all.

                Production value: this documents the safer ClickHouse runbook for catch-all
                traffic and the follow-up maintenance path that turns emergency overflow
                into explicit future ranges.
        """
        assert async_clickhouse_production_maxvalue_partition_table == PRODUCTION_MAXVALUE_TABLE
        metadata = await async_clickhouse_backend.fetch_all(
            *_partition_metadata_expression_for_table(
                async_clickhouse_backend.dialect,
                PRODUCTION_MAXVALUE_TABLE,
            ).to_sql()
        )
        _assert_partition_metadata(metadata, ["p2026", "pmax"])
        assert any("MAXVALUE" in str(row["description"]).upper() for row in metadata)

        await async_clickhouse_backend.execute(
            *_insert_production_events_into_expression(
                async_clickhouse_backend.dialect,
                PRODUCTION_MAXVALUE_TABLE,
                [
                    [101, datetime(2026, 6, 1), 10, "regular-year"],
                    [102, datetime(2035, 1, 1), 10, "catch-all"],
                ],
            ).to_sql()
        )
        future_rows = await async_clickhouse_backend.fetch_all(
            *_select_production_payloads_from_expression(
                async_clickhouse_backend.dialect,
                PRODUCTION_MAXVALUE_TABLE,
                datetime(2030, 1, 1),
                datetime(2040, 1, 1),
                tenant_id=10,
            ).to_sql()
        )
        assert [row["payload"] for row in future_rows] == ["catch-all"]

        result = await async_clickhouse_backend.explain(
            _production_range_query_for_table_expression(
                async_clickhouse_backend.dialect,
                PRODUCTION_MAXVALUE_TABLE,
                datetime(2030, 1, 1),
                datetime(2040, 1, 1),
                tenant_id=10,
            )
        )
        partitions = set(_collect_explain_partitions(result))
        if partitions:
            assert partitions == {"pmax"}

        await async_clickhouse_backend.execute(
            *_reorganize_maxvalue_partition_expression(async_clickhouse_backend.dialect).to_sql()
        )
        metadata = await async_clickhouse_backend.fetch_all(
            *_partition_metadata_expression_for_table(
                async_clickhouse_backend.dialect,
                PRODUCTION_MAXVALUE_TABLE,
            ).to_sql()
        )
        _assert_partition_metadata(metadata, ["p2026", "p2027", "pmax"])
        await async_clickhouse_backend.execute(
            *_insert_production_events_into_expression(
                async_clickhouse_backend.dialect,
                PRODUCTION_MAXVALUE_TABLE,
                [[103, datetime(2027, 6, 1), 10, "split-year"]],
            ).to_sql()
        )
        rows = await async_clickhouse_backend.fetch_all(
            *_select_production_payloads_from_expression(
                async_clickhouse_backend.dialect,
                PRODUCTION_MAXVALUE_TABLE,
                datetime(2027, 1, 1),
                datetime(2040, 1, 1),
                tenant_id=10,
            ).to_sql()
        )
        assert [row["payload"] for row in rows] == ["catch-all", "split-year"]

    @pytest.mark.asyncio
    async def test_initial_year_partition_uses_microsecond_boundaries(
        self,
        async_clickhouse_backend,
        async_clickhouse_production_year_partition_table,
    ):
        """Validate the initial annual partition used during table rollout.
        
                Scenario: the production table starts with only the 2026 calendar-year
                partition. The partition key is `created_at DATETIME(6)`, and the
                primary key includes `(id, created_at)` to satisfy ClickHouse partitioned
                unique-key rules.
        
                Steps: create the parent table with only `p2026`, insert the 2026 lower
                bound and the last microsecond before 2027, then try to insert the first
                timestamp of 2027 before a future partition exists.
        
                Assertions: metadata lists only `p2026`; microsecond boundary rows are
                queryable through the parent table; out-of-range future data is rejected
                by the database.
        
                Production value: this proves the annual rollout can cover a complete
                calendar year while exposing a missing future partition as an operational
                failure instead of silently losing data.
        """
        assert async_clickhouse_production_year_partition_table == PRODUCTION_PARTITION_TABLE
        rows = await _async_production_partition_metadata(async_clickhouse_backend)
        _assert_partition_metadata(rows, ["p2026"])

        await async_clickhouse_backend.execute(
            *_insert_production_events_expression(
                async_clickhouse_backend.dialect,
                [
                    [1, datetime(2026, 1, 1, 0, 0, 0, 0), 10, "year-start"],
                    [2, datetime(2026, 12, 31, 23, 59, 59, 999999), 10, "year-end"],
                ],
            ).to_sql()
        )

        rows = await async_clickhouse_backend.fetch_all(
            *_select_production_payloads_expression(
                async_clickhouse_backend.dialect,
                datetime(2026, 1, 1),
                datetime(2027, 1, 1),
            ).to_sql()
        )
        assert [row["payload"] for row in rows] == ["year-start", "year-end"]

        with pytest.raises(Exception):
            await async_clickhouse_backend.execute(
                *_insert_production_events_expression(
                    async_clickhouse_backend.dialect,
                    [[3, datetime(2027, 1, 1, 0, 0, 0, 0), 10, "missing-partition"]],
                ).to_sql()
            )

    @pytest.mark.asyncio
    async def test_precreate_future_partitions_before_traffic_arrives(
        self,
        async_clickhouse_backend,
        async_clickhouse_production_year_partition_table,
    ):
        """Pre-create future partitions with mixed operational granularities.
        
                Scenario: operators prepare future partitions before traffic arrives,
                and the future granularity may shift from yearly to quarterly, monthly,
                or weekly partitions.
        
                Steps: start from the initial `p2026` table, add `p2027_q1`,
                `p2027_04`, and `p2027_w18`, then insert rows into each future window.
        
                Assertions: metadata reflects all newly added partitions; future rows
                are accepted; parent-table queries can read the full pre-created range.
        
                Production value: this verifies rolling partition pre-creation so the
                database can cross time boundaries without emergency DDL during traffic.
        """
        for name, upper_bound in PRODUCTION_PARTITIONS[1:]:
            await async_clickhouse_backend.execute(
                *_add_production_partition_expression(
                    async_clickhouse_backend.dialect,
                    name,
                    upper_bound,
                ).to_sql()
            )

        rows = await _async_production_partition_metadata(async_clickhouse_backend)
        _assert_partition_metadata(rows, [name for name, _ in PRODUCTION_PARTITIONS])
        await async_clickhouse_backend.execute(
            *_insert_production_events_expression(
                async_clickhouse_backend.dialect,
                [
                    [11, datetime(2027, 2, 15, 8, 0, 0, 123456), 10, "q1"],
                    [12, datetime(2027, 4, 15, 8, 0, 0, 123456), 10, "month"],
                    [13, datetime(2027, 5, 3, 8, 0, 0, 123456), 10, "week"],
                ],
            ).to_sql()
        )

        rows = await async_clickhouse_backend.fetch_all(
            *_select_production_payloads_expression(
                async_clickhouse_backend.dialect,
                datetime(2027, 1, 1),
                datetime(2027, 5, 8),
            ).to_sql()
        )
        assert [row["payload"] for row in rows] == ["q1", "month", "week"]

    @pytest.mark.asyncio
    async def test_query_continuous_partitions_and_explain_uses_index(
        self,
        async_clickhouse_backend,
        async_clickhouse_production_partition_table,
    ):
        """Query a continuous time range and inspect pruning/index candidates.
        
                Scenario: production searches often span several continuous partitions
                while filtering by tenant and time range.
        
                Steps: insert rows across yearly, quarterly, monthly, and weekly
                partitions, query `[2027-02-01, 2027-05-08)` for `tenant_id=10`, and run
                ClickHouse EXPLAIN for the same expression.
        
                Assertions: the query returns only target-tenant rows in the continuous
                range; EXPLAIN reports only the target partitions when partition data is
                available; `possible_keys` or `key` exposes the `(tenant_id, created_at)`
                composite index.
        
                Production value: this demonstrates that partition pruning and business
                indexes work together, and that partitioning does not replace the need
                for query indexes.
        """
        await async_clickhouse_backend.execute(
            *_insert_production_events_expression(
                async_clickhouse_backend.dialect,
                [
                    [21, datetime(2026, 6, 1), 10, "old-year"],
                    [22, datetime(2027, 2, 15), 10, "q1"],
                    [23, datetime(2027, 4, 15), 10, "month"],
                    [24, datetime(2027, 5, 3), 10, "week"],
                    [25, datetime(2027, 5, 3), 20, "other-tenant"],
                ],
            ).to_sql()
        )

        rows = await async_clickhouse_backend.fetch_all(
            *_select_production_payloads_expression(
                async_clickhouse_backend.dialect,
                datetime(2027, 2, 1),
                datetime(2027, 5, 8),
                tenant_id=10,
            ).to_sql()
        )
        assert [row["payload"] for row in rows] == ["q1", "month", "week"]

        result = await async_clickhouse_backend.explain(
            _production_range_query_expression(
                async_clickhouse_backend.dialect,
                datetime(2027, 2, 1),
                datetime(2027, 5, 8),
                tenant_id=10,
            )
        )
        partitions = set(_collect_explain_partitions(result))
        if partitions:
            assert partitions <= {"p2027_q1", "p2027_04", "p2027_w18"}
            assert {"p2027_q1", "p2027_04", "p2027_w18"}.issubset(partitions)
        key_names = {
            key
            for row in result.rows
            for key in (row.key, row.possible_keys)
            if key
        }
        assert any("idx_tenant_created_at" in key for key in key_names)

    @pytest.mark.asyncio
    async def test_exchange_expired_year_partition_for_cold_archive(
        self,
        async_clickhouse_backend,
        async_clickhouse_production_partition_table,
    ):
        """Cold-archive an expired year partition with EXCHANGE PARTITION.
        
                Scenario: ClickHouse has no PostgreSQL-style `DETACH PARTITION`; `DROP
                PARTITION` and `TRUNCATE PARTITION` must not be used as cold archival
                operations because they delete or clear data.
        
                Steps: create a structurally identical archive table, insert cold 2026
                data and hot 2027 data, then exchange `p2026` with the archive table.
        
                Assertions: parent metadata still keeps the `p2026` partition; the
                parent table no longer returns cold data but still returns hot data; the
                archive table keeps the exchanged cold data.
        
                Production value: this documents the safe ClickHouse cold-archive path that
                preserves data instead of using destructive partition maintenance.
        """
        if not async_clickhouse_backend.dialect.supports_exchange_partition():
            pytest.skip("ClickHouse scenario does not support EXCHANGE PARTITION")

        await async_clickhouse_backend.execute(
            *_create_production_archive_table_expression(async_clickhouse_backend.dialect).to_sql()
        )
        await async_clickhouse_backend.execute(
            *_insert_production_events_expression(
                async_clickhouse_backend.dialect,
                [
                    [31, datetime(2026, 6, 1), 10, "cold-year"],
                    [32, datetime(2027, 2, 1), 10, "hot-quarter"],
                ],
            ).to_sql()
        )
        await async_clickhouse_backend.execute(
            *ClickHouseExchangePartitionExpression(
                async_clickhouse_backend.dialect,
                PRODUCTION_PARTITION_TABLE,
                "p2026",
                PRODUCTION_ARCHIVE_TABLE,
            ).to_sql()
        )

        parent_count = (await async_clickhouse_backend.fetch_one(
            *_select_production_count_expression(async_clickhouse_backend.dialect).to_sql()
        ))["count"]
        archive_count = (await async_clickhouse_backend.fetch_one(
            *_select_archive_count_expression(async_clickhouse_backend.dialect).to_sql()
        ))["count"]
        assert parent_count == 1
        assert archive_count == 1
        rows = await _async_production_partition_metadata(async_clickhouse_backend)
        _assert_partition_metadata(rows, [name for name, _ in PRODUCTION_PARTITIONS])


class TestAsyncClickHousePartitionOperations:
    """Asynchronous real backend tests for ClickHouse partition operations."""

    @pytest.mark.asyncio
    async def test_create_range_partitioned_table(
        self,
        async_clickhouse_backend,
        async_clickhouse_partitioned_table,
    ):
        """information_schema.PARTITIONS should expose created partitions."""
        assert async_clickhouse_partitioned_table == PARTITION_TABLE
        assert await _async_partition_names(async_clickhouse_backend) == ["p2026_01", "p2026_02"]

    @pytest.mark.asyncio
    async def test_partition_metadata_contains_strategy_key_and_bounds(
        self,
        async_clickhouse_backend,
        async_clickhouse_partitioned_table,
    ):
        """information_schema.PARTITIONS should expose strategy, key, and bounds."""
        _assert_base_partition_metadata(await _async_partition_metadata(async_clickhouse_backend))

    @pytest.mark.asyncio
    async def test_show_create_table_includes_partition_definition(
        self,
        async_clickhouse_backend,
        async_clickhouse_partitioned_table,
    ):
        """SHOW CREATE TABLE should include the native partition definition."""
        create_sql = await _async_show_create_table_sql(async_clickhouse_backend)
        _assert_show_create_table_includes_partition_definition(create_sql)

    @pytest.mark.asyncio
    async def test_insert_across_partitions_and_query(
        self,
        async_clickhouse_backend,
        async_clickhouse_partitioned_table,
    ):
        """Rows inserted across ranges should remain queryable through parent table."""
        insert = _insert_events_expression(
            async_clickhouse_backend.dialect,
            [
                [1, datetime(2026, 1, 15), "jan"],
                [2, datetime(2026, 2, 15), "feb"],
            ],
        )
        await async_clickhouse_backend.execute(*insert.to_sql())

        rows = await async_clickhouse_backend.fetch_all(*_select_payloads_expression(async_clickhouse_backend.dialect).to_sql())
        assert [row["payload"] for row in rows] == ["jan", "feb"]

    @pytest.mark.asyncio
    async def test_add_partition_for_future_range(
        self,
        async_clickhouse_backend,
        async_clickhouse_partitioned_table,
    ):
        """ALTER TABLE ADD PARTITION should allow future range inserts."""
        await async_clickhouse_backend.execute(*_add_future_partition_expression(async_clickhouse_backend.dialect).to_sql())
        await async_clickhouse_backend.execute(
            *_insert_events_expression(
                async_clickhouse_backend.dialect,
                [[3, datetime(2026, 3, 15), "mar"]],
            ).to_sql()
        )

        assert await _async_partition_names(async_clickhouse_backend) == [
            "p2026_01",
            "p2026_02",
            "p2026_03",
        ]
        row = await async_clickhouse_backend.fetch_one(
            *_select_payload_by_id_expression(async_clickhouse_backend.dialect, 3).to_sql()
        )
        assert row["payload"] == "mar"

    @pytest.mark.asyncio
    async def test_drop_partition(self, async_clickhouse_backend, async_clickhouse_partitioned_table):
        """ALTER TABLE DROP PARTITION should remove the partition and its rows."""
        await async_clickhouse_backend.execute(
            *_insert_events_expression(
                async_clickhouse_backend.dialect,
                [
                    [1, datetime(2026, 1, 15), "jan"],
                    [2, datetime(2026, 2, 15), "feb"],
                ],
            ).to_sql()
        )
        await async_clickhouse_backend.execute(
            *_drop_partition_expression(async_clickhouse_backend.dialect, "p2026_01").to_sql()
        )

        assert await _async_partition_names(async_clickhouse_backend) == ["p2026_02"]
        rows = await async_clickhouse_backend.fetch_all(*_select_payloads_expression(async_clickhouse_backend.dialect).to_sql())
        assert [row["payload"] for row in rows] == ["feb"]

    @pytest.mark.asyncio
    async def test_truncate_partition(self, async_clickhouse_backend, async_clickhouse_partitioned_table):
        """ALTER TABLE TRUNCATE PARTITION should clear one range only."""
        await async_clickhouse_backend.execute(
            *_insert_events_expression(
                async_clickhouse_backend.dialect,
                [
                    [1, datetime(2026, 1, 15), "jan"],
                    [2, datetime(2026, 2, 15), "feb"],
                ],
            ).to_sql()
        )
        await async_clickhouse_backend.execute(
            *_truncate_partition_expression(async_clickhouse_backend.dialect, "p2026_01").to_sql()
        )

        rows = await async_clickhouse_backend.fetch_all(*_select_payloads_expression(async_clickhouse_backend.dialect).to_sql())
        assert [row["payload"] for row in rows] == ["feb"]

    @pytest.mark.asyncio
    async def test_reorganize_partition(self, async_clickhouse_backend, async_clickhouse_partitioned_table):
        """ALTER TABLE REORGANIZE PARTITION should split an existing range."""
        await async_clickhouse_backend.execute(*_reorganize_partition_expression(async_clickhouse_backend.dialect).to_sql())

        assert await _async_partition_names(async_clickhouse_backend) == [
            "p2026_01",
            "p2026_02a",
            "p2026_02b",
        ]

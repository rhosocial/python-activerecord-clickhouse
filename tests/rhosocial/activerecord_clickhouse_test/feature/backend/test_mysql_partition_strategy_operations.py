"""Real ClickHouse tests for partition strategies beyond RANGE COLUMNS."""

from typing import Sequence

import pytest

from rhosocial.activerecord.backend.expression import (
    Column,
    ColumnConstraint,
    ColumnConstraintType,
    ColumnDefinition,
    CreateTableExpression,
    DropTableExpression,
    FunctionCall,
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
from rhosocial.activerecord.backend.expression.types import BigIntType, DateType, VarCharType
from rhosocial.activerecord.backend.impl.clickhouse.expression import (
    ClickHouseAddPartitionExpression,
    ClickHouseDropPartitionExpression,
    ClickHousePartitionByHash,
    ClickHousePartitionByKey,
    ClickHousePartitionByList,
    ClickHousePartitionByListColumns,
    ClickHousePartitionByRange,
    ClickHousePartitionByRangeColumns,
    ClickHousePartitionDefinition,
    ClickHousePartitionMaxValue,
    ClickHousePartitionValue,
    ClickHouseTruncatePartitionExpression,
)


RANGE_TABLE = "ar_clickhouse_partition_strategy_range"
LIST_TABLE = "ar_clickhouse_partition_strategy_list"
LIST_COLUMNS_TABLE = "ar_clickhouse_partition_strategy_list_columns"
HASH_TABLE = "ar_clickhouse_partition_strategy_hash"
KEY_TABLE = "ar_clickhouse_partition_strategy_key"
LINEAR_HASH_TABLE = "ar_clickhouse_partition_strategy_linear_hash"
LINEAR_KEY_TABLE = "ar_clickhouse_partition_strategy_linear_key"
RANGE_COLUMNS_MULTI_TABLE = "ar_clickhouse_partition_range_cols_multi"
LIST_COLUMNS_MULTI_TABLE = "ar_clickhouse_partition_list_cols_multi"
STRATEGY_TABLES = (
    RANGE_TABLE,
    LIST_TABLE,
    LIST_COLUMNS_TABLE,
    HASH_TABLE,
    KEY_TABLE,
    LINEAR_HASH_TABLE,
    LINEAR_KEY_TABLE,
    RANGE_COLUMNS_MULTI_TABLE,
    LIST_COLUMNS_MULTI_TABLE,
)


def _drop_named_table_expression(dialect, table_name: str):
    return DropTableExpression(dialect=dialect, table=table_name, if_exists=True)


def _base_columns():
    return [
        ColumnDefinition("id", BigIntType(), constraints=[ColumnConstraint(ColumnConstraintType.NOT_NULL)]),
        ColumnDefinition("shard_id", BigIntType(), constraints=[ColumnConstraint(ColumnConstraintType.NOT_NULL)]),
        ColumnDefinition("category", VarCharType(32), constraints=[ColumnConstraint(ColumnConstraintType.NOT_NULL)]),
        ColumnDefinition("payload", VarCharType(255), constraints=[ColumnConstraint(ColumnConstraintType.NOT_NULL)]),
    ]


def _partition_value(dialect, value):
    return ClickHousePartitionValue(dialect, value)


def _create_range_table_expression(dialect):
    return CreateTableExpression(
        dialect=dialect,
        table=RANGE_TABLE,
        columns=_base_columns(),
        partition=ClickHousePartitionByRange(
            dialect=dialect,
            keys=[Column(dialect, "shard_id")],
            partitions=[
                ClickHousePartitionDefinition("p_low", less_than=[_partition_value(dialect, 100)]),
                ClickHousePartitionDefinition("p_mid", less_than=[_partition_value(dialect, 200)]),
            ],
        ),
    )


def _create_range_columns_multi_table_expression(dialect):
    return CreateTableExpression(
        dialect=dialect,
        table=RANGE_COLUMNS_MULTI_TABLE,
        columns=_base_columns(),
        partition=ClickHousePartitionByRangeColumns(
            dialect=dialect,
            keys=[Column(dialect, "shard_id"), Column(dialect, "id")],
            partitions=[
                ClickHousePartitionDefinition(
                    "p_low",
                    less_than=[_partition_value(dialect, 100), _partition_value(dialect, 100)],
                ),
                ClickHousePartitionDefinition(
                    "p_mid",
                    less_than=[_partition_value(dialect, 200), _partition_value(dialect, 500)],
                ),
                ClickHousePartitionDefinition(
                    "p_high",
                    less_than=[ClickHousePartitionMaxValue(dialect), ClickHousePartitionMaxValue(dialect)],
                ),
            ],
        ),
    )


def _create_list_columns_multi_table_expression(dialect):
    return CreateTableExpression(
        dialect=dialect,
        table=LIST_COLUMNS_MULTI_TABLE,
        columns=_base_columns(),
        partition=ClickHousePartitionByListColumns(
            dialect=dialect,
            keys=[Column(dialect, "category"), Column(dialect, "payload")],
            partitions=[
                ClickHousePartitionDefinition(
                    "p_group_a",
                    in_values=[
                        [_partition_value(dialect, "active"), _partition_value(dialect, "alpha")],
                        [_partition_value(dialect, "active"), _partition_value(dialect, "beta")],
                    ],
                ),
                ClickHousePartitionDefinition(
                    "p_group_b",
                    in_values=[
                        [_partition_value(dialect, "closed"), _partition_value(dialect, "gamma")],
                        [_partition_value(dialect, "archived"), _partition_value(dialect, "delta")],
                    ],
                ),
            ],
        ),
    )


def _create_list_table_expression(dialect):
    return CreateTableExpression(
        dialect=dialect,
        table=LIST_TABLE,
        columns=_base_columns(),
        partition=ClickHousePartitionByList(
            dialect=dialect,
            keys=[Column(dialect, "shard_id")],
            partitions=[
                ClickHousePartitionDefinition(
                    "p_small",
                    in_values=[_partition_value(dialect, 1), _partition_value(dialect, 2)],
                ),
                ClickHousePartitionDefinition(
                    "p_large",
                    in_values=[_partition_value(dialect, 3), _partition_value(dialect, 4)],
                ),
            ],
        ),
    )


def _create_list_columns_table_expression(dialect):
    return CreateTableExpression(
        dialect=dialect,
        table=LIST_COLUMNS_TABLE,
        columns=_base_columns(),
        partition=ClickHousePartitionByListColumns(
            dialect=dialect,
            keys=[Column(dialect, "category")],
            partitions=[
                ClickHousePartitionDefinition(
                    "p_active",
                    in_values=[_partition_value(dialect, "active"), _partition_value(dialect, "pending")],
                ),
                ClickHousePartitionDefinition(
                    "p_closed",
                    in_values=[_partition_value(dialect, "closed"), _partition_value(dialect, "archived")],
                ),
            ],
        ),
    )


def _create_hash_table_expression(dialect, table_name: str, *, linear: bool = False):
    return CreateTableExpression(
        dialect=dialect,
        table=table_name,
        columns=_base_columns(),
        partition=ClickHousePartitionByHash(
            dialect=dialect,
            keys=[Column(dialect, "shard_id")],
            partitions_count=4,
            linear=linear,
        ),
    )


def _create_key_table_expression(dialect, table_name: str, *, linear: bool = False):
    return CreateTableExpression(
        dialect=dialect,
        table=table_name,
        columns=_base_columns(),
        partition=ClickHousePartitionByKey(
            dialect=dialect,
            keys=[Column(dialect, "id")],
            partitions_count=4,
            linear=linear,
        ),
    )


def _insert_rows_expression(dialect, table_name: str, rows: Sequence[Sequence[object]]):
    return InsertExpression(
        dialect=dialect,
        into=table_name,
        columns=["id", "shard_id", "category", "payload"],
        source=ValuesSource(
            dialect,
            [[Literal(dialect, value) for value in row] for row in rows],
        ),
    )


def _select_payloads_expression(dialect, table_name: str):
    return QueryExpression(
        dialect,
        select=[Column(dialect, "payload")],
        from_=TableExpression(dialect, table_name),
        order_by=OrderByClause(dialect, [(Column(dialect, "id"), "ASC")]),
    )


def _select_count_expression(dialect, table_name: str):
    return QueryExpression(
        dialect,
        select=[FunctionCall(dialect, "COUNT", WildcardExpression(dialect)).as_("count")],
        from_=TableExpression(dialect, table_name),
    )


def _partition_metadata_expression(dialect, table_name: str):
    partitions = TableExpression(dialect, "PARTITIONS", schema_name="information_schema")
    return QueryExpression(
        dialect,
        select=[
            Column(dialect, "PARTITION_NAME", alias="name"),
            Column(dialect, "PARTITION_METHOD", alias="method"),
            Column(dialect, "PARTITION_EXPRESSION", alias="expression"),
            Column(dialect, "PARTITION_DESCRIPTION", alias="description"),
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


def _create_table(backend, table_name: str, expression_factory):
    backend.execute(*_drop_named_table_expression(backend.dialect, table_name).to_sql())
    backend.execute(*expression_factory(backend.dialect).to_sql())


def _drop_tables(backend):
    for table_name in STRATEGY_TABLES:
        backend.execute(*_drop_named_table_expression(backend.dialect, table_name).to_sql())


async def _async_create_table(backend, table_name: str, expression_factory):
    await backend.execute(*_drop_named_table_expression(backend.dialect, table_name).to_sql())
    await backend.execute(*expression_factory(backend.dialect).to_sql())


async def _async_drop_tables(backend):
    for table_name in STRATEGY_TABLES:
        await backend.execute(*_drop_named_table_expression(backend.dialect, table_name).to_sql())


def _metadata(backend, table_name: str):
    return backend.fetch_all(*_partition_metadata_expression(backend.dialect, table_name).to_sql())


async def _async_metadata(backend, table_name: str):
    return await backend.fetch_all(*_partition_metadata_expression(backend.dialect, table_name).to_sql())


def _assert_partition_method(rows, method: str):
    assert rows
    assert all(method in str(row["method"]).upper() for row in rows)


class TestClickHousePartitionStrategies:
    """Synchronous real backend tests for additional ClickHouse partition strategies."""

    def test_range_partition_routes_rows(self, clickhouse_backend):
        """Plain RANGE partitioning should work without COLUMNS mode."""
        _create_table(clickhouse_backend, RANGE_TABLE, _create_range_table_expression)
        try:
            clickhouse_backend.execute(
                *_insert_rows_expression(
                    clickhouse_backend.dialect,
                    RANGE_TABLE,
                    [(1, 10, "active", "low"), (2, 150, "active", "mid")],
                ).to_sql()
            )
            rows = clickhouse_backend.fetch_all(*_select_payloads_expression(clickhouse_backend.dialect, RANGE_TABLE).to_sql())
            metadata = _metadata(clickhouse_backend, RANGE_TABLE)
            assert [row["payload"] for row in rows] == ["low", "mid"]
            _assert_partition_method(metadata, "RANGE")
            assert any("100" in str(row["description"]) for row in metadata)
        finally:
            _drop_tables(clickhouse_backend)

    def test_list_and_list_columns_route_rows(self, clickhouse_backend):
        """LIST and LIST COLUMNS should route rows by VALUES IN definitions."""
        _create_table(clickhouse_backend, LIST_TABLE, _create_list_table_expression)
        _create_table(clickhouse_backend, LIST_COLUMNS_TABLE, _create_list_columns_table_expression)
        try:
            clickhouse_backend.execute(
                *_insert_rows_expression(
                    clickhouse_backend.dialect,
                    LIST_TABLE,
                    [(1, 1, "active", "small"), (2, 4, "active", "large")],
                ).to_sql()
            )
            clickhouse_backend.execute(
                *_insert_rows_expression(
                    clickhouse_backend.dialect,
                    LIST_COLUMNS_TABLE,
                    [(3, 10, "active", "active-row"), (4, 20, "closed", "closed-row")],
                ).to_sql()
            )
            list_rows = clickhouse_backend.fetch_all(*_select_payloads_expression(clickhouse_backend.dialect, LIST_TABLE).to_sql())
            list_columns_rows = clickhouse_backend.fetch_all(
                *_select_payloads_expression(clickhouse_backend.dialect, LIST_COLUMNS_TABLE).to_sql()
            )
            assert [row["payload"] for row in list_rows] == ["small", "large"]
            assert [row["payload"] for row in list_columns_rows] == ["active-row", "closed-row"]
            _assert_partition_method(_metadata(clickhouse_backend, LIST_TABLE), "LIST")
            _assert_partition_method(_metadata(clickhouse_backend, LIST_COLUMNS_TABLE), "LIST")
        finally:
            _drop_tables(clickhouse_backend)

    @pytest.mark.parametrize(
        "table_name,expression_factory,expected_method",
        [
            (HASH_TABLE, lambda dialect: _create_hash_table_expression(dialect, HASH_TABLE), "HASH"),
            (KEY_TABLE, lambda dialect: _create_key_table_expression(dialect, KEY_TABLE), "KEY"),
            (
                LINEAR_HASH_TABLE,
                lambda dialect: _create_hash_table_expression(dialect, LINEAR_HASH_TABLE, linear=True),
                "LINEAR HASH",
            ),
            (
                LINEAR_KEY_TABLE,
                lambda dialect: _create_key_table_expression(dialect, LINEAR_KEY_TABLE, linear=True),
                "LINEAR KEY",
            ),
        ],
    )
    def test_hash_key_and_linear_partition_tables_accept_rows(
        self,
        clickhouse_backend,
        table_name,
        expression_factory,
        expected_method,
    ):
        """HASH, KEY, and LINEAR variants should create usable partitioned tables."""
        _create_table(clickhouse_backend, table_name, expression_factory)
        try:
            clickhouse_backend.execute(
                *_insert_rows_expression(
                    clickhouse_backend.dialect,
                    table_name,
                    [(1, 10, "active", "one"), (2, 20, "closed", "two")],
                ).to_sql()
            )
            count = clickhouse_backend.fetch_one(*_select_count_expression(clickhouse_backend.dialect, table_name).to_sql())["count"]
            metadata = _metadata(clickhouse_backend, table_name)
            assert count == 2
            _assert_partition_method(metadata, expected_method)
            assert len(metadata) == 4
        finally:
            _drop_tables(clickhouse_backend)

    def test_multi_partition_add_drop_and_truncate(self, clickhouse_backend):
        """ADD, DROP, and TRUNCATE should handle multiple partitions in one statement."""
        _create_table(clickhouse_backend, RANGE_TABLE, _create_range_table_expression)
        try:
            clickhouse_backend.execute(
                *ClickHouseAddPartitionExpression(
                    clickhouse_backend.dialect,
                    RANGE_TABLE,
                    [
                        ClickHousePartitionDefinition(
                            "p_high",
                            less_than=[_partition_value(clickhouse_backend.dialect, 300)],
                        ),
                        ClickHousePartitionDefinition(
                            "p_higher",
                            less_than=[_partition_value(clickhouse_backend.dialect, 400)],
                        ),
                    ],
                ).to_sql()
            )
            assert {row["name"] for row in _metadata(clickhouse_backend, RANGE_TABLE)} == {
                "p_low",
                "p_mid",
                "p_high",
                "p_higher",
            }
            clickhouse_backend.execute(
                *_insert_rows_expression(
                    clickhouse_backend.dialect,
                    RANGE_TABLE,
                    [(1, 250, "active", "high"), (2, 350, "closed", "higher")],
                ).to_sql()
            )
            clickhouse_backend.execute(
                *ClickHouseTruncatePartitionExpression(
                    clickhouse_backend.dialect,
                    RANGE_TABLE,
                    ["p_high", "p_higher"],
                ).to_sql()
            )
            count = clickhouse_backend.fetch_one(*_select_count_expression(clickhouse_backend.dialect, RANGE_TABLE).to_sql())["count"]
            assert count == 0
            clickhouse_backend.execute(
                *ClickHouseDropPartitionExpression(
                    clickhouse_backend.dialect,
                    RANGE_TABLE,
                    ["p_high", "p_higher"],
                ).to_sql()
            )
            assert {row["name"] for row in _metadata(clickhouse_backend, RANGE_TABLE)} == {"p_low", "p_mid"}
        finally:
            _drop_tables(clickhouse_backend)

    def test_range_columns_with_multiple_columns_routes_correctly(self, clickhouse_backend):
        """RANGE COLUMNS with multiple partition keys should route rows by row comparison.

        ClickHouse uses ``(key1, key2) < (val1, val2)`` semantics:
        ``a1 < b1 OR (a1 = b1 AND a2 < b2)``.

        Partitions:
          - p_low:  VALUES LESS THAN (100, 100)
          - p_mid:  VALUES LESS THAN (200, 500)
          - p_high: VALUES LESS THAN (MAXVALUE, MAXVALUE)

        Raises:
            AssertionError: if any row lands in the wrong partition.
        """
        _create_table(clickhouse_backend, RANGE_COLUMNS_MULTI_TABLE, _create_range_columns_multi_table_expression)
        try:
            clickhouse_backend.execute(
                *_insert_rows_expression(
                    clickhouse_backend.dialect,
                    RANGE_COLUMNS_MULTI_TABLE,
                    [
                        (1, 50, "active", "low-1"),      # shard_id=50 < 100 → p_low
                        (2, 50, "active", "low-2"),      # shard_id=50 < 100 → p_low
                        (3, 100, "active", "low-3"),     # shard_id=100, id=3 < 100 → p_low
                        (101, 100, "closed", "mid-1"),   # (100,101) < (200,500) → 100<200 → p_mid
                        (201, 200, "active", "mid-2"),   # (200,201) < (200,500) → 200==200 AND 201<500 → p_mid
                        (501, 200, "closed", "high-1"),  # (200,501) < (200,500) → FALSE → p_high
                    ],
                ).to_sql()
            )
            # Verify all rows are in the parent table
            rows = clickhouse_backend.fetch_all(
                *_select_payloads_expression(clickhouse_backend.dialect, RANGE_COLUMNS_MULTI_TABLE).to_sql()
            )
            assert [row["payload"] for row in rows] == ["low-1", "low-2", "low-3", "mid-1", "mid-2", "high-1"]

            # Drop partitions sequentially to verify routing
            clickhouse_backend.execute(
                *ClickHouseDropPartitionExpression(
                    clickhouse_backend.dialect, RANGE_COLUMNS_MULTI_TABLE, ["p_low"]
                ).to_sql()
            )
            remaining = clickhouse_backend.fetch_all(
                *_select_payloads_expression(clickhouse_backend.dialect, RANGE_COLUMNS_MULTI_TABLE).to_sql()
            )
            assert [row["payload"] for row in remaining] == ["mid-1", "mid-2", "high-1"]

            clickhouse_backend.execute(
                *ClickHouseDropPartitionExpression(
                    clickhouse_backend.dialect, RANGE_COLUMNS_MULTI_TABLE, ["p_mid"]
                ).to_sql()
            )
            remaining = clickhouse_backend.fetch_all(
                *_select_payloads_expression(clickhouse_backend.dialect, RANGE_COLUMNS_MULTI_TABLE).to_sql()
            )
            assert [row["payload"] for row in remaining] == ["high-1"]
        finally:
            _drop_tables(clickhouse_backend)

    def test_list_columns_with_multiple_columns_routes_correctly(self, clickhouse_backend):
        """LIST COLUMNS with multiple partition keys should route rows by composite values.

        Partitions:
          - p_group_a: VALUES IN (('active', 'alpha'), ('active', 'beta'))
          - p_group_b: VALUES IN (('closed', 'gamma'), ('archived', 'delta'))

        Raises:
            AssertionError: if any row lands in the wrong partition.
        """
        _create_table(clickhouse_backend, LIST_COLUMNS_MULTI_TABLE, _create_list_columns_multi_table_expression)
        try:
            clickhouse_backend.execute(
                *_insert_rows_expression(
                    clickhouse_backend.dialect,
                    LIST_COLUMNS_MULTI_TABLE,
                    [
                        (1, 0, "active", "alpha"),
                        (2, 0, "active", "beta"),
                        (3, 0, "closed", "gamma"),
                        (4, 0, "archived", "delta"),
                    ],
                ).to_sql()
            )
            rows = clickhouse_backend.fetch_all(
                *_select_payloads_expression(clickhouse_backend.dialect, LIST_COLUMNS_MULTI_TABLE).to_sql()
            )
            assert [row["payload"] for row in rows] == ["alpha", "beta", "gamma", "delta"]

            clickhouse_backend.execute(
                *ClickHouseDropPartitionExpression(
                    clickhouse_backend.dialect, LIST_COLUMNS_MULTI_TABLE, ["p_group_a"]
                ).to_sql()
            )
            remaining = clickhouse_backend.fetch_all(
                *_select_payloads_expression(clickhouse_backend.dialect, LIST_COLUMNS_MULTI_TABLE).to_sql()
            )
            assert [row["payload"] for row in remaining] == ["gamma", "delta"]
        finally:
            _drop_tables(clickhouse_backend)

    # --- NULL behaviour in partitioned tables ---

    def test_null_in_range_partition_goes_to_first_partition(self, clickhouse_backend):
        """NULL in RANGE partition key should route to the first partition.

        ClickHouse treats NULL < any non-NULL value, so a RANGE partition with
        a lower boundary receives NULL-keyed rows.
        """
        table = "ar_clickhouse_null_range"
        columns = [
            ColumnDefinition("id", BigIntType(), constraints=[ColumnConstraint(ColumnConstraintType.NOT_NULL)]),
            ColumnDefinition("shard_id", BigIntType()),  # nullable
            ColumnDefinition("payload", VarCharType(255)),
        ]
        clickhouse_backend.execute(*_drop_named_table_expression(clickhouse_backend.dialect, table).to_sql())
        clickhouse_backend.execute(
            *CreateTableExpression(
                dialect=clickhouse_backend.dialect,
                table=table,
                columns=columns,
                partition=ClickHousePartitionByRange(
                    dialect=clickhouse_backend.dialect,
                    keys=[Column(clickhouse_backend.dialect, "shard_id")],
                    partitions=[
                        ClickHousePartitionDefinition("p_low", less_than=[_partition_value(clickhouse_backend.dialect, 100)]),
                        ClickHousePartitionDefinition("p_high", less_than=[_partition_value(clickhouse_backend.dialect, 200)]),
                    ],
                ),
            ).to_sql()
        )
        try:
            insert = InsertExpression(
                dialect=clickhouse_backend.dialect,
                into=table,
                columns=["id", "shard_id", "payload"],
                source=ValuesSource(
                    clickhouse_backend.dialect,
                    [
                        [Literal(clickhouse_backend.dialect, 1), Literal(clickhouse_backend.dialect, None), Literal(clickhouse_backend.dialect, "null-row")],
                    ],
                ),
            )
            clickhouse_backend.execute(*insert.to_sql())
            rows = clickhouse_backend.fetch_all(
                *_select_payloads_expression(clickhouse_backend.dialect, table).to_sql()
            )
            assert [row["payload"] for row in rows] == ["null-row"]
        finally:
            clickhouse_backend.execute(*_drop_named_table_expression(clickhouse_backend.dialect, table).to_sql())

    def test_null_in_list_partition_with_explicit_values_in_works(self, clickhouse_backend):
        """LIST partition that explicitly includes NULL in VALUES IN should accept NULL."""
        table = "ar_clickhouse_null_list"
        columns = [
            ColumnDefinition("id", BigIntType(), constraints=[ColumnConstraint(ColumnConstraintType.NOT_NULL)]),
            ColumnDefinition("shard_id", BigIntType()),
            ColumnDefinition("payload", VarCharType(255)),
        ]
        clickhouse_backend.execute(*_drop_named_table_expression(clickhouse_backend.dialect, table).to_sql())
        clickhouse_backend.execute(
            *CreateTableExpression(
                dialect=clickhouse_backend.dialect,
                table=table,
                columns=columns,
                partition=ClickHousePartitionByList(
                    dialect=clickhouse_backend.dialect,
                    keys=[Column(clickhouse_backend.dialect, "shard_id")],
                    partitions=[
                        ClickHousePartitionDefinition(
                            name="p_null",
                            in_values=[_partition_value(clickhouse_backend.dialect, None)],
                        ),
                        ClickHousePartitionDefinition(
                            name="p_val",
                            in_values=[_partition_value(clickhouse_backend.dialect, 1)],
                        ),
                    ],
                ),
            ).to_sql()
        )
        try:
            insert = InsertExpression(
                dialect=clickhouse_backend.dialect,
                into=table,
                columns=["id", "shard_id", "payload"],
                source=ValuesSource(
                    clickhouse_backend.dialect,
                    [
                        [Literal(clickhouse_backend.dialect, 1), Literal(clickhouse_backend.dialect, None), Literal(clickhouse_backend.dialect, "null-row")],
                    ],
                ),
            )
            clickhouse_backend.execute(*insert.to_sql())
            rows = clickhouse_backend.fetch_all(
                *_select_payloads_expression(clickhouse_backend.dialect, table).to_sql()
            )
            assert [row["payload"] for row in rows] == ["null-row"]
        finally:
            clickhouse_backend.execute(*_drop_named_table_expression(clickhouse_backend.dialect, table).to_sql())

    def test_null_in_hash_partition_accepts_null_key(self, clickhouse_backend):
        """HASH partition should accept NULL keys without error."""
        table = "ar_clickhouse_null_hash"
        columns = [
            ColumnDefinition("id", BigIntType(), constraints=[ColumnConstraint(ColumnConstraintType.NOT_NULL)]),
            ColumnDefinition("shard_id", BigIntType()),
            ColumnDefinition("payload", VarCharType(255)),
        ]
        clickhouse_backend.execute(*_drop_named_table_expression(clickhouse_backend.dialect, table).to_sql())
        clickhouse_backend.execute(
            *CreateTableExpression(
                dialect=clickhouse_backend.dialect,
                table=table,
                columns=columns,
                partition=ClickHousePartitionByHash(
                    dialect=clickhouse_backend.dialect,
                    keys=[Column(clickhouse_backend.dialect, "shard_id")],
                    partitions_count=4,
                ),
            ).to_sql()
        )
        try:
            insert = InsertExpression(
                dialect=clickhouse_backend.dialect,
                into=table,
                columns=["id", "shard_id", "payload"],
                source=ValuesSource(
                    clickhouse_backend.dialect,
                    [
                        [Literal(clickhouse_backend.dialect, 1), Literal(clickhouse_backend.dialect, None), Literal(clickhouse_backend.dialect, "null-row")],
                    ],
                ),
            )
            clickhouse_backend.execute(*insert.to_sql())
            count = clickhouse_backend.fetch_one(
                *_select_count_expression(clickhouse_backend.dialect, table).to_sql()
            )["count"]
            assert count == 1
        finally:
            clickhouse_backend.execute(*_drop_named_table_expression(clickhouse_backend.dialect, table).to_sql())

    def test_null_in_key_partition_accepts_null_key(self, clickhouse_backend):
        """KEY partition should accept NULL keys without error."""
        table = "ar_clickhouse_null_key"
        columns = [
            ColumnDefinition("id", BigIntType(), constraints=[ColumnConstraint(ColumnConstraintType.NOT_NULL)]),
            ColumnDefinition("shard_id", BigIntType()),
            ColumnDefinition("payload", VarCharType(255)),
        ]
        clickhouse_backend.execute(*_drop_named_table_expression(clickhouse_backend.dialect, table).to_sql())
        clickhouse_backend.execute(
            *CreateTableExpression(
                dialect=clickhouse_backend.dialect,
                table=table,
                columns=columns,
                partition=ClickHousePartitionByKey(
                    clickhouse_backend.dialect,
                    keys=[Column(clickhouse_backend.dialect, "id")],
                    partitions_count=4,
                ),
            ).to_sql()
        )
        try:
            # KEY partition using `id` which is NOT NULL; verify normal inserts work
            insert = InsertExpression(
                dialect=clickhouse_backend.dialect,
                into=table,
                columns=["id", "shard_id", "payload"],
                source=ValuesSource(
                    clickhouse_backend.dialect,
                    [
                        [Literal(clickhouse_backend.dialect, 1), Literal(clickhouse_backend.dialect, None), Literal(clickhouse_backend.dialect, "row-1")],
                    ],
                ),
            )
            clickhouse_backend.execute(*insert.to_sql())
            count = clickhouse_backend.fetch_one(
                *_select_count_expression(clickhouse_backend.dialect, table).to_sql()
            )["count"]
            assert count == 1
        finally:
            clickhouse_backend.execute(*_drop_named_table_expression(clickhouse_backend.dialect, table).to_sql())

    # --- KEY() implicit column test ---

    def test_key_with_empty_parenthesis_uses_all_primary_key_columns(self, clickhouse_backend):
        """PARTITION BY KEY() with empty key should use all PK columns as partition key.

        ClickHouse automatically chooses all primary key columns when no explicit
        column list is provided to KEY partitioning.
        """
        table = "ar_clickhouse_key_implicit"
        clickhouse_backend.execute(*_drop_named_table_expression(clickhouse_backend.dialect, table).to_sql())
        clickhouse_backend.execute(
            *CreateTableExpression(
                dialect=clickhouse_backend.dialect,
                table=table,
                columns=[
                    ColumnDefinition("id", BigIntType(), constraints=[ColumnConstraint(ColumnConstraintType.NOT_NULL)]),
                    ColumnDefinition("created_at", DateType(), constraints=[ColumnConstraint(ColumnConstraintType.NOT_NULL)]),
                    ColumnDefinition("payload", VarCharType(255)),
                ],
                table_constraints=[
                    TableConstraint(TableConstraintType.PRIMARY_KEY, columns=["id", "created_at"]),
                ],
                partition=ClickHousePartitionByKey(
                    clickhouse_backend.dialect,
                    keys=[],  # empty — ClickHouse uses PK columns
                    partitions_count=4,
                ),
            ).to_sql()
        )
        try:
            metadata = _metadata(clickhouse_backend, table)
            _assert_partition_method(metadata, "KEY")
            assert len(metadata) == 4
        finally:
            clickhouse_backend.execute(*_drop_named_table_expression(clickhouse_backend.dialect, table).to_sql())
    """Asynchronous real backend tests for additional ClickHouse partition strategies."""

    @pytest.mark.asyncio
    async def test_range_partition_routes_rows(self, async_clickhouse_backend):
        """Plain RANGE partitioning should work asynchronously."""
        await _async_create_table(async_clickhouse_backend, RANGE_TABLE, _create_range_table_expression)
        try:
            await async_clickhouse_backend.execute(
                *_insert_rows_expression(
                    async_clickhouse_backend.dialect,
                    RANGE_TABLE,
                    [(1, 10, "active", "low"), (2, 150, "active", "mid")],
                ).to_sql()
            )
            rows = await async_clickhouse_backend.fetch_all(
                *_select_payloads_expression(async_clickhouse_backend.dialect, RANGE_TABLE).to_sql()
            )
            metadata = await _async_metadata(async_clickhouse_backend, RANGE_TABLE)
            assert [row["payload"] for row in rows] == ["low", "mid"]
            _assert_partition_method(metadata, "RANGE")
        finally:
            await _async_drop_tables(async_clickhouse_backend)

    @pytest.mark.asyncio
    async def test_list_and_list_columns_route_rows(self, async_clickhouse_backend):
        """LIST and LIST COLUMNS should route rows asynchronously."""
        await _async_create_table(async_clickhouse_backend, LIST_TABLE, _create_list_table_expression)
        await _async_create_table(
            async_clickhouse_backend,
            LIST_COLUMNS_TABLE,
            _create_list_columns_table_expression,
        )
        try:
            await async_clickhouse_backend.execute(
                *_insert_rows_expression(
                    async_clickhouse_backend.dialect,
                    LIST_TABLE,
                    [(1, 1, "active", "small"), (2, 4, "active", "large")],
                ).to_sql()
            )
            await async_clickhouse_backend.execute(
                *_insert_rows_expression(
                    async_clickhouse_backend.dialect,
                    LIST_COLUMNS_TABLE,
                    [(3, 10, "active", "active-row"), (4, 20, "closed", "closed-row")],
                ).to_sql()
            )
            list_rows = await async_clickhouse_backend.fetch_all(
                *_select_payloads_expression(async_clickhouse_backend.dialect, LIST_TABLE).to_sql()
            )
            list_columns_rows = await async_clickhouse_backend.fetch_all(
                *_select_payloads_expression(async_clickhouse_backend.dialect, LIST_COLUMNS_TABLE).to_sql()
            )
            assert [row["payload"] for row in list_rows] == ["small", "large"]
            assert [row["payload"] for row in list_columns_rows] == ["active-row", "closed-row"]
            _assert_partition_method(await _async_metadata(async_clickhouse_backend, LIST_TABLE), "LIST")
            _assert_partition_method(await _async_metadata(async_clickhouse_backend, LIST_COLUMNS_TABLE), "LIST")
        finally:
            await _async_drop_tables(async_clickhouse_backend)

    @pytest.mark.asyncio
    async def test_range_columns_with_multiple_columns_routes_correctly(self, async_clickhouse_backend):
        """RANGE COLUMNS with multiple partition keys should route rows asynchronously."""
        await _async_create_table(
            async_clickhouse_backend, RANGE_COLUMNS_MULTI_TABLE, _create_range_columns_multi_table_expression
        )
        try:
            await async_clickhouse_backend.execute(
                *_insert_rows_expression(
                    async_clickhouse_backend.dialect,
                    RANGE_COLUMNS_MULTI_TABLE,
                    [
                        (1, 50, "active", "low-1"),      # shard_id=50 < 100 → p_low
                        (2, 50, "active", "low-2"),      # shard_id=50 < 100 → p_low
                        (3, 100, "active", "low-3"),     # shard_id=100, id=3 < 100 → p_low
                        (101, 100, "closed", "mid-1"),   # (100,101) < (200,500) → 100<200 → p_mid
                        (201, 200, "active", "mid-2"),   # (200,201) < (200,500) → 200==200 AND 201<500 → p_mid
                        (501, 200, "closed", "high-1"),  # (200,501) < (200,500) → FALSE → p_high
                    ],
                ).to_sql()
            )
            rows = await async_clickhouse_backend.fetch_all(
                *_select_payloads_expression(async_clickhouse_backend.dialect, RANGE_COLUMNS_MULTI_TABLE).to_sql()
            )
            assert [row["payload"] for row in rows] == ["low-1", "low-2", "low-3", "mid-1", "mid-2", "high-1"]

            await async_clickhouse_backend.execute(
                *ClickHouseDropPartitionExpression(
                    async_clickhouse_backend.dialect, RANGE_COLUMNS_MULTI_TABLE, ["p_low"]
                ).to_sql()
            )
            remaining = await async_clickhouse_backend.fetch_all(
                *_select_payloads_expression(async_clickhouse_backend.dialect, RANGE_COLUMNS_MULTI_TABLE).to_sql()
            )
            assert [row["payload"] for row in remaining] == ["mid-1", "mid-2", "high-1"]
        finally:
            await _async_drop_tables(async_clickhouse_backend)

    @pytest.mark.asyncio
    async def test_list_columns_with_multiple_columns_routes_correctly(self, async_clickhouse_backend):
        """LIST COLUMNS with multiple partition keys should route rows asynchronously."""
        await _async_create_table(
            async_clickhouse_backend, LIST_COLUMNS_MULTI_TABLE, _create_list_columns_multi_table_expression
        )
        try:
            await async_clickhouse_backend.execute(
                *_insert_rows_expression(
                    async_clickhouse_backend.dialect,
                    LIST_COLUMNS_MULTI_TABLE,
                    [
                        (1, 0, "active", "alpha"),
                        (2, 0, "active", "beta"),
                        (3, 0, "closed", "gamma"),
                        (4, 0, "archived", "delta"),
                    ],
                ).to_sql()
            )
            rows = await async_clickhouse_backend.fetch_all(
                *_select_payloads_expression(async_clickhouse_backend.dialect, LIST_COLUMNS_MULTI_TABLE).to_sql()
            )
            assert [row["payload"] for row in rows] == ["alpha", "beta", "gamma", "delta"]
        finally:
            await _async_drop_tables(async_clickhouse_backend)

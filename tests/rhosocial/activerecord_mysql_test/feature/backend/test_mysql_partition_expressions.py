"""ClickHouse partition expression construction and safety tests."""

from decimal import Decimal

import pytest

from rhosocial.activerecord.backend.expression import Column
from rhosocial.activerecord.backend.impl.clickhouse.dialect import ClickHouseDialect
from rhosocial.activerecord.backend.impl.clickhouse.expression import (
    ClickHouseAddPartitionExpression,
    ClickHouseAddPartitionHelper,
    ClickHouseAddSubpartitionHelper,
    ClickHouseCoalescePartitionExpression,
    ClickHouseCoalescePartitionHelper,
    ClickHouseDropOldestPartitionHelper,
    ClickHouseDropPartitionExpression,
    ClickHouseExchangePartitionExpression,
    ClickHouseGetPartitionsExpression,
    ClickHouseRemovePartitioningExpression,
    ClickHouseAnalyzePartitionExpression,
    ClickHouseCheckPartitionExpression,
    ClickHouseOptimizePartitionExpression,
    ClickHouseRebuildPartitionExpression,
    ClickHouseReorganizePartitionHelper,
    ClickHouseRepairPartitionExpression,
    ClickHousePartitionByHash,
    ClickHousePartitionByKey,
    ClickHousePartitionByList,
    ClickHousePartitionByListColumns,
    ClickHousePartitionByRange,
    ClickHousePartitionByRangeColumns,
    ClickHousePartitionDefinition,
    ClickHousePartitionMaxValue,
    ClickHousePartitionValue,
    ClickHouseSubpartitionStrategy,
    ClickHouseSubpartitionClause,
    ClickHouseSubpartitionDefinition,
    ClickHouseTruncatePartitionExpression,
)


@pytest.fixture
def dialect():
    """Create a ClickHouse dialect for expression tests."""
    return ClickHouseDialect()


def _partition_value(dialect, value):
    return ClickHousePartitionValue(dialect, value)


def test_partition_by_range_expression(dialect):
    """PARTITION BY RANGE should format expression keys and bounds."""
    expr = ClickHousePartitionByRange(
        dialect=dialect,
        keys=[Column(dialect, "created_year")],
        partitions=[
            ClickHousePartitionDefinition(
                name="p2026",
                less_than=[_partition_value(dialect, 2027)],
            )
        ],
    )

    sql, params = expr.to_sql()

    assert "PARTITION BY RANGE" in sql
    assert "created_year" in sql
    assert "PARTITION" in sql
    assert "p2026" in sql
    assert "VALUES LESS THAN (2027)" in sql
    assert params == ()


@pytest.mark.parametrize(
    "expr_factory, expected",
    [
        (
            lambda dialect: ClickHousePartitionByList(
                dialect=dialect,
                keys=[Column(dialect, "tenant_id")],
                partitions=[
                    ClickHousePartitionDefinition(
                        name="p_tenant_10_20",
                        in_values=[_partition_value(dialect, 10), _partition_value(dialect, 20)],
                    )
                ],
            ),
            "PARTITION BY LIST",
        ),
        (
            lambda dialect: ClickHousePartitionByListColumns(
                dialect=dialect,
                keys=[Column(dialect, "status")],
                partitions=[
                    ClickHousePartitionDefinition(
                        name="p_active",
                        in_values=[_partition_value(dialect, "active"), _partition_value(dialect, "pending")],
                    )
                ],
            ),
            "PARTITION BY LIST COLUMNS",
        ),
    ],
)
def test_values_in_partition_definitions(dialect, expr_factory, expected):
    """LIST and LIST COLUMNS should render VALUES IN definitions."""
    sql, params = expr_factory(dialect).to_sql()

    assert expected in sql
    assert "VALUES IN" in sql
    assert "p_" in sql
    assert params == ()


def test_hash_and_key_partition_counts(dialect):
    """HASH and KEY partition expressions should support PARTITIONS count."""
    hash_sql, hash_params = ClickHousePartitionByHash(
        dialect=dialect,
        keys=[Column(dialect, "id")],
        partitions_count=4,
    ).to_sql()
    key_sql, key_params = ClickHousePartitionByKey(
        dialect=dialect,
        keys=[Column(dialect, "id")],
        partitions_count=4,
    ).to_sql()

    assert "PARTITION BY HASH" in hash_sql
    assert "PARTITIONS 4" in hash_sql
    assert hash_params == ()
    assert "PARTITION BY KEY" in key_sql
    assert "PARTITIONS 4" in key_sql
    assert key_params == ()


def test_linear_hash_and_key_partition_counts(dialect):
    """LINEAR HASH and LINEAR KEY should be expressible."""
    hash_sql, _ = ClickHousePartitionByHash(
        dialect=dialect,
        keys=[Column(dialect, "id")],
        partitions_count=4,
        linear=True,
    ).to_sql()
    key_sql, _ = ClickHousePartitionByKey(
        dialect=dialect,
        keys=[Column(dialect, "id")],
        partitions_count=4,
        linear=True,
    ).to_sql()

    assert "PARTITION BY LINEAR HASH" in hash_sql
    assert "PARTITION BY LINEAR KEY" in key_sql


def test_multiple_partition_maintenance_statements(dialect):
    """ADD, DROP, and TRUNCATE should format multiple partitions."""
    partitions = [
        ClickHousePartitionDefinition(name="p2026_03", less_than=[_partition_value(dialect, "2026-04-01")]),
        ClickHousePartitionDefinition(name="p2026_04", less_than=[_partition_value(dialect, "2026-05-01")]),
    ]

    add_sql, add_params = ClickHouseAddPartitionExpression(dialect, "events", partitions).to_sql()
    drop_sql, drop_params = ClickHouseDropPartitionExpression(dialect, "events", ["p2026_03", "p2026_04"]).to_sql()
    truncate_sql, truncate_params = ClickHouseTruncatePartitionExpression(
        dialect,
        "events",
        ["p2026_03", "p2026_04"],
    ).to_sql()

    assert "ADD PARTITION" in add_sql
    assert "p2026_03" in add_sql and "p2026_04" in add_sql
    assert add_params == ()
    assert "DROP PARTITION" in drop_sql
    assert "p2026_03" in drop_sql and "p2026_04" in drop_sql
    assert drop_params == ()
    assert "TRUNCATE PARTITION" in truncate_sql
    assert "p2026_03" in truncate_sql and "p2026_04" in truncate_sql
    assert truncate_params == ()


def test_exchange_partition_without_validation(dialect):
    """EXCHANGE PARTITION should support WITHOUT VALIDATION."""
    sql, params = ClickHouseExchangePartitionExpression(
        dialect,
        "events",
        "p2026",
        "events_archive",
        with_validation=False,
    ).to_sql()

    assert "EXCHANGE PARTITION" in sql
    assert "WITHOUT VALIDATION" in sql
    assert params == ()


def test_partition_definition_rejects_invalid_value_mode_combinations(dialect):
    """Partition definitions require exactly one value mode."""
    with pytest.raises(ValueError, match="mutually exclusive"):
        ClickHousePartitionDefinition(
            name="p_bad",
            less_than=[_partition_value(dialect, 10)],
            in_values=[_partition_value(dialect, 1)],
        )

    with pytest.raises(ValueError, match="requires less_than or in_values"):
        ClickHousePartitionDefinition(name="p_bad")


def test_partition_value_rejects_unsafe_or_invalid_values(dialect):
    """Partition values should reject invalid types and non-finite numbers."""
    with pytest.raises(TypeError, match="must not be bool"):
        ClickHousePartitionValue(dialect, True).to_sql()

    with pytest.raises(ValueError, match="float must be finite"):
        ClickHousePartitionValue(dialect, float("inf"))

    with pytest.raises(ValueError, match="Decimal must be finite"):
        ClickHousePartitionValue(dialect, Decimal("NaN")).to_sql()

    with pytest.raises(TypeError, match="partition value must be"):
        ClickHousePartitionValue(dialect, object())


def test_partition_value_escapes_string_literals(dialect):
    """String boundary values should be escaped as SQL literals."""
    sql, params = ClickHousePartitionValue(dialect, "x'); DROP TABLE users; --").to_sql()

    assert "DROP TABLE" in sql
    assert "''" in sql
    assert params == ()


def test_maxvalue_uses_capability(dialect):
    """MAXVALUE should format through the partition value formatter."""
    sql, params = ClickHousePartitionMaxValue(dialect).to_sql()

    assert sql == "MAXVALUE"
    assert params == ()


def test_partition_definition_options_are_formatted(dialect):
    """Supported partition definition options should render explicitly."""
    definition = ClickHousePartitionDefinition(
        name="p2026",
        less_than=[_partition_value(dialect, "2027-01-01")],
        dialect_options={
            "engine": "InnoDB",
            "comment": "tenant's partition",
            "max_rows": 1000,
            "tablespace": "ts_hot",
        },
    )

    sql, params = dialect.format_partition_definition(definition)

    assert "ENGINE" in sql and "InnoDB" in sql
    assert "COMMENT" in sql and "tenant''s partition" in sql
    assert "MAX_ROWS 1000" in sql
    assert "TABLESPACE" in sql and "ts_hot" in sql
    assert params == ()


def test_partition_definition_options_reject_invalid_options(dialect):
    """Unsupported or invalid partition options should fail clearly."""
    with pytest.raises(ValueError, match="Unsupported partition definition option"):
        dialect.format_partition_definition_options({"unknown": "value"})

    with pytest.raises(TypeError, match="max_rows option"):
        dialect.format_partition_definition_options({"max_rows": -1})

def test_extended_partition_maintenance_expressions(dialect):
    """ClickHouse maintenance expressions should delegate to public formatters."""
    cases = [
        (ClickHouseRemovePartitioningExpression(dialect, "events"), "REMOVE PARTITIONING"),
        (ClickHouseCoalescePartitionExpression(dialect, "events", 2), "COALESCE PARTITION 2"),
        (ClickHouseAnalyzePartitionExpression(dialect, "events", ["p0", "p1"]), "ANALYZE PARTITION"),
        (ClickHouseCheckPartitionExpression(dialect, "events", ["p0", "p1"]), "CHECK PARTITION"),
        (ClickHouseOptimizePartitionExpression(dialect, "events", ["p0", "p1"]), "OPTIMIZE PARTITION"),
        (ClickHouseRebuildPartitionExpression(dialect, "events", ["p0", "p1"]), "REBUILD PARTITION"),
        (ClickHouseRepairPartitionExpression(dialect, "events", ["p0", "p1"]), "REPAIR PARTITION"),
    ]

    for expr, expected in cases:
        sql, params = expr.to_sql()
        assert expected in sql
    assert params == ()


def test_partition_value_finite_float(dialect):
    """Partition values with finite float should work correctly."""
    sql, params = ClickHousePartitionValue(dialect, 3.14).to_sql()
    assert "3.14" in sql
    assert params == ()


def test_partition_value_finite_decimal(dialect):
    """Partition values with finite Decimal should work correctly."""
    sql, params = ClickHousePartitionValue(dialect, Decimal("10.5")).to_sql()
    assert "10.5" in sql
    assert params == ()


def test_partition_by_list_columns_multi_column_row_tuples(dialect):
    """Multi-column LIST COLUMNS should render row tuples correctly."""
    expr = ClickHousePartitionByListColumns(
        dialect=dialect,
        keys=[Column(dialect, "col_a"), Column(dialect, "col_b")],
        partitions=[
            ClickHousePartitionDefinition(
                name="p1",
                in_values=[
                    [_partition_value(dialect, 1), _partition_value(dialect, "a")],
                    [_partition_value(dialect, 2), _partition_value(dialect, "b")],
                ],
            ),
        ],
    )

    sql, params = expr.to_sql()

    assert "PARTITION BY LIST COLUMNS" in sql
    assert "`col_a`" in sql
    assert "VALUES IN" in sql
    assert "(1, 'a')" in sql or "(1,`a`)" in sql
    assert params == ()


def test_extended_partition_maintenance_rejects_invalid_arguments(dialect):
    """Maintenance expressions should reject invalid counts and empty lists."""
    with pytest.raises(ValueError, match="positive integer"):
        ClickHouseCoalescePartitionExpression(dialect, "events", 0)

    with pytest.raises(ValueError, match="partitions must not be empty"):
        ClickHouseAnalyzePartitionExpression(dialect, "events", []).to_sql()


# --- Subpartition expression tests ---


def test_subpartition_by_hash_with_expression(dialect):
    """SUBPARTITION BY HASH with expression should produce correct SQL."""
    expr = ClickHousePartitionByRange(
        dialect=dialect,
        keys=[Column(dialect, "created_at")],
        partitions=[
            ClickHousePartitionDefinition("p0", less_than=[_partition_value(dialect, "2026-01-01")]),
            ClickHousePartitionDefinition("p1", less_than=[_partition_value(dialect, "2027-01-01")]),
        ],
        subpartition_by=ClickHouseSubpartitionClause(
            dialect=dialect,
            strategy=ClickHouseSubpartitionStrategy.HASH,
            expression=Column(dialect, "id"),
            count=4,
        ),
    )

    sql, params = expr.to_sql()

    assert "PARTITION BY RANGE" in sql
    assert "SUBPARTITION BY HASH" in sql
    assert "`id`" in sql
    assert "SUBPARTITIONS 4" in sql
    assert "PARTITION" in sql
    assert params == ()


def test_subpartition_by_key_with_implicit_columns(dialect):
    """SUBPARTITION BY KEY() without expression should produce correct SQL."""
    expr = ClickHousePartitionByRange(
        dialect=dialect,
        keys=[Column(dialect, "created_at")],
        partitions=[
            ClickHousePartitionDefinition("p0", less_than=[_partition_value(dialect, "2026-01-01")]),
        ],
        subpartition_by=ClickHouseSubpartitionClause(
            dialect=dialect,
            strategy=ClickHouseSubpartitionStrategy.KEY,
            count=4,
        ),
    )

    sql, params = expr.to_sql()

    assert "SUBPARTITION BY KEY" in sql
    assert "SUBPARTITIONS 4" in sql
    assert params == ()


def test_subpartition_by_linear_hash(dialect):
    """SUBPARTITION BY LINEAR HASH should produce correct SQL."""
    sub = ClickHouseSubpartitionClause(
        dialect=dialect,
        strategy=ClickHouseSubpartitionStrategy.LINEAR_HASH,
        expression=Column(dialect, "id"),
        count=2,
    )

    sql, params = dialect.format_subpartition_by(sub)

    assert "SUBPARTITION BY LINEAR HASH" in sql
    assert "`id`" in sql
    assert "SUBPARTITIONS 2" in sql
    assert params == ()


def test_subpartition_by_linear_key(dialect):
    """SUBPARTITION BY LINEAR KEY should produce correct SQL."""
    sub = ClickHouseSubpartitionClause(
        dialect=dialect,
        strategy=ClickHouseSubpartitionStrategy.LINEAR_KEY,
        expression=Column(dialect, "id"),
        count=4,
    )

    sql, params = dialect.format_subpartition_by(sub)

    assert "SUBPARTITION BY LINEAR KEY" in sql
    assert "`id`" in sql
    assert "SUBPARTITIONS 4" in sql
    assert params == ()


def test_subpartition_with_explicit_definitions(dialect):
    """Explicit subpartition definitions within a RANGE partition should format correctly."""
    definition = ClickHousePartitionDefinition(
        name="p0",
        less_than=[_partition_value(dialect, "2026-01-01")],
        subpartition_definitions=[
            ClickHouseSubpartitionDefinition(name="sp0"),
            ClickHouseSubpartitionDefinition(name="sp1"),
        ],
    )

    sql, params = dialect.format_partition_definition(definition)

    assert "`p0`" in sql
    assert "`sp0`" in sql
    assert "`sp1`" in sql
    assert params == ()


def test_subpartition_definition_rejects_empty_name(dialect):
    """Subpartition definition should reject empty names."""
    definition = ClickHouseSubpartitionDefinition(name="")

    with pytest.raises(ValueError, match="must not be empty"):
        dialect.format_subpartition_definition(definition)


def test_subpartition_clause_rejects_invalid_strategy(dialect):
    """Subpartition clause should reject non-ClickHouseSubpartitionStrategy values."""
    with pytest.raises(TypeError, match="must be a ClickHouseSubpartitionStrategy"):
        ClickHouseSubpartitionClause(dialect, strategy="HASH")  # type: ignore[arg-type]


def test_subpartition_clause_rejects_invalid_count(dialect):
    """Subpartition clause should reject non-positive count."""
    with pytest.raises(ValueError, match="positive integer"):
        ClickHouseSubpartitionClause(
            dialect=dialect,
            strategy=ClickHouseSubpartitionStrategy.HASH,
            expression=Column(dialect, "id"),
            count=0,
        )


def test_subpartition_preserves_dialect_options_on_subpartition_definitions(dialect):
    """Subpartition definitions should accept dialect_options."""
    sub_def = ClickHouseSubpartitionDefinition(
        name="sp_active",
        dialect_options={"engine": "InnoDB", "comment": "active subpartition"},
    )

    sql, params = dialect.format_subpartition_definition(sub_def)

    assert "`sp_active`" in sql
    assert "ENGINE" in sql
    assert "InnoDB" in sql
    assert params == ()


def test_get_partitions_expression_contains_select_and_from(dialect):
    """GetPartitionsExpression should build a SELECT query against information_schema.PARTITIONS."""
    expr = ClickHouseGetPartitionsExpression(dialect, "my_table")

    sql, params = expr.to_sql()

    assert sql.startswith("SELECT") or "SELECT" in sql.upper()
    assert "information_schema" in sql or "PARTITIONS" in sql
    assert "TABLE_NAME" in sql
    assert "PARTITION_NAME" in sql
    assert params == ("my_table",)


def test_get_partitions_expression_rejects_empty_table_name(dialect):
    """GetPartitionsExpression should reject empty table names."""
    with pytest.raises(ValueError, match="must not be empty"):
        ClickHouseGetPartitionsExpression(dialect, "")
    with pytest.raises(ValueError, match="must not be empty"):
        ClickHouseGetPartitionsExpression(dialect, "  ")


def test_add_partition_helper_generates_sql(dialect):
    """AddPartitionHelper should generate ADD PARTITION SQL."""
    expr = ClickHouseAddPartitionHelper(dialect, "orders", partition_values=[2020, 2021])

    sql, params = expr.to_sql()

    assert "ALTER TABLE" in sql
    assert "ADD PARTITION" in sql
    assert "orders" in sql
    assert "p2020" in sql
    assert "p2021" in sql
    assert params == ()


def test_add_partition_helper_rejects_empty_values(dialect):
    """AddPartitionHelper should reject empty partition_values."""
    with pytest.raises(ValueError, match="must not be empty"):
        ClickHouseAddPartitionHelper(dialect, "orders", partition_values=[])


def test_coalesce_partition_helper_generates_sql(dialect):
    """CoalescePartitionHelper should generate COALESCE PARTITION SQL."""
    expr = ClickHouseCoalescePartitionHelper(dialect, "orders", target_count=4, current_count=6)

    sql, params = expr.to_sql()

    assert "ALTER TABLE" in sql
    assert "COALESCE PARTITION" in sql
    assert "2" in sql
    assert params == ()


def test_coalesce_partition_helper_rejects_invalid_target(dialect):
    """CoalescePartitionHelper should reject target_count >= current_count."""
    with pytest.raises(ValueError, match="must be less than"):
        ClickHouseCoalescePartitionHelper(dialect, "orders", target_count=6, current_count=6).to_sql()

    with pytest.raises(ValueError, match="must be less than"):
        ClickHouseCoalescePartitionHelper(dialect, "orders", target_count=7, current_count=6).to_sql()


def test_coalesce_partition_helper_rejects_non_positive_target(dialect):
    """CoalescePartitionHelper should reject non-positive target_count."""
    with pytest.raises(ValueError, match="must be positive"):
        ClickHouseCoalescePartitionHelper(dialect, "orders", target_count=0, current_count=6)


def test_drop_oldest_partition_helper_generates_sql(dialect):
    """DropOldestPartitionHelper should drop the lexicographically first partition."""
    expr = ClickHouseDropOldestPartitionHelper(
        dialect, "orders", partition_names=["p2020", "p2019", "p2021"]
    )

    sql, params = expr.to_sql()

    assert "ALTER TABLE" in sql
    assert "DROP PARTITION" in sql
    assert "p2019" in sql
    assert params == ()


def test_drop_oldest_partition_helper_rejects_empty_names(dialect):
    """DropOldestPartitionHelper should reject empty partition_names."""
    with pytest.raises(ValueError, match="must not be empty"):
        ClickHouseDropOldestPartitionHelper(dialect, "orders", partition_names=[])


def test_reorganize_partition_helper_generates_sql(dialect):
    """ReorganizePartitionHelper should generate REORGANIZE PARTITION SQL."""
    new_partitions = [
        ClickHousePartitionDefinition(name="p2020a", less_than=[ClickHousePartitionValue(dialect, 2021)]),
        ClickHousePartitionDefinition(name="p2020b", less_than=[ClickHousePartitionValue(dialect, 2022)]),
    ]
    expr = ClickHouseReorganizePartitionHelper(dialect, "orders", "p2020", into=new_partitions)

    sql, params = expr.to_sql()

    assert "ALTER TABLE" in sql
    assert "REORGANIZE PARTITION" in sql
    assert "p2020" in sql
    assert params == ()


def test_add_subpartition_helper_generates_sql(dialect):
    """AddSubpartitionHelper should generate ADD PARTITION with subpartition definitions."""
    expr = ClickHouseAddSubpartitionHelper(
        dialect, "orders", "p2025",
        less_than=[2026],
        subpartition_names=["sp0", "sp1"],
    )

    sql, params = expr.to_sql()

    assert "ALTER TABLE" in sql
    assert "ADD PARTITION" in sql
    assert "p2025" in sql
    assert "`sp0`" in sql
    assert "`sp1`" in sql
    assert params == ()


def test_subpartition_clause_to_sql(dialect):
    """SubpartitionClause.to_sql() should produce correct SQL directly."""
    from rhosocial.activerecord.backend.impl.clickhouse.expression import ClickHouseSubpartitionClause, ClickHouseSubpartitionStrategy
    sub = ClickHouseSubpartitionClause(
        dialect,
        strategy=ClickHouseSubpartitionStrategy.HASH,
        expression=Column(dialect, "id"),
        count=4,
    )
    sql, params = sub.to_sql()
    assert "SUBPARTITION BY HASH" in sql
    assert "`id`" in sql
    assert params == ()


def test_partition_value_with_date(dialect):
    """ClickHousePartitionValue should accept datetime.date values."""
    from datetime import date
    value = ClickHousePartitionValue(dialect, date(2026, 6, 1))
    sql, params = value.to_sql()
    assert "2026-06-01" in sql
    assert params == ()


def test_partition_value_with_datetime(dialect):
    """ClickHousePartitionValue should accept datetime.datetime values."""
    from datetime import datetime
    value = ClickHousePartitionValue(dialect, datetime(2026, 6, 1, 12, 30, 0))
    sql, params = value.to_sql()
    assert "2026-06-01" in sql
    assert params == ()


def test_partition_definition_rejects_invalid_dialect_options(dialect):
    """ClickHousePartitionDefinition should reject non-dict dialect_options."""
    with pytest.raises(TypeError, match="dialect_options must be dict"):
        ClickHousePartitionDefinition(
            name="p0",
            less_than=[ClickHousePartitionValue(dialect, 100)],
            dialect_options="invalid",  # type: ignore[arg-type]
        )


def test_partition_by_range_rejects_invalid_subpartition_by(dialect):
    """RANGE partition clause should reject non-ClickHouseSubpartitionClause subpartition_by."""
    with pytest.raises(TypeError, match="subpartition_by must be a ClickHouseSubpartitionClause"):
        ClickHousePartitionByRange(
            dialect, keys=[Column(dialect, "id")],
            subpartition_by="invalid",  # type: ignore[arg-type]
        )


def test_partition_by_range_columns_rejects_invalid_subpartition_by(dialect):
    """RANGE COLUMNS partition clause should reject invalid subpartition_by."""
    with pytest.raises(TypeError, match="subpartition_by must be a ClickHouseSubpartitionClause"):
        ClickHousePartitionByRangeColumns(
            dialect, keys=[Column(dialect, "id")],
            subpartition_by="invalid",  # type: ignore[arg-type]
        )


def test_partition_by_list_rejects_invalid_subpartition_by(dialect):
    """LIST partition clause should reject non-ClickHouseSubpartitionClause subpartition_by."""
    with pytest.raises(TypeError, match="subpartition_by must be a ClickHouseSubpartitionClause"):
        ClickHousePartitionByList(
            dialect, keys=[Column(dialect, "id")],
            subpartition_by="invalid",  # type: ignore[arg-type]
        )


def test_partition_by_list_columns_rejects_invalid_subpartition_by(dialect):
    """LIST COLUMNS partition clause should reject non-ClickHouseSubpartitionClause subpartition_by."""
    with pytest.raises(TypeError, match="subpartition_by must be a ClickHouseSubpartitionClause"):
        ClickHousePartitionByListColumns(
            dialect, keys=[Column(dialect, "id")],
            subpartition_by="invalid",  # type: ignore[arg-type]
        )


def test_add_subpartition_helper_without_subpartitions(dialect):
    """AddSubpartitionHelper should work without subpartition_names."""
    expr = ClickHouseAddSubpartitionHelper(
        dialect, "orders", "p2025",
        less_than=[2026],
    )
    sql, params = expr.to_sql()
    assert "ADD PARTITION" in sql
    assert "`p2025`" in sql
    assert params == ()


def test_add_subpartition_helper_with_in_values(dialect):
    """AddSubpartitionHelper should accept in_values for LIST-based partitioning."""
    expr = ClickHouseAddSubpartitionHelper(
        dialect, "orders", "p_ny",
        subpartition_names=["sp_active", "sp_archived"],
        in_values=["NY"],
    )
    sql, params = expr.to_sql()
    assert "ADD PARTITION" in sql
    assert "`p_ny`" in sql
    assert params == ()


def test_partition_by_range_columns_expression(dialect):
    """PARTITION BY RANGE COLUMNS should format correctly."""
    expr = ClickHousePartitionByRangeColumns(
        dialect=dialect,
        keys=[Column(dialect, "created_year"), Column(dialect, "created_month")],
        partitions=[
            ClickHousePartitionDefinition(
                name="p2026",
                less_than=[_partition_value(dialect, 2026), _partition_value(dialect, 6)],
            )
        ],
    )

    sql, params = expr.to_sql()

    assert "PARTITION BY RANGE COLUMNS" in sql
    assert "created_year" in sql
    assert "created_month" in sql
    assert "PARTITION" in sql
    assert "p2026" in sql
    assert "VALUES LESS THAN" in sql
    assert params == ()


def test_partition_by_range_columns_with_subpartition(dialect):
    """PARTITION BY RANGE COLUMNS with subpartition should format correctly."""
    from rhosocial.activerecord.backend.impl.clickhouse.expression import ClickHouseSubpartitionClause, ClickHouseSubpartitionStrategy
    expr = ClickHousePartitionByRangeColumns(
        dialect=dialect,
        keys=[Column(dialect, "created_year")],
        partitions=[
            ClickHousePartitionDefinition(
                name="p2026",
                less_than=[_partition_value(dialect, 2026)],
            )
        ],
        subpartition_by=ClickHouseSubpartitionClause(
            dialect=dialect,
            strategy=ClickHouseSubpartitionStrategy.HASH,
            expression=Column(dialect, "id"),
            count=4,
        ),
    )

    sql, params = expr.to_sql()

    assert "PARTITION BY RANGE COLUMNS" in sql
    assert "SUBPARTITION BY HASH" in sql
    assert "`id`" in sql
    assert params == ()


def test_partition_by_list_with_subpartition(dialect):
    """PARTITION BY LIST with subpartition should format correctly."""
    from rhosocial.activerecord.backend.impl.clickhouse.expression import ClickHouseSubpartitionClause, ClickHouseSubpartitionStrategy
    expr = ClickHousePartitionByList(
        dialect=dialect,
        keys=[Column(dialect, "status")],
        partitions=[
            ClickHousePartitionDefinition(
                name="p_active",
                in_values=[_partition_value(dialect, "active")],
            )
        ],
        subpartition_by=ClickHouseSubpartitionClause(
            dialect=dialect,
            strategy=ClickHouseSubpartitionStrategy.HASH,
            expression=Column(dialect, "id"),
            count=2,
        ),
    )

    sql, params = expr.to_sql()

    assert "PARTITION BY LIST" in sql
    assert "SUBPARTITION BY HASH" in sql
    assert "`id`" in sql
    assert params == ()


def test_partition_by_list_columns_with_subpartition(dialect):
    """PARTITION BY LIST COLUMNS with subpartition should format correctly."""
    from rhosocial.activerecord.backend.impl.clickhouse.expression import ClickHouseSubpartitionClause, ClickHouseSubpartitionStrategy
    expr = ClickHousePartitionByListColumns(
        dialect=dialect,
        keys=[Column(dialect, "status")],
        partitions=[
            ClickHousePartitionDefinition(
                name="p_active",
                in_values=[_partition_value(dialect, "active")],
            )
        ],
        subpartition_by=ClickHouseSubpartitionClause(
            dialect=dialect,
            strategy=ClickHouseSubpartitionStrategy.HASH,
            expression=Column(dialect, "id"),
            count=2,
        ),
    )

    sql, params = expr.to_sql()

    assert "PARTITION BY LIST COLUMNS" in sql
    assert "SUBPARTITION BY HASH" in sql
    assert "`id`" in sql
    assert params == ()


# tests/providers/fixtures/events.py
"""DDL expressions for the ``feature/events`` table group (ClickHouse).

Reference: ``tests/rhosocial/activerecord_clickhouse_test/feature/events/schema/``.

ClickHouse-specific notes:
- Primary keys are plain ``Int64`` columns; ids are generated client-side by
  the backend (snowflake), so no ``AUTO_INCREMENT`` is emitted.
- Tables use ``ENGINE = MergeTree`` with ``ORDER BY id`` and the lightweight
  update/delete settings required by modern ClickHouse.
"""

from typing import Callable, Dict

from rhosocial.activerecord.backend.expression import (
    CreateTableExpression,
)
from rhosocial.activerecord.backend.expression.statements import (
    ColumnDefinition,
    ColumnConstraint,
    ColumnConstraintType,
)
from rhosocial.activerecord.backend.expression.types import (
    BigIntType,
    DateTimeType,
    IntegerType,
    TextType,
    VarCharType,
)

from rhosocial.activerecord.backend.impl.clickhouse.expression import ClickHouseDateTime64Type

from . import _common

# Standard ClickHouse table options.
_DEFAULT_STORAGE_OPTIONS = {
    "ENGINE": "MergeTree",
    "ORDER BY": "id",
    "SETTINGS": "enable_block_number_column = 1, enable_block_offset_column = 1",
}


def to_sql(expr: CreateTableExpression):
    return _common.to_clickhouse_ddl_sql(expr)


# ---------------------------------------------------------------------------
# events/event_tests.sql
# ---------------------------------------------------------------------------

def create_event_tests_table(dialect, table_name: str = "event_tests") -> CreateTableExpression:
    return CreateTableExpression(
        dialect=dialect,
        table=table_name,
        if_not_exists=False,
        columns=[
            ColumnDefinition("id", BigIntType(),
                constraints=[ColumnConstraint(ColumnConstraintType.PRIMARY_KEY)]),
            ColumnDefinition("name", VarCharType(length=255),
                constraints=[ColumnConstraint(ColumnConstraintType.NOT_NULL)]),
            ColumnDefinition("status", VarCharType(length=50),
                constraints=[ColumnConstraint(ColumnConstraintType.NOT_NULL),
                             ColumnConstraint(ColumnConstraintType.DEFAULT, default_value="draft")]),
            ColumnDefinition("revision", IntegerType(),
                constraints=[ColumnConstraint(ColumnConstraintType.NOT_NULL),
                             ColumnConstraint(ColumnConstraintType.DEFAULT, default_value=1)]),
            ColumnDefinition("content", TextType()),
            ColumnDefinition("created_at", ClickHouseDateTime64Type(6)),
            ColumnDefinition("updated_at", ClickHouseDateTime64Type(6)),
        ],
        storage_options=dict(_DEFAULT_STORAGE_OPTIONS),
    )


# ---------------------------------------------------------------------------
# events/event_tracking_models.sql
# ---------------------------------------------------------------------------

def create_event_tracking_models_table(dialect, table_name: str = "event_tracking_models") -> CreateTableExpression:
    return CreateTableExpression(
        dialect=dialect,
        table=table_name,
        if_not_exists=False,
        columns=[
            ColumnDefinition("id", BigIntType(),
                constraints=[ColumnConstraint(ColumnConstraintType.PRIMARY_KEY)]),
            ColumnDefinition("title", VarCharType(length=255),
                constraints=[ColumnConstraint(ColumnConstraintType.NOT_NULL)]),
            ColumnDefinition("content", TextType(),
                constraints=[ColumnConstraint(ColumnConstraintType.NOT_NULL)]),
            ColumnDefinition("view_count", IntegerType(),
                constraints=[ColumnConstraint(ColumnConstraintType.NOT_NULL),
                             ColumnConstraint(ColumnConstraintType.DEFAULT, default_value=0)]),
            ColumnDefinition("last_viewed_at", ClickHouseDateTime64Type(6),
                constraints=[ColumnConstraint(ColumnConstraintType.NULL)]),
        ],
        storage_options=dict(_DEFAULT_STORAGE_OPTIONS),
    )


TABLE_EXPRESSIONS: Dict[str, Callable] = {
    "event_tests": create_event_tests_table,
    "event_tracking_models": create_event_tracking_models_table,
}
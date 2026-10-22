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
    CreateTableStatement,
)
from rhosocial.activerecord.backend.expression.objects import Table
from rhosocial.activerecord.backend.expression.statements import (
    ColumnDefinition,
    ColumnConstraint,
    ColumnPrimaryKeyConstraint, ColumnNotNullConstraint, ColumnNullableConstraint, ColumnDefaultConstraint,
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


def to_sql(expr: CreateTableStatement):
    return _common.to_clickhouse_ddl_sql(expr)


# ---------------------------------------------------------------------------
# events/event_tests.sql
# ---------------------------------------------------------------------------

def create_event_tests_table(dialect, table_name: str = "event_tests") -> CreateTableStatement:
    return CreateTableStatement(
        dialect=dialect,
        table=Table(dialect, table_name),
        if_not_exists=False,
        columns=[
            ColumnDefinition(dialect, "id", BigIntType(dialect),
                constraints=[ColumnConstraint(dialect, branch=ColumnPrimaryKeyConstraint(dialect))]),
            ColumnDefinition(dialect, "name", VarCharType(dialect, length=255),
                constraints=[ColumnConstraint(dialect, branch=ColumnNotNullConstraint(dialect))]),
            ColumnDefinition(dialect, "status", VarCharType(dialect, length=50),
                constraints=[ColumnConstraint(dialect, branch=ColumnNotNullConstraint(dialect)),
                             ColumnConstraint(dialect, branch=ColumnDefaultConstraint(dialect, "draft"))]),
            ColumnDefinition(dialect, "revision", IntegerType(dialect),
                constraints=[ColumnConstraint(dialect, branch=ColumnNotNullConstraint(dialect)),
                             ColumnConstraint(dialect, branch=ColumnDefaultConstraint(dialect, 1))]),
            ColumnDefinition(dialect, "content", TextType(dialect)),
            ColumnDefinition(dialect, "created_at", ClickHouseDateTime64Type(dialect, precision=6)),
            ColumnDefinition(dialect, "updated_at", ClickHouseDateTime64Type(dialect, precision=6)),
        ],
        table_options=_common.default_table_options(dialect),
    )


# ---------------------------------------------------------------------------
# events/event_tracking_models.sql
# ---------------------------------------------------------------------------

def create_event_tracking_models_table(dialect, table_name: str = "event_tracking_models") -> CreateTableStatement:
    return CreateTableStatement(
        dialect=dialect,
        table=Table(dialect, table_name),
        if_not_exists=False,
        columns=[
            ColumnDefinition(dialect, "id", BigIntType(dialect),
                constraints=[ColumnConstraint(dialect, branch=ColumnPrimaryKeyConstraint(dialect))]),
            ColumnDefinition(dialect, "title", VarCharType(dialect, length=255),
                constraints=[ColumnConstraint(dialect, branch=ColumnNotNullConstraint(dialect))]),
            ColumnDefinition(dialect, "content", TextType(dialect),
                constraints=[ColumnConstraint(dialect, branch=ColumnNotNullConstraint(dialect))]),
            ColumnDefinition(dialect, "view_count", IntegerType(dialect),
                constraints=[ColumnConstraint(dialect, branch=ColumnNotNullConstraint(dialect)),
                             ColumnConstraint(dialect, branch=ColumnDefaultConstraint(dialect, 0))]),
            ColumnDefinition(dialect, "last_viewed_at", ClickHouseDateTime64Type(dialect, precision=6),
                constraints=[ColumnConstraint(dialect, branch=ColumnNullableConstraint(dialect))]),
        ],
        table_options=_common.default_table_options(dialect),
    )


TABLE_EXPRESSIONS: Dict[str, Callable] = {
    "event_tests": create_event_tests_table,
    "event_tracking_models": create_event_tracking_models_table,
}
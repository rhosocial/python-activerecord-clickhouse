# tests/providers/fixtures/mixins.py
"""DDL expressions for the ``feature/mixins`` table group (ClickHouse).

Reference: ``tests/rhosocial/activerecord_clickhouse_test/feature/mixins/schema/``.

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
    BooleanType,
    DateTimeType,
    DecimalType,
    IntegerType,
    TextType,
    VarCharType,
)

from rhosocial.activerecord.backend.impl.clickhouse.expression import ClickHouseDateTime64Type

from . import _common


def to_sql(expr: CreateTableStatement):
    return _common.to_clickhouse_ddl_sql(expr)


# ---------------------------------------------------------------------------
# mixins/combined_articles.sql
# ---------------------------------------------------------------------------

def create_combined_articles_table(dialect, table_name: str = "combined_articles") -> CreateTableStatement:
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
            ColumnDefinition(dialect, "status", VarCharType(dialect, length=50),
                constraints=[ColumnConstraint(dialect, branch=ColumnNotNullConstraint(dialect)),
                             ColumnConstraint(dialect, branch=ColumnDefaultConstraint(dialect, "draft"))]),
            ColumnDefinition(dialect, "created_at", ClickHouseDateTime64Type(dialect, precision=6)),
            ColumnDefinition(dialect, "updated_at", ClickHouseDateTime64Type(dialect, precision=6)),
            ColumnDefinition(dialect, "version", IntegerType(dialect),
                constraints=[ColumnConstraint(dialect, branch=ColumnNotNullConstraint(dialect)),
                             ColumnConstraint(dialect, branch=ColumnDefaultConstraint(dialect, 1))]),
            ColumnDefinition(dialect, "deleted_at", ClickHouseDateTime64Type(dialect, precision=6),
                constraints=[ColumnConstraint(dialect, branch=ColumnNullableConstraint(dialect))]),
        ],
        table_options=_common.default_table_options(dialect),
    )


# ---------------------------------------------------------------------------
# mixins/tasks.sql
# ---------------------------------------------------------------------------

def create_tasks_table(dialect, table_name: str = "tasks") -> CreateTableStatement:
    return CreateTableStatement(
        dialect=dialect,
        table=Table(dialect, table_name),
        if_not_exists=False,
        columns=[
            ColumnDefinition(dialect, "id", BigIntType(dialect),
                constraints=[ColumnConstraint(dialect, branch=ColumnPrimaryKeyConstraint(dialect))]),
            ColumnDefinition(dialect, "title", VarCharType(dialect, length=255),
                constraints=[ColumnConstraint(dialect, branch=ColumnNotNullConstraint(dialect))]),
            ColumnDefinition(dialect, "is_completed", BooleanType(dialect),
                constraints=[ColumnConstraint(dialect, branch=ColumnNotNullConstraint(dialect)),
                             ColumnConstraint(dialect, branch=ColumnDefaultConstraint(dialect, 0))]),
            ColumnDefinition(dialect, "deleted_at", TextType(dialect),
                constraints=[ColumnConstraint(dialect, branch=ColumnNullableConstraint(dialect))]),
        ],
        table_options=_common.default_table_options(dialect),
    )


# ---------------------------------------------------------------------------
# mixins/timestamped_posts.sql
# ---------------------------------------------------------------------------

def create_timestamped_posts_table(dialect, table_name: str = "timestamped_posts") -> CreateTableStatement:
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
            ColumnDefinition(dialect, "created_at", ClickHouseDateTime64Type(dialect, precision=6)),
            ColumnDefinition(dialect, "updated_at", ClickHouseDateTime64Type(dialect, precision=6)),
        ],
        table_options=_common.default_table_options(dialect),
    )


# ---------------------------------------------------------------------------
# mixins/versioned_products.sql
# ---------------------------------------------------------------------------

def create_versioned_products_table(dialect, table_name: str = "versioned_products") -> CreateTableStatement:
    return CreateTableStatement(
        dialect=dialect,
        table=Table(dialect, table_name),
        if_not_exists=False,
        columns=[
            ColumnDefinition(dialect, "id", BigIntType(dialect),
                constraints=[ColumnConstraint(dialect, branch=ColumnPrimaryKeyConstraint(dialect))]),
            ColumnDefinition(dialect, "name", VarCharType(dialect, length=255),
                constraints=[ColumnConstraint(dialect, branch=ColumnNotNullConstraint(dialect))]),
            ColumnDefinition(dialect, "price", DecimalType(dialect, precision=10, scale=2),
                constraints=[ColumnConstraint(dialect, branch=ColumnNotNullConstraint(dialect)),
                             ColumnConstraint(dialect, branch=ColumnDefaultConstraint(dialect, 0.0))]),
            ColumnDefinition(dialect, "version", IntegerType(dialect),
                constraints=[ColumnConstraint(dialect, branch=ColumnNotNullConstraint(dialect)),
                             ColumnConstraint(dialect, branch=ColumnDefaultConstraint(dialect, 1))]),
        ],
        table_options=_common.default_table_options(dialect),
    )


TABLE_EXPRESSIONS: Dict[str, Callable] = {
    "combined_articles": create_combined_articles_table,
    "tasks": create_tasks_table,
    "timestamped_posts": create_timestamped_posts_table,
    "versioned_products": create_versioned_products_table,
}
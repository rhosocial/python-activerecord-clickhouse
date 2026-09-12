# tests/providers/fixtures/query.py
"""DDL expressions for the ``feature/query`` table group (ClickHouse).

Each factory builds a :class:`CreateTableExpression` whose generated ClickHouse DDL
is semantically equivalent to the reference ``.sql`` schema files under
``tests/rhosocial/activerecord_clickhouse_test/feature/query/schema/``.  Those
``.sql`` files are kept as the authoritative reference and are no longer
loaded at runtime.

ClickHouse-specific notes:
- Primary keys and FK reference columns are ``Int64`` (snowflake ids are
  generated client-side by the backend; no ``AUTO_INCREMENT`` is emitted).
- ``UNIQUE`` and ``FOREIGN KEY`` constraints are not supported and are dropped.
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
    ForeignKeyConstraint,
    IndexDefinition,
    ReferentialAction,
)
from rhosocial.activerecord.backend.expression.types import (
    BigIntType,
    BooleanType,
    DateTimeType,
    DecimalType,
    DoubleType,
    IntegerType,
    JsonType,
    TextType,
    VarCharType,
)

from rhosocial.activerecord.backend.impl.clickhouse.expression import (
    ClickHouseDateTime64Type,
    ClickHouseNullableType,
)

from . import _common

# Standard ClickHouse table options.
_DEFAULT_STORAGE_OPTIONS = {
    "ENGINE": "MergeTree",
    "ORDER BY": "id",
    "SETTINGS": "enable_block_number_column = 1, enable_block_offset_column = 1",
}

_CASCADE = ReferentialAction.CASCADE


def to_sql(expr: CreateTableExpression):
    return _common.to_clickhouse_ddl_sql(expr)


# ---------------------------------------------------------------------------
# query/users.sql
# ---------------------------------------------------------------------------

def create_users_table(dialect, table_name: str = "users") -> CreateTableExpression:
    return CreateTableExpression(
        dialect=dialect,
        table=table_name,
        if_not_exists=False,
        columns=[
            ColumnDefinition(dialect, "id", BigIntType(dialect),
                constraints=[ColumnConstraint(dialect, ColumnConstraintType.PRIMARY_KEY)]),
            ColumnDefinition(dialect, "username", VarCharType(dialect, length=191),
                constraints=[ColumnConstraint(dialect, ColumnConstraintType.NOT_NULL)]),
            ColumnDefinition(dialect, "email", VarCharType(dialect, length=191),
                constraints=[ColumnConstraint(dialect, ColumnConstraintType.NOT_NULL)]),
            # Optional[T] model fields must map to Nullable columns so that None
            # is stored/returned as SQL NULL instead of ClickHouse's zero value.
            ColumnDefinition(dialect, "age", ClickHouseNullableType(dialect, inner_type=IntegerType(dialect))),
            ColumnDefinition(dialect, "balance", DoubleType(dialect),
                constraints=[ColumnConstraint(dialect, ColumnConstraintType.NOT_NULL),
                             ColumnConstraint(dialect, ColumnConstraintType.DEFAULT, default_value=0.0)]),
            ColumnDefinition(dialect, "is_active", BooleanType(dialect),
                constraints=[ColumnConstraint(dialect, ColumnConstraintType.NOT_NULL),
                             ColumnConstraint(dialect, ColumnConstraintType.DEFAULT, default_value=1)]),
            ColumnDefinition(dialect, "created_at", ClickHouseDateTime64Type(precision=6)),
            ColumnDefinition(dialect, "updated_at", ClickHouseDateTime64Type(precision=6)),
        ],
        storage_options=dict(_DEFAULT_STORAGE_OPTIONS),
    )


# ---------------------------------------------------------------------------
# query/posts.sql
# ---------------------------------------------------------------------------

def create_posts_table(dialect, table_name: str = "posts") -> CreateTableExpression:
    return CreateTableExpression(
        dialect=dialect,
        table=table_name,
        if_not_exists=False,
        columns=[
            ColumnDefinition(dialect, "id", BigIntType(dialect),
                constraints=[ColumnConstraint(dialect, ColumnConstraintType.PRIMARY_KEY)]),
            ColumnDefinition(dialect, "user_id", BigIntType(dialect),
                constraints=[ColumnConstraint(dialect, ColumnConstraintType.NOT_NULL)]),
            ColumnDefinition(dialect, "title", VarCharType(dialect, length=255),
                constraints=[ColumnConstraint(dialect, ColumnConstraintType.NOT_NULL)]),
            ColumnDefinition(dialect, "content", TextType(dialect)),
            ColumnDefinition(dialect, "status", VarCharType(dialect, length=50),
                constraints=[ColumnConstraint(dialect, ColumnConstraintType.NOT_NULL),
                             ColumnConstraint(dialect, ColumnConstraintType.DEFAULT, default_value="published")]),
            ColumnDefinition(dialect, "created_at", ClickHouseDateTime64Type(precision=6)),
            ColumnDefinition(dialect, "updated_at", ClickHouseDateTime64Type(precision=6)),
        ],
        indexes=[IndexDefinition(dialect, name="idx_user_id", columns=["user_id"]),
                 IndexDefinition(dialect, name="idx_status", columns=["status"])],
        storage_options=dict(_DEFAULT_STORAGE_OPTIONS),
    )


# ---------------------------------------------------------------------------
# query/comments.sql
# ---------------------------------------------------------------------------

def create_comments_table(dialect, table_name: str = "comments") -> CreateTableExpression:
    return CreateTableExpression(
        dialect=dialect,
        table=table_name,
        if_not_exists=False,
        columns=[
            ColumnDefinition(dialect, "id", BigIntType(dialect),
                constraints=[ColumnConstraint(dialect, ColumnConstraintType.PRIMARY_KEY)]),
            ColumnDefinition(dialect, "user_id", BigIntType(dialect),
                constraints=[ColumnConstraint(dialect, ColumnConstraintType.NOT_NULL)]),
            ColumnDefinition(dialect, "post_id", BigIntType(dialect),
                constraints=[ColumnConstraint(dialect, ColumnConstraintType.NOT_NULL)]),
            ColumnDefinition(dialect, "content", TextType(dialect)),
            ColumnDefinition(dialect, "is_hidden", BooleanType(dialect),
                constraints=[ColumnConstraint(dialect, ColumnConstraintType.DEFAULT, default_value=0)]),
            ColumnDefinition(dialect, "created_at", ClickHouseDateTime64Type(precision=6)),
            ColumnDefinition(dialect, "updated_at", ClickHouseDateTime64Type(precision=6)),
        ],
        indexes=[IndexDefinition(dialect, name="idx_user_id", columns=["user_id"]),
                 IndexDefinition(dialect, name="idx_post_id", columns=["post_id"])],
        storage_options=dict(_DEFAULT_STORAGE_OPTIONS),
    )


# ---------------------------------------------------------------------------
# query/orders.sql
# ---------------------------------------------------------------------------

def create_orders_table(dialect, table_name: str = "orders") -> CreateTableExpression:
    return CreateTableExpression(
        dialect=dialect,
        table=table_name,
        if_not_exists=False,
        columns=[
            ColumnDefinition(dialect, "id", BigIntType(dialect),
                constraints=[ColumnConstraint(dialect, ColumnConstraintType.PRIMARY_KEY)]),
            ColumnDefinition(dialect, "user_id", BigIntType(dialect),
                constraints=[ColumnConstraint(dialect, ColumnConstraintType.NOT_NULL)]),
            ColumnDefinition(dialect, "order_number", VarCharType(dialect, length=255),
                constraints=[ColumnConstraint(dialect, ColumnConstraintType.NOT_NULL)]),
            ColumnDefinition(dialect, "total_amount", DecimalType(dialect, precision=10, scale=2),
                constraints=[ColumnConstraint(dialect, ColumnConstraintType.NOT_NULL),
                             ColumnConstraint(dialect, ColumnConstraintType.DEFAULT, default_value=0.0)]),
            ColumnDefinition(dialect, "status", VarCharType(dialect, length=50),
                constraints=[ColumnConstraint(dialect, ColumnConstraintType.NOT_NULL),
                             ColumnConstraint(dialect, ColumnConstraintType.DEFAULT, default_value="pending")]),
            ColumnDefinition(dialect, "created_at", ClickHouseDateTime64Type(precision=6)),
            ColumnDefinition(dialect, "updated_at", ClickHouseDateTime64Type(precision=6)),
        ],
        indexes=[IndexDefinition(dialect, name="idx_user_id", columns=["user_id"])],
        storage_options=dict(_DEFAULT_STORAGE_OPTIONS),
    )


# ---------------------------------------------------------------------------
# query/order_items.sql
# ---------------------------------------------------------------------------

def create_order_items_table(dialect, table_name: str = "order_items") -> CreateTableExpression:
    return CreateTableExpression(
        dialect=dialect,
        table=table_name,
        if_not_exists=False,
        columns=[
            ColumnDefinition(dialect, "id", BigIntType(dialect),
                constraints=[ColumnConstraint(dialect, ColumnConstraintType.PRIMARY_KEY)]),
            ColumnDefinition(dialect, "order_id", BigIntType(dialect),
                constraints=[ColumnConstraint(dialect, ColumnConstraintType.NOT_NULL)]),
            ColumnDefinition(dialect, "product_name", VarCharType(dialect, length=255),
                constraints=[ColumnConstraint(dialect, ColumnConstraintType.NOT_NULL)]),
            ColumnDefinition(dialect, "quantity", IntegerType(dialect),
                constraints=[ColumnConstraint(dialect, ColumnConstraintType.NOT_NULL),
                             ColumnConstraint(dialect, ColumnConstraintType.DEFAULT, default_value=1)]),
            ColumnDefinition(dialect, "unit_price", DecimalType(dialect, precision=10, scale=2),
                constraints=[ColumnConstraint(dialect, ColumnConstraintType.NOT_NULL)]),
            ColumnDefinition(dialect, "subtotal", DecimalType(dialect, precision=10, scale=2),
                constraints=[ColumnConstraint(dialect, ColumnConstraintType.NOT_NULL),
                             ColumnConstraint(dialect, ColumnConstraintType.DEFAULT, default_value=0.0)]),
            ColumnDefinition(dialect, "created_at", ClickHouseDateTime64Type(precision=6)),
            ColumnDefinition(dialect, "updated_at", ClickHouseDateTime64Type(precision=6)),
        ],
        indexes=[IndexDefinition(dialect, name="idx_order_id", columns=["order_id"])],
        storage_options=dict(_DEFAULT_STORAGE_OPTIONS),
    )


# ---------------------------------------------------------------------------
# query/profiles.sql
# ---------------------------------------------------------------------------

def create_profiles_table(dialect, table_name: str = "profiles") -> CreateTableExpression:
    return CreateTableExpression(
        dialect=dialect,
        table=table_name,
        if_not_exists=False,
        columns=[
            ColumnDefinition(dialect, "id", BigIntType(dialect),
                constraints=[ColumnConstraint(dialect, ColumnConstraintType.PRIMARY_KEY)]),
            ColumnDefinition(dialect, "user_id", BigIntType(dialect),
                constraints=[ColumnConstraint(dialect, ColumnConstraintType.NOT_NULL)]),
            ColumnDefinition(dialect, "bio", TextType(dialect)),
            ColumnDefinition(dialect, "avatar_url", VarCharType(dialect, length=512)),
            ColumnDefinition(dialect, "created_at", ClickHouseDateTime64Type(precision=6)),
            ColumnDefinition(dialect, "updated_at", ClickHouseDateTime64Type(precision=6)),
        ],
        storage_options=dict(_DEFAULT_STORAGE_OPTIONS),
    )


# ---------------------------------------------------------------------------
# query/json_users.sql
# ---------------------------------------------------------------------------

def create_json_users_table(dialect, table_name: str = "json_users") -> CreateTableExpression:
    return CreateTableExpression(
        dialect=dialect,
        table=table_name,
        if_not_exists=False,
        columns=[
            ColumnDefinition(dialect, "id", BigIntType(dialect),
                constraints=[ColumnConstraint(dialect, ColumnConstraintType.PRIMARY_KEY)]),
            ColumnDefinition(dialect, "username", VarCharType(dialect, length=255),
                constraints=[ColumnConstraint(dialect, ColumnConstraintType.NOT_NULL)]),
            ColumnDefinition(dialect, "email", VarCharType(dialect, length=255),
                constraints=[ColumnConstraint(dialect, ColumnConstraintType.NOT_NULL)]),
            ColumnDefinition(dialect, "age", ClickHouseNullableType(dialect, inner_type=IntegerType(dialect))),
            ColumnDefinition(dialect, "created_at", ClickHouseDateTime64Type(precision=6)),
            ColumnDefinition(dialect, "updated_at", ClickHouseDateTime64Type(precision=6)),
            ColumnDefinition(dialect, "settings", JsonType(dialect)),
            ColumnDefinition(dialect, "tags", JsonType(dialect)),
            ColumnDefinition(dialect, "profile", JsonType(dialect)),
            ColumnDefinition(dialect, "roles", JsonType(dialect)),
            ColumnDefinition(dialect, "scores", JsonType(dialect)),
            ColumnDefinition(dialect, "subscription", JsonType(dialect)),
            ColumnDefinition(dialect, "preferences", JsonType(dialect)),
        ],
        storage_options=dict(_DEFAULT_STORAGE_OPTIONS),
    )


# ---------------------------------------------------------------------------
# query/nodes.sql (self-referential FK)
# ---------------------------------------------------------------------------

def create_nodes_table(dialect, table_name: str = "nodes") -> CreateTableExpression:
    return CreateTableExpression(
        dialect=dialect,
        table=table_name,
        if_not_exists=False,
        columns=[
            ColumnDefinition(dialect, "id", BigIntType(dialect),
                constraints=[ColumnConstraint(dialect, ColumnConstraintType.PRIMARY_KEY)]),
            ColumnDefinition(dialect, "name", VarCharType(dialect, length=255),
                constraints=[ColumnConstraint(dialect, ColumnConstraintType.NOT_NULL)]),
            ColumnDefinition(dialect, "parent_id", BigIntType(dialect),
                constraints=[ColumnConstraint(dialect, ColumnConstraintType.NULL)]),
            ColumnDefinition(dialect, "value", DecimalType(dialect, precision=10, scale=2),
                constraints=[ColumnConstraint(dialect, ColumnConstraintType.NOT_NULL),
                             ColumnConstraint(dialect, ColumnConstraintType.DEFAULT, default_value=0.0)]),
            ColumnDefinition(dialect, "created_at", ClickHouseDateTime64Type(precision=6)),
            ColumnDefinition(dialect, "updated_at", ClickHouseDateTime64Type(precision=6)),
        ],
        storage_options=dict(_DEFAULT_STORAGE_OPTIONS),
    )


# ---------------------------------------------------------------------------
# query/searchable_items.sql
# ---------------------------------------------------------------------------

def create_searchable_items_table(dialect, table_name: str = "searchable_items") -> CreateTableExpression:
    return CreateTableExpression(
        dialect=dialect,
        table=table_name,
        if_not_exists=False,
        columns=[
            ColumnDefinition(dialect, "id", BigIntType(dialect),
                constraints=[ColumnConstraint(dialect, ColumnConstraintType.PRIMARY_KEY)]),
            ColumnDefinition(dialect, "name", VarCharType(dialect, length=255)),
            ColumnDefinition(dialect, "tags", TextType(dialect)),
            ColumnDefinition(dialect, "created_at", ClickHouseDateTime64Type(precision=6)),
            ColumnDefinition(dialect, "updated_at", ClickHouseDateTime64Type(precision=6)),
        ],
        storage_options=dict(_DEFAULT_STORAGE_OPTIONS),
    )


# ---------------------------------------------------------------------------
# query/extended_orders.sql
# ---------------------------------------------------------------------------

def create_extended_orders_table(dialect, table_name: str = "extended_orders") -> CreateTableExpression:
    return CreateTableExpression(
        dialect=dialect,
        table=table_name,
        if_not_exists=False,
        columns=[
            ColumnDefinition(dialect, "id", BigIntType(dialect),
                constraints=[ColumnConstraint(dialect, ColumnConstraintType.PRIMARY_KEY)]),
            ColumnDefinition(dialect, "user_id", BigIntType(dialect),
                constraints=[ColumnConstraint(dialect, ColumnConstraintType.NOT_NULL)]),
            ColumnDefinition(dialect, "order_number", VarCharType(dialect, length=255),
                constraints=[ColumnConstraint(dialect, ColumnConstraintType.NOT_NULL)]),
            ColumnDefinition(dialect, "total_amount", DecimalType(dialect, precision=10, scale=2),
                constraints=[ColumnConstraint(dialect, ColumnConstraintType.NOT_NULL),
                             ColumnConstraint(dialect, ColumnConstraintType.DEFAULT, default_value=0.0)]),
            ColumnDefinition(dialect, "status", VarCharType(dialect, length=50),
                constraints=[ColumnConstraint(dialect, ColumnConstraintType.NOT_NULL),
                             ColumnConstraint(dialect, ColumnConstraintType.DEFAULT, default_value="pending")]),
            ColumnDefinition(dialect, "priority", VarCharType(dialect, length=50),
                constraints=[ColumnConstraint(dialect, ColumnConstraintType.NOT_NULL),
                             ColumnConstraint(dialect, ColumnConstraintType.DEFAULT, default_value="medium")]),
            ColumnDefinition(dialect, "region", VarCharType(dialect, length=50),
                constraints=[ColumnConstraint(dialect, ColumnConstraintType.NOT_NULL),
                             ColumnConstraint(dialect, ColumnConstraintType.DEFAULT, default_value="default")]),
            ColumnDefinition(dialect, "category", VarCharType(dialect, length=255)),
            ColumnDefinition(dialect, "product", VarCharType(dialect, length=255)),
            ColumnDefinition(dialect, "department", VarCharType(dialect, length=255)),
            ColumnDefinition(dialect, "year", VarCharType(dialect, length=10)),
            ColumnDefinition(dialect, "quarter", VarCharType(dialect, length=10)),
            ColumnDefinition(dialect, "created_at", ClickHouseDateTime64Type(precision=6)),
            ColumnDefinition(dialect, "updated_at", ClickHouseDateTime64Type(precision=6)),
        ],
        indexes=[IndexDefinition(dialect, name="idx_user_id", columns=["user_id"]),
                 IndexDefinition(dialect, name="idx_status", columns=["status"]),
                 IndexDefinition(dialect, name="idx_priority", columns=["priority"]),
                 IndexDefinition(dialect, name="idx_region", columns=["region"])],
        storage_options=dict(_DEFAULT_STORAGE_OPTIONS),
    )


# ---------------------------------------------------------------------------
# query/extended_order_items.sql
# ---------------------------------------------------------------------------

def create_extended_order_items_table(dialect, table_name: str = "extended_order_items") -> CreateTableExpression:
    return CreateTableExpression(
        dialect=dialect,
        table=table_name,
        if_not_exists=False,
        columns=[
            ColumnDefinition(dialect, "id", BigIntType(dialect),
                constraints=[ColumnConstraint(dialect, ColumnConstraintType.PRIMARY_KEY)]),
            ColumnDefinition(dialect, "order_id", BigIntType(dialect),
                constraints=[ColumnConstraint(dialect, ColumnConstraintType.NOT_NULL)]),
            ColumnDefinition(dialect, "product_name", VarCharType(dialect, length=255),
                constraints=[ColumnConstraint(dialect, ColumnConstraintType.NOT_NULL)]),
            ColumnDefinition(dialect, "quantity", IntegerType(dialect),
                constraints=[ColumnConstraint(dialect, ColumnConstraintType.NOT_NULL),
                             ColumnConstraint(dialect, ColumnConstraintType.DEFAULT, default_value=1)]),
            ColumnDefinition(dialect, "price", DecimalType(dialect, precision=10, scale=2),
                constraints=[ColumnConstraint(dialect, ColumnConstraintType.NOT_NULL)]),
            ColumnDefinition(dialect, "category", VarCharType(dialect, length=255)),
            ColumnDefinition(dialect, "region", VarCharType(dialect, length=50)),
            ColumnDefinition(dialect, "created_at", ClickHouseDateTime64Type(precision=6)),
            ColumnDefinition(dialect, "updated_at", ClickHouseDateTime64Type(precision=6)),
        ],
        indexes=[IndexDefinition(dialect, name="idx_order_id", columns=["order_id"])],
        storage_options=dict(_DEFAULT_STORAGE_OPTIONS),
    )


TABLE_EXPRESSIONS: Dict[str, Callable] = {
    "users": create_users_table,
    "posts": create_posts_table,
    "comments": create_comments_table,
    "orders": create_orders_table,
    "order_items": create_order_items_table,
    "profiles": create_profiles_table,
    "json_users": create_json_users_table,
    "nodes": create_nodes_table,
    "searchable_items": create_searchable_items_table,
    "extended_orders": create_extended_orders_table,
    "extended_order_items": create_extended_order_items_table,
}
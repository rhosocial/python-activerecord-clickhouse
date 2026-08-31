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
            ColumnDefinition("id", BigIntType(),
                constraints=[ColumnConstraint(ColumnConstraintType.PRIMARY_KEY)]),
            ColumnDefinition("username", VarCharType(length=191),
                constraints=[ColumnConstraint(ColumnConstraintType.NOT_NULL)]),
            ColumnDefinition("email", VarCharType(length=191),
                constraints=[ColumnConstraint(ColumnConstraintType.NOT_NULL)]),
            # Optional[T] model fields must map to Nullable columns so that None
            # is stored/returned as SQL NULL instead of ClickHouse's zero value.
            ColumnDefinition("age", ClickHouseNullableType(inner_type=IntegerType())),
            ColumnDefinition("balance", DoubleType(),
                constraints=[ColumnConstraint(ColumnConstraintType.NOT_NULL),
                             ColumnConstraint(ColumnConstraintType.DEFAULT, default_value=0.0)]),
            ColumnDefinition("is_active", BooleanType(),
                constraints=[ColumnConstraint(ColumnConstraintType.NOT_NULL),
                             ColumnConstraint(ColumnConstraintType.DEFAULT, default_value=1)]),
            ColumnDefinition("created_at", ClickHouseDateTime64Type(6)),
            ColumnDefinition("updated_at", ClickHouseDateTime64Type(6)),
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
            ColumnDefinition("id", BigIntType(),
                constraints=[ColumnConstraint(ColumnConstraintType.PRIMARY_KEY)]),
            ColumnDefinition("user_id", BigIntType(),
                constraints=[ColumnConstraint(ColumnConstraintType.NOT_NULL)]),
            ColumnDefinition("title", VarCharType(length=255),
                constraints=[ColumnConstraint(ColumnConstraintType.NOT_NULL)]),
            ColumnDefinition("content", TextType()),
            ColumnDefinition("status", VarCharType(length=50),
                constraints=[ColumnConstraint(ColumnConstraintType.NOT_NULL),
                             ColumnConstraint(ColumnConstraintType.DEFAULT, default_value="published")]),
            ColumnDefinition("created_at", ClickHouseDateTime64Type(6)),
            ColumnDefinition("updated_at", ClickHouseDateTime64Type(6)),
        ],
        indexes=[IndexDefinition(name="idx_user_id", columns=["user_id"]),
                 IndexDefinition(name="idx_status", columns=["status"])],
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
            ColumnDefinition("id", BigIntType(),
                constraints=[ColumnConstraint(ColumnConstraintType.PRIMARY_KEY)]),
            ColumnDefinition("user_id", BigIntType(),
                constraints=[ColumnConstraint(ColumnConstraintType.NOT_NULL)]),
            ColumnDefinition("post_id", BigIntType(),
                constraints=[ColumnConstraint(ColumnConstraintType.NOT_NULL)]),
            ColumnDefinition("content", TextType()),
            ColumnDefinition("is_hidden", BooleanType(),
                constraints=[ColumnConstraint(ColumnConstraintType.DEFAULT, default_value=0)]),
            ColumnDefinition("created_at", ClickHouseDateTime64Type(6)),
            ColumnDefinition("updated_at", ClickHouseDateTime64Type(6)),
        ],
        indexes=[IndexDefinition(name="idx_user_id", columns=["user_id"]),
                 IndexDefinition(name="idx_post_id", columns=["post_id"])],
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
            ColumnDefinition("id", BigIntType(),
                constraints=[ColumnConstraint(ColumnConstraintType.PRIMARY_KEY)]),
            ColumnDefinition("user_id", BigIntType(),
                constraints=[ColumnConstraint(ColumnConstraintType.NOT_NULL)]),
            ColumnDefinition("order_number", VarCharType(length=255),
                constraints=[ColumnConstraint(ColumnConstraintType.NOT_NULL)]),
            ColumnDefinition("total_amount", DecimalType(precision=10, scale=2),
                constraints=[ColumnConstraint(ColumnConstraintType.NOT_NULL),
                             ColumnConstraint(ColumnConstraintType.DEFAULT, default_value=0.0)]),
            ColumnDefinition("status", VarCharType(length=50),
                constraints=[ColumnConstraint(ColumnConstraintType.NOT_NULL),
                             ColumnConstraint(ColumnConstraintType.DEFAULT, default_value="pending")]),
            ColumnDefinition("created_at", ClickHouseDateTime64Type(6)),
            ColumnDefinition("updated_at", ClickHouseDateTime64Type(6)),
        ],
        indexes=[IndexDefinition(name="idx_user_id", columns=["user_id"])],
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
            ColumnDefinition("id", BigIntType(),
                constraints=[ColumnConstraint(ColumnConstraintType.PRIMARY_KEY)]),
            ColumnDefinition("order_id", BigIntType(),
                constraints=[ColumnConstraint(ColumnConstraintType.NOT_NULL)]),
            ColumnDefinition("product_name", VarCharType(length=255),
                constraints=[ColumnConstraint(ColumnConstraintType.NOT_NULL)]),
            ColumnDefinition("quantity", IntegerType(),
                constraints=[ColumnConstraint(ColumnConstraintType.NOT_NULL),
                             ColumnConstraint(ColumnConstraintType.DEFAULT, default_value=1)]),
            ColumnDefinition("unit_price", DecimalType(precision=10, scale=2),
                constraints=[ColumnConstraint(ColumnConstraintType.NOT_NULL)]),
            ColumnDefinition("subtotal", DecimalType(precision=10, scale=2),
                constraints=[ColumnConstraint(ColumnConstraintType.NOT_NULL),
                             ColumnConstraint(ColumnConstraintType.DEFAULT, default_value=0.0)]),
            ColumnDefinition("created_at", ClickHouseDateTime64Type(6)),
            ColumnDefinition("updated_at", ClickHouseDateTime64Type(6)),
        ],
        indexes=[IndexDefinition(name="idx_order_id", columns=["order_id"])],
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
            ColumnDefinition("id", BigIntType(),
                constraints=[ColumnConstraint(ColumnConstraintType.PRIMARY_KEY)]),
            ColumnDefinition("user_id", BigIntType(),
                constraints=[ColumnConstraint(ColumnConstraintType.NOT_NULL)]),
            ColumnDefinition("bio", TextType()),
            ColumnDefinition("avatar_url", VarCharType(length=512)),
            ColumnDefinition("created_at", ClickHouseDateTime64Type(6)),
            ColumnDefinition("updated_at", ClickHouseDateTime64Type(6)),
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
            ColumnDefinition("id", BigIntType(),
                constraints=[ColumnConstraint(ColumnConstraintType.PRIMARY_KEY)]),
            ColumnDefinition("username", VarCharType(length=255),
                constraints=[ColumnConstraint(ColumnConstraintType.NOT_NULL)]),
            ColumnDefinition("email", VarCharType(length=255),
                constraints=[ColumnConstraint(ColumnConstraintType.NOT_NULL)]),
            ColumnDefinition("age", ClickHouseNullableType(inner_type=IntegerType())),
            ColumnDefinition("created_at", ClickHouseDateTime64Type(6)),
            ColumnDefinition("updated_at", ClickHouseDateTime64Type(6)),
            ColumnDefinition("settings", JsonType()),
            ColumnDefinition("tags", JsonType()),
            ColumnDefinition("profile", JsonType()),
            ColumnDefinition("roles", JsonType()),
            ColumnDefinition("scores", JsonType()),
            ColumnDefinition("subscription", JsonType()),
            ColumnDefinition("preferences", JsonType()),
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
            ColumnDefinition("id", BigIntType(),
                constraints=[ColumnConstraint(ColumnConstraintType.PRIMARY_KEY)]),
            ColumnDefinition("name", VarCharType(length=255),
                constraints=[ColumnConstraint(ColumnConstraintType.NOT_NULL)]),
            ColumnDefinition("parent_id", BigIntType(),
                constraints=[ColumnConstraint(ColumnConstraintType.NULL)]),
            ColumnDefinition("value", DecimalType(precision=10, scale=2),
                constraints=[ColumnConstraint(ColumnConstraintType.NOT_NULL),
                             ColumnConstraint(ColumnConstraintType.DEFAULT, default_value=0.0)]),
            ColumnDefinition("created_at", ClickHouseDateTime64Type(6)),
            ColumnDefinition("updated_at", ClickHouseDateTime64Type(6)),
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
            ColumnDefinition("id", BigIntType(),
                constraints=[ColumnConstraint(ColumnConstraintType.PRIMARY_KEY)]),
            ColumnDefinition("name", VarCharType(length=255)),
            ColumnDefinition("tags", TextType()),
            ColumnDefinition("created_at", ClickHouseDateTime64Type(6)),
            ColumnDefinition("updated_at", ClickHouseDateTime64Type(6)),
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
            ColumnDefinition("id", BigIntType(),
                constraints=[ColumnConstraint(ColumnConstraintType.PRIMARY_KEY)]),
            ColumnDefinition("user_id", BigIntType(),
                constraints=[ColumnConstraint(ColumnConstraintType.NOT_NULL)]),
            ColumnDefinition("order_number", VarCharType(length=255),
                constraints=[ColumnConstraint(ColumnConstraintType.NOT_NULL)]),
            ColumnDefinition("total_amount", DecimalType(precision=10, scale=2),
                constraints=[ColumnConstraint(ColumnConstraintType.NOT_NULL),
                             ColumnConstraint(ColumnConstraintType.DEFAULT, default_value=0.0)]),
            ColumnDefinition("status", VarCharType(length=50),
                constraints=[ColumnConstraint(ColumnConstraintType.NOT_NULL),
                             ColumnConstraint(ColumnConstraintType.DEFAULT, default_value="pending")]),
            ColumnDefinition("priority", VarCharType(length=50),
                constraints=[ColumnConstraint(ColumnConstraintType.NOT_NULL),
                             ColumnConstraint(ColumnConstraintType.DEFAULT, default_value="medium")]),
            ColumnDefinition("region", VarCharType(length=50),
                constraints=[ColumnConstraint(ColumnConstraintType.NOT_NULL),
                             ColumnConstraint(ColumnConstraintType.DEFAULT, default_value="default")]),
            ColumnDefinition("category", VarCharType(length=255)),
            ColumnDefinition("product", VarCharType(length=255)),
            ColumnDefinition("department", VarCharType(length=255)),
            ColumnDefinition("year", VarCharType(length=10)),
            ColumnDefinition("quarter", VarCharType(length=10)),
            ColumnDefinition("created_at", ClickHouseDateTime64Type(6)),
            ColumnDefinition("updated_at", ClickHouseDateTime64Type(6)),
        ],
        indexes=[IndexDefinition(name="idx_user_id", columns=["user_id"]),
                 IndexDefinition(name="idx_status", columns=["status"]),
                 IndexDefinition(name="idx_priority", columns=["priority"]),
                 IndexDefinition(name="idx_region", columns=["region"])],
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
            ColumnDefinition("id", BigIntType(),
                constraints=[ColumnConstraint(ColumnConstraintType.PRIMARY_KEY)]),
            ColumnDefinition("order_id", BigIntType(),
                constraints=[ColumnConstraint(ColumnConstraintType.NOT_NULL)]),
            ColumnDefinition("product_name", VarCharType(length=255),
                constraints=[ColumnConstraint(ColumnConstraintType.NOT_NULL)]),
            ColumnDefinition("quantity", IntegerType(),
                constraints=[ColumnConstraint(ColumnConstraintType.NOT_NULL),
                             ColumnConstraint(ColumnConstraintType.DEFAULT, default_value=1)]),
            ColumnDefinition("price", DecimalType(precision=10, scale=2),
                constraints=[ColumnConstraint(ColumnConstraintType.NOT_NULL)]),
            ColumnDefinition("category", VarCharType(length=255)),
            ColumnDefinition("region", VarCharType(length=50)),
            ColumnDefinition("created_at", ClickHouseDateTime64Type(6)),
            ColumnDefinition("updated_at", ClickHouseDateTime64Type(6)),
        ],
        indexes=[IndexDefinition(name="idx_order_id", columns=["order_id"])],
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
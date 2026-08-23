# tests/providers/fixtures/basic.py
"""DDL expressions for the ``feature/basic`` table group (ClickHouse).

Each factory builds a :class:`CreateTableExpression` whose generated ClickHouse
DDL is semantically equivalent to the reference ``.sql`` schema files under
``tests/rhosocial/activerecord_clickhouse_test/feature/basic/schema/``.  Those
``.sql`` files are kept as the authoritative reference and are no longer
loaded at runtime.

ClickHouse-specific notes:
- Primary keys are plain ``Int64`` columns; ids are generated client-side by
  the backend (snowflake), so no ``AUTO_INCREMENT`` is emitted.
- ``UNIQUE`` and ``FOREIGN KEY`` constraints are not supported and are omitted.
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
    IndexDefinition,
    TableConstraint,
    TableConstraintType,
)
from rhosocial.activerecord.backend.expression.types import (
    BigIntType,
    BooleanType,
    CharType,
    DateTimeType,
    DecimalType,
    DoubleType,
    FloatType,
    IntegerType,
    JsonType,
    TextType,
    TinyIntType,
    VarCharType,
)

from rhosocial.activerecord.backend.impl.clickhouse.expression import (
    ClickHouseDateTime64Type,
    ClickHouseEnum8Type,
    ClickHouseNullableType,
    ClickHouseStringType,
)

from . import _common

# Standard ClickHouse table options.
_DEFAULT_STORAGE_OPTIONS = {
    "ENGINE": "MergeTree",
    "ORDER BY": "id",
    "SETTINGS": "enable_block_number_column = 1, enable_block_offset_column = 1",
}


def to_sql(expr: CreateTableExpression):
    """Route a CreateTableExpression through the canonical ClickHouse DDL post-processor."""
    return _common.to_clickhouse_ddl_sql(expr)


# ---------------------------------------------------------------------------
# basic/users.sql
# ---------------------------------------------------------------------------

def create_users_table(dialect, table_name: str = "users") -> CreateTableExpression:
    return CreateTableExpression(
        dialect=dialect,
        table=table_name,
        if_not_exists=False,
        columns=[
            ColumnDefinition("id", BigIntType(),
                constraints=[ColumnConstraint(ColumnConstraintType.PRIMARY_KEY)]),
            ColumnDefinition("username", VarCharType(191),
                constraints=[ColumnConstraint(ColumnConstraintType.NOT_NULL)]),
            ColumnDefinition("email", VarCharType(191),
                constraints=[ColumnConstraint(ColumnConstraintType.NOT_NULL)]),
            ColumnDefinition("age", IntegerType()),
            ColumnDefinition("balance", FloatType(),
                constraints=[ColumnConstraint(ColumnConstraintType.NOT_NULL),
                             ColumnConstraint(ColumnConstraintType.DEFAULT, default_value=0.0)]),
            ColumnDefinition("is_active", BooleanType(),
                constraints=[ColumnConstraint(ColumnConstraintType.NOT_NULL),
                             ColumnConstraint(ColumnConstraintType.DEFAULT, default_value=1)]),
            ColumnDefinition("created_at", TextType()),
            ColumnDefinition("updated_at", TextType()),
        ],
        storage_options=dict(_DEFAULT_STORAGE_OPTIONS),
    )


# ---------------------------------------------------------------------------
# basic/type_cases.sql
# ---------------------------------------------------------------------------

def create_type_cases_table(dialect, table_name: str = "type_cases") -> CreateTableExpression:
    return CreateTableExpression(
        dialect=dialect,
        table=table_name,
        if_not_exists=False,
        columns=[
            ColumnDefinition("id", CharType(36),
                constraints=[ColumnConstraint(ColumnConstraintType.NOT_NULL),
                             ColumnConstraint(ColumnConstraintType.PRIMARY_KEY)]),
            ColumnDefinition("username", TextType(),
                constraints=[ColumnConstraint(ColumnConstraintType.NOT_NULL)]),
            ColumnDefinition("email", TextType(),
                constraints=[ColumnConstraint(ColumnConstraintType.NOT_NULL)]),
            ColumnDefinition("tiny_int", TextType()),
            ColumnDefinition("small_int", TextType()),
            ColumnDefinition("big_int", TextType()),
            ColumnDefinition("float_val", TextType()),
            ColumnDefinition("double_val", TextType()),
            ColumnDefinition("decimal_val", TextType()),
            ColumnDefinition("char_val", TextType()),
            ColumnDefinition("varchar_val", TextType()),
            ColumnDefinition("text_val", TextType()),
            ColumnDefinition("date_val", TextType()),
            ColumnDefinition("time_val", TextType()),
            ColumnDefinition("timestamp_val", TextType()),
            ColumnDefinition("blob_val", TextType()),
            ColumnDefinition("json_val", TextType()),
            ColumnDefinition("array_val", TextType()),
            ColumnDefinition("is_active", TextType()),
        ],
        storage_options=dict(_DEFAULT_STORAGE_OPTIONS),
    )


# ---------------------------------------------------------------------------
# basic/type_tests.sql
# ---------------------------------------------------------------------------

def create_type_tests_table(dialect, table_name: str = "type_tests") -> CreateTableExpression:
    return CreateTableExpression(
        dialect=dialect,
        table=table_name,
        if_not_exists=False,
        columns=[
            ColumnDefinition("id", CharType(36),
                constraints=[ColumnConstraint(ColumnConstraintType.NOT_NULL),
                             ColumnConstraint(ColumnConstraintType.PRIMARY_KEY)]),
            ColumnDefinition("string_field", VarCharType(255),
                constraints=[ColumnConstraint(ColumnConstraintType.NOT_NULL),
                             ColumnConstraint(ColumnConstraintType.DEFAULT, default_value="test string")]),
            ColumnDefinition("int_field", IntegerType(),
                constraints=[ColumnConstraint(ColumnConstraintType.NOT_NULL),
                             ColumnConstraint(ColumnConstraintType.DEFAULT, default_value=42)]),
            ColumnDefinition("float_field", FloatType(),
                constraints=[ColumnConstraint(ColumnConstraintType.NOT_NULL),
                             ColumnConstraint(ColumnConstraintType.DEFAULT, default_value=3.14)]),
            ColumnDefinition("decimal_field", DoubleType(),
                constraints=[ColumnConstraint(ColumnConstraintType.NOT_NULL),
                             ColumnConstraint(ColumnConstraintType.DEFAULT, default_value=10.99)]),
            ColumnDefinition("bool_field", TinyIntType(),
                constraints=[ColumnConstraint(ColumnConstraintType.NOT_NULL),
                             ColumnConstraint(ColumnConstraintType.DEFAULT, default_value=1)]),
            ColumnDefinition("datetime_field", TextType(),
                constraints=[ColumnConstraint(ColumnConstraintType.NOT_NULL)]),
            ColumnDefinition("json_field", JsonType()),
            ColumnDefinition("nullable_field", ClickHouseNullableType(ClickHouseStringType())),
        ],
        storage_options=dict(_DEFAULT_STORAGE_OPTIONS),
    )


# ---------------------------------------------------------------------------
# basic/validated_field_users.sql
# ---------------------------------------------------------------------------

def create_validated_field_users_table(dialect, table_name: str = "validated_field_users") -> CreateTableExpression:
    # ClickHouse ENUM column for status.
    status_enum = ClickHouseEnum8Type([('active', 1), ('inactive', 2), ('banned', 3), ('pending', 4), ('suspended', 5)])
    return CreateTableExpression(
        dialect=dialect,
        table=table_name,
        if_not_exists=False,
        columns=[
            ColumnDefinition("id", BigIntType(),
                constraints=[ColumnConstraint(ColumnConstraintType.PRIMARY_KEY)]),
            ColumnDefinition("username", VarCharType(255),
                constraints=[ColumnConstraint(ColumnConstraintType.NOT_NULL)]),
            ColumnDefinition("email", VarCharType(255),
                constraints=[ColumnConstraint(ColumnConstraintType.NOT_NULL)]),
            ColumnDefinition("age", IntegerType()),
            ColumnDefinition("balance", DecimalType(precision=10, scale=2)),
            ColumnDefinition("credit_score", IntegerType(),
                constraints=[ColumnConstraint(ColumnConstraintType.NOT_NULL)]),
            ColumnDefinition("status", status_enum,
                constraints=[ColumnConstraint(ColumnConstraintType.NOT_NULL),
                             ColumnConstraint(ColumnConstraintType.DEFAULT, default_value="active")]),
            ColumnDefinition("is_active", TinyIntType(),
                constraints=[ColumnConstraint(ColumnConstraintType.NOT_NULL),
                             ColumnConstraint(ColumnConstraintType.DEFAULT, default_value=1)]),
        ],
        storage_options=dict(_DEFAULT_STORAGE_OPTIONS),
    )


# ---------------------------------------------------------------------------
# basic/validated_users.sql
# ---------------------------------------------------------------------------

def create_validated_users_table(dialect, table_name: str = "validated_users") -> CreateTableExpression:
    return CreateTableExpression(
        dialect=dialect,
        table=table_name,
        if_not_exists=False,
        columns=[
            ColumnDefinition("id", BigIntType(),
                constraints=[ColumnConstraint(ColumnConstraintType.PRIMARY_KEY)]),
            ColumnDefinition("username", VarCharType(50),
                constraints=[ColumnConstraint(ColumnConstraintType.NOT_NULL)]),
            ColumnDefinition("email", VarCharType(255),
                constraints=[ColumnConstraint(ColumnConstraintType.NOT_NULL)]),
            ColumnDefinition("age", ClickHouseNullableType(IntegerType())),
        ],
        storage_options=dict(_DEFAULT_STORAGE_OPTIONS),
    )


# ---------------------------------------------------------------------------
# basic/pydantic_validated_models.sql
# ---------------------------------------------------------------------------

def create_pydantic_validated_models_table(dialect, table_name: str = "pydantic_validated_models") -> CreateTableExpression:
    return CreateTableExpression(
        dialect=dialect,
        table=table_name,
        if_not_exists=False,
        columns=[
            ColumnDefinition("id", BigIntType(),
                constraints=[ColumnConstraint(ColumnConstraintType.PRIMARY_KEY)]),
            ColumnDefinition("code", VarCharType(32)),
            ColumnDefinition("quantity", IntegerType()),
            ColumnDefinition("step_count", IntegerType()),
            ColumnDefinition("price", DecimalType(precision=10, scale=2)),
            ColumnDefinition("start_at", ClickHouseDateTime64Type(6)),
            ColumnDefinition("end_at", ClickHouseDateTime64Type(6)),
            ColumnDefinition("status", VarCharType(32)),
            ColumnDefinition("normalized_name", VarCharType(50)),
            ColumnDefinition("created_token", VarCharType(255)),
        ],
        storage_options=dict(_DEFAULT_STORAGE_OPTIONS),
    )


# ---------------------------------------------------------------------------
# basic/bulk_users.sql
# ---------------------------------------------------------------------------

def create_bulk_users_table(dialect, table_name: str = "bulk_users") -> CreateTableExpression:
    return CreateTableExpression(
        dialect=dialect,
        table=table_name,
        if_not_exists=False,
        columns=[
            ColumnDefinition("id", BigIntType(),
                constraints=[ColumnConstraint(ColumnConstraintType.PRIMARY_KEY)]),
            ColumnDefinition("name", VarCharType(255),
                constraints=[ColumnConstraint(ColumnConstraintType.NOT_NULL)]),
            ColumnDefinition("age", IntegerType(),
                constraints=[ColumnConstraint(ColumnConstraintType.DEFAULT, default_value=0)]),
            ColumnDefinition("email", VarCharType(255),
                constraints=[ColumnConstraint(ColumnConstraintType.DEFAULT, default_value="")]),
        ],
        storage_options=dict(_DEFAULT_STORAGE_OPTIONS),
    )


# ---------------------------------------------------------------------------
# basic/posts.sql
# ---------------------------------------------------------------------------

def create_posts_table(dialect, table_name: str = "posts") -> CreateTableExpression:
    return CreateTableExpression(
        dialect=dialect,
        table=table_name,
        if_not_exists=False,
        columns=[
            ColumnDefinition("id", BigIntType(),
                constraints=[ColumnConstraint(ColumnConstraintType.PRIMARY_KEY)]),
            ColumnDefinition("author", BigIntType(),
                constraints=[ColumnConstraint(ColumnConstraintType.NOT_NULL)]),
            ColumnDefinition("title", VarCharType(255),
                constraints=[ColumnConstraint(ColumnConstraintType.NOT_NULL)]),
            ColumnDefinition("content", TextType()),
            ColumnDefinition("published_at", ClickHouseDateTime64Type(6)),
            ColumnDefinition("published", BooleanType(),
                constraints=[ColumnConstraint(ColumnConstraintType.DEFAULT, default_value=0)]),
            ColumnDefinition("created_at", ClickHouseDateTime64Type(6)),
            ColumnDefinition("updated_at", ClickHouseDateTime64Type(6)),
        ],
        indexes=[IndexDefinition(name="idx_author", columns=["author"])],
        storage_options=dict(_DEFAULT_STORAGE_OPTIONS),
    )


# ---------------------------------------------------------------------------
# basic/comments.sql
# ---------------------------------------------------------------------------

def create_comments_table(dialect, table_name: str = "comments") -> CreateTableExpression:
    return CreateTableExpression(
        dialect=dialect,
        table=table_name,
        if_not_exists=False,
        columns=[
            ColumnDefinition("id", BigIntType(),
                constraints=[ColumnConstraint(ColumnConstraintType.PRIMARY_KEY)]),
            ColumnDefinition("post_ref", BigIntType(),
                constraints=[ColumnConstraint(ColumnConstraintType.NOT_NULL)]),
            ColumnDefinition("author", BigIntType(),
                constraints=[ColumnConstraint(ColumnConstraintType.NOT_NULL)]),
            ColumnDefinition("text", TextType(),
                constraints=[ColumnConstraint(ColumnConstraintType.NOT_NULL)]),
            ColumnDefinition("created_at", ClickHouseDateTime64Type(6),
                constraints=[ColumnConstraint(ColumnConstraintType.NOT_NULL)]),
            ColumnDefinition("updated_at", ClickHouseDateTime64Type(6)),
            ColumnDefinition("approved", BooleanType(),
                constraints=[ColumnConstraint(ColumnConstraintType.DEFAULT, default_value=0)]),
        ],
        indexes=[
            IndexDefinition(name="idx_post_ref", columns=["post_ref"]),
            IndexDefinition(name="idx_author", columns=["author"]),
        ],
        storage_options=dict(_DEFAULT_STORAGE_OPTIONS),
    )


# ---------------------------------------------------------------------------
# basic/column_mapping_items.sql
# ---------------------------------------------------------------------------

def create_column_mapping_items_table(dialect, table_name: str = "column_mapping_items") -> CreateTableExpression:
    return CreateTableExpression(
        dialect=dialect,
        table=table_name,
        if_not_exists=False,
        columns=[
            ColumnDefinition("id", BigIntType(),
                constraints=[ColumnConstraint(ColumnConstraintType.PRIMARY_KEY)]),
            ColumnDefinition("name", VarCharType(255),
                constraints=[ColumnConstraint(ColumnConstraintType.NOT_NULL)]),
            ColumnDefinition("item_total", IntegerType(),
                constraints=[ColumnConstraint(ColumnConstraintType.NOT_NULL)]),
            ColumnDefinition("remarks", IntegerType()),
        ],
        storage_options=dict(_DEFAULT_STORAGE_OPTIONS),
    )


# ---------------------------------------------------------------------------
# basic/mixed_annotation_items.sql
# ---------------------------------------------------------------------------

def create_mixed_annotation_items_table(dialect, table_name: str = "mixed_annotation_items") -> CreateTableExpression:
    return CreateTableExpression(
        dialect=dialect,
        table=table_name,
        if_not_exists=False,
        columns=[
            ColumnDefinition("id", BigIntType(),
                constraints=[ColumnConstraint(ColumnConstraintType.PRIMARY_KEY)]),
            ColumnDefinition("name", VarCharType(255),
                constraints=[ColumnConstraint(ColumnConstraintType.NOT_NULL)]),
            ColumnDefinition("tags", TextType()),
            ColumnDefinition("meta", TextType()),
            ColumnDefinition("description", TextType()),
            ColumnDefinition("status", TextType()),
        ],
        storage_options=dict(_DEFAULT_STORAGE_OPTIONS),
    )


# ---------------------------------------------------------------------------
# basic/type_adapter_tests.sql  (no ENGINE/CHARSET in reference file)
# ---------------------------------------------------------------------------

def create_type_adapter_tests_table(dialect, table_name: str = "type_adapter_tests") -> CreateTableExpression:
    return CreateTableExpression(
        dialect=dialect,
        table=table_name,
        if_not_exists=True,
        columns=[
            ColumnDefinition("id", BigIntType(),
                constraints=[ColumnConstraint(ColumnConstraintType.PRIMARY_KEY)]),
            ColumnDefinition("name", VarCharType(255),
                constraints=[ColumnConstraint(ColumnConstraintType.NOT_NULL)]),
            # Optional[T] model fields must map to Nullable columns so that None
            # is stored/returned as SQL NULL instead of ClickHouse's empty string.
            ColumnDefinition("optional_name", ClickHouseNullableType(VarCharType(255))),
            ColumnDefinition("optional_age", ClickHouseNullableType(IntegerType())),
            ColumnDefinition("last_login", ClickHouseNullableType(TextType())),
            ColumnDefinition("is_premium", ClickHouseNullableType(BooleanType())),
            ColumnDefinition("unsupported_union", VarCharType(255)),
            ColumnDefinition("custom_bool", VarCharType(3)),
            ColumnDefinition("optional_custom_bool", ClickHouseNullableType(VarCharType(3))),
        ],
        storage_options=dict(_DEFAULT_STORAGE_OPTIONS),
    )


# ---------------------------------------------------------------------------
# basic/order_items.sql (composite PK)
# ---------------------------------------------------------------------------

def create_composite_pk_order_items_table(dialect, table_name: str = "order_items") -> CreateTableExpression:
    return CreateTableExpression(
        dialect=dialect,
        table=table_name,
        if_not_exists=False,
        columns=[
            ColumnDefinition("order_id", IntegerType(),
                constraints=[ColumnConstraint(ColumnConstraintType.NOT_NULL)]),
            ColumnDefinition("product_id", IntegerType(),
                constraints=[ColumnConstraint(ColumnConstraintType.NOT_NULL)]),
            ColumnDefinition("quantity", IntegerType(),
                constraints=[ColumnConstraint(ColumnConstraintType.NOT_NULL),
                             ColumnConstraint(ColumnConstraintType.DEFAULT, default_value=1)]),
            ColumnDefinition("unit_price", DecimalType(precision=10, scale=2),
                constraints=[ColumnConstraint(ColumnConstraintType.NOT_NULL)]),
        ],
        table_constraints=[
            TableConstraint(constraint_type=TableConstraintType.PRIMARY_KEY,
                columns=["order_id", "product_id"]),
        ],
        storage_options={
            "ENGINE": "MergeTree",
            "ORDER BY": ("order_id", "product_id"),
            "SETTINGS": "enable_block_number_column = 1, enable_block_offset_column = 1",
        },
    )


# ---------------------------------------------------------------------------
# basic/store_inventory.sql (composite PK, no FK)
# ---------------------------------------------------------------------------

def create_store_inventory_table(dialect, table_name: str = "store_inventory") -> CreateTableExpression:
    return CreateTableExpression(
        dialect=dialect,
        table=table_name,
        if_not_exists=False,
        columns=[
            ColumnDefinition("store_id", IntegerType(),
                constraints=[ColumnConstraint(ColumnConstraintType.NOT_NULL)]),
            ColumnDefinition("product_id", IntegerType(),
                constraints=[ColumnConstraint(ColumnConstraintType.NOT_NULL)]),
            ColumnDefinition("batch_id", VarCharType(64),
                constraints=[ColumnConstraint(ColumnConstraintType.NOT_NULL)]),
            ColumnDefinition("stock", IntegerType(),
                constraints=[ColumnConstraint(ColumnConstraintType.NOT_NULL),
                             ColumnConstraint(ColumnConstraintType.DEFAULT, default_value=0)]),
        ],
        table_constraints=[
            TableConstraint(constraint_type=TableConstraintType.PRIMARY_KEY,
                columns=["store_id", "product_id", "batch_id"]),
        ],
        storage_options={
            "ENGINE": "MergeTree",
            "ORDER BY": ("store_id", "product_id", "batch_id"),
            "SETTINGS": "enable_block_number_column = 1, enable_block_offset_column = 1",
        },
    )


# ---------------------------------------------------------------------------
# basic/orders.sql (single PK, no FK in composite-PK scenario)
# ---------------------------------------------------------------------------

def create_orders_table(dialect, table_name: str = "orders") -> CreateTableExpression:
    return CreateTableExpression(
        dialect=dialect,
        table=table_name,
        if_not_exists=False,
        columns=[
            ColumnDefinition("id", BigIntType(),
                constraints=[ColumnConstraint(ColumnConstraintType.PRIMARY_KEY)]),
            ColumnDefinition("total", DecimalType(precision=10, scale=2),
                constraints=[ColumnConstraint(ColumnConstraintType.NOT_NULL)]),
            ColumnDefinition("created_at", TextType()),
            ColumnDefinition("updated_at", TextType()),
        ],
        storage_options=dict(_DEFAULT_STORAGE_OPTIONS),
    )


# ---------------------------------------------------------------------------
# basic/product.sql (single PK)
# ---------------------------------------------------------------------------

def create_product_table(dialect, table_name: str = "product") -> CreateTableExpression:
    return CreateTableExpression(
        dialect=dialect,
        table=table_name,
        if_not_exists=True,
        columns=[
            ColumnDefinition("id", BigIntType(),
                constraints=[ColumnConstraint(ColumnConstraintType.PRIMARY_KEY)]),
            ColumnDefinition("name", TextType(),
                constraints=[ColumnConstraint(ColumnConstraintType.NOT_NULL)]),
            ColumnDefinition("price", FloatType(),
                constraints=[ColumnConstraint(ColumnConstraintType.NOT_NULL)]),
            ColumnDefinition("quantity", IntegerType(),
                constraints=[ColumnConstraint(ColumnConstraintType.NOT_NULL)]),
        ],
        storage_options=dict(_DEFAULT_STORAGE_OPTIONS),
    )


TABLE_EXPRESSIONS: Dict[str, Callable] = {
    "users": create_users_table,
    "type_cases": create_type_cases_table,
    "type_tests": create_type_tests_table,
    "validated_field_users": create_validated_field_users_table,
    "validated_users": create_validated_users_table,
    "pydantic_validated_models": create_pydantic_validated_models_table,
    "bulk_users": create_bulk_users_table,
    "posts": create_posts_table,
    "comments": create_comments_table,
    "column_mapping_items": create_column_mapping_items_table,
    "mixed_annotation_items": create_mixed_annotation_items_table,
    "type_adapter_tests": create_type_adapter_tests_table,
    "order_items": create_composite_pk_order_items_table,
    "store_inventory": create_store_inventory_table,
    "orders": create_orders_table,
    "product": create_product_table,
}

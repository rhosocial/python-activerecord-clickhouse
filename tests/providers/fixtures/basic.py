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
            ColumnDefinition(dialect, "id", BigIntType(dialect),
                constraints=[ColumnConstraint(dialect, ColumnConstraintType.PRIMARY_KEY)]),
            ColumnDefinition(dialect, "username", VarCharType(dialect, length=191),
                constraints=[ColumnConstraint(dialect, ColumnConstraintType.NOT_NULL)]),
            ColumnDefinition(dialect, "email", VarCharType(dialect, length=191),
                constraints=[ColumnConstraint(dialect, ColumnConstraintType.NOT_NULL)]),
            ColumnDefinition(dialect, "age", IntegerType(dialect)),
            ColumnDefinition(dialect, "balance", FloatType(dialect),
                constraints=[ColumnConstraint(dialect, ColumnConstraintType.NOT_NULL),
                             ColumnConstraint(dialect, ColumnConstraintType.DEFAULT, default_value=0.0)]),
            ColumnDefinition(dialect, "is_active", BooleanType(dialect),
                constraints=[ColumnConstraint(dialect, ColumnConstraintType.NOT_NULL),
                             ColumnConstraint(dialect, ColumnConstraintType.DEFAULT, default_value=1)]),
            ColumnDefinition(dialect, "created_at", TextType(dialect)),
            ColumnDefinition(dialect, "updated_at", TextType(dialect)),
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
            ColumnDefinition(dialect, "id", CharType(dialect, length=36),
                constraints=[ColumnConstraint(dialect, ColumnConstraintType.NOT_NULL),
                             ColumnConstraint(dialect, ColumnConstraintType.PRIMARY_KEY)]),
            ColumnDefinition(dialect, "username", TextType(dialect),
                constraints=[ColumnConstraint(dialect, ColumnConstraintType.NOT_NULL)]),
            ColumnDefinition(dialect, "email", TextType(dialect),
                constraints=[ColumnConstraint(dialect, ColumnConstraintType.NOT_NULL)]),
            ColumnDefinition(dialect, "tiny_int", TextType(dialect)),
            ColumnDefinition(dialect, "small_int", TextType(dialect)),
            ColumnDefinition(dialect, "big_int", TextType(dialect)),
            ColumnDefinition(dialect, "float_val", TextType(dialect)),
            ColumnDefinition(dialect, "double_val", TextType(dialect)),
            ColumnDefinition(dialect, "decimal_val", TextType(dialect)),
            ColumnDefinition(dialect, "char_val", TextType(dialect)),
            ColumnDefinition(dialect, "varchar_val", TextType(dialect)),
            ColumnDefinition(dialect, "text_val", TextType(dialect)),
            ColumnDefinition(dialect, "date_val", TextType(dialect)),
            ColumnDefinition(dialect, "time_val", TextType(dialect)),
            ColumnDefinition(dialect, "timestamp_val", TextType(dialect)),
            ColumnDefinition(dialect, "blob_val", TextType(dialect)),
            ColumnDefinition(dialect, "json_val", TextType(dialect)),
            ColumnDefinition(dialect, "array_val", TextType(dialect)),
            ColumnDefinition(dialect, "is_active", TextType(dialect)),
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
            ColumnDefinition(dialect, "id", CharType(dialect, length=36),
                constraints=[ColumnConstraint(dialect, ColumnConstraintType.NOT_NULL),
                             ColumnConstraint(dialect, ColumnConstraintType.PRIMARY_KEY)]),
            ColumnDefinition(dialect, "string_field", VarCharType(dialect, length=255),
                constraints=[ColumnConstraint(dialect, ColumnConstraintType.NOT_NULL),
                             ColumnConstraint(dialect, ColumnConstraintType.DEFAULT, default_value="test string")]),
            ColumnDefinition(dialect, "int_field", IntegerType(dialect),
                constraints=[ColumnConstraint(dialect, ColumnConstraintType.NOT_NULL),
                             ColumnConstraint(dialect, ColumnConstraintType.DEFAULT, default_value=42)]),
            ColumnDefinition(dialect, "float_field", FloatType(dialect),
                constraints=[ColumnConstraint(dialect, ColumnConstraintType.NOT_NULL),
                             ColumnConstraint(dialect, ColumnConstraintType.DEFAULT, default_value=3.14)]),
            ColumnDefinition(dialect, "decimal_field", DoubleType(dialect),
                constraints=[ColumnConstraint(dialect, ColumnConstraintType.NOT_NULL),
                             ColumnConstraint(dialect, ColumnConstraintType.DEFAULT, default_value=10.99)]),
            ColumnDefinition(dialect, "bool_field", TinyIntType(dialect),
                constraints=[ColumnConstraint(dialect, ColumnConstraintType.NOT_NULL),
                             ColumnConstraint(dialect, ColumnConstraintType.DEFAULT, default_value=1)]),
            ColumnDefinition(dialect, "datetime_field", TextType(dialect),
                constraints=[ColumnConstraint(dialect, ColumnConstraintType.NOT_NULL)]),
            ColumnDefinition(dialect, "json_field", JsonType(dialect)),
            ColumnDefinition(dialect, "nullable_field", ClickHouseNullableType(dialect, inner_type=ClickHouseStringType(dialect))),
        ],
        storage_options=dict(_DEFAULT_STORAGE_OPTIONS),
    )


# ---------------------------------------------------------------------------
# basic/validated_field_users.sql
# ---------------------------------------------------------------------------

def create_validated_field_users_table(dialect, table_name: str = "validated_field_users") -> CreateTableExpression:
    # ClickHouse ENUM column for status.
    status_enum = ClickHouseEnum8Type(dialect, values=[('active', 1), ('inactive', 2), ('banned', 3), ('pending', 4), ('suspended', 5)])
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
            ColumnDefinition(dialect, "age", IntegerType(dialect)),
            ColumnDefinition(dialect, "balance", DecimalType(dialect, precision=10, scale=2)),
            ColumnDefinition(dialect, "credit_score", IntegerType(dialect),
                constraints=[ColumnConstraint(dialect, ColumnConstraintType.NOT_NULL)]),
            ColumnDefinition(dialect, "status", status_enum,
                constraints=[ColumnConstraint(dialect, ColumnConstraintType.NOT_NULL),
                             ColumnConstraint(dialect, ColumnConstraintType.DEFAULT, default_value="active")]),
            ColumnDefinition(dialect, "is_active", TinyIntType(dialect),
                constraints=[ColumnConstraint(dialect, ColumnConstraintType.NOT_NULL),
                             ColumnConstraint(dialect, ColumnConstraintType.DEFAULT, default_value=1)]),
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
            ColumnDefinition(dialect, "id", BigIntType(dialect),
                constraints=[ColumnConstraint(dialect, ColumnConstraintType.PRIMARY_KEY)]),
            ColumnDefinition(dialect, "username", VarCharType(dialect, length=50),
                constraints=[ColumnConstraint(dialect, ColumnConstraintType.NOT_NULL)]),
            ColumnDefinition(dialect, "email", VarCharType(dialect, length=255),
                constraints=[ColumnConstraint(dialect, ColumnConstraintType.NOT_NULL)]),
            ColumnDefinition(dialect, "age", ClickHouseNullableType(dialect, inner_type=IntegerType(dialect))),
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
            ColumnDefinition(dialect, "id", BigIntType(dialect),
                constraints=[ColumnConstraint(dialect, ColumnConstraintType.PRIMARY_KEY)]),
            ColumnDefinition(dialect, "code", VarCharType(dialect, length=32)),
            ColumnDefinition(dialect, "quantity", IntegerType(dialect)),
            ColumnDefinition(dialect, "step_count", IntegerType(dialect)),
            ColumnDefinition(dialect, "price", DecimalType(dialect, precision=10, scale=2)),
            ColumnDefinition(dialect, "start_at", ClickHouseDateTime64Type(dialect, precision=6)),
            ColumnDefinition(dialect, "end_at", ClickHouseDateTime64Type(dialect, precision=6)),
            ColumnDefinition(dialect, "status", VarCharType(dialect, length=32)),
            ColumnDefinition(dialect, "normalized_name", VarCharType(dialect, length=50)),
            ColumnDefinition(dialect, "created_token", VarCharType(dialect, length=255)),
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
            ColumnDefinition(dialect, "id", BigIntType(dialect),
                constraints=[ColumnConstraint(dialect, ColumnConstraintType.PRIMARY_KEY)]),
            ColumnDefinition(dialect, "name", VarCharType(dialect, length=255),
                constraints=[ColumnConstraint(dialect, ColumnConstraintType.NOT_NULL)]),
            ColumnDefinition(dialect, "age", IntegerType(dialect),
                constraints=[ColumnConstraint(dialect, ColumnConstraintType.DEFAULT, default_value=0)]),
            ColumnDefinition(dialect, "email", VarCharType(dialect, length=255),
                constraints=[ColumnConstraint(dialect, ColumnConstraintType.DEFAULT, default_value="")]),
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
            ColumnDefinition(dialect, "id", BigIntType(dialect),
                constraints=[ColumnConstraint(dialect, ColumnConstraintType.PRIMARY_KEY)]),
            ColumnDefinition(dialect, "author", BigIntType(dialect),
                constraints=[ColumnConstraint(dialect, ColumnConstraintType.NOT_NULL)]),
            ColumnDefinition(dialect, "title", VarCharType(dialect, length=255),
                constraints=[ColumnConstraint(dialect, ColumnConstraintType.NOT_NULL)]),
            ColumnDefinition(dialect, "content", TextType(dialect)),
            ColumnDefinition(dialect, "published_at", ClickHouseDateTime64Type(dialect, precision=6)),
            ColumnDefinition(dialect, "published", BooleanType(dialect),
                constraints=[ColumnConstraint(dialect, ColumnConstraintType.DEFAULT, default_value=0)]),
            ColumnDefinition(dialect, "created_at", ClickHouseDateTime64Type(dialect, precision=6)),
            ColumnDefinition(dialect, "updated_at", ClickHouseDateTime64Type(dialect, precision=6)),
        ],
        indexes=[IndexDefinition(dialect, name="idx_author", columns=["author"])],
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
            ColumnDefinition(dialect, "id", BigIntType(dialect),
                constraints=[ColumnConstraint(dialect, ColumnConstraintType.PRIMARY_KEY)]),
            ColumnDefinition(dialect, "post_ref", BigIntType(dialect),
                constraints=[ColumnConstraint(dialect, ColumnConstraintType.NOT_NULL)]),
            ColumnDefinition(dialect, "author", BigIntType(dialect),
                constraints=[ColumnConstraint(dialect, ColumnConstraintType.NOT_NULL)]),
            ColumnDefinition(dialect, "text", TextType(dialect),
                constraints=[ColumnConstraint(dialect, ColumnConstraintType.NOT_NULL)]),
            ColumnDefinition(dialect, "created_at", ClickHouseDateTime64Type(dialect, precision=6),
                constraints=[ColumnConstraint(dialect, ColumnConstraintType.NOT_NULL)]),
            ColumnDefinition(dialect, "updated_at", ClickHouseDateTime64Type(dialect, precision=6)),
            ColumnDefinition(dialect, "approved", BooleanType(dialect),
                constraints=[ColumnConstraint(dialect, ColumnConstraintType.DEFAULT, default_value=0)]),
        ],
        indexes=[
            IndexDefinition(dialect, name="idx_post_ref", columns=["post_ref"]),
            IndexDefinition(dialect, name="idx_author", columns=["author"]),
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
            ColumnDefinition(dialect, "id", BigIntType(dialect),
                constraints=[ColumnConstraint(dialect, ColumnConstraintType.PRIMARY_KEY)]),
            ColumnDefinition(dialect, "name", VarCharType(dialect, length=255),
                constraints=[ColumnConstraint(dialect, ColumnConstraintType.NOT_NULL)]),
            ColumnDefinition(dialect, "item_total", IntegerType(dialect),
                constraints=[ColumnConstraint(dialect, ColumnConstraintType.NOT_NULL)]),
            ColumnDefinition(dialect, "remarks", IntegerType(dialect)),
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
            ColumnDefinition(dialect, "id", BigIntType(dialect),
                constraints=[ColumnConstraint(dialect, ColumnConstraintType.PRIMARY_KEY)]),
            ColumnDefinition(dialect, "name", VarCharType(dialect, length=255),
                constraints=[ColumnConstraint(dialect, ColumnConstraintType.NOT_NULL)]),
            ColumnDefinition(dialect, "tags", TextType(dialect)),
            ColumnDefinition(dialect, "meta", TextType(dialect)),
            ColumnDefinition(dialect, "description", TextType(dialect)),
            ColumnDefinition(dialect, "status", TextType(dialect)),
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
            ColumnDefinition(dialect, "id", BigIntType(dialect),
                constraints=[ColumnConstraint(dialect, ColumnConstraintType.PRIMARY_KEY)]),
            ColumnDefinition(dialect, "name", VarCharType(dialect, length=255),
                constraints=[ColumnConstraint(dialect, ColumnConstraintType.NOT_NULL)]),
            # Optional[T] model fields must map to Nullable columns so that None
            # is stored/returned as SQL NULL instead of ClickHouse's empty string.
            ColumnDefinition(dialect, "optional_name", ClickHouseNullableType(dialect, inner_type=VarCharType(dialect, length=255))),
            ColumnDefinition(dialect, "optional_age", ClickHouseNullableType(dialect, inner_type=IntegerType(dialect))),
            ColumnDefinition(dialect, "last_login", ClickHouseNullableType(dialect, inner_type=TextType(dialect))),
            ColumnDefinition(dialect, "is_premium", ClickHouseNullableType(dialect, inner_type=BooleanType(dialect))),
            ColumnDefinition(dialect, "unsupported_union", VarCharType(dialect, length=255)),
            ColumnDefinition(dialect, "custom_bool", VarCharType(dialect, length=3)),
            ColumnDefinition(dialect, "optional_custom_bool", ClickHouseNullableType(dialect, inner_type=VarCharType(dialect, length=3))),
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
            ColumnDefinition(dialect, "order_id", IntegerType(dialect),
                constraints=[ColumnConstraint(dialect, ColumnConstraintType.NOT_NULL)]),
            ColumnDefinition(dialect, "product_id", IntegerType(dialect),
                constraints=[ColumnConstraint(dialect, ColumnConstraintType.NOT_NULL)]),
            ColumnDefinition(dialect, "quantity", IntegerType(dialect),
                constraints=[ColumnConstraint(dialect, ColumnConstraintType.NOT_NULL),
                             ColumnConstraint(dialect, ColumnConstraintType.DEFAULT, default_value=1)]),
            ColumnDefinition(dialect, "unit_price", DecimalType(dialect, precision=10, scale=2),
                constraints=[ColumnConstraint(dialect, ColumnConstraintType.NOT_NULL)]),
        ],
        table_constraints=[
            TableConstraint(dialect, constraint_type=TableConstraintType.PRIMARY_KEY,
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
            ColumnDefinition(dialect, "store_id", IntegerType(dialect),
                constraints=[ColumnConstraint(dialect, ColumnConstraintType.NOT_NULL)]),
            ColumnDefinition(dialect, "product_id", IntegerType(dialect),
                constraints=[ColumnConstraint(dialect, ColumnConstraintType.NOT_NULL)]),
            ColumnDefinition(dialect, "batch_id", VarCharType(dialect, length=64),
                constraints=[ColumnConstraint(dialect, ColumnConstraintType.NOT_NULL)]),
            ColumnDefinition(dialect, "stock", IntegerType(dialect),
                constraints=[ColumnConstraint(dialect, ColumnConstraintType.NOT_NULL),
                             ColumnConstraint(dialect, ColumnConstraintType.DEFAULT, default_value=0)]),
        ],
        table_constraints=[
            TableConstraint(dialect, constraint_type=TableConstraintType.PRIMARY_KEY,
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
            ColumnDefinition(dialect, "id", BigIntType(dialect),
                constraints=[ColumnConstraint(dialect, ColumnConstraintType.PRIMARY_KEY)]),
            ColumnDefinition(dialect, "total", DecimalType(dialect, precision=10, scale=2),
                constraints=[ColumnConstraint(dialect, ColumnConstraintType.NOT_NULL)]),
            ColumnDefinition(dialect, "created_at", TextType(dialect)),
            ColumnDefinition(dialect, "updated_at", TextType(dialect)),
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
            ColumnDefinition(dialect, "id", BigIntType(dialect),
                constraints=[ColumnConstraint(dialect, ColumnConstraintType.PRIMARY_KEY)]),
            ColumnDefinition(dialect, "name", TextType(dialect),
                constraints=[ColumnConstraint(dialect, ColumnConstraintType.NOT_NULL)]),
            ColumnDefinition(dialect, "price", FloatType(dialect),
                constraints=[ColumnConstraint(dialect, ColumnConstraintType.NOT_NULL)]),
            ColumnDefinition(dialect, "quantity", IntegerType(dialect),
                constraints=[ColumnConstraint(dialect, ColumnConstraintType.NOT_NULL)]),
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

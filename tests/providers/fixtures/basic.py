# tests/providers/fixtures/basic.py
"""DDL expressions for the ``feature/basic`` table group (ClickHouse).

Each factory builds a :class:`CreateTableStatement` whose generated ClickHouse
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
    CreateTableStatement,
)
from rhosocial.activerecord.backend.expression.objects import Table
from rhosocial.activerecord.backend.expression.statements import (
    ColumnDefinition,
    ColumnConstraint,
    ColumnPrimaryKeyConstraint, ColumnNotNullConstraint, ColumnDefaultConstraint,
    IndexDefinition,
    TableConstraint,
    TablePrimaryKeyConstraint,
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


def to_sql(expr: CreateTableStatement):
    """Route a CreateTableStatement through the canonical ClickHouse DDL post-processor."""
    return _common.to_clickhouse_ddl_sql(expr)


# ---------------------------------------------------------------------------
# basic/users.sql
# ---------------------------------------------------------------------------

def create_users_table(dialect, table_name: str = "users") -> CreateTableStatement:
    return CreateTableStatement(
        dialect=dialect,
        table=Table(dialect, table_name),
        if_not_exists=False,
        columns=[
            ColumnDefinition(dialect, "id", BigIntType(dialect),
                constraints=[ColumnConstraint(dialect, branch=ColumnPrimaryKeyConstraint(dialect))]),
            ColumnDefinition(dialect, "username", VarCharType(dialect, length=191),
                constraints=[ColumnConstraint(dialect, branch=ColumnNotNullConstraint(dialect))]),
            ColumnDefinition(dialect, "email", VarCharType(dialect, length=191),
                constraints=[ColumnConstraint(dialect, branch=ColumnNotNullConstraint(dialect))]),
            ColumnDefinition(dialect, "age", IntegerType(dialect)),
            ColumnDefinition(dialect, "balance", FloatType(dialect),
                constraints=[ColumnConstraint(dialect, branch=ColumnNotNullConstraint(dialect)),
                             ColumnConstraint(dialect, branch=ColumnDefaultConstraint(dialect, 0.0))]),
            ColumnDefinition(dialect, "is_active", BooleanType(dialect),
                constraints=[ColumnConstraint(dialect, branch=ColumnNotNullConstraint(dialect)),
                             ColumnConstraint(dialect, branch=ColumnDefaultConstraint(dialect, 1))]),
            ColumnDefinition(dialect, "created_at", TextType(dialect)),
            ColumnDefinition(dialect, "updated_at", TextType(dialect)),
        ],
        table_options=_common.default_table_options(dialect),
    )


# ---------------------------------------------------------------------------
# basic/type_cases.sql
# ---------------------------------------------------------------------------

def create_type_cases_table(dialect, table_name: str = "type_cases") -> CreateTableStatement:
    return CreateTableStatement(
        dialect=dialect,
        table=Table(dialect, table_name),
        if_not_exists=False,
        columns=[
            ColumnDefinition(dialect, "id", CharType(dialect, length=36),
                constraints=[ColumnConstraint(dialect, branch=ColumnNotNullConstraint(dialect)),
                             ColumnConstraint(dialect, branch=ColumnPrimaryKeyConstraint(dialect))]),
            ColumnDefinition(dialect, "username", TextType(dialect),
                constraints=[ColumnConstraint(dialect, branch=ColumnNotNullConstraint(dialect))]),
            ColumnDefinition(dialect, "email", TextType(dialect),
                constraints=[ColumnConstraint(dialect, branch=ColumnNotNullConstraint(dialect))]),
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
        table_options=_common.default_table_options(dialect),
    )


# ---------------------------------------------------------------------------
# basic/type_tests.sql
# ---------------------------------------------------------------------------

def create_type_tests_table(dialect, table_name: str = "type_tests") -> CreateTableStatement:
    return CreateTableStatement(
        dialect=dialect,
        table=Table(dialect, table_name),
        if_not_exists=False,
        columns=[
            ColumnDefinition(dialect, "id", CharType(dialect, length=36),
                constraints=[ColumnConstraint(dialect, branch=ColumnNotNullConstraint(dialect)),
                             ColumnConstraint(dialect, branch=ColumnPrimaryKeyConstraint(dialect))]),
            ColumnDefinition(dialect, "string_field", VarCharType(dialect, length=255),
                constraints=[ColumnConstraint(dialect, branch=ColumnNotNullConstraint(dialect)),
                             ColumnConstraint(dialect, branch=ColumnDefaultConstraint(dialect, "test string"))]),
            ColumnDefinition(dialect, "int_field", IntegerType(dialect),
                constraints=[ColumnConstraint(dialect, branch=ColumnNotNullConstraint(dialect)),
                             ColumnConstraint(dialect, branch=ColumnDefaultConstraint(dialect, 42))]),
            ColumnDefinition(dialect, "float_field", FloatType(dialect),
                constraints=[ColumnConstraint(dialect, branch=ColumnNotNullConstraint(dialect)),
                             ColumnConstraint(dialect, branch=ColumnDefaultConstraint(dialect, 3.14))]),
            ColumnDefinition(dialect, "decimal_field", DoubleType(dialect),
                constraints=[ColumnConstraint(dialect, branch=ColumnNotNullConstraint(dialect)),
                             ColumnConstraint(dialect, branch=ColumnDefaultConstraint(dialect, 10.99))]),
            ColumnDefinition(dialect, "bool_field", TinyIntType(dialect),
                constraints=[ColumnConstraint(dialect, branch=ColumnNotNullConstraint(dialect)),
                             ColumnConstraint(dialect, branch=ColumnDefaultConstraint(dialect, 1))]),
            ColumnDefinition(dialect, "datetime_field", TextType(dialect),
                constraints=[ColumnConstraint(dialect, branch=ColumnNotNullConstraint(dialect))]),
            ColumnDefinition(dialect, "json_field", JsonType(dialect)),
            ColumnDefinition(dialect, "nullable_field", ClickHouseNullableType(dialect, inner_type=ClickHouseStringType(dialect))),
        ],
        table_options=_common.default_table_options(dialect),
    )


# ---------------------------------------------------------------------------
# basic/validated_field_users.sql
# ---------------------------------------------------------------------------

def create_validated_field_users_table(dialect, table_name: str = "validated_field_users") -> CreateTableStatement:
    # ClickHouse ENUM column for status.
    status_enum = ClickHouseEnum8Type(dialect, values=[('active', 1), ('inactive', 2), ('banned', 3), ('pending', 4), ('suspended', 5)])
    return CreateTableStatement(
        dialect=dialect,
        table=Table(dialect, table_name),
        if_not_exists=False,
        columns=[
            ColumnDefinition(dialect, "id", BigIntType(dialect),
                constraints=[ColumnConstraint(dialect, branch=ColumnPrimaryKeyConstraint(dialect))]),
            ColumnDefinition(dialect, "username", VarCharType(dialect, length=255),
                constraints=[ColumnConstraint(dialect, branch=ColumnNotNullConstraint(dialect))]),
            ColumnDefinition(dialect, "email", VarCharType(dialect, length=255),
                constraints=[ColumnConstraint(dialect, branch=ColumnNotNullConstraint(dialect))]),
            ColumnDefinition(dialect, "age", IntegerType(dialect)),
            ColumnDefinition(dialect, "balance", DecimalType(dialect, precision=10, scale=2)),
            ColumnDefinition(dialect, "credit_score", IntegerType(dialect),
                constraints=[ColumnConstraint(dialect, branch=ColumnNotNullConstraint(dialect))]),
            ColumnDefinition(dialect, "status", status_enum,
                constraints=[ColumnConstraint(dialect, branch=ColumnNotNullConstraint(dialect)),
                             ColumnConstraint(dialect, branch=ColumnDefaultConstraint(dialect, "active"))]),
            ColumnDefinition(dialect, "is_active", TinyIntType(dialect),
                constraints=[ColumnConstraint(dialect, branch=ColumnNotNullConstraint(dialect)),
                             ColumnConstraint(dialect, branch=ColumnDefaultConstraint(dialect, 1))]),
        ],
        table_options=_common.default_table_options(dialect),
    )


# ---------------------------------------------------------------------------
# basic/validated_users.sql
# ---------------------------------------------------------------------------

def create_validated_users_table(dialect, table_name: str = "validated_users") -> CreateTableStatement:
    return CreateTableStatement(
        dialect=dialect,
        table=Table(dialect, table_name),
        if_not_exists=False,
        columns=[
            ColumnDefinition(dialect, "id", BigIntType(dialect),
                constraints=[ColumnConstraint(dialect, branch=ColumnPrimaryKeyConstraint(dialect))]),
            ColumnDefinition(dialect, "username", VarCharType(dialect, length=50),
                constraints=[ColumnConstraint(dialect, branch=ColumnNotNullConstraint(dialect))]),
            ColumnDefinition(dialect, "email", VarCharType(dialect, length=255),
                constraints=[ColumnConstraint(dialect, branch=ColumnNotNullConstraint(dialect))]),
            ColumnDefinition(dialect, "age", ClickHouseNullableType(dialect, inner_type=IntegerType(dialect))),
        ],
        table_options=_common.default_table_options(dialect),
    )


# ---------------------------------------------------------------------------
# basic/pydantic_validated_models.sql
# ---------------------------------------------------------------------------

def create_pydantic_validated_models_table(dialect, table_name: str = "pydantic_validated_models") -> CreateTableStatement:
    return CreateTableStatement(
        dialect=dialect,
        table=Table(dialect, table_name),
        if_not_exists=False,
        columns=[
            ColumnDefinition(dialect, "id", BigIntType(dialect),
                constraints=[ColumnConstraint(dialect, branch=ColumnPrimaryKeyConstraint(dialect))]),
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
        table_options=_common.default_table_options(dialect),
    )


# ---------------------------------------------------------------------------
# basic/bulk_users.sql
# ---------------------------------------------------------------------------

def create_bulk_users_table(dialect, table_name: str = "bulk_users") -> CreateTableStatement:
    return CreateTableStatement(
        dialect=dialect,
        table=Table(dialect, table_name),
        if_not_exists=False,
        columns=[
            ColumnDefinition(dialect, "id", BigIntType(dialect),
                constraints=[ColumnConstraint(dialect, branch=ColumnPrimaryKeyConstraint(dialect))]),
            ColumnDefinition(dialect, "name", VarCharType(dialect, length=255),
                constraints=[ColumnConstraint(dialect, branch=ColumnNotNullConstraint(dialect))]),
            ColumnDefinition(dialect, "age", IntegerType(dialect),
                constraints=[ColumnConstraint(dialect, branch=ColumnDefaultConstraint(dialect, 0))]),
            ColumnDefinition(dialect, "email", VarCharType(dialect, length=255),
                constraints=[ColumnConstraint(dialect, branch=ColumnDefaultConstraint(dialect, ""))]),
        ],
        table_options=_common.default_table_options(dialect),
    )


# ---------------------------------------------------------------------------
# basic/posts.sql
# ---------------------------------------------------------------------------

def create_posts_table(dialect, table_name: str = "posts") -> CreateTableStatement:
    return CreateTableStatement(
        dialect=dialect,
        table=Table(dialect, table_name),
        if_not_exists=False,
        columns=[
            ColumnDefinition(dialect, "id", BigIntType(dialect),
                constraints=[ColumnConstraint(dialect, branch=ColumnPrimaryKeyConstraint(dialect))]),
            ColumnDefinition(dialect, "author", BigIntType(dialect),
                constraints=[ColumnConstraint(dialect, branch=ColumnNotNullConstraint(dialect))]),
            ColumnDefinition(dialect, "title", VarCharType(dialect, length=255),
                constraints=[ColumnConstraint(dialect, branch=ColumnNotNullConstraint(dialect))]),
            ColumnDefinition(dialect, "content", TextType(dialect)),
            ColumnDefinition(dialect, "published_at", ClickHouseDateTime64Type(dialect, precision=6)),
            ColumnDefinition(dialect, "published", BooleanType(dialect),
                constraints=[ColumnConstraint(dialect, branch=ColumnDefaultConstraint(dialect, 0))]),
            ColumnDefinition(dialect, "created_at", ClickHouseDateTime64Type(dialect, precision=6)),
            ColumnDefinition(dialect, "updated_at", ClickHouseDateTime64Type(dialect, precision=6)),
        ],
        indexes=[IndexDefinition(dialect, name="idx_author", columns=["author"])],
        table_options=_common.default_table_options(dialect),
    )


# ---------------------------------------------------------------------------
# basic/comments.sql
# ---------------------------------------------------------------------------

def create_comments_table(dialect, table_name: str = "comments") -> CreateTableStatement:
    return CreateTableStatement(
        dialect=dialect,
        table=Table(dialect, table_name),
        if_not_exists=False,
        columns=[
            ColumnDefinition(dialect, "id", BigIntType(dialect),
                constraints=[ColumnConstraint(dialect, branch=ColumnPrimaryKeyConstraint(dialect))]),
            ColumnDefinition(dialect, "post_ref", BigIntType(dialect),
                constraints=[ColumnConstraint(dialect, branch=ColumnNotNullConstraint(dialect))]),
            ColumnDefinition(dialect, "author", BigIntType(dialect),
                constraints=[ColumnConstraint(dialect, branch=ColumnNotNullConstraint(dialect))]),
            ColumnDefinition(dialect, "text", TextType(dialect),
                constraints=[ColumnConstraint(dialect, branch=ColumnNotNullConstraint(dialect))]),
            ColumnDefinition(dialect, "created_at", ClickHouseDateTime64Type(dialect, precision=6),
                constraints=[ColumnConstraint(dialect, branch=ColumnNotNullConstraint(dialect))]),
            ColumnDefinition(dialect, "updated_at", ClickHouseDateTime64Type(dialect, precision=6)),
            ColumnDefinition(dialect, "approved", BooleanType(dialect),
                constraints=[ColumnConstraint(dialect, branch=ColumnDefaultConstraint(dialect, 0))]),
        ],
        indexes=[
            IndexDefinition(dialect, name="idx_post_ref", columns=["post_ref"]),
            IndexDefinition(dialect, name="idx_author", columns=["author"]),
        ],
        table_options=_common.default_table_options(dialect),
    )


# ---------------------------------------------------------------------------
# basic/column_mapping_items.sql
# ---------------------------------------------------------------------------

def create_column_mapping_items_table(dialect, table_name: str = "column_mapping_items") -> CreateTableStatement:
    return CreateTableStatement(
        dialect=dialect,
        table=Table(dialect, table_name),
        if_not_exists=False,
        columns=[
            ColumnDefinition(dialect, "id", BigIntType(dialect),
                constraints=[ColumnConstraint(dialect, branch=ColumnPrimaryKeyConstraint(dialect))]),
            ColumnDefinition(dialect, "name", VarCharType(dialect, length=255),
                constraints=[ColumnConstraint(dialect, branch=ColumnNotNullConstraint(dialect))]),
            ColumnDefinition(dialect, "item_total", IntegerType(dialect),
                constraints=[ColumnConstraint(dialect, branch=ColumnNotNullConstraint(dialect))]),
            ColumnDefinition(dialect, "remarks", IntegerType(dialect)),
        ],
        table_options=_common.default_table_options(dialect),
    )


# ---------------------------------------------------------------------------
# basic/mixed_annotation_items.sql
# ---------------------------------------------------------------------------

def create_mixed_annotation_items_table(dialect, table_name: str = "mixed_annotation_items") -> CreateTableStatement:
    return CreateTableStatement(
        dialect=dialect,
        table=Table(dialect, table_name),
        if_not_exists=False,
        columns=[
            ColumnDefinition(dialect, "id", BigIntType(dialect),
                constraints=[ColumnConstraint(dialect, branch=ColumnPrimaryKeyConstraint(dialect))]),
            ColumnDefinition(dialect, "name", VarCharType(dialect, length=255),
                constraints=[ColumnConstraint(dialect, branch=ColumnNotNullConstraint(dialect))]),
            ColumnDefinition(dialect, "tags", TextType(dialect)),
            ColumnDefinition(dialect, "meta", TextType(dialect)),
            ColumnDefinition(dialect, "description", TextType(dialect)),
            ColumnDefinition(dialect, "status", TextType(dialect)),
        ],
        table_options=_common.default_table_options(dialect),
    )


# ---------------------------------------------------------------------------
# basic/type_adapter_tests.sql  (no ENGINE/CHARSET in reference file)
# ---------------------------------------------------------------------------

def create_type_adapter_tests_table(dialect, table_name: str = "type_adapter_tests") -> CreateTableStatement:
    return CreateTableStatement(
        dialect=dialect,
        table=Table(dialect, table_name),
        if_not_exists=True,
        columns=[
            ColumnDefinition(dialect, "id", BigIntType(dialect),
                constraints=[ColumnConstraint(dialect, branch=ColumnPrimaryKeyConstraint(dialect))]),
            ColumnDefinition(dialect, "name", VarCharType(dialect, length=255),
                constraints=[ColumnConstraint(dialect, branch=ColumnNotNullConstraint(dialect))]),
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
        table_options=_common.default_table_options(dialect),
    )


# ---------------------------------------------------------------------------
# basic/order_items.sql (composite PK)
# ---------------------------------------------------------------------------

def create_composite_pk_order_items_table(dialect, table_name: str = "order_items") -> CreateTableStatement:
    return CreateTableStatement(
        dialect=dialect,
        table=Table(dialect, table_name),
        if_not_exists=False,
        columns=[
            ColumnDefinition(dialect, "order_id", IntegerType(dialect),
                constraints=[ColumnConstraint(dialect, branch=ColumnNotNullConstraint(dialect))]),
            ColumnDefinition(dialect, "product_id", IntegerType(dialect),
                constraints=[ColumnConstraint(dialect, branch=ColumnNotNullConstraint(dialect))]),
            ColumnDefinition(dialect, "quantity", IntegerType(dialect),
                constraints=[ColumnConstraint(dialect, branch=ColumnNotNullConstraint(dialect)),
                             ColumnConstraint(dialect, branch=ColumnDefaultConstraint(dialect, 1))]),
            ColumnDefinition(dialect, "unit_price", DecimalType(dialect, precision=10, scale=2),
                constraints=[ColumnConstraint(dialect, branch=ColumnNotNullConstraint(dialect))]),
        ],
        table_constraints=[
            TableConstraint(dialect,
                branch=TablePrimaryKeyConstraint(dialect, columns=["order_id", "product_id"])),
        ],
        table_options=_common.default_table_options(dialect, order_by=("order_id", "product_id")),
    )


# ---------------------------------------------------------------------------
# basic/store_inventory.sql (composite PK, no FK)
# ---------------------------------------------------------------------------

def create_store_inventory_table(dialect, table_name: str = "store_inventory") -> CreateTableStatement:
    return CreateTableStatement(
        dialect=dialect,
        table=Table(dialect, table_name),
        if_not_exists=False,
        columns=[
            ColumnDefinition(dialect, "store_id", IntegerType(dialect),
                constraints=[ColumnConstraint(dialect, branch=ColumnNotNullConstraint(dialect))]),
            ColumnDefinition(dialect, "product_id", IntegerType(dialect),
                constraints=[ColumnConstraint(dialect, branch=ColumnNotNullConstraint(dialect))]),
            ColumnDefinition(dialect, "batch_id", VarCharType(dialect, length=64),
                constraints=[ColumnConstraint(dialect, branch=ColumnNotNullConstraint(dialect))]),
            ColumnDefinition(dialect, "stock", IntegerType(dialect),
                constraints=[ColumnConstraint(dialect, branch=ColumnNotNullConstraint(dialect)),
                             ColumnConstraint(dialect, branch=ColumnDefaultConstraint(dialect, 0))]),
        ],
        table_constraints=[
            TableConstraint(dialect,
                branch=TablePrimaryKeyConstraint(dialect, columns=["store_id", "product_id", "batch_id"])),
        ],
        table_options=_common.default_table_options(dialect, order_by=("store_id", "product_id", "batch_id")),
    )


# ---------------------------------------------------------------------------
# basic/orders.sql (single PK, no FK in composite-PK scenario)
# ---------------------------------------------------------------------------

def create_orders_table(dialect, table_name: str = "orders") -> CreateTableStatement:
    return CreateTableStatement(
        dialect=dialect,
        table=Table(dialect, table_name),
        if_not_exists=False,
        columns=[
            ColumnDefinition(dialect, "id", BigIntType(dialect),
                constraints=[ColumnConstraint(dialect, branch=ColumnPrimaryKeyConstraint(dialect))]),
            ColumnDefinition(dialect, "total", DecimalType(dialect, precision=10, scale=2),
                constraints=[ColumnConstraint(dialect, branch=ColumnNotNullConstraint(dialect))]),
            ColumnDefinition(dialect, "created_at", TextType(dialect)),
            ColumnDefinition(dialect, "updated_at", TextType(dialect)),
        ],
        table_options=_common.default_table_options(dialect),
    )


# ---------------------------------------------------------------------------
# basic/product.sql (single PK)
# ---------------------------------------------------------------------------

def create_product_table(dialect, table_name: str = "product") -> CreateTableStatement:
    return CreateTableStatement(
        dialect=dialect,
        table=Table(dialect, table_name),
        if_not_exists=True,
        columns=[
            ColumnDefinition(dialect, "id", BigIntType(dialect),
                constraints=[ColumnConstraint(dialect, branch=ColumnPrimaryKeyConstraint(dialect))]),
            ColumnDefinition(dialect, "name", TextType(dialect),
                constraints=[ColumnConstraint(dialect, branch=ColumnNotNullConstraint(dialect))]),
            ColumnDefinition(dialect, "price", FloatType(dialect),
                constraints=[ColumnConstraint(dialect, branch=ColumnNotNullConstraint(dialect))]),
            ColumnDefinition(dialect, "quantity", IntegerType(dialect),
                constraints=[ColumnConstraint(dialect, branch=ColumnNotNullConstraint(dialect))]),
        ],
        table_options=_common.default_table_options(dialect),
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

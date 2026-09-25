# tests/rhosocial/activerecord_clickhouse_test/feature/backend/ddl/test_ddl_source_mixin.py

from typing import Optional

try:
    from typing import Annotated
except ImportError:
    from typing_extensions import Annotated

import pytest

from rhosocial.activerecord.backend.expression.core import Column
from rhosocial.activerecord.backend.expression.statements import (
    ColumnConstraintType,
    CreateTableExpression,
    CreateTableOptions,
    IndexDefinition,
    StorageOptionsExpression,
    TableConstraint,
    TableConstraintType,
)
from rhosocial.activerecord.backend.expression.statements.ddl_partition import (
    PartitionClause,
    PartitionStrategy,
)
from rhosocial.activerecord.backend.impl.clickhouse.dialect import ClickHouseDialect
from rhosocial.activerecord.backend.impl.clickhouse.expression import (
    ClickHouseColumnDefinition,
    ClickHouseColumnOptions,
    ClickHouseIndexDefinition,
    ClickHouseInt64Type,
    ClickHouseStringType,
)
from rhosocial.activerecord.base import (
    CollationAttribute,
    DDLAnnotationHandler,
    DDLSource,
    IdentityAttribute,
    UseColumn,
    UseColumnAttributes,
    UseComment,
    UseConstraint,
    UseGeneratedColumn,
    UseIndex,
    UseSqlType,
)
from rhosocial.activerecord.model import ActiveRecord, AsyncActiveRecord

NATIVE_TYPES = (ClickHouseStringType(), ClickHouseInt64Type())
SQL_TYPE = UseSqlType(*NATIVE_TYPES)
VALUE_COLUMN = UseColumn("physical_value")
DEFAULT_CONSTRAINT = UseConstraint(
    ColumnConstraintType.DEFAULT,
    name="dflt_value",
    default_value=17,
)
UNIQUE_CONSTRAINT = UseConstraint(
    ColumnConstraintType.UNIQUE,
    name="uq_value",
)
CHECK_CONDITION = Column(None, "physical_value") == "active"
CHECK_CONSTRAINT = UseConstraint(
    ColumnConstraintType.CHECK,
    name="ck_value",
    check_condition=CHECK_CONDITION,
)
FIRST_INDEX_CONDITION = object()
FIRST_INCLUDE_COLUMNS = ["id"]
FIRST_INDEX = UseIndex(
    "idx_value_first",
    unique=True,
    type="minmax",
    partial_condition=FIRST_INDEX_CONDITION,
    include_columns=FIRST_INCLUDE_COLUMNS,
    if_not_exists=True,
    tablespace="ts_index",
    concurrent=True,
)
SECOND_INDEX = UseIndex("idx_value_second", type="set")
VALUE_ATTRIBUTES = (
    CollationAttribute(name="NOCASE"),
    IdentityAttribute(generation="ALWAYS", start=10, increment=2),
)
VALUE_ATTRIBUTES_MARKER = UseColumnAttributes(*VALUE_ATTRIBUTES)
VALUE_COMMENT = UseComment("physical value")


def generated_expression(dialect):
    return object()


GENERATED_EXPRESSION = generated_expression
VALUE_GENERATED = UseGeneratedColumn(GENERATED_EXPRESSION)
CLICKHOUSE_OPTIONS = (
    ClickHouseColumnOptions(codec=("ZSTD",)),
    ClickHouseColumnOptions(codec=("LZ4",)),
)

TABLE_CONSTRAINT_ONE = TableConstraint(
    None,
    TableConstraintType.UNIQUE,
    name="uq_physical_quantity",
    columns=["physical_value", "quantity"],
)
TABLE_CONSTRAINT_TWO = TableConstraint(
    None,
    TableConstraintType.CHECK,
    name="ck_physical_quantity",
    check_condition=Column(None, "physical_value") == "active",
)
TABLE_CONSTRAINTS = [TABLE_CONSTRAINT_ONE, TABLE_CONSTRAINT_TWO]
TABLE_INDEX_ONE = ClickHouseIndexDefinition(
    None,
    name="idx_table_physical",
    columns=["physical_value"],
    type="minmax",
    granularity=4,
)
TABLE_INDEX_TWO = IndexDefinition(
    None,
    name="idx_table_quantity",
    columns=["quantity"],
)
TABLE_INDEXES = [TABLE_INDEX_ONE, TABLE_INDEX_TWO]
TABLE_OPTIONS = (
    CreateTableOptions(None, or_replace=True),
    CreateTableOptions(None),
)
STORAGE_OPTIONS = StorageOptionsExpression(None, {"engine": "MergeTree"})
TABLE_PARTITION = PartitionClause(
    None,
    PartitionStrategy.RANGE,
    [Column(None, "physical_value")],
)
TABLE_INHERITS = ["parent_a", "parent_b"]
TABLE_TABLESPACE = "ts_data"
COMPOSITE_CONSTRAINT = TableConstraint(
    None,
    TableConstraintType.CHECK,
    name="ck_composite",
    columns=["tenant_id", "order_id"],
)


class ClickHouseOptionsHandler(DDLAnnotationHandler):
    annotation_types = (ClickHouseColumnOptions,)

    @classmethod
    def apply(cls, new_class, field_name, annotation, metadata):
        metadata.add_column_options(annotation)


class ClickHouseOptionsMixin:
    _feature_handlers = [ClickHouseOptionsHandler]


class TableDeclarationOverrides:
    @classmethod
    def table_options(cls):
        return TABLE_OPTIONS

    @classmethod
    def table_storage_options(cls):
        return STORAGE_OPTIONS

    @classmethod
    def table_partition(cls):
        return TABLE_PARTITION

    @classmethod
    def table_inherits(cls):
        return TABLE_INHERITS

    @classmethod
    def table_tablespace(cls):
        return TABLE_TABLESPACE

    @classmethod
    def create_table_statement_classes(cls):
        return CreateTableExpression


class DeclarationModel(
    ClickHouseOptionsMixin,
    TableDeclarationOverrides,
    ActiveRecord,
):
    __table_name__ = "ddl_source_declarations"
    __schema_name__ = "analytics"
    __primary_key__ = "record_id"

    id: Annotated[int, UseColumn("record_id")]
    value: Annotated[
        Optional[str],
        VALUE_COLUMN,
        SQL_TYPE,
        DEFAULT_CONSTRAINT,
        UNIQUE_CONSTRAINT,
        CHECK_CONSTRAINT,
        FIRST_INDEX,
        SECOND_INDEX,
        VALUE_ATTRIBUTES_MARKER,
        VALUE_COMMENT,
        VALUE_GENERATED,
        CLICKHOUSE_OPTIONS[0],
        CLICKHOUSE_OPTIONS[1],
    ] = None
    quantity: Annotated[int, UseConstraint(ColumnConstraintType.DEFAULT, default_value=7)] = 1

    __table_constraints__ = TABLE_CONSTRAINTS
    __table_indexes__ = TABLE_INDEXES


class AsyncDeclarationModel(
    ClickHouseOptionsMixin,
    TableDeclarationOverrides,
    AsyncActiveRecord,
):
    __table_name__ = "ddl_source_declarations_async"
    __schema_name__ = "analytics"
    __primary_key__ = "record_id"

    id: Annotated[int, UseColumn("record_id")]
    value: Annotated[
        Optional[str],
        VALUE_COLUMN,
        SQL_TYPE,
        DEFAULT_CONSTRAINT,
        UNIQUE_CONSTRAINT,
        CHECK_CONSTRAINT,
        FIRST_INDEX,
        SECOND_INDEX,
        VALUE_ATTRIBUTES_MARKER,
        VALUE_COMMENT,
        VALUE_GENERATED,
        CLICKHOUSE_OPTIONS[0],
        CLICKHOUSE_OPTIONS[1],
    ] = None
    quantity: Annotated[int, UseConstraint(ColumnConstraintType.DEFAULT, default_value=7)] = 1

    __table_constraints__ = TABLE_CONSTRAINTS
    __table_indexes__ = TABLE_INDEXES


class PlainModel(ActiveRecord):
    __table_name__ = "ddl_source_plain"

    id: int
    value: Optional[str] = None


class AsyncPlainModel(AsyncActiveRecord):
    __table_name__ = "ddl_source_plain_async"

    id: int
    value: Optional[str] = None


class CompositeModel(
    ClickHouseOptionsMixin,
    TableDeclarationOverrides,
    ActiveRecord,
):
    __table_name__ = "ddl_source_composite"
    __primary_key__ = ("tenant_id", "order_id")

    tenant_ref: Annotated[int, UseColumn("tenant_id")]
    order_ref: Annotated[int, UseColumn("order_id")]

    __table_constraints__ = [COMPOSITE_CONSTRAINT]
    __table_indexes__ = TABLE_INDEXES


class AsyncCompositeModel(
    ClickHouseOptionsMixin,
    TableDeclarationOverrides,
    AsyncActiveRecord,
):
    __table_name__ = "ddl_source_composite_async"
    __primary_key__ = ("tenant_id", "order_id")

    tenant_ref: Annotated[int, UseColumn("tenant_id")]
    order_ref: Annotated[int, UseColumn("order_id")]

    __table_constraints__ = [COMPOSITE_CONSTRAINT]
    __table_indexes__ = TABLE_INDEXES


MODEL_CLASSES = (DeclarationModel, AsyncDeclarationModel)
COMPOSITE_MODEL_CLASSES = (CompositeModel, AsyncCompositeModel)
PLAIN_MODEL_CLASSES = (PlainModel, AsyncPlainModel)


def _assert_declaration_model(model):
    assert isinstance(model, DDLSource)
    assert model.table_name().startswith("ddl_source_declarations")
    assert model.schema_name() == "analytics"
    assert model.primary_key_columns() == ("record_id",)
    assert model.primary_key_field() == "id"
    assert model.is_composite_pk() is False
    assert model.ddl_field_names() == ("id", "value", "quantity")
    assert model.is_derived_field("value") is False
    assert model.field_python_type("value") is str
    assert model.field_is_optional("value") is True
    assert model.field_python_type("quantity") is int
    assert model.field_is_optional("quantity") is False
    assert model.column_name("id") == "record_id"
    assert model.columns_name() == {
        "id": "record_id",
        "value": "physical_value",
        "quantity": "quantity",
    }

    metadata = model.ddl_field_metadata("value")
    assert metadata is model.__table_ddl_fields__["value"]
    expected_annotations = (
        VALUE_COLUMN,
        SQL_TYPE,
        DEFAULT_CONSTRAINT,
        UNIQUE_CONSTRAINT,
        CHECK_CONSTRAINT,
        FIRST_INDEX,
        SECOND_INDEX,
        VALUE_ATTRIBUTES_MARKER,
        VALUE_COMMENT,
        VALUE_GENERATED,
        CLICKHOUSE_OPTIONS[0],
        CLICKHOUSE_OPTIONS[1],
    )
    assert metadata.annotations == expected_annotations
    assert model.column_type("value") is SQL_TYPE
    assert model.column_type("value").data_types == NATIVE_TYPES
    assert all(
        actual is expected
        for actual, expected in zip(model.column_type("value").data_types, NATIVE_TYPES, strict=True)
    )

    value_constraints = model.column_constraints("value")
    assert [item.constraint_type for item in value_constraints] == [
        ColumnConstraintType.DEFAULT,
        ColumnConstraintType.UNIQUE,
        ColumnConstraintType.CHECK,
    ]
    assert value_constraints[0] is DEFAULT_CONSTRAINT.constraint
    assert value_constraints[1] is UNIQUE_CONSTRAINT.constraint
    assert value_constraints[2] is CHECK_CONSTRAINT.constraint
    assert value_constraints[2].check_condition is CHECK_CONDITION

    value_indexes = model.column_indexes("value")
    assert [item.name for item in value_indexes] == [
        "idx_value_first",
        "idx_value_second",
    ]
    assert value_indexes[0].columns == ["physical_value"]
    assert value_indexes[0].unique is True
    assert value_indexes[0].type == "minmax"
    assert value_indexes[0].partial_condition is FIRST_INDEX_CONDITION
    assert value_indexes[0].include_columns is FIRST_INCLUDE_COLUMNS
    assert value_indexes[0].if_not_exists is True
    assert value_indexes[0].tablespace == "ts_index"
    assert value_indexes[0].concurrent is True
    assert value_indexes[1].columns == ["physical_value"]
    assert value_indexes[1].unique is False

    assert model.column_attributes("value") == list(VALUE_ATTRIBUTES)
    assert all(
        actual is expected
        for actual, expected in zip(model.column_attributes("value"), VALUE_ATTRIBUTES, strict=True)
    )
    assert model.column_comment("value") == "physical value"
    assert model.generated_column("value") is GENERATED_EXPRESSION
    options = model.column_options("value")
    assert isinstance(options, list)
    assert [option.column_definition_class() for option in options] == [
        ClickHouseColumnDefinition,
        ClickHouseColumnDefinition,
    ]
    assert options[0] is CLICKHOUSE_OPTIONS[0]
    assert options[1] is CLICKHOUSE_OPTIONS[1]

    id_constraints = model.column_constraints("id")
    assert [item.constraint_type for item in id_constraints] == [
        ColumnConstraintType.PRIMARY_KEY,
        ColumnConstraintType.NOT_NULL,
    ]
    quantity_constraints = model.column_constraints("quantity")
    assert model.model_fields["quantity"].default == 1
    assert quantity_constraints[0].constraint_type == ColumnConstraintType.DEFAULT
    assert quantity_constraints[0].default_value == 7
    assert quantity_constraints[1].constraint_type == ColumnConstraintType.NOT_NULL

    assert model.table_options() is TABLE_OPTIONS
    assert [item.or_replace for item in model.table_options()] == [True, False]
    assert model.table_storage_options() is STORAGE_OPTIONS
    assert model.table_partition() is TABLE_PARTITION
    assert model.table_partition().keys[0].name == "physical_value"
    assert model.table_inherits() is TABLE_INHERITS
    assert model.table_tablespace() == TABLE_TABLESPACE
    assert model.create_table_statement_classes() is CreateTableExpression
    assert model.table_constraints() == TABLE_CONSTRAINTS
    assert all(
        actual is expected
        for actual, expected in zip(model.table_constraints(), TABLE_CONSTRAINTS, strict=True)
    )
    assert model.table_indexes() == TABLE_INDEXES
    assert all(
        actual is expected
        for actual, expected in zip(model.table_indexes(), TABLE_INDEXES, strict=True)
    )
    assert model.table_indexes()[0].granularity == 4


def _assert_batch_interfaces(model):
    fields = ["value", "id", "quantity"]
    assert list(model.columns_name()) == ["id", "value", "quantity"]
    assert list(model.columns_name(fields)) == fields
    assert model.columns_name(fields) == {
        "value": "physical_value",
        "id": "record_id",
        "quantity": "quantity",
    }
    assert list(model.columns_type(fields)) == fields
    assert model.columns_type(fields)["value"] is SQL_TYPE
    assert model.columns_type(fields)["quantity"] is None
    assert list(model.columns_constraints(fields)) == fields
    assert model.columns_constraints(fields)["value"][0] is DEFAULT_CONSTRAINT.constraint
    assert list(model.columns_attributes(fields)) == fields
    assert model.columns_attributes(fields)["value"][0] is VALUE_ATTRIBUTES[0]
    assert list(model.columns_indexes(fields)) == fields
    assert model.columns_indexes(fields)["value"][0].name == "idx_value_first"
    assert list(model.columns_comment(fields)) == fields
    assert model.columns_comment(fields)["value"] == "physical value"
    assert list(model.columns_generated(fields)) == fields
    assert model.columns_generated(fields)["value"] is GENERATED_EXPRESSION
    assert list(model.columns_options(fields)) == fields
    batch_options = model.columns_options(fields)["value"]
    assert [option.column_definition_class() for option in batch_options] == [
        ClickHouseColumnDefinition,
        ClickHouseColumnDefinition,
    ]
    assert batch_options[0] is CLICKHOUSE_OPTIONS[0]
    assert batch_options[1] is CLICKHOUSE_OPTIONS[1]


def _assert_plain_defaults(model):
    assert isinstance(model, DDLSource)
    assert model.ddl_field_names() == ("id", "value")
    assert model.column_type("value") is None
    assert model.column_constraints("value") == []
    assert model.column_attributes("value") == []
    assert model.column_indexes("value") == []
    assert model.column_comment("value") is None
    assert model.generated_column("value") is None
    assert model.column_options("value") is None
    assert model.table_options() is None
    assert model.table_storage_options() is None
    assert model.table_partition() is None
    assert model.table_inherits() is None
    assert model.table_tablespace() is None
    assert model.create_table_statement_classes() is None
    assert model.table_indexes() == []
    assert model.table_constraints() == []


def _assert_composite_model(model):
    assert model.primary_key_columns() == ("tenant_id", "order_id")
    assert model.primary_key_field() == ("tenant_ref", "order_ref")
    assert model.is_composite_pk() is True
    assert model.column_name("tenant_ref") == "tenant_id"
    assert model.column_name("order_ref") == "order_id"
    assert model.columns_name() == {
        "tenant_ref": "tenant_id",
        "order_ref": "order_id",
    }
    for field in ("tenant_ref", "order_ref"):
        constraints = model.column_constraints(field)
        assert [item.constraint_type for item in constraints] == [
            ColumnConstraintType.NOT_NULL,
        ]

    constraints = model.table_constraints()
    assert constraints[0] is COMPOSITE_CONSTRAINT
    assert constraints[-1].constraint_type == TableConstraintType.PRIMARY_KEY
    assert constraints[-1].columns == ["tenant_id", "order_id"]
    assert all(
        item.constraint_type != TableConstraintType.PRIMARY_KEY
        for item in constraints[:-1]
    )


@pytest.mark.parametrize("model", MODEL_CLASSES, ids=("sync", "async"))
def test_ddl_source_collects_field_and_table_declarations(model):
    _assert_declaration_model(model)
    _assert_batch_interfaces(model)


@pytest.mark.parametrize("model", COMPOSITE_MODEL_CLASSES, ids=("sync", "async"))
def test_composite_primary_key_is_collected_at_table_level(model):
    _assert_composite_model(model)


@pytest.mark.parametrize("model", PLAIN_MODEL_CLASSES, ids=("sync", "async"))
def test_ddl_source_defaults_are_empty_or_none(model):
    _assert_plain_defaults(model)


async def test_sync_and_async_declarations_are_identical():
    sync_model, async_model = MODEL_CLASSES
    assert sync_model.ddl_field_names() == async_model.ddl_field_names()
    assert sync_model.columns_name() == async_model.columns_name()
    assert sync_model.column_type("value") is async_model.column_type("value")
    assert sync_model.column_constraints("value") == async_model.column_constraints("value")
    assert sync_model.column_attributes("value") == async_model.column_attributes("value")
    sync_indexes = sync_model.column_indexes("value")
    async_indexes = async_model.column_indexes("value")
    assert [
        (item.name, item.columns, item.unique, item.type, item.partial_condition)
        for item in sync_indexes
    ] == [
        (item.name, item.columns, item.unique, item.type, item.partial_condition)
        for item in async_indexes
    ]
    assert sync_model.column_comment("value") == async_model.column_comment("value")
    assert sync_model.generated_column("value") is async_model.generated_column("value")
    assert sync_model.table_options() is async_model.table_options()
    assert sync_model.table_storage_options() is async_model.table_storage_options()
    assert sync_model.table_partition() is async_model.table_partition()
    assert sync_model.table_inherits() is async_model.table_inherits()
    assert sync_model.table_tablespace() == async_model.table_tablespace()
    sync_options = sync_model.column_options("value")
    async_options = async_model.column_options("value")
    assert [option.codec for option in sync_options] == [option.codec for option in async_options]
    assert sync_options[0] is async_options[0]
    assert sync_options[1] is async_options[1]


def test_clickhouse_column_options_are_collected_with_explicit_handler():
    options = DeclarationModel.column_options("value")
    assert [option.codec for option in options] == [["ZSTD"], ["LZ4"]]
    assert options[0].column_definition_class() is ClickHouseColumnDefinition


def test_collected_clickhouse_type_and_options_render_minimal_column():
    dialect = ClickHouseDialect(version=(26, 7, 3))
    data_type = DeclarationModel.column_type("value").data_types[0]
    assert isinstance(data_type, ClickHouseStringType)
    option = DeclarationModel.column_options("value")[0]
    data_type.dialect = dialect
    try:
        column = option.column_definition_class()(dialect, "physical_value", data_type)
        option.apply_to(column)
        expression = CreateTableExpression(dialect, "rendered", [column])
        rendered = expression.to_sql()
    finally:
        data_type.dialect = None
    assert rendered == (
        "CREATE TABLE `rendered` (`physical_value` String CODEC(ZSTD))",
        (),
    )

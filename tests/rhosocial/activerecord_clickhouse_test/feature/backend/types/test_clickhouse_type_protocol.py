# tests/rhosocial/activerecord_clickhouse_test/feature/backend/types/test_clickhouse_type_protocol.py
"""ClickHouse type protocol conformance tests (unit, no DB connection)."""

from __future__ import annotations

import re

import pytest

from rhosocial.activerecord.backend.expression.types import DataType
from rhosocial.activerecord.backend.impl.clickhouse.dialect import ClickHouseDialect
from rhosocial.activerecord.backend.impl.clickhouse.expression.types import (
    ClickHouseAggregateFunctionType,
    ClickHouseArrayType,
    ClickHouseBoolType,
    ClickHouseDate32Type,
    ClickHouseDateType,
    ClickHouseDateTime64Type,
    ClickHouseDateTimeType,
    ClickHouseDecimal128Type,
    ClickHouseDecimal32Type,
    ClickHouseDecimal64Type,
    ClickHouseDecimalType,
    ClickHouseEnum16Type,
    ClickHouseEnum8Type,
    ClickHouseFixedStringType,
    ClickHouseFloat32Type,
    ClickHouseFloat64Type,
    ClickHouseGeometryCollectionType,
    ClickHouseGeometryType,
    ClickHouseInt16Type,
    ClickHouseInt32Type,
    ClickHouseInt64Type,
    ClickHouseInt8Type,
    ClickHouseIPv4Type,
    ClickHouseIPv6Type,
    ClickHouseJSONType,
    ClickHouseLineStringType,
    ClickHouseLowCardinalityType,
    ClickHouseMapType,
    ClickHouseMultiLineStringType,
    ClickHouseMultiPointType,
    ClickHouseMultiPolygonType,
    ClickHouseNullableType,
    ClickHousePointType,
    ClickHousePolygonType,
    ClickHouseSimpleAggregateFunctionType,
    ClickHouseStringType,
    ClickHouseTupleType,
    ClickHouseUInt16Type,
    ClickHouseUInt32Type,
    ClickHouseUInt64Type,
    ClickHouseUInt8Type,
    ClickHouseUUIDType,
    ClickHouseVectorType,
)
from rhosocial.activerecord.backend.impl.clickhouse.mixins.types import (
    ClickHouseTypeSupportMixin,
)


# ── W1: Name prefix enforcement ───────────────────────────────────────

ALL_CLICKHOUSE_TYPES = [
    ClickHouseInt8Type, ClickHouseInt16Type, ClickHouseInt32Type,
    ClickHouseInt64Type, ClickHouseUInt8Type, ClickHouseUInt16Type,
    ClickHouseUInt32Type, ClickHouseUInt64Type,
    ClickHouseFloat32Type, ClickHouseFloat64Type,
    ClickHouseDecimalType, ClickHouseDecimal32Type,
    ClickHouseDecimal64Type, ClickHouseDecimal128Type,
    ClickHouseStringType, ClickHouseFixedStringType,
    ClickHouseDateType, ClickHouseDate32Type,
    ClickHouseDateTimeType, ClickHouseDateTime64Type,
    ClickHouseBoolType, ClickHouseUUIDType,
    ClickHouseIPv4Type, ClickHouseIPv6Type,
    ClickHouseEnum8Type, ClickHouseEnum16Type,
    ClickHouseArrayType, ClickHouseMapType, ClickHouseTupleType,
    ClickHouseNullableType, ClickHouseLowCardinalityType,
    ClickHouseJSONType,
    ClickHouseAggregateFunctionType, ClickHouseSimpleAggregateFunctionType,
    ClickHouseGeometryType, ClickHousePointType, ClickHouseLineStringType,
    ClickHousePolygonType, ClickHouseMultiPointType,
    ClickHouseMultiLineStringType, ClickHouseMultiPolygonType,
    ClickHouseGeometryCollectionType,
    ClickHouseVectorType,
]


class TestNamePrefix:
    def test_all_names_clickhouse_prefixed(self):
        for cls in ALL_CLICKHOUSE_TYPES:
            assert cls.name.startswith("clickhouse_"), (
                f"{cls.__name__}.name = {cls.name!r} — must start with 'clickhouse_'"
            )

    def test_name_matches_valid_identifier(self):
        pat = re.compile(r"^[a-z][a-z0-9_]*$")
        for cls in ALL_CLICKHOUSE_TYPES:
            assert pat.match(cls.name), (
                f"{cls.__name__}.name = {cls.name!r} — must match [a-z][a-z0-9_]*"
            )


# ── W1: __init__ forwards dialect_options ──────────────────────────────

class TestDialectOptionsForwarding:
    def test_simple_types_accept_dialect_options(self):
        for cls in [ClickHouseInt8Type, ClickHouseStringType, ClickHouseBoolType,
                    ClickHouseUUIDType, ClickHouseIPv4Type, ClickHouseJSONType]:
            instance = cls(dialect_options={"custom": True})
            assert instance.dialect_options == {"custom": True}

    def test_decimal_forwards_dialect_options(self):
        t = ClickHouseDecimalType(precision=10, scale=2, dialect_options={"x": 1})
        assert t.dialect_options == {"x": 1}

    def test_decimal32_forwards_dialect_options(self):
        t = ClickHouseDecimal32Type(scale=4, dialect_options={"x": 1})
        assert t.dialect_options == {"x": 1}

    def test_decimal64_forwards_dialect_options(self):
        t = ClickHouseDecimal64Type(scale=8, dialect_options={"x": 1})
        assert t.dialect_options == {"x": 1}

    def test_decimal128_forwards_dialect_options(self):
        t = ClickHouseDecimal128Type(scale=18, dialect_options={"x": 1})
        assert t.dialect_options == {"x": 1}

    def test_fixed_string_forwards_dialect_options(self):
        t = ClickHouseFixedStringType(length=10, dialect_options={"x": 1})
        assert t.dialect_options == {"x": 1}

    def test_datetime64_forwards_dialect_options(self):
        t = ClickHouseDateTime64Type(precision=6, dialect_options={"x": 1})
        assert t.dialect_options == {"x": 1}

    def test_enum8_forwards_dialect_options(self):
        t = ClickHouseEnum8Type(values=[("a", 1)], dialect_options={"x": 1})
        assert t.dialect_options == {"x": 1}

    def test_enum16_forwards_dialect_options(self):
        t = ClickHouseEnum16Type(values=[("a", 1)], dialect_options={"x": 1})
        assert t.dialect_options == {"x": 1}

    def test_map_forwards_dialect_options(self):
        t = ClickHouseMapType(
            key_type=ClickHouseStringType(),
            value_type=ClickHouseInt32Type(),
            dialect_options={"x": 1},
        )
        assert t.dialect_options == {"x": 1}

    def test_tuple_forwards_dialect_options(self):
        t = ClickHouseTupleType(
            element_types=[ClickHouseStringType(), ClickHouseInt32Type()],
            dialect_options={"x": 1},
        )
        assert t.dialect_options == {"x": 1}

    def test_nullable_forwards_dialect_options(self):
        t = ClickHouseNullableType(inner_type=ClickHouseInt32Type(), dialect_options={"x": 1})
        assert t.dialect_options == {"x": 1}

    def test_low_cardinality_forwards_dialect_options(self):
        t = ClickHouseLowCardinalityType(inner_type=ClickHouseStringType(), dialect_options={"x": 1})
        assert t.dialect_options == {"x": 1}

    def test_aggregate_function_forwards_dialect_options(self):
        t = ClickHouseAggregateFunctionType(
            function_name="sum", arg_types=[ClickHouseInt32Type()],
            dialect_options={"x": 1},
        )
        assert t.dialect_options == {"x": 1}

    def test_simple_aggregate_function_forwards_dialect_options(self):
        t = ClickHouseSimpleAggregateFunctionType(
            function_name="sum", arg_types=[ClickHouseInt32Type()],
            dialect_options={"x": 1},
        )
        assert t.dialect_options == {"x": 1}

    def test_geometry_forwards_dialect_options(self):
        t = ClickHouseGeometryType(srid=4326, dialect_options={"x": 1})
        assert t.dialect_options == {"x": 1}

    def test_vector_forwards_dialect_options(self):
        t = ClickHouseVectorType(dim=128, dialect_options={"x": 1})
        assert t.dialect_options == {"x": 1}


# ── W1: _type_params replaces hand-written __eq__/__hash__ ────────────

class TestTypeParamsSemantics:
    def test_decimal_equality_via_type_params(self):
        a = ClickHouseDecimalType(precision=10, scale=2)
        b = ClickHouseDecimalType(precision=10, scale=2)
        c = ClickHouseDecimalType(precision=10, scale=3)
        assert a == b
        assert a != c
        assert hash(a) == hash(b)
        assert hash(a) != hash(c)

    def test_decimal_dialect_options_affect_equality_not_hash(self):
        a = ClickHouseDecimalType(precision=10, scale=2, dialect_options={"x": 1})
        b = ClickHouseDecimalType(precision=10, scale=2, dialect_options={"x": 2})
        c = ClickHouseDecimalType(precision=10, scale=2)
        assert a != b  # different options
        assert a != c  # one has options, other doesn't
        assert hash(a) == hash(c)  # hash ignores options

    def test_fixed_string_equality(self):
        a = ClickHouseFixedStringType(length=10)
        b = ClickHouseFixedStringType(length=10)
        c = ClickHouseFixedStringType(length=20)
        assert a == b
        assert a != c

    def test_datetime64_equality(self):
        a = ClickHouseDateTime64Type(precision=3)
        b = ClickHouseDateTime64Type(precision=3)
        c = ClickHouseDateTime64Type(precision=6)
        assert a == b
        assert a != c

    def test_enum8_equality(self):
        a = ClickHouseEnum8Type(values=[("a", 1), ("b", 2)])
        b = ClickHouseEnum8Type(values=[("a", 1), ("b", 2)])
        c = ClickHouseEnum8Type(values=[("a", 1)])
        assert a == b
        assert a != c

    def test_map_equality(self):
        a = ClickHouseMapType(key_type=ClickHouseStringType(), value_type=ClickHouseInt32Type())
        b = ClickHouseMapType(key_type=ClickHouseStringType(), value_type=ClickHouseInt32Type())
        c = ClickHouseMapType(key_type=ClickHouseStringType(), value_type=ClickHouseInt64Type())
        assert a == b
        assert a != c

    def test_tuple_equality(self):
        a = ClickHouseTupleType(element_types=[ClickHouseStringType(), ClickHouseInt32Type()])
        b = ClickHouseTupleType(element_types=[ClickHouseStringType(), ClickHouseInt32Type()])
        c = ClickHouseTupleType(element_types=[ClickHouseStringType()])
        assert a == b
        assert a != c

    def test_nullable_equality(self):
        a = ClickHouseNullableType(inner_type=ClickHouseInt32Type())
        b = ClickHouseNullableType(inner_type=ClickHouseInt32Type())
        c = ClickHouseNullableType(inner_type=ClickHouseInt64Type())
        assert a == b
        assert a != c

    def test_low_cardinality_equality(self):
        a = ClickHouseLowCardinalityType(inner_type=ClickHouseStringType())
        b = ClickHouseLowCardinalityType(inner_type=ClickHouseStringType())
        c = ClickHouseLowCardinalityType(inner_type=ClickHouseInt32Type())
        assert a == b
        assert a != c

    def test_aggregate_function_equality(self):
        a = ClickHouseAggregateFunctionType(function_name="sum", arg_types=[ClickHouseInt32Type()])
        b = ClickHouseAggregateFunctionType(function_name="sum", arg_types=[ClickHouseInt32Type()])
        c = ClickHouseAggregateFunctionType(function_name="avg", arg_types=[ClickHouseInt32Type()])
        assert a == b
        assert a != c

    def test_geometry_equality(self):
        a = ClickHouseGeometryType(srid=4326)
        b = ClickHouseGeometryType(srid=4326)
        c = ClickHouseGeometryType(srid=0)
        assert a == b
        assert a != c

    def test_vector_equality(self):
        a = ClickHouseVectorType(dim=128)
        b = ClickHouseVectorType(dim=128)
        c = ClickHouseVectorType(dim=256)
        assert a == b
        assert a != c

    def test_type_is_value_object(self):
        a = ClickHouseDecimalType(precision=10, scale=2)
        b = ClickHouseDecimalType(precision=10, scale=2)
        assert type(a) is type(b)
        assert a == b
        assert hash(a) == hash(b)
        assert a is not b


# ── W1: No hand-written __eq__/__hash__ on subclasses ─────────────────

class TestNoHandWrittenEqHash:
    """Verify that parameterized types use _type_params() and inherit
    __eq__/__hash__ from DataType (which uses _type_params)."""

    PARAMETERIZED_TYPES = [
        ClickHouseDecimalType(precision=10, scale=2),
        ClickHouseDecimal32Type(scale=4),
        ClickHouseDecimal64Type(scale=8),
        ClickHouseDecimal128Type(scale=18),
        ClickHouseFixedStringType(length=10),
        ClickHouseDateTime64Type(precision=3),
        ClickHouseEnum8Type(values=[("a", 1)]),
        ClickHouseEnum16Type(values=[("a", 1)]),
        ClickHouseMapType(key_type=ClickHouseStringType(), value_type=ClickHouseInt32Type()),
        ClickHouseTupleType(element_types=[ClickHouseStringType()]),
        ClickHouseNullableType(inner_type=ClickHouseInt32Type()),
        ClickHouseLowCardinalityType(inner_type=ClickHouseStringType()),
        ClickHouseAggregateFunctionType(function_name="sum", arg_types=[ClickHouseInt32Type()]),
        ClickHouseSimpleAggregateFunctionType(function_name="sum", arg_types=[ClickHouseInt32Type()]),
        ClickHouseGeometryType(srid=4326),
        ClickHouseVectorType(dim=128),
    ]

    def test_no_custom_eq(self):
        for instance in self.PARAMETERIZED_TYPES:
            assert "__eq__" not in type(instance).__dict__, (
                f"{type(instance).__name__} defines __eq__ — should use _type_params()"
            )

    def test_no_custom_hash(self):
        for instance in self.PARAMETERIZED_TYPES:
            assert "__hash__" not in type(instance).__dict__, (
                f"{type(instance).__name__} defines __hash__ — should use _type_params()"
            )


# ── W2: supports_data_type_* 1:1 with format_data_type_* ─────────────

class TestSupportsFormat1To1:
    def test_clickhouse_types_have_supports_method(self):
        mixin = ClickHouseTypeSupportMixin()
        format_methods = [
            m for m in dir(mixin) if m.startswith("format_data_type_clickhouse_")
        ]
        for fmt in format_methods:
            suffix = fmt[len("format_data_type_"):]
            supports = f"supports_data_type_{suffix}"
            assert hasattr(mixin, supports), (
                f"Missing {supports} for {fmt}"
            )

    def test_core_types_have_supports_method(self):
        mixin = ClickHouseTypeSupportMixin()
        format_methods = [
            m for m in dir(mixin)
            if m.startswith("format_data_type_")
            and not m.startswith("format_data_type_clickhouse_")
        ]
        for fmt in format_methods:
            suffix = fmt[len("format_data_type_"):]
            supports = f"supports_data_type_{suffix}"
            assert hasattr(mixin, supports), (
                f"Missing {supports} for {fmt}"
            )

    def test_all_clickhouse_supports_return_true(self):
        mixin = ClickHouseTypeSupportMixin()
        supports_methods = [
            m for m in dir(mixin) if m.startswith("supports_data_type_clickhouse_")
        ]
        for method_name in supports_methods:
            method = getattr(mixin, method_name)
            assert method() is True, f"{method_name}() should return True"


# ── W3: supports_data_types() mapping ─────────────────────────────────

class TestSupportsDataTypes:
    def test_includes_clickhouse_native_types(self):
        dialect = ClickHouseDialect()
        supported = dialect.supports_data_types()
        for cls in ALL_CLICKHOUSE_TYPES:
            assert cls.name in supported, (
                f"{cls.__name__} (name={cls.name!r}) missing from supports_data_types()"
            )

    def test_includes_core_types(self):
        dialect = ClickHouseDialect()
        supported = dialect.supports_data_types()
        core_names = [
            "integer", "bigint", "smallint", "tinyint",
            "varchar", "char", "text", "boolean",
            "date", "datetime", "timestamp", "time",
            "float", "double", "real", "decimal",
            "json", "blob", "array",
        ]
        for name in core_names:
            assert name in supported, f"Core type {name!r} missing from supports_data_types()"

    def test_values_are_data_type_subclasses(self):
        dialect = ClickHouseDialect()
        supported = dialect.supports_data_types()
        for name, cls in supported.items():
            assert isinstance(cls, type), f"{name}: value is not a type"
            assert issubclass(cls, DataType), f"{name}: {cls} is not a DataType subclass"


# ── W3: suggested_data_types() ────────────────────────────────────────

class TestSuggestedDataTypes:
    def test_returns_dict(self):
        dialect = ClickHouseDialect()
        suggested = dialect.suggested_data_types()
        assert isinstance(suggested, dict)

    def test_suggests_string_for_binary_types(self):
        dialect = ClickHouseDialect()
        suggested = dialect.suggested_data_types()
        for key in ("binary", "varbinary", "blob"):
            if key in suggested:
                assert suggested[key] is ClickHouseStringType, (
                    f"suggested type for {key!r} should be ClickHouseStringType"
                )

    def test_suggests_string_for_enum(self):
        dialect = ClickHouseDialect()
        suggested = dialect.suggested_data_types()
        if "enum" in suggested:
            assert suggested["enum"] is ClickHouseStringType

    def test_suggests_string_for_jsonb(self):
        dialect = ClickHouseDialect()
        suggested = dialect.suggested_data_types()
        if "jsonb" in suggested:
            assert suggested["jsonb"] is ClickHouseStringType

    def test_no_overlap_with_supported(self):
        dialect = ClickHouseDialect()
        supported = set(dialect.supports_data_types().keys())
        suggested = set(dialect.suggested_data_types().keys())
        overlap = supported & suggested
        assert not overlap, (
            f"suggested and supported keys overlap: {overlap}"
        )


# ── W4: Precision validation ──────────────────────────────────────────

class TestDecimalPrecisionValidation:
    def test_decimal_precision_1_to_38_valid(self):
        for p in (1, 10, 38):
            ClickHouseDecimalType(precision=p, scale=0)

    def test_decimal_precision_0_invalid(self):
        with pytest.raises(ValueError, match="precision must be between 1 and 38"):
            ClickHouseDecimalType(precision=0, scale=0)

    def test_decimal_precision_39_invalid(self):
        with pytest.raises(ValueError, match="precision must be between 1 and 38"):
            ClickHouseDecimalType(precision=39, scale=0)

    def test_decimal_scale_0_to_38_valid(self):
        for s in (0, 10, 38):
            ClickHouseDecimalType(precision=10, scale=s)

    def test_decimal_scale_39_invalid(self):
        with pytest.raises(ValueError, match="scale must be between 0 and 38"):
            ClickHouseDecimalType(precision=10, scale=39)

    def test_decimal32_scale_validation(self):
        ClickHouseDecimal32Type(scale=0)
        ClickHouseDecimal32Type(scale=38)
        with pytest.raises(ValueError, match="scale must be between 0 and 38"):
            ClickHouseDecimal32Type(scale=39)

    def test_decimal64_scale_validation(self):
        ClickHouseDecimal64Type(scale=0)
        ClickHouseDecimal64Type(scale=38)
        with pytest.raises(ValueError, match="scale must be between 0 and 38"):
            ClickHouseDecimal64Type(scale=39)

    def test_decimal128_scale_validation(self):
        ClickHouseDecimal128Type(scale=0)
        ClickHouseDecimal128Type(scale=38)
        with pytest.raises(ValueError, match="scale must be between 0 and 38"):
            ClickHouseDecimal128Type(scale=39)


# ── W4: Float has no precision constraint ─────────────────────────────

class TestFloatNoPrecision:
    def test_float32_no_params(self):
        t = ClickHouseFloat32Type()
        assert t._type_params() == ()

    def test_float64_no_params(self):
        t = ClickHouseFloat64Type()
        assert t._type_params() == ()


# ── format_data_type dispatch ─────────────────────────────────────────

class TestFormatDispatch:
    def test_format_clickhouse_int8(self):
        dialect = ClickHouseDialect()
        sql, params = dialect.format_data_type(ClickHouseInt8Type())
        assert sql == "Int8"
        assert params == ()

    def test_format_clickhouse_decimal(self):
        dialect = ClickHouseDialect()
        sql, params = dialect.format_data_type(ClickHouseDecimalType(precision=18, scale=4))
        assert sql == "Decimal(18, 4)"

    def test_format_clickhouse_enum8(self):
        dialect = ClickHouseDialect()
        t = ClickHouseEnum8Type(values=[("active", 1), ("inactive", 0)])
        sql, _ = dialect.format_data_type(t)
        assert sql == "Enum8('active' = 1, 'inactive' = 0)"

    def test_format_core_integer_maps_to_int32(self):
        from rhosocial.activerecord.backend.expression.types import IntegerType
        dialect = ClickHouseDialect()
        sql, _ = dialect.format_data_type(IntegerType(dialect))
        assert sql == "Int32"

    def test_format_core_varchar_maps_to_string(self):
        from rhosocial.activerecord.backend.expression.types import VarCharType
        dialect = ClickHouseDialect()
        sql, _ = dialect.format_data_type(VarCharType())
        assert sql == "String"

    def test_format_unsupported_type_raises(self):
        dialect = ClickHouseDialect()
        from rhosocial.activerecord.backend.expression.types import UUIDType
        with pytest.raises(TypeError, match="does not support"):
            dialect.format_data_type(UUIDType(dialect))

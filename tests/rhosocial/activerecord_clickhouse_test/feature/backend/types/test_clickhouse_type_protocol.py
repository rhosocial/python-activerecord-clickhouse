# tests/rhosocial/activerecord_clickhouse_test/feature/backend/types/test_clickhouse_type_protocol.py
"""ClickHouse type protocol conformance tests (unit, no DB connection)."""

from __future__ import annotations

import inspect
import re

import pytest

from rhosocial.activerecord.backend.expression.types import (
    ArrayType,
    BigIntType,
    BinaryType,
    BooleanType,
    CharType,
    DataType,
    DateType,
    DecimalType,
    DoubleType,
    FloatType,
    IntegerType,
    JsonType,
    RealType,
    SmallIntType,
    TextType,
    TimestampType,
    TinyIntType,
    UUIDType,
    VarCharType,
)
from rhosocial.activerecord.backend.impl.clickhouse.dialect import ClickHouseDialect
from rhosocial.activerecord.backend.impl.clickhouse.expression import types as clickhouse_types
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
from rhosocial.activerecord.backend.dialect.protocols import DataTypeSupport
from rhosocial.activerecord.backend.impl.clickhouse.protocols import (
    ClickHouseTypeSupport,
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

class TestDialectOptionsRemoved:
    def test_constructor_rejects_dialect_options(self):
        with pytest.raises(TypeError):
            ClickHouseDecimalType(precision=10, scale=2, dialect_options={"x": 1})


















# ── W1: PARAMETERS replaces hand-written __eq__/__hash__ ────────────

class TestTypeParamsSemantics:
    def test_decimal_equality_via_declared_identity(self):
        a = ClickHouseDecimalType(precision=10, scale=2)
        b = ClickHouseDecimalType(precision=10, scale=2)
        c = ClickHouseDecimalType(precision=10, scale=3)
        assert a == b
        assert a != c
        assert hash(a) == hash(b)
        assert hash(a) != hash(c)


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
    """Verify that parameterized types declare PARAMETERS and inherit
    __eq__/__hash__ from DataType (which reads PARAMETERS)."""

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
                f"{type(instance).__name__} defines __eq__ — should declare PARAMETERS"
            )

    def test_no_custom_hash(self):
        for instance in self.PARAMETERIZED_TYPES:
            assert "__hash__" not in type(instance).__dict__, (
                f"{type(instance).__name__} defines __hash__ — should declare PARAMETERS"
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
            "json", "blob", "array", "uuid",
        ]
        for name in core_names:
            assert name in supported, f"Core type {name!r} missing from supports_data_types()"

    def test_core_names_map_to_the_core_classes(self):
        """The value is the class whose ``name`` is the key, so
        ``supports_data_types()['integer'] is IntegerType``."""
        dialect = ClickHouseDialect()
        supported = dialect.supports_data_types()
        assert supported["integer"] is IntegerType
        assert supported["bigint"] is BigIntType
        assert supported["uuid"] is UUIDType
        assert supported["clickhouse_int8"] is ClickHouseInt8Type
        assert supported["clickhouse_timestamp"] is ClickHouseDateTimeType

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

    def test_suggests_string_for_byte_and_text_concepts(self):
        dialect = ClickHouseDialect()
        suggested = dialect.suggested_data_types()
        for key in ("binary", "varbinary", "custom", "enum", "jsonb"):
            assert suggested[key] is ClickHouseStringType, key

    def test_suggests_what_clickhouse_really_stores_for_each(self):
        """An interval is a count of seconds; a timezone-aware instant is a
        ``DateTime64``; a time of day has no ClickHouse type at all; XML is not in
        the manual's list of types."""
        dialect = ClickHouseDialect()
        suggested = dialect.suggested_data_types()
        assert suggested["interval"] is ClickHouseInt64Type
        assert suggested["timestamptz"] is ClickHouseDateTime64Type
        assert suggested["timetz"] is ClickHouseDateTimeType
        assert suggested["xml"] is TextType

    def test_every_entry_has_a_reason(self):
        """A suggestion with no explanation is a guess the reader has to check."""
        dialect = ClickHouseDialect()
        doc = (type(dialect).suggested_data_types.__doc__ or "")
        for concept in dialect.suggested_data_types():
            assert concept in doc, (
                f"suggested_data_types() offers {concept!r} but its docstring "
                f"never says why"
            )

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
    """``Float32``/``Float64`` carry no adjustable precision.

    ClickHouse's float types are fixed widths — there is no ``FLOAT(p)`` spelling
    to widen the mantissa to — so neither class has a ``precision`` parameter, and
    ``PARAMETERS`` is stated rather than inherited so that equality does not
    report a parameter the constructor will not accept.
    """

    def test_float32_no_params(self):
        # Declared empty on purpose: ``__init__`` takes no precision, so
        # inheriting the base's ``precision`` would advertise an identity the
        # class cannot have.
        assert ClickHouseFloat32Type.PARAMETERS == ()
        t = ClickHouseFloat32Type()
        assert t.identity() == ()
        assert t.get_params() == {}

    def test_float64_no_params(self):
        assert ClickHouseFloat64Type.PARAMETERS == ()
        t = ClickHouseFloat64Type()
        assert t.identity() == ()
        assert t.get_params() == {}

    @pytest.mark.parametrize("cls", [ClickHouseFloat32Type, ClickHouseFloat64Type])
    def test_float_rejects_precision(self, cls):
        """A precision the server cannot honour must not be accepted silently."""
        with pytest.raises(TypeError, match="precision"):
            cls(precision=5)

    @pytest.mark.parametrize("cls", [ClickHouseFloat32Type, ClickHouseFloat64Type])
    def test_float_rejects_a_second_positional_argument(self, cls):
        """``dialect`` is first: a stray positional must not land in ``precision``."""
        with pytest.raises(TypeError):
            cls(None, 5)


class TestDateTimeTypeHasNoPrecision:
    """``DateTime`` is whole seconds; ``DateTime64(p)`` is the variable one.

    Same reasoning as the floats, and the same risk in the other direction:
    :class:`TimestampType` reads ``precision``, so an inherited constructor would
    accept a sub-second precision that ``DateTime`` cannot store.
    """

    def test_datetime_type_is_hashable(self):
        t = ClickHouseDateTimeType()
        assert t == ClickHouseDateTimeType()
        assert hash(t) == hash(ClickHouseDateTimeType())
        assert isinstance(t.get_params(), dict)

    def test_datetime_type_has_no_params(self):
        assert ClickHouseDateTimeType.PARAMETERS == ()
        t = ClickHouseDateTimeType()
        assert t.identity() == ()
        assert t.get_params() == {}

    def test_datetime_type_rejects_precision(self):
        with pytest.raises(TypeError, match="precision"):
            ClickHouseDateTimeType(precision=3)

    def test_datetime64_keeps_precision(self):
        assert ClickHouseDateTime64Type.PARAMETERS == ("precision",)
        assert ClickHouseDateTime64Type(precision=6).get_params() == {"precision": 6}
        assert ClickHouseDateTime64Type(precision=6).identity() == (6,)
        assert ClickHouseDateTime64Type(precision=6) != ClickHouseDateTime64Type()


# ── D1: every ClickHouse type that is a core concept derives from it ──

#: ClickHouse type -> the core concept it is. Asserted rather than derived from
#: ``__mro__`` because that is what the refactor changed: a ClickHouse type left
#: on ``DataType`` would still render the same SQL and still pass every dispatch
#: test, while ``isinstance`` would answer "no" to "is this an 8-byte integer?" —
#: which is the question the hierarchy exists to answer once, not per backend.
REPARENTED_TO_CORE_CONCEPT = {
    ClickHouseInt8Type: TinyIntType,
    ClickHouseUInt8Type: TinyIntType,
    ClickHouseInt16Type: SmallIntType,
    ClickHouseUInt16Type: SmallIntType,
    ClickHouseInt32Type: IntegerType,
    ClickHouseUInt32Type: IntegerType,
    ClickHouseInt64Type: BigIntType,
    ClickHouseUInt64Type: BigIntType,
    ClickHouseFloat32Type: FloatType,
    ClickHouseFloat64Type: DoubleType,
    ClickHouseDecimalType: DecimalType,
    ClickHouseDecimal32Type: DecimalType,
    ClickHouseDecimal64Type: DecimalType,
    ClickHouseDecimal128Type: DecimalType,
    ClickHouseStringType: TextType,
    ClickHouseFixedStringType: BinaryType,
    ClickHouseDateType: DateType,
    ClickHouseDate32Type: DateType,
    ClickHouseDateTimeType: TimestampType,
    ClickHouseDateTime64Type: TimestampType,
    ClickHouseBoolType: BooleanType,
    ClickHouseUUIDType: UUIDType,
    ClickHouseJSONType: JsonType,
}


class TestCoreConceptReParenting:
    @pytest.mark.parametrize("cls,base", sorted(
        REPARENTED_TO_CORE_CONCEPT.items(),
        key=lambda pair: pair[0].__name__))
    def test_direct_base_is_the_core_concept(self, cls, base):
        assert cls.__bases__ == (base,), (
            f"{cls.__name__} should derive directly from {base.__name__}, "
            f"not {', '.join(b.__name__ for b in cls.__bases__)}"
        )

    @pytest.mark.parametrize(
        "cls", sorted(REPARENTED_TO_CORE_CONCEPT, key=lambda c: c.__name__))
    def test_reparenting_did_not_change_the_name(self, cls):
        """``name`` is the dispatch key; re-parenting must not move it.

        ``ClickHouseInt32Type`` deriving from ``IntegerType`` does **not** make
        its name ``integer``: the DDL says ``Int32`` and a schema diff compares
        the word the server wrote.
        """
        assert cls.name.startswith("clickhouse_")

    def test_every_clickhouse_type_is_either_reparented_or_on_the_root_list(self):
        """Otherwise a class was added and neither list was updated.

        ``ALL_CLICKHOUSE_TYPES`` is the canonical inventory; the check is that the
        two lists between them account for it exactly.
        """
        accounted = set(REPARENTED_TO_CORE_CONCEPT) | set(ON_DATA_TYPE) \
            | set(ON_A_DOCUMENTED_BACKEND_BASE) | {ClickHouseArrayType}
        missing = sorted(cls.__name__ for cls in ALL_CLICKHOUSE_TYPES
                         if cls not in accounted)
        assert not missing, missing

    def test_unsigned_clickhouse_integers_say_so(self):
        """D5: signedness is a field, and here it is not left lying."""
        for signed, unsigned in (
            (ClickHouseInt8Type, ClickHouseUInt8Type),
            (ClickHouseInt16Type, ClickHouseUInt16Type),
            (ClickHouseInt32Type, ClickHouseUInt32Type),
            (ClickHouseInt64Type, ClickHouseUInt64Type),
        ):
            assert signed().unsigned is False
            assert unsigned().unsigned is True

    def test_fixed_string_is_the_byte_string_concept(self):
        """``FixedString(N)`` is N **bytes**, zero-padded — not ``CHAR(N)``.

        The padding is the whole argument: a fixed-length *character* type cannot
        make ``FixedString(3)`` holding ``'a'`` equal ``'a'`` but not match
        ``LIKE 'a'``, which is exactly what zero-filling produces.
        """
        assert issubclass(ClickHouseFixedStringType, BinaryType)
        assert not issubclass(ClickHouseFixedStringType, CharType)
        assert not issubclass(ClickHouseFixedStringType, TextType)

    def test_datetime_is_a_timestamp_not_a_mysql_datetime(self):
        """ClickHouse's ``DateTime`` is a count of seconds since the epoch.

        That is SQL's ``TIMESTAMP``. MySQL's ``DATETIME`` has no epoch to convert
        against, and the two are not interchangeable, so the parent is the one
        whose storage is an instant.
        """
        from rhosocial.activerecord.backend.expression.types import DateTimeType
        assert issubclass(ClickHouseDateTimeType, TimestampType)
        assert not issubclass(ClickHouseDateTimeType, DateTimeType)


# ── D1/D4: the chain is linear — no diamonds, no grouping nodes ──────

def _all_data_type_subclasses():
    seen, stack, out = set(), [DataType], []
    while stack:
        klass = stack.pop()
        if klass in seen:
            continue
        seen.add(klass)
        stack.extend(klass.__subclasses__())
        if klass is not DataType:
            out.append(klass)
    return out


_CORE_MODULE = "rhosocial.activerecord.backend.expression.types"


def _core_concepts():
    """The concrete concepts core itself owns, keyed by dispatch ``name``.

    Discovered rather than listed so that a concept added to core later is
    covered here without an edit — which is the whole point of the
    expression/protocol correspondence: the set of concepts is open.
    """
    return {
        klass.name: klass
        for klass in _all_data_type_subclasses()
        if getattr(klass, "__module__", "").startswith(_CORE_MODULE)
        and getattr(klass, "name", None)
    }


def _core_concept_by_name():
    return _core_concepts()


class TestChainIsLinear:
    def test_no_multiple_inheritance_among_data_type_subclasses(self):
        """D1/D4: width is a class and signedness a field, so no (width x sign)
        grid — which means no class can have two bases."""
        offenders = [
            klass.__name__ for klass in _all_data_type_subclasses()
            if len(klass.__bases__) > 1
        ]
        assert not offenders, offenders

    def test_every_backend_type_base_is_a_data_type(self):
        for klass in _all_data_type_subclasses():
            for base in klass.__bases__:
                assert issubclass(base, DataType), (
                    f"{klass.__name__} derives from {base.__name__}, which is "
                    f"not a DataType"
                )


class TestDialectFirstConstructor:
    """``dialect`` is the first positional parameter of every ``DataType``.

    A signature that puts a business parameter first fails *silently*: the dialect
    object is stored as the bit count and the error only appears at render time.
    """

    def test_dialect_is_first_everywhere(self):
        offenders = []
        for klass in _all_data_type_subclasses():
            params = list(inspect.signature(klass.__init__).parameters.values())
            if not params or params[0].name == "self":
                continue
            first = params[1] if params[0].name == "self" else params[0]
            if first.name != "dialect":
                offenders.append(f"{klass.__name__}({first.name}, ...)")
        assert not offenders, offenders

    def test_dialect_cannot_be_stored_as_a_length_or_a_count(self):
        """The failure this convention prevents, asserted where it would bite."""
        sentinel = object()
        with pytest.raises(TypeError):
            ClickHouseFixedStringType(sentinel, 8)
        with pytest.raises(TypeError):
            ClickHouseEnum8Type(sentinel, [("a", 1)])
        with pytest.raises(TypeError):
            ClickHouseVectorType(sentinel, 4)


# ── D7: the classes that stay on DataType say why ────────────────────

#: ClickHouse types with no core concept to be, that sit **directly** on
#: ``DataType``. Each must argue the point in its docstring — see
#: :class:`TestRootSittingTypesAreDocumented`.
ON_DATA_TYPE = [
    ClickHouseEnum8Type, ClickHouseEnum16Type,
    ClickHouseNullableType, ClickHouseLowCardinalityType,
    ClickHouseMapType, ClickHouseTupleType,
    ClickHouseAggregateFunctionType, ClickHouseSimpleAggregateFunctionType,
    ClickHouseIPv4Type, ClickHouseIPv6Type,
    ClickHouseGeometryType, ClickHouseVectorType,
]

#: ClickHouse types with no core concept that are *not* on ``DataType`` either,
#: because they are correct: ``ClickHouseArrayType`` is core's ``ArrayType`` in
#: ClickHouse's spelling, and the spatial classes hang off
#: :class:`ClickHouseGeometryType`, which is ClickHouse's own real type as well
#: as their base — not a grouping node invented to hold them.
ON_A_DOCUMENTED_BACKEND_BASE = [
    ClickHousePointType, ClickHouseLineStringType, ClickHousePolygonType,
    ClickHouseMultiPointType, ClickHouseMultiLineStringType,
    ClickHouseMultiPolygonType, ClickHouseGeometryCollectionType,
]


class TestRootSittingTypesAreDocumented:
    """D7: sitting on ``DataType`` is legitimate but must be *argued*.

    Not an exemption with a marker — there is no allowlist, no annotation and no
    registry anywhere — so the requirement is the docstring itself: it has to say
    why this is not a core concept, with the concrete difference, not just name
    the type.
    """

    @pytest.mark.parametrize("cls", ON_DATA_TYPE, ids=lambda c: c.__name__)
    def test_sits_directly_on_data_type(self, cls):
        assert cls.__bases__ == (DataType,), (
            f"{cls.__name__} is listed as a ClickHouse-only type but derives "
            f"from {', '.join(b.__name__ for b in cls.__bases__)}"
        )

    @pytest.mark.parametrize("cls", ON_DATA_TYPE, ids=lambda c: c.__name__)
    def test_docstring_explains_why_not_core(self, cls):
        doc = (cls.__doc__ or "").strip()
        assert len(doc) > 120, (
            f"{cls.__name__}.__doc__ is {len(doc)} chars — D7 wants the reason "
            f"this is not a core concept, not a restatement of the type name"
        )
        lowered = doc.lower()
        assert "core" in lowered or "sql:2016" in lowered, (
            f"{cls.__name__}.__doc__ never mentions core or SQL:2016, so it "
            f"cannot be saying why it is not a core concept"
        )

    @pytest.mark.parametrize(
        "cls", ON_A_DOCUMENTED_BACKEND_BASE, ids=lambda c: c.__name__)
    def test_backend_internal_base_is_a_real_type_not_a_grouping_node(self, cls):
        """The seven spatial classes share a base, and D1 forbids a group node.

        The escape is that the base is not invented: ClickHouse *names*
        ``GEOMETRY`` as a type in its own right and a column declared ``GEOMETRY``
        accepts any of the seven. Asserted so the arrangement cannot be copied
        into a real grouping node later.
        """
        assert issubclass(cls, ClickHouseGeometryType), (
            f"{cls.__name__} does not hang off ClickHouseGeometryType"
        )
        base = cls.__bases__[0]
        assert base.__module__.startswith(_CORE_MODULE) \
            or ".impl.clickhouse." in base.__module__, (
            f"{cls.__name__} derives from {base.__name__}, which is neither a "
            f"core concept nor a ClickHouse type"
        )
        assert (cls.__doc__ or "").strip(), f"{cls.__name__} has no docstring"

    def test_array_is_core_in_clickhouse_spelling(self):
        """``ClickHouseArrayType`` is not in either "not a core concept" list
        because it *is* one — core's ``ArrayType``, written the way ClickHouse
        writes it."""
        assert ClickHouseArrayType.__bases__ == (ArrayType,)
        assert ClickHouseArrayType.name == "clickhouse_array"

    def test_every_non_core_clickhouse_type_is_on_one_of_the_two_lists(self):
        """Neither list may silently grow a class the other does not know about."""
        known = set(REPARENTED_TO_CORE_CONCEPT) | set(ON_DATA_TYPE) \
            | set(ON_A_DOCUMENTED_BACKEND_BASE) | {ClickHouseArrayType}
        unknown = sorted(cls.__name__ for cls in ALL_CLICKHOUSE_TYPES
                         if cls not in known)
        assert not unknown, unknown

    def test_enum_docstring_lists_the_consequences(self):
        """Not "this is Enum8" — the *consequences* of it not being ``EnumType``.

        Checked against ClickHouse's own documentation: explicit possibly-negative
        integers, ordering by the assigned integer, non-nullable, and undefined
        for most numeric and string operations.
        """
        for cls in (ClickHouseEnum8Type, ClickHouseEnum16Type):
            doc = (cls.__doc__ or "").lower()
            assert "integer" in doc, cls.__name__
            assert "order" in doc, cls.__name__
            assert "null" in doc, cls.__name__
            assert "undefined" in doc, cls.__name__

    def test_low_cardinality_is_a_storage_encoding(self):
        """It is not a different type from its inner type, which is the reason it
        cannot derive from one."""
        doc = (ClickHouseLowCardinalityType.__doc__ or "").lower()
        assert "encoding" in doc
        assert not issubclass(ClickHouseLowCardinalityType, ClickHouseStringType)


# ── D9: expression <-> protocol correspondence ────────────────────────

class TestCorrespondence:
    """Every concrete core concept is rendered or named as a substitute."""

    def test_every_core_concept_is_declared(self):
        dialect = ClickHouseDialect()
        supported = dialect.supports_data_types()
        suggested = dialect.suggested_data_types()
        undeclared = sorted(
            name for name in _core_concepts()
            if name not in supported and name not in suggested
        )
        assert not undeclared, undeclared

    def test_supported_and_suggested_are_disjoint(self):
        dialect = ClickHouseDialect()
        overlap = set(dialect.supports_data_types()) & set(dialect.suggested_data_types())
        assert not overlap, overlap

    def test_every_suggested_substitute_is_renderable(self):
        """A substitute the dialect cannot render is advice nobody can take."""
        dialect = ClickHouseDialect()
        supported = dialect.supports_data_types()
        for concept, substitute in dialect.suggested_data_types().items():
            assert isinstance(substitute, type) and issubclass(substitute, DataType), (
                f"{concept} -> {substitute!r} is not a DataType subclass"
            )
            assert substitute.name in supported, (
                f"{concept} -> {substitute.__name__} (name={substitute.name!r}), "
                f"which this dialect does not render"
            )

    def test_concepts_clickhouse_cannot_spell_are_all_substituted(self):
        dialect = ClickHouseDialect()
        suggested = dialect.suggested_data_types()
        # ClickHouse's manual enumerates its types; these are the concepts that
        # are genuinely not among them.
        for concept in ("custom", "interval", "timestamptz", "timetz", "xml"):
            assert concept in suggested, f"{concept} is undeclared"
            assert concept not in dialect.supports_data_types(), concept

    def test_uuid_is_rendered_not_substituted(self):
        """ClickHouse has a native ``UUID``, so the concept is rendered."""
        dialect = ClickHouseDialect()
        assert "uuid" in dialect.supports_data_types()
        assert "uuid" not in dialect.suggested_data_types()
        assert dialect.format_data_type(UUIDType(dialect))[0] == "UUID"

    def test_error_for_an_unrendered_concept_names_the_substitute(self):
        """Silence is the one forbidden answer: the message must say what to use."""
        from rhosocial.activerecord.backend.expression.types import IntervalType
        dialect = ClickHouseDialect()
        with pytest.raises(TypeError) as excinfo:
            dialect.format_data_type(IntervalType(dialect))
        assert "ClickHouseInt64Type" in str(excinfo.value)

    def test_backend_type_protocol_is_in_the_mro_before_the_generic_one(self):
        mro = ClickHouseDialect.__mro__
        assert ClickHouseTypeSupport in mro
        assert mro.index(ClickHouseTypeSupport) < mro.index(DataTypeSupport)
        assert isinstance(ClickHouseDialect(), ClickHouseTypeSupport)

    def test_protocol_does_not_absorb_the_set_type_contract(self):
        """``ClickHouseSetTypeSupport`` is about functions, not a column type."""
        from rhosocial.activerecord.backend.impl.clickhouse.protocols import (
            ClickHouseSetTypeSupport,
        )
        assert ClickHouseSetTypeSupport not in ClickHouseTypeSupport.__mro__


class TestSpellingGates:
    """D9: a formatter states which spellings it renders and refuses the rest."""

    SPELLING_RENDERINGS = {
        "integer": {"integer": "Int32", "int": "Int32"},
        "bigint": {"bigint": "Int64", "int8": "Int64"},
        "smallint": {"smallint": "Int16", "int2": "Int16"},
        "tinyint": {"tinyint": "Int8", "int1": "Int8"},
        "char": {"char": "String", "character": "String"},
        "varchar": {"varchar": "String", "character varying": "String"},
        "text": {"text": "String", "clob": "String"},
        "boolean": {"boolean": "Bool", "bool": "Bool"},
        "decimal": {
            "decimal": "Decimal(10, 0)",
            "numeric": "Decimal(10, 0)",
            "dec": "Decimal(10, 0)",
        },
        "double": {"double": "Float64", "double precision": "Float64"},
        "blob": {"blob": "String", "bytea": "String"},
    }

    @pytest.mark.parametrize("concept", sorted(SPELLING_RENDERINGS))
    def test_every_declared_spelling_renders(self, concept):
        dialect = ClickHouseDialect()
        cls = _core_concept_by_name()[concept]
        for spelling, expected in self.SPELLING_RENDERINGS[concept].items():
            sql, _ = dialect.format_data_type(cls(dialect, spelling=spelling))
            assert sql == expected, f"{concept}[{spelling!r}] -> {sql}"

    def test_default_spelling_always_renders(self):
        """The core invariant: a concept must be usable on this backend."""
        dialect = ClickHouseDialect()
        for name, cls in sorted(_core_concept_by_name().items()):
            if not getattr(cls, "SPELLINGS", ()):
                continue
            sql, _ = dialect.format_data_type(cls(dialect))
            assert sql, name

    @pytest.mark.parametrize("concept", sorted(SPELLING_RENDERINGS))
    def test_a_spelling_outside_the_list_is_refused_by_name(self, concept):
        """No silent fallback: the error names the spelling that was rejected."""
        dialect = ClickHouseDialect()
        data_type = _core_concept_by_name()[concept](
            dialect, spelling="not_a_real_spelling")
        with pytest.raises(TypeError, match="not_a_real_spelling"):
            dialect.format_data_type(data_type)

    def test_clickhouse_spells_all_of_a_concepts_spellings(self):
        """``accepted`` may be an explicit tuple for a backend that spells only
        some of a concept. ClickHouse spells all of them, so the concept class is
        passed to ``_check_spelling`` — asserted here so narrowing any one of them
        has to be deliberate rather than a copy-paste slip."""
        dialect = ClickHouseDialect()
        # ``clob`` is not a ClickHouse word, yet it is accepted and rendered
        # ``String``; refusing it would refuse the concept's own second spelling
        # without saying anything the rendered column does not say.
        assert dialect.format_data_type(TextType(dialect, spelling="clob"))[0] == "String"


# ── D8: parse_type is canonical ──────────────────────────────────────

class TestParseTypeCanonicality:
    @pytest.fixture
    def dialect(self):
        return ClickHouseDialect()

    @pytest.mark.parametrize("raw,expected", [
        ("Decimal32(4)", "Decimal32(4)"),
        ("Decimal64(8)", "Decimal64(8)"),
        ("Decimal128(18)", "Decimal128(18)"),
        ("Decimal32", "Decimal32(0)"),
        ("Decimal(10, 2)", "Decimal(10, 2)"),
        ("Decimal(10)", "Decimal(10, 0)"),
    ])
    def test_decimal_width_digits_are_not_mistaken_for_the_scale(self, dialect, raw, expected):
        """The digits in the *name* are the width.

        ``Decimal32(4)`` used to parse as ``Decimal32(32)``, and
        ``Decimal64(8)`` / ``Decimal128(18)`` raised ``ValueError`` because the
        width came back as a scale outside 0..38.
        """
        assert dialect.format_data_type(dialect.parse_type(raw))[0] == expected

    @pytest.mark.parametrize("raw", ["Bool", "BOOLEAN"])
    def test_boolean_spellings_are_one_class(self, dialect, raw):
        """ClickHouse accepts ``Bool`` and ``BOOLEAN`` for the same type."""
        parsed = dialect.parse_type(raw)
        assert isinstance(parsed, ClickHouseBoolType)
        assert dialect.format_data_type(parsed)[0] == "Bool"

    @pytest.mark.parametrize("raw", ["Decimal(10, 2)", "NUMERIC(10, 2)", "DEC(10, 2)"])
    def test_decimal_spellings_are_one_class(self, dialect, raw):
        """The core ``SPELLINGS`` list is exactly ClickHouse's own vocabulary."""
        parsed = dialect.parse_type(raw)
        assert isinstance(parsed, ClickHouseDecimalType)
        assert dialect.format_data_type(parsed)[0] == "Decimal(10, 2)"

    def test_enum_order_is_canonicalised_by_the_assigned_integer(self, dialect):
        """ClickHouse reorders enum labels by their integer, not by declaration.

        A live 26.7 server reports ``Enum8('x' = 1, 'y' = -2)`` back as
        ``Enum8('y' = -2, 'x' = 1)``, so a parser that kept the written order
        would make an introspected column differ from the declaration that
        produced it.
        """
        assert dialect.parse_type("Enum8('x' = 1, 'y' = -2)") == \
            dialect.parse_type("Enum8('y' = -2, 'x' = 1)")

    @pytest.mark.parametrize("raw", [
        "Int8", "UInt64", "Float32", "Decimal32(4)", "String", "FixedString(8)",
        "Date", "Date32", "DateTime", "DateTime64(3)", "Bool", "UUID", "IPv4",
        "IPv6", "JSON", "Array(Int32)", "Map(String, Int32)",
        "Tuple(String, Int32)", "Nullable(Int32)", "LowCardinality(String)",
        "Enum8('a' = 1)",
    ])
    def test_parse_then_render_is_a_fixed_point(self, dialect, raw):
        parsed = dialect.parse_type(raw)
        assert dialect.format_data_type(parsed)[0] == raw

    def test_an_unknown_name_is_not_silently_written_out(self, dialect):
        """ClickHouse's type grammar is closed, so there is no
        ``format_data_type_custom`` — the fallback must be a *render failure*
        with advice, not a pass-through."""
        from rhosocial.activerecord.backend.expression.types import CustomType
        parsed = dialect.parse_type("SomeTypeWeDoNotKnow")
        assert isinstance(parsed, CustomType)
        with pytest.raises(TypeError) as excinfo:
            dialect.format_data_type(parsed)
        assert "ClickHouseStringType" in str(excinfo.value)

    def test_sql_standard_words_are_not_claimed_as_clickhouse_types(self, dialect):
        """``VARCHAR(10)`` is not claimed; the server's alias table is wider.

        Measured on 26.7.3.19: ``CREATE TABLE t (a VARCHAR(10))`` is actually
        accepted and resolves to ``String`` — it is one of the server's 73
        aliases — but this parser claims the native names this dialect renders,
        not the whole alias table.  An unclaimed word falls through to
        ``CustomType``, which cannot be rendered, so the caller gets a reported
        failure rather than a wrong declaration.
        """
        from rhosocial.activerecord.backend.expression.types import CustomType
        for raw in ("VARCHAR(10)", "TINYINT", "BYTEA", "CLOB"):
            try:
                parsed = dialect.parse_type(raw)
            except Exception:
                continue
            assert isinstance(parsed, CustomType), raw

    @pytest.mark.parametrize("raw", [
        "TINYINT", "INT1", "SMALLINT", "MEDIUMINT", "INT", "INTEGER", "BIGINT",
    ])
    def test_the_single_word_signed_aliases_are_not_claimed(self, dialect, raw):
        """The other half of the alias table is deliberately left where it was.

        The server accepts every one of these and resolves them to the *signed*
        widths — ``toTypeName(CAST(1 AS TINYINT))`` is ``Int8`` on 26.7.3.19 —
        but they are alternate spellings of the signed columns whose native names
        (``Int8``…``Int64``) this parser already claims, and the server's alias
        table is wider than the vocabulary this dialect reads (``FLOAT``,
        ``DOUBLE`` and ``VARCHAR(10)`` are unclaimed too).  A single word falls
        through to ``CustomType``, exactly as before the ``* UNSIGNED`` family
        was recognised: "not claimed", not "rejected by the server".
        """
        from rhosocial.activerecord.backend.expression.types import CustomType
        assert isinstance(dialect.parse_type(raw), CustomType), raw

    def test_case_is_tolerated_even_though_native_type_names_are_case_sensitive(
            self, dialect):
        """Documented leniency, asserted so it stays a decision.

        Case decides only the *native* names, and only at the server: measured
        on 26.7.3.19, ``CREATE TABLE t (a Int8)`` and ``(a String)`` succeed
        while ``(a INT8)``, ``(a int8)`` and ``(a string)`` come back code 50
        ``Unknown data type family`` (the alias words — ``TINYINT``,
        ``VARCHAR``, ``YEAR`` and friends — are ``case_insensitive = 1``).
        ``parse_type`` upper-cases everything, so it tolerates any case —
        harmless for its introspection caller, which is handed the server's own
        canonical output, and convenient for hand-written DDL.
        """
        for raw, expected in (
            ("int8", "Int8"),
            ("STRING", "String"),
            ("boolean", "Bool"),
        ):
            parsed = dialect.parse_type(raw)
            assert dialect.format_data_type(parsed)[0] == expected, raw


# ── format_data_type dispatch ─────────────────────────────────────────

#: ``{label: rendered SQL}`` captured from the tree *before* the re-parenting.
#:
#: The point of re-parenting is that it is a pure structural change: a ClickHouse
#: type that becomes a subclass of a core concept must render byte-for-byte what
#: it rendered when it sat on ``DataType``. A golden table is the only evidence
#: that does not depend on comparing two checkouts at test time, and a subclass
#: can silently start rendering differently (through an inherited declaration,
#: a changed default, a lost width) while every dispatch test still passes.
BEFORE_REPARENTING_SQL = {
    "ClickHouseInt8Type": "Int8",
    "ClickHouseInt16Type": "Int16",
    "ClickHouseInt32Type": "Int32",
    "ClickHouseInt64Type": "Int64",
    "ClickHouseUInt8Type": "UInt8",
    "ClickHouseUInt16Type": "UInt16",
    "ClickHouseUInt32Type": "UInt32",
    "ClickHouseUInt64Type": "UInt64",
    "ClickHouseFloat32Type": "Float32",
    "ClickHouseFloat64Type": "Float64",
    "ClickHouseDecimalType": "Decimal(18, 4)",
    "ClickHouseDecimal32Type": "Decimal32(4)",
    "ClickHouseDecimal64Type": "Decimal64(8)",
    "ClickHouseDecimal128Type": "Decimal128(18)",
    "ClickHouseStringType": "String",
    "ClickHouseFixedStringType": "FixedString(16)",
    "ClickHouseDateType": "Date",
    "ClickHouseDate32Type": "Date32",
    "ClickHouseDateTimeType": "DateTime",
    "ClickHouseDateTime64Type": "DateTime64(3)",
    "ClickHouseBoolType": "Bool",
    "ClickHouseUUIDType": "UUID",
    "ClickHouseJSONType": "JSON",
    "ClickHouseIPv4Type": "IPv4",
    "ClickHouseIPv6Type": "IPv6",
    "ClickHouseGeometryType": "GEOMETRY",
    "ClickHousePointType": "POINT",
    "ClickHouseLineStringType": "LINESTRING",
    "ClickHousePolygonType": "POLYGON",
    "ClickHouseMultiPointType": "MULTIPOINT",
    "ClickHouseMultiLineStringType": "MULTILINESTRING",
    "ClickHouseMultiPolygonType": "MULTIPOLYGON",
    "ClickHouseGeometryCollectionType": "GEOMETRYCOLLECTION",
}


class TestRenderingIsUnchangedByReParenting:
    """The golden table above, asserted against today's rendering."""

    ARGS = {
        "ClickHouseDecimalType": {"precision": 18, "scale": 4},
        "ClickHouseDecimal32Type": {"scale": 4},
        "ClickHouseDecimal64Type": {"scale": 8},
        "ClickHouseDecimal128Type": {"scale": 18},
        "ClickHouseFixedStringType": {"length": 16},
        "ClickHouseDateTime64Type": {"precision": 3},
    }

    @pytest.mark.parametrize("cls_name", sorted(BEFORE_REPARENTING_SQL))
    def test_rendered_sql_matches_the_pre_reparenting_snapshot(self, cls_name):
        dialect = ClickHouseDialect()
        cls = _all_data_type_subclasses_by_name()[cls_name]
        sql, params = cls(dialect, **self.ARGS.get(cls_name, {})).to_sql()
        assert sql == BEFORE_REPARENTING_SQL[cls_name]
        assert params == ()

    @pytest.mark.parametrize("cls_name", sorted(BEFORE_REPARENTING_SQL))
    def test_the_golden_table_covers_every_reparented_class(self, cls_name):
        """A class re-parented without being added here would go unchecked.

        The reverse direction is not asserted: the table also covers the classes
        that legitimately stay on ``DataType`` (the spatial family), because those
        render exactly as they did before the refactor too.
        """
        assert cls_name in {c.__name__ for c in ALL_CLICKHOUSE_TYPES}, cls_name


def _all_data_type_subclasses_by_name():
    return {klass.__name__: klass for klass in _all_data_type_subclasses()}


class TestFormatDispatch:
    def test_format_clickhouse_int8(self):
        dialect = ClickHouseDialect()
        sql, params = ClickHouseInt8Type(dialect).to_sql()
        assert sql == "Int8"
        assert params == ()

    def test_format_clickhouse_decimal(self):
        dialect = ClickHouseDialect()
        sql, params = ClickHouseDecimalType(dialect, precision=18, scale=4).to_sql()
        assert sql == "Decimal(18, 4)"

    def test_format_clickhouse_enum8(self):
        dialect = ClickHouseDialect()
        t = ClickHouseEnum8Type(dialect, values=[("active", 1), ("inactive", 0)])
        sql, _ = t.to_sql()
        assert sql == "Enum8('active' = 1, 'inactive' = 0)"

    def test_format_core_integer_maps_to_int32(self):
        dialect = ClickHouseDialect()
        sql, _ = IntegerType(dialect).to_sql()
        assert sql == "Int32"

    def test_format_core_varchar_maps_to_string(self):
        dialect = ClickHouseDialect()
        sql, _ = VarCharType(dialect).to_sql()
        assert sql == "String"

    def test_format_unsupported_type_raises(self):
        """A concept with no renderer and no substitute must still fail loudly.

        ``uuid`` used to be the example here, and no longer is: ClickHouse has a
        native ``UUID``, so the concept is rendered (see
        :meth:`TestCorrespondence.test_uuid_is_rendered_not_substituted`). What is
        left genuinely unrenderable on this backend is an unrecognised type name,
        because ClickHouse's type grammar is closed and there is no
        ``format_data_type_custom`` to pass it through.
        """
        from rhosocial.activerecord.backend.expression.types import CustomType
        dialect = ClickHouseDialect()
        with pytest.raises(TypeError, match="does not support the generic type 'custom'"):
            CustomType(dialect, "SomeTypeWeDoNotKnow").to_sql()

    def test_format_unknown_type_error_names_the_substitute(self):
        """The message has to say what to use, not just that nothing is there."""
        from rhosocial.activerecord.backend.expression.types import CustomType
        dialect = ClickHouseDialect()
        with pytest.raises(TypeError, match="ClickHouseStringType"):
            CustomType(dialect, "SomeTypeWeDoNotKnow").to_sql()


# ── ``unsigned`` is refused, not dropped ─────────────────────────────
#
# ``unsigned`` is in the four core integer concepts' ``PARAMETERS``, so it is part
# of their identity: the differ compares ``ClickHouseInt8Type(unsigned=True)``
# against ``ClickHouseInt8Type()`` and sees two different columns. A dialect must
# therefore honour it or refuse it. ClickHouse refuses, because it spells
# signedness in the type *name* — ``Int8`` and ``UInt8`` are two types over one
# storage size, and ``UNSIGNED`` is not an attribute a declaration can carry:
# ``CREATE TABLE t (a Int8 UNSIGNED)`` fails with ``Unknown data type family:
# INT8 UNSIGNED`` on 26.7.3.19.
#
# https://clickhouse.com/docs/sql-reference/data-types/int-uint
#
# Honouring it was available and was still refused: ClickHouse does accept the
# MySQL-compat alias ``TINYINT UNSIGNED`` (``SELECT toTypeName(CAST(1 AS
# TINYINT UNSIGNED))`` returns ``UInt8``), but that column is byte-for-byte the one
# ``ClickHouseUInt8Type`` already renders. Two declarations for one column is what
# one-concept-one-class forbids.

#: (backend class, core class reached by the same name, signed word, unsigned word,
#:  unsigned class)
UNSIGNED_PAIRS = [
    (ClickHouseInt8Type, TinyIntType, "Int8", "UInt8", "ClickHouseUInt8Type"),
    (ClickHouseInt16Type, SmallIntType, "Int16", "UInt16", "ClickHouseUInt16Type"),
    (ClickHouseInt32Type, IntegerType, "Int32", "UInt32", "ClickHouseUInt32Type"),
    (ClickHouseInt64Type, BigIntType, "Int64", "UInt64", "ClickHouseUInt64Type"),
]


class TestUnsignedIsRefusedNotDropped:
    @pytest.mark.parametrize(
        "signed, core, signed_word, unsigned_word, unsigned_class",
        UNSIGNED_PAIRS, ids=[pair[2] for pair in UNSIGNED_PAIRS])
    def test_signed_rendering_is_unchanged(
        self, signed, core, signed_word, unsigned_word, unsigned_class):
        """The default declaration still renders exactly what it always did."""
        dialect = ClickHouseDialect(version=(26, 7, 0))
        assert signed(dialect).to_sql()[0] == signed_word
        assert dialect.format_data_type(core(dialect))[0] == signed_word

    @pytest.mark.parametrize(
        "signed, core, signed_word, unsigned_word, unsigned_class",
        UNSIGNED_PAIRS, ids=[pair[2] for pair in UNSIGNED_PAIRS])
    def test_unsigned_on_the_signed_class_raises(
        self, signed, core, signed_word, unsigned_word, unsigned_class):
        """Both dispatch keys refuse, because both can receive the flag.

        ``clickhouse_int8`` and ``tinyint`` are different dispatch keys for the
        same concept, and ``unsigned`` is a field on the concept — so a caller who
        reaches it through ``TinyIntType(unsigned=True)`` must be refused just as
        loudly as one who reaches it through ``ClickHouseInt8Type(unsigned=True)``.
        """
        from rhosocial.activerecord.backend.dialect.exceptions import (
            UnsupportedFeatureError,
        )
        dialect = ClickHouseDialect(version=(26, 7, 0))
        for declaration in (signed(dialect, unsigned=True), core(dialect, unsigned=True)):
            with pytest.raises(UnsupportedFeatureError) as excinfo:
                declaration.to_sql()
            message = str(excinfo.value)
            assert "unsigned" in message
            assert signed_word in message, "the error must name the width"
            assert unsigned_class in message, "the error must say what to use"

    def test_before_the_fix_the_sql_was_identical(self):
        """What the defect was, stated as an executable claim.

        Two declarations the framework treats as two different columns — they are
        ``!=`` because ``unsigned`` is in ``PARAMETERS`` — used to render the same
        SQL. The only thing this backend may do about that is refuse one of them.
        """
        dialect = ClickHouseDialect(version=(26, 7, 0))
        signed = ClickHouseInt8Type(dialect)
        unsigned = ClickHouseInt8Type(dialect, unsigned=True)
        assert signed != unsigned, "unsigned must still be part of the identity"
        assert signed.unsigned is False and unsigned.unsigned is True

    @pytest.mark.parametrize(
        "signed, core, signed_word, unsigned_word, unsigned_class",
        UNSIGNED_PAIRS, ids=[pair[2] for pair in UNSIGNED_PAIRS])
    def test_the_unsigned_class_owns_the_unsigned_column(
        self, signed, core, signed_word, unsigned_word, unsigned_class):
        """One concept, one class: the unsigned column belongs to ``UInt*``.

        The class pins ``unsigned=True`` in its own ``__init__`` and takes no flag,
        so there is nothing for its formatter to refuse and the ``supports_*``
        1:1 pair keeps answering ``True``.
        """
        dialect = ClickHouseDialect(version=(26, 7, 0))
        declaration = getattr(clickhouse_types, unsigned_class)(dialect)
        assert declaration.unsigned is True
        assert declaration.to_sql()[0] == unsigned_word
        # dispatch is by name, so the 1:1 support method is the one named after it
        assert getattr(dialect, f"supports_data_type_{declaration.name}")() is True

    def test_a_signed_and_an_unsigned_declaration_are_different_columns(self):
        """The differ's input is different, so the renderer must not be silent."""
        dialect = ClickHouseDialect(version=(26, 7, 0))
        assert ClickHouseInt8Type(dialect) != ClickHouseUInt8Type(dialect)
        assert len({ClickHouseInt8Type(dialect), ClickHouseUInt8Type(dialect)}) == 2


class TestUnsignedFloatAndDecimalAreRefused:
    """ClickHouse's ``UInt8``…``UInt64`` are **integer families of their own**, and
    ``Decimal`` / ``Float32`` / ``Float64`` have no unsigned counterpart at all — so
    ``unsigned`` on those three is **refused**.

    Measured on the wired scenario server, 26.7.3.19:

    * ``system.data_type_families`` names 140 families. The eight whose names
      contain ``UNSIGNED`` are all integer *aliases* and every one resolves to a
      ``UInt`` family — ``TINYINT UNSIGNED``/``INT1 UNSIGNED`` → ``UInt8``,
      ``SMALLINT UNSIGNED`` → ``UInt16``,
      ``MEDIUMINT UNSIGNED``/``INT UNSIGNED``/``INTEGER UNSIGNED`` → ``UInt32``,
      ``BIGINT UNSIGNED``/``UNSIGNED`` → ``UInt64``. There is **no** unsigned float or
      decimal family among them, and the float and decimal families' own ``syntax``
      strings are the whole of their grammar: ``Float32``, ``Float64``,
      ``Decimal(P, S)``, ``Decimal32(S)``…``Decimal256(S)``, ``BFloat16``.
    * Nothing parses with the attribute appended. ``Decimal(10, 2) UNSIGNED``,
      ``Decimal(10, 0) UNSIGNED``, ``Float32 UNSIGNED``, ``Float32(10) UNSIGNED`` and
      ``Float64 UNSIGNED`` are all ``SYNTAX_ERROR`` code 62,
      ``failed at position N (UNSIGNED)``. The expected-token list the server prints
      back — ``COLLATE, NOT, NULL, DEFAULT, MATERIALIZED, ALIAS, EPHEMERAL,
      AUTO_INCREMENT, COMMENT, CODEC, STATISTICS, TTL, PRIMARY KEY, SETTINGS, token,
      Comma, ClosingRoundBracket`` — is everything that may follow a column type, and
      no signedness attribute is on it. The **inline** ``CHECK (c >= 0)`` is rejected
      by the same rule at the same position: the slot does not exist.
    * Signedness in the name means the unsigned integers are a different kind of
      thing, not a decorated one: ``CAST(-1 AS UInt8)`` is ``255``, while
      ``CAST(-1 AS Float32)``, ``CAST(-1 AS Float64)`` and
      ``CAST(-1 AS Decimal(10,2))`` are all ``-1``. So no reachable value differs,
      and the only way to make one differ is to leave the float family.

    **The route forward is not the ``CHECK`` the other four backends suggest**, and
    that difference is measured too: ``CREATE TABLE t (c Float32 CHECK (c >= 0))``
    fails with the same code-62 syntax error as ``UNSIGNED``, while
    ``CREATE TABLE t (c Float32, CONSTRAINT cc CHECK (c >= 0))`` is accepted and
    ``INSERT INTO t VALUES (-1)`` then fails with code 469,
    ``Constraint 'cc' ... is violated ... Column values: c = -1``. ClickHouse does
    enforce the constraint; it just has nowhere to put an inline one.
    """

    #: ``(label, class, builder, signed SQL, the ClickHouse word the refusal
    #: names)``.
    _FLOATS_AND_DECIMALS = [
        ("decimal", DecimalType,
         lambda d, u: DecimalType(d, 10, 2, unsigned=u),
         "Decimal(10, 2)", "Decimal(P, S)"),
        ("float", FloatType,
         lambda d, u: FloatType(d, unsigned=u),
         "Float32", "Float32"),
        ("double", DoubleType,
         lambda d, u: DoubleType(d, unsigned=u),
         "Float64", "Float64"),
        ("real", RealType,
         lambda d, u: RealType(d, unsigned=u),
         "Float32", "Float32"),
    ]
    _IDS = [row[0] for row in _FLOATS_AND_DECIMALS]

    def _dialect(self):
        return ClickHouseDialect(version=(26, 7, 0))

    @pytest.mark.parametrize("label,klass,build,signed_sql,word",
                             _FLOATS_AND_DECIMALS, ids=_IDS)
    def test_unsigned_is_refused_by_name(self, label, klass, build, signed_sql,
                                         word):
        """The rule: the field is in ``PARAMETERS``, so it must reach the SQL or
        flip must raise. Byte-identical SQL for both signs is the violation — and
        it is exactly what all four of these formatters used to produce."""
        from rhosocial.activerecord.backend.dialect.exceptions import (
            UnsupportedFeatureError,
        )
        dialect = self._dialect()
        with pytest.raises(UnsupportedFeatureError) as excinfo:
            dialect.format_data_type(build(dialect, True))
        message = str(excinfo.value)
        assert "unsigned" in message
        assert word in message, "the error must name the type that has no variant"
        assert "type NAME" in message, (
            "the error must say where ClickHouse puts signedness instead"
        )

    @pytest.mark.parametrize("label,klass,build,signed_sql,word",
                             _FLOATS_AND_DECIMALS, ids=_IDS)
    def test_the_refusal_points_at_the_table_level_constraint(
            self, label, klass, build, signed_sql, word):
        """``CHECK`` is the route forward on four backends and is a **syntax error**
        on this one; only the named table-level form is accepted, and the server
        enforces it. Suggesting the inline form would be worse than saying nothing.
        """
        from rhosocial.activerecord.backend.dialect.exceptions import (
            UnsupportedFeatureError,
        )
        dialect = self._dialect()
        with pytest.raises(UnsupportedFeatureError) as excinfo:
            dialect.format_data_type(build(dialect, True))
        suggestion = excinfo.value.suggestion or ""
        assert "CONSTRAINT" in suggestion, suggestion
        assert "469" in suggestion, suggestion
        assert "syntax error" in suggestion, suggestion

    @pytest.mark.parametrize("label,klass,build,signed_sql,word",
                             _FLOATS_AND_DECIMALS, ids=_IDS)
    def test_the_signed_form_is_byte_identical_to_what_it_was(
            self, label, klass, build, signed_sql, word):
        dialect = self._dialect()
        assert dialect.format_data_type(build(dialect, False)) == (signed_sql, ())
        # The bare declaration is a different column for ``decimal`` — this dialect
        # fills its own ``Decimal(10, 0)`` default in — and the same one for the
        # three floats, so it is compared against its own rendering rather than the
        # builder's.
        bare = dialect.format_data_type(klass(dialect))[0]
        assert bare == ("Decimal(10, 0)" if label == "decimal" else signed_sql)

    @pytest.mark.parametrize("label,klass,build,signed_sql,word",
                             _FLOATS_AND_DECIMALS, ids=_IDS)
    def test_signedness_still_participates_in_equality(self, label, klass, build,
                                                       signed_sql, word):
        """Why refusing is the right answer: the two declarations are genuinely
        different types, so the differ can see a caller changed their mind. Refusing
        at render time stops the DDL lying about that; it must not flatten the
        model instead."""
        dialect = self._dialect()
        signed, unsigned = build(dialect, False), build(dialect, True)
        assert signed != unsigned
        assert hash(signed) != hash(unsigned)

    def test_unsigned_is_appended_so_hashes_are_stable(self):
        """Appended, never inserted: the order of ``PARAMETERS`` is what
        ``identity()`` reads, so it is what ``__eq__`` and ``__hash__`` read."""
        assert DecimalType.PARAMETERS == ("precision", "scale", "unsigned")
        assert FloatType.PARAMETERS == ("precision", "unsigned")
        assert DoubleType.PARAMETERS == ("unsigned",)
        assert RealType.PARAMETERS == ("unsigned",)

    def test_the_native_float_and_decimal_classes_cannot_be_given_the_field(self):
        """Why the refusal lives on the four core concepts and not on
        ``clickhouse_float32`` / ``clickhouse_float64`` / ``clickhouse_decimal*``.

        Those classes narrow ``PARAMETERS`` to ``()`` and their ``__init__`` takes
        no ``unsigned``, so the flag is *pinned* — there is no reachable
        declaration to drop. The core concepts are the four a caller reaches by the
        plain SQL words ``DECIMAL`` / ``FLOAT`` / ``DOUBLE`` / ``REAL``, and those
        are the four that must answer.
        """
        dialect = self._dialect()
        for name in ("ClickHouseFloat32Type", "ClickHouseFloat64Type",
                     "ClickHouseDecimal32Type", "ClickHouseDecimal64Type",
                     "ClickHouseDecimal128Type"):
            klass = getattr(clickhouse_types, name)
            assert "unsigned" not in klass.PARAMETERS, name
            assert klass(dialect).unsigned is False, name
        with pytest.raises(TypeError):
            clickhouse_types.ClickHouseFloat32Type(dialect, unsigned=True)

    def test_a_type_string_carrying_unsigned_is_refused_rather_than_read(self):
        """The same rule in the *reading* direction.

        Every numeric branch of ``parse_type`` matches on the word in front of the
        attribute, so without a check ``parse_type("Float32 UNSIGNED")`` was a signed
        ``ClickHouseFloat32Type`` and ``parse_type("Decimal(10,2) UNSIGNED")`` was
        ``ClickHouseDecimalType(10, 2)`` — value objects ``==`` calls equal to the
        signed column, so the differ reported no change for the one change the
        string describes.

        The MySQL-style integer aliases ClickHouse **does** accept (``TINYINT
        UNSIGNED`` and friends, which the server resolves to ``UInt8``…``UInt64``)
        are spellings of a column rather than an attribute tacked onto one, so they
        are read as the ``UInt`` family they name — see
        :meth:`test_the_mysql_unsigned_aliases_are_read_as_the_uint_family` — and
        this refusal must not swallow them.
        """
        from rhosocial.activerecord.backend.dialect.exceptions import (
            UnsupportedFeatureError,
        )
        dialect = self._dialect()
        for raw in ("Float32 UNSIGNED", "Float64 UNSIGNED",
                    "Decimal(10,2) UNSIGNED", "Decimal(10, 2) UNSIGNED",
                    "Int8 UNSIGNED", "Int32 UNSIGNED"):
            with pytest.raises(UnsupportedFeatureError) as excinfo:
                dialect.parse_type(raw)
            assert "UNSIGNED" in str(excinfo.value), raw
        # ... and the unsigned-free strings of the same shapes are untouched.
        assert dialect.parse_type("Float32") == clickhouse_types.ClickHouseFloat32Type(
            dialect)
        assert dialect.parse_type("Decimal(10, 2)") == (
            clickhouse_types.ClickHouseDecimalType(dialect, precision=10, scale=2))
        # ... and a real UInt column still reads back as unsigned.
        assert dialect.parse_type("UInt8").unsigned is True

    #: ``(alias, class, the native word it renders)``.  Every alias is
    #: ``case_insensitive = 1`` in ``system.data_type_families`` with the matching
    #: ``alias_to``, measured on 26.7.3.19; the live half of the check is
    #: ``types/test_native_types.py::TestSignednessIsInTheTypeName``.
    _UNSIGNED_ALIASES = [
        ("TINYINT UNSIGNED", ClickHouseUInt8Type, "UInt8"),
        ("INT1 UNSIGNED", ClickHouseUInt8Type, "UInt8"),
        ("SMALLINT UNSIGNED", ClickHouseUInt16Type, "UInt16"),
        ("YEAR", ClickHouseUInt16Type, "UInt16"),
        ("MEDIUMINT UNSIGNED", ClickHouseUInt32Type, "UInt32"),
        ("INT UNSIGNED", ClickHouseUInt32Type, "UInt32"),
        ("INTEGER UNSIGNED", ClickHouseUInt32Type, "UInt32"),
        ("BIGINT UNSIGNED", ClickHouseUInt64Type, "UInt64"),
        ("UNSIGNED", ClickHouseUInt64Type, "UInt64"),
    ]
    _UNSIGNED_ALIAS_IDS = [row[0] for row in _UNSIGNED_ALIASES]

    @pytest.mark.parametrize("raw, klass, rendered", _UNSIGNED_ALIASES,
                             ids=_UNSIGNED_ALIAS_IDS)
    def test_the_mysql_unsigned_aliases_are_read_as_the_uint_family(
            self, raw, klass, rendered):
        """One concept, one class: every alias yields the class that owns the column.

        ``parse_type("TINYINT UNSIGNED")`` used to raise through the ``CustomType``
        validation, because a two-word name is not in the core grammar's multi-word
        list.  The server accepts it and resolves it to ``UInt8``, so the parser
        hands back ``ClickHouseUInt8Type`` — not a synonym, not the signed class —
        and ``format_data_type`` writes the native spelling.  That is what makes an
        aliased DDL string equal to the column it creates.
        """
        dialect = self._dialect()
        parsed = dialect.parse_type(raw)
        assert parsed == klass(dialect), raw
        assert parsed.unsigned is True, raw
        assert dialect.format_data_type(parsed)[0] == rendered, raw
        # The server records these as case-insensitive; the parser upper-cases,
        # so the lower-case spelling must reach the same class.
        assert dialect.parse_type(raw.lower()) == klass(dialect), raw

    @pytest.mark.parametrize("case,expected", [
        # the pre-existing ValueErrors, still firing for a *signed* declaration
        ("decimal_precision", ValueError),
        ("decimal_scale", ValueError),
    ])
    def test_every_pre_existing_check_still_fires_for_a_signed_declaration(
            self, case, expected):
        """Nothing moved except the signedness refusal.

        The two bounds below live in ``ClickHouseDecimalType.__init__`` rather than
        in a formatter — this backend fixes the precision at the width and validates
        it where the value enters — so the ``raises`` block wraps the construction,
        which is where the ``ValueError`` has always come from.
        """
        dialect = self._dialect()
        with pytest.raises(expected):
            {
                "decimal_precision": clickhouse_types.ClickHouseDecimalType(
                    dialect, precision=99),
                "decimal_scale": clickhouse_types.ClickHouseDecimalType(
                    dialect, precision=10, scale=99),
            }[case]

    def test_the_signedness_gate_runs_before_the_spelling_gate(self):
        """A request wrong in two ways is told about the right one first.

        Signedness is a declaration this grammar cannot express **at all**, which is
        a stronger and less recoverable statement than a misspelled word, so the
        refusal comes first.
        """
        from rhosocial.activerecord.backend.dialect.exceptions import (
            UnsupportedFeatureError,
        )
        dialect = self._dialect()
        for built in (DecimalType(dialect, 10, 2, spelling="fixed", unsigned=True),
                      DoubleType(dialect, spelling="float", unsigned=True)):
            with pytest.raises(UnsupportedFeatureError) as excinfo:
                dialect.format_data_type(built)
            assert "unsigned" in str(excinfo.value).lower()

    def test_the_refusal_is_not_a_value_error(self):
        """The cross-backend exception convention, stated as a test: a wrong value
        is ``ValueError``; a declaration this grammar cannot express at all is
        ``UnsupportedFeatureError``; the two do not share a base class."""
        from rhosocial.activerecord.backend.dialect.exceptions import (
            UnsupportedFeatureError,
        )
        assert not issubclass(UnsupportedFeatureError, ValueError)
        with pytest.raises(UnsupportedFeatureError):
            self._dialect().format_data_type(
                DecimalType(self._dialect(), unsigned=True))


# ── The vector type renders ClickHouse's word, not MySQL's ─────────────

class TestVectorRendersQBit:
    """``ClickHouseVectorType`` renders ``QBit(Float32, n)``, not ``VECTOR(n)``.

    ``VECTOR(n)`` is **MySQL 9.0's** spelling and was carried into this backend
    together with MySQL's ``STRING_TO_VECTOR`` / ``VECTOR_DIM`` / ``DISTANCE_*``
    family. ClickHouse has no such type: on the 26.7 scenario server
    ``CREATE TABLE t (a VECTOR(4))`` returns
    ``Unknown data type family: VECTOR``, and ``system.data_type_families``
    lists ``QBit`` and no ``VECTOR`` entry. ClickHouse's own vector type is
    ``QBit(element_type, dimension[, stride])`` —
    https://clickhouse.com/docs/reference/data-types/qbit
    """

    def test_rendered_sql_is_the_documented_qbit_spelling(self):
        dialect = ClickHouseDialect(version=(26, 7, 0))
        sql, params = ClickHouseVectorType(dialect, dim=4).to_sql()
        assert sql == "QBit(Float32, 4)"
        assert params == ()

    @pytest.mark.parametrize("dim", [3, 4, 128, 1536])
    def test_dimension_is_carried_through(self, dim):
        dialect = ClickHouseDialect(version=(26, 7, 0))
        assert dialect.format_data_type(
            ClickHouseVectorType(dialect, dim=dim))[0] == f"QBit(Float32, {dim})"

    def test_it_does_not_render_the_mysql_spelling(self):
        """The regression this whole class exists for.

        Rendering ``VECTOR(n)`` produced DDL the server refuses, which is worse
        than not supporting the type at all: it fails at ``CREATE TABLE`` time, on
        a statement the framework itself built.
        """
        dialect = ClickHouseDialect(version=(26, 7, 0))
        sql, _ = ClickHouseVectorType(dialect, dim=4).to_sql()
        assert "VECTOR" not in sql.upper()

    # ── version gate ────────────────────────────────────────────────────
    #
    # QBit appeared in 25.10 behind ``allow_experimental_qbit_type``, was promoted
    # to Beta in 26.1 and to General Availability in 26.2. The gate is GA: before
    # 26.2 a column declaration still needs an experimental opt-in that DDL does
    # not carry.

    @pytest.mark.parametrize("version", [(26, 2, 0), (26, 3, 0), (26, 7, 3)])
    def test_supported_from_ga_onwards(self, version):
        dialect = ClickHouseDialect(version=version)
        assert dialect.format_data_type(
            ClickHouseVectorType(dialect, dim=8))[0] == "QBit(Float32, 8)"

    @pytest.mark.parametrize("version", [(25, 8, 0), (25, 10, 0), (26, 1, 0)])
    def test_refused_before_ga(self, version):
        from rhosocial.activerecord.backend.dialect.exceptions import (
            UnsupportedFeatureError,
        )
        dialect = ClickHouseDialect(version=version)
        with pytest.raises(UnsupportedFeatureError) as excinfo:
            dialect.format_data_type(ClickHouseVectorType(dialect, dim=8))
        message = str(excinfo.value)
        assert "QBit" in message
        assert "Array(Float32)" in message, "the error must say what to use instead"

    def test_unadapted_dialect_refuses_rather_than_guessing(self):
        """No version means no guarantee, and an unguessed guess is the defect.

        The dialect has not talked to a server, so it cannot know whether ``QBit``
        is available — emitting it blind would reintroduce exactly the failure
        this fix removes.
        """
        from rhosocial.activerecord.backend.dialect.exceptions import (
            DialectNotAdaptedException,
        )
        dialect = ClickHouseDialect()
        with pytest.raises(DialectNotAdaptedException):
            dialect.format_data_type(ClickHouseVectorType(dialect, dim=8))

    # ── parse_type, which is what introspection actually calls ──────────

    @pytest.mark.parametrize("raw", [
        "QBit(Float32, 8)",
        "QBit(Float64, 1536)",
        "QBit(BFloat16, 5)",
        "QBit(Int8, 2048)",
    ])
    def test_parse_reads_the_dimension_not_the_element_type(self, raw):
        """The server reports ``QBit(Float32, 8)`` — checked with DESCRIBE on 26.7.

        The obvious implementation, scanning for the first digit run, reads the
        ``32`` out of ``Float32`` and reports an 8-dimensional column as
        32-dimensional. The dimension is the first argument that is a *bare*
        integer, which is exactly why the element type must be skipped rather
        than parsed.
        """
        dialect = ClickHouseDialect(version=(26, 7, 0))
        expected = int(raw[raw.rindex(",") + 1: raw.rindex(")")])
        assert dialect.parse_type(raw) == ClickHouseVectorType(dialect, dim=expected)

    def test_parse_keeps_the_dimension_of_a_strided_qbit(self):
        """``stride`` was added in 26.7; it is a third argument, not the dimension."""
        dialect = ClickHouseDialect(version=(26, 7, 0))
        assert dialect.parse_type("QBit(Float32, 16, 8)") == \
            ClickHouseVectorType(dialect, dim=16)

    @pytest.mark.parametrize("dim", [8, 1536])
    def test_parse_then_render_is_a_fixed_point(self, dim):
        dialect = ClickHouseDialect(version=(26, 7, 0))
        raw = f"QBit(Float32, {dim})"
        assert dialect.format_data_type(dialect.parse_type(raw))[0] == raw

    @pytest.mark.parametrize("element_type", ["BFloat16", "Float64", "Int8"])
    def test_parse_loses_the_element_type(self, element_type):
        """Known lossiness, asserted so it stays a decision.

        ``QBit``'s element type is part of its SQL form but not part of
        :class:`ClickHouseVectorType`'s identity, so a column introspected as
        ``QBit(BFloat16, 1536)`` comes back as ``QBit(Float32, 1536)``. The
        *dimension* — the part this class does model, and the part that cannot
        change without rewriting the column — round-trips exactly. Carrying the
        element type would mean making it part of the class's identity, which is
        a wider change than fixing a wrong spelling; reported rather than fixed.
        """
        dialect = ClickHouseDialect(version=(26, 7, 0))
        parsed = dialect.parse_type(f"QBit({element_type}, 1536)")
        assert parsed == ClickHouseVectorType(dialect, dim=1536)
        assert dialect.format_data_type(parsed)[0] == "QBit(Float32, 1536)"

    def test_mysql_vector_spelling_is_not_a_clickhouse_type(self):
        """``VECTOR(4)`` is not ClickHouse's, so ``parse_type`` must not claim it.

        It falls through to ``CustomType``, which cannot be rendered — the same
        treatment an unclaimed word gets.  ``VARCHAR(10)`` is the sharper
        example: the server *accepts* it (it resolves to ``String``), but this
        parser does not claim it, so it too falls to ``CustomType``.
        """
        from rhosocial.activerecord.backend.expression.types import CustomType
        dialect = ClickHouseDialect(version=(26, 7, 0))
        assert isinstance(dialect.parse_type("VECTOR(4)"), CustomType)


# ── the rest of MySQL's vector API is not here at all ─────────────────
#
# ``VECTOR(n)`` is only the visible end of the imported surface. The same commit
# brought ``STRING_TO_VECTOR`` / ``VECTOR_TO_STRING`` / ``VECTOR_DIM`` /
# ``DISTANCE_*`` and a ``MAX_VECTOR_DIMENSION = 16384`` ceiling, all MySQL's. On
# the 26.7 scenario server none of the functions exists — each answers
# ``Function with name `...` does not exist`` — and 16384 is MySQL's limit for a
# type ClickHouse does not have. The surface is therefore deleted rather than
# stubbed; the live half of that evidence is in ``types/test_native_types.py``.

MYSQL_VECTOR_FUNCTIONS = (
    "STRING_TO_VECTOR",
    "VECTOR_TO_STRING",
    "VECTOR_DIM",
    "DISTANCE_EUCLIDEAN",
    "DISTANCE_COSINE",
    "DISTANCE_DOT",
)

#: The dialect methods the deleted ``ClickHouseVectorSupport`` / mixin declared.
MYSQL_VECTOR_DIALECT_METHODS = (
    "supports_vector_type",
    "supports_vector_index",
    "get_max_vector_dimension",
    "format_vector_literal",
    "format_string_to_vector",
    "format_vector_to_string",
    "format_vector_dim",
    "format_distance_euclidean",
    "format_distance_cosine",
    "format_distance_dot",
    "format_create_vector_index",
)


class TestMySQLVectorSurfaceIsGone:
    """The MySQL surface is **absent**, not stubbed.

    Keeping it as a fail-fast stub was the state this class replaces, and it had a
    defect beyond being dead weight: ``supports_vector_type()`` answered ``False``
    on the same dialect where ``supports_data_type_clickhouse_vector()`` answers
    ``True`` and renders ``QBit(Float32, n)``. Two capability flags on one dialect
    disagreeing about whether ClickHouse has a vector type is worse than silence —
    ``get_max_vector_dimension()`` then returned MySQL's 16384 for a type this
    backend does not have.

    ClickHouse's real vector functions are ``L2Distance``, ``cosineDistance``,
    ``dotProduct`` (and the ``*Transposed`` trio for ``QBit`` columns):
    https://clickhouse.com/docs/reference/functions/regular-functions/distance-functions
    """

    @pytest.mark.parametrize("method", MYSQL_VECTOR_DIALECT_METHODS)
    def test_the_dialect_has_no_such_method(self, method):
        dialect = ClickHouseDialect(version=(26, 7, 0))
        assert not hasattr(dialect, method), (
            f"{method} is MySQL's; ClickHouse's vector type is QBit"
        )

    def test_no_protocol_declares_it(self):
        from rhosocial.activerecord.backend.impl.clickhouse import protocols
        assert not [name for name in vars(protocols) if "Vector" in name]
        assert not hasattr(protocols, "ClickHouseVectorSupport")

    def test_no_mixin_implements_it(self):
        from rhosocial.activerecord.backend.impl.clickhouse import mixins
        assert not hasattr(mixins, "ClickHouseVectorMixin")
        assert not [name for name in vars(mixins) if "VectorMixin" in name]

    @pytest.mark.parametrize("function_name", MYSQL_VECTOR_FUNCTIONS)
    def test_no_expression_node_claims_to_render_it(self, function_name):
        """No expression class advertises a ``format_method`` the dialect cannot have.

        The deleted nodes each returned e.g. ``"format_string_to_vector"`` from
        ``format_method``; a node whose dispatcher name the dialect does not define
        is a node that fails with ``AttributeError`` rather than with an
        ``UnsupportedFeatureError`` that says what to use.
        """
        from rhosocial.activerecord.backend.impl.clickhouse import expression as expr

        wanted = "format_" + function_name.lower()
        offending = []
        for name in expr.__all__:
            klass = getattr(expr, name, None)
            if not (isinstance(klass, type) and hasattr(klass, "format_method")):
                continue
            # every concrete getter returns a literal, so the class is a
            # sufficient stand-in for an instance; an abstract one raises
            try:
                dispatcher = klass.format_method.fget(klass)
            except NotImplementedError:
                continue
            if dispatcher == wanted:
                offending.append(name)
        assert not offending, offending

    def test_the_capability_flag_no_longer_contradicts_itself(self):
        """The concept this backend *does* support keeps answering for itself."""
        dialect = ClickHouseDialect(version=(26, 7, 0))
        assert dialect.supports_data_type_clickhouse_vector() is True
        assert dialect.format_data_type(
            ClickHouseVectorType(dialect, dim=4))[0] == "QBit(Float32, 4)"


# ---------------------------------------------------------------------------
# parse_type: the sweep, and the two words it found unreadable
# ---------------------------------------------------------------------------


class TestGeometryCollectionIsNotTheGenericGeometry:
    """``GEOMETRYCOLLECTION`` begins with ``GEOMETRY``, and the map put

    ``GEOMETRY`` first, so the ``startswith`` loop read a collection column
    as the generic geometry type -- the same defect MariaDB's and MySQL's
    branches of this family each found and fixed, found here by the
    render-parse-re-render sweep. Dispatch is on the leading word now,
    which is the whole name for every one of the eight words.
    """

    def test_a_collection_is_not_the_generic_geometry_type(self):
        from rhosocial.activerecord.backend.impl.clickhouse.expression.types import (
            ClickHouseGeometryCollectionType,
            ClickHouseGeometryType,
        )

        dialect = ClickHouseDialect()
        collection = dialect.parse_type("GEOMETRYCOLLECTION")
        generic = dialect.parse_type("GEOMETRY")
        assert isinstance(collection, ClickHouseGeometryCollectionType)
        assert collection != generic
        assert type(collection) is not type(generic)

    @pytest.mark.parametrize("word,expected", [
        ("POINT", "ClickHousePointType"),
        ("LINESTRING", "ClickHouseLineStringType"),
        ("POLYGON", "ClickHousePolygonType"),
        ("MULTIPOINT", "ClickHouseMultiPointType"),
        ("MULTILINESTRING", "ClickHouseMultiLineStringType"),
        ("MULTIPOLYGON", "ClickHouseMultiPolygonType"),
        ("GEOMETRYCOLLECTION", "ClickHouseGeometryCollectionType"),
    ])
    def test_each_word_reads_back_as_its_own_shape(self, word, expected):
        dialect = ClickHouseDialect()
        assert type(dialect.parse_type(word)).__name__ == expected, word

    def test_srid_survives_the_dispatch(self):
        from rhosocial.activerecord.backend.impl.clickhouse.expression.types import (
            ClickHouseGeometryCollectionType,
        )

        dialect = ClickHouseDialect()
        parsed = dialect.parse_type("GEOMETRYCOLLECTION SRID 4326")
        assert isinstance(parsed, ClickHouseGeometryCollectionType)
        assert parsed.srid == 4326


class TestTupleElementsParseBack:
    """``Tuple(name Type, ...)`` -- the field names are part of the type.

    Live evidence on ClickHouse 26.7.3.19: the names are stored and
    reported (``system.columns.type`` / ``SHOW CREATE`` / ``DESCRIBE`` /
    ``toTypeName``), compared and hashed, used for ``tuple.name`` access,
    and matched during INSERT conversion -- see the class docstring in
    ``expression/types.py`` and the report's section A. The parse has to
    read them: handing ``"name Type"`` to ``parse_type`` whole fell through
    to ``CustomType``, whose type-name validation refused the space, so the
    dialect raised on its own rendering. The leading identifier is split
    off when a second word follows, and carried into ``element_names``
    because the class records them in PARAMETERS -- the assertions below
    pin that two tuples differing only in their names are different types.
    """

    def test_a_named_tuple_parses_back(self):
        from rhosocial.activerecord.backend.impl.clickhouse.expression.types import (
            ClickHouseTupleType,
            ClickHouseInt32Type,
        )

        dialect = ClickHouseDialect()
        parsed = dialect.parse_type("Tuple(a Int32)")
        assert isinstance(parsed, ClickHouseTupleType)
        assert parsed.element_types == (ClickHouseInt32Type(dialect),)
        assert parsed.element_names == ("a",)

    def test_a_bare_positional_tuple_parses_back(self):
        from rhosocial.activerecord.backend.impl.clickhouse.expression.types import (
            ClickHouseTupleType,
        )

        dialect = ClickHouseDialect()
        parsed = dialect.parse_type("Tuple(Int32, String)")
        assert isinstance(parsed, ClickHouseTupleType)
        assert len(parsed.element_types) == 2
        assert parsed.element_names is None

    def test_the_named_render_round_trips(self):
        from rhosocial.activerecord.backend.impl.clickhouse.expression.types import (
            ClickHouseTupleType,
            ClickHouseInt32Type,
        )

        dialect = ClickHouseDialect()
        declared = ClickHouseTupleType(
            dialect,
            element_types=[ClickHouseInt32Type(dialect)],
            element_names=["a"],
        )
        sql, _ = declared.to_sql()
        assert sql == "Tuple(a Int32)"
        assert dialect.parse_type(sql) == declared

    def test_tuples_differing_only_in_element_names_are_different(self):
        """The names are identity, not documentation.

        ``Tuple(a Int32)`` and ``Tuple(b Int32)`` are different columns to
        the server, and the differ relies on this inequality to emit the
        renaming ``ALTER ... MODIFY COLUMN``; a tuple with no names is
        different from either named one.
        """
        from rhosocial.activerecord.backend.impl.clickhouse.expression.types import (
            ClickHouseTupleType,
            ClickHouseInt32Type,
        )

        dialect = ClickHouseDialect()
        element = ClickHouseInt32Type(dialect)
        named_a = ClickHouseTupleType(
            dialect, element_types=[element], element_names=["a"],
        )
        named_b = ClickHouseTupleType(
            dialect, element_types=[element], element_names=["b"],
        )
        unnamed = ClickHouseTupleType(dialect, element_types=[element])
        assert named_a != named_b
        assert named_a != unnamed
        assert hash(named_a) != hash(named_b)
        assert hash(named_a) != hash(unnamed)


class TestParseRoundTripSweep:
    """The shared sweep across this backend's whole declared surface.

    Asserts the two invariants at once: **string stability** -- parsing a
    rendering and re-rendering the answer produces the identical string --
    and **class honesty** -- the answer is the declared instance, or the
    documented widening answer recorded below. Every answer here is
    string-stable; the widening table maps each core concept onto the
    ClickHouse class of the storage it renders (Int8..Int64, Float32/64,
    String for the text and byte families, DateTime for the temporal ones),
    and the backend's own classes parse back to themselves.
    """

    #: Core concept -> the backend class of the storage it renders here.
    WIDENING_ANSWERS = {
        "ArrayType": "ClickHouseArrayType",
        "BlobType": "ClickHouseStringType",
        "BooleanType": "ClickHouseBoolType",
        "DateTimeType": "ClickHouseDateTimeType",
        "DateType": "ClickHouseDateType",
        "TimeType": "ClickHouseDateTimeType",
        "TimestampType": "ClickHouseDateTimeType",
        "BigIntType": "ClickHouseInt64Type",
        "IntegerType": "ClickHouseInt32Type",
        "SmallIntType": "ClickHouseInt16Type",
        "TinyIntType": "ClickHouseInt8Type",
        "JsonType": "ClickHouseStringType",
        "DecimalType": "ClickHouseDecimalType",
        "DoubleType": "ClickHouseFloat64Type",
        "FloatType": "ClickHouseFloat32Type",
        "RealType": "ClickHouseFloat32Type",
        "CharType": "ClickHouseStringType",
        "TextType": "ClickHouseStringType",
        "VarCharType": "ClickHouseStringType",
        "UUIDType": "ClickHouseUUIDType",
        # The backend's own classes: same class back, the parameter
        # normalisation the parse applies (tuples for lists) is the only
        # difference, and the re-render is byte-identical.
        "ClickHouseAggregateFunctionType": "ClickHouseAggregateFunctionType",
        "ClickHouseArrayType": "ClickHouseArrayType",
        "ClickHouseLowCardinalityType": "ClickHouseLowCardinalityType",
        "ClickHouseMapType": "ClickHouseMapType",
        "ClickHouseNullableType": "ClickHouseNullableType",
        "ClickHouseSimpleAggregateFunctionType": "ClickHouseSimpleAggregateFunctionType",
        "ClickHouseTupleType": "ClickHouseTupleType",
    }

    @pytest.fixture(scope="class")
    def registry(self):
        """The round-trip module's registry, loaded from the parent

        directory. Executing it also registers its special constructors,
        which the sweep's ``make_instance`` consults -- the same
        registrations the full suite performs at collection time.
        """
        import importlib.util
        from pathlib import Path

        path = Path(__file__).resolve().parent.parent / (
            "test_expression_roundtrip_all.py"
        )
        spec = importlib.util.spec_from_file_location(
            "clickhouse_rt_registry",
            path,
        )
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        registry = getattr(module, "ALL_CLASSES", None) or module.REGISTERED
        assert registry, "the round-trip module exposes no registry"
        return registry

    def test_every_rendered_type_parses_back_coherently(self, registry):
        from rhosocial.activerecord.testsuite.utils.parse_contract import (
            parse_roundtrip_failures,
        )

        dialect = ClickHouseDialect()
        failures = parse_roundtrip_failures(
            dialect,
            registry,
            widening=self.WIDENING_ANSWERS,
        )
        assert failures == [], "\n".join(failures)


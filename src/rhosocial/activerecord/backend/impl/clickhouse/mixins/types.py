# src/rhosocial/activerecord/backend/impl/clickhouse/mixins/types.py
"""ClickHouse DataType formatting and parsing mixin."""

from __future__ import annotations

import re
from typing import Dict, Tuple

from rhosocial.activerecord.backend.dialect.mixins.ddl_type import DDLTypeMixin
from rhosocial.activerecord.backend.dialect.protocols import DDLTypeSupport
from rhosocial.activerecord.backend.expression.types import (
    ArrayType,
    BigIntType,
    BlobType,
    BooleanType,
    CharType,
    DataType,
    DateType,
    DateTimeType,
    DecimalType,
    DoubleType,
    FloatType,
    IntegerType,
    JsonType,
    RealType,
    SmallIntType,
    TextType,
    TimeType,
    TimestampType,
    TinyIntType,
    VarCharType,
)
from ..expression.types import (
    ClickHouseAggregateFunctionType,
    ClickHouseArrayType,
    ClickHouseBoolType,
    ClickHouseDate32Type,
    ClickHouseDateType,
    ClickHouseDateTime64Type,
    ClickHouseDateTimeType,
    ClickHouseDecimal32Type,
    ClickHouseDecimal64Type,
    ClickHouseDecimal128Type,
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


class ClickHouseTypeSupportMixin(DDLTypeMixin, DDLTypeSupport):
    """ClickHouse DataType formatting and parsing.

    Implements ``DDLTypeSupport`` so the dialect can render ``DataType``
    expressions to SQL strings and parse raw SQL type strings back into
    ``DataType`` instances.

    Formatting dispatches by the type instance's ``name`` through the
    naming-convention ``format_data_type_<name>`` methods (see
    ``DDLTypeMixin``). ClickHouse-specific types carry ``clickhouse_``-prefixed
    names; core types render their real ClickHouse SQL.
    """

    # ------------------------------------------------------------------
    # DDLTypeSupport — formatting
    # ------------------------------------------------------------------

    # --- ClickHouse-specific type formatters (dispatch key = type name) ---

    def format_data_type_clickhouse_int8(self, data_type: ClickHouseInt8Type) -> Tuple[str, tuple]:
        return "Int8", ()

    def format_data_type_clickhouse_int16(self, data_type: ClickHouseInt16Type) -> Tuple[str, tuple]:
        return "Int16", ()

    def format_data_type_clickhouse_int32(self, data_type: ClickHouseInt32Type) -> Tuple[str, tuple]:
        return "Int32", ()

    def format_data_type_clickhouse_int64(self, data_type: ClickHouseInt64Type) -> Tuple[str, tuple]:
        return "Int64", ()

    def format_data_type_clickhouse_uint8(self, data_type: ClickHouseUInt8Type) -> Tuple[str, tuple]:
        return "UInt8", ()

    def format_data_type_clickhouse_uint16(self, data_type: ClickHouseUInt16Type) -> Tuple[str, tuple]:
        return "UInt16", ()

    def format_data_type_clickhouse_uint32(self, data_type: ClickHouseUInt32Type) -> Tuple[str, tuple]:
        return "UInt32", ()

    def format_data_type_clickhouse_uint64(self, data_type: ClickHouseUInt64Type) -> Tuple[str, tuple]:
        return "UInt64", ()

    def format_data_type_clickhouse_float32(self, data_type: ClickHouseFloat32Type) -> Tuple[str, tuple]:
        return "Float32", ()

    def format_data_type_clickhouse_float64(self, data_type: ClickHouseFloat64Type) -> Tuple[str, tuple]:
        return "Float64", ()

    def format_data_type_clickhouse_decimal(self, data_type: ClickHouseDecimalType) -> Tuple[str, tuple]:
        return f"Decimal({data_type.precision}, {data_type.scale})", ()

    def format_data_type_clickhouse_decimal32(self, data_type: ClickHouseDecimal32Type) -> Tuple[str, tuple]:
        return f"Decimal32({data_type.scale})", ()

    def format_data_type_clickhouse_decimal64(self, data_type: ClickHouseDecimal64Type) -> Tuple[str, tuple]:
        return f"Decimal64({data_type.scale})", ()

    def format_data_type_clickhouse_decimal128(self, data_type: ClickHouseDecimal128Type) -> Tuple[str, tuple]:
        return f"Decimal128({data_type.scale})", ()

    def format_data_type_clickhouse_string(self, data_type: ClickHouseStringType) -> Tuple[str, tuple]:
        return "String", ()

    def format_data_type_clickhouse_fixed_string(self, data_type: ClickHouseFixedStringType) -> Tuple[str, tuple]:
        return f"FixedString({data_type.length})", ()

    def format_data_type_clickhouse_date(self, data_type: ClickHouseDateType) -> Tuple[str, tuple]:
        return "Date", ()

    def format_data_type_clickhouse_date32(self, data_type: ClickHouseDate32Type) -> Tuple[str, tuple]:
        return "Date32", ()

    def format_data_type_clickhouse_datetime(self, data_type: ClickHouseDateTimeType) -> Tuple[str, tuple]:
        return "DateTime", ()

    def format_data_type_clickhouse_datetime64(self, data_type: ClickHouseDateTime64Type) -> Tuple[str, tuple]:
        return f"DateTime64({data_type.precision})", ()

    def format_data_type_clickhouse_bool(self, data_type: ClickHouseBoolType) -> Tuple[str, tuple]:
        return "Bool", ()

    def format_data_type_clickhouse_uuid(self, data_type: ClickHouseUUIDType) -> Tuple[str, tuple]:
        return "UUID", ()

    def format_data_type_clickhouse_ipv4(self, data_type: ClickHouseIPv4Type) -> Tuple[str, tuple]:
        return "IPv4", ()

    def format_data_type_clickhouse_ipv6(self, data_type: ClickHouseIPv6Type) -> Tuple[str, tuple]:
        return "IPv6", ()

    def format_data_type_clickhouse_enum8(self, data_type: ClickHouseEnum8Type) -> Tuple[str, tuple]:
        values_str = ", ".join(f"'{name}' = {num}" for name, num in data_type.values)
        return f"Enum8({values_str})", ()

    def format_data_type_clickhouse_enum16(self, data_type: ClickHouseEnum16Type) -> Tuple[str, tuple]:
        values_str = ", ".join(f"'{name}' = {num}" for name, num in data_type.values)
        return f"Enum16({values_str})", ()

    def format_data_type_clickhouse_array(self, data_type: ClickHouseArrayType) -> Tuple[str, tuple]:
        inner_sql, inner_params = self.format_data_type(data_type.element_type)
        return f"Array({inner_sql})", inner_params

    def format_data_type_clickhouse_map(self, data_type: ClickHouseMapType) -> Tuple[str, tuple]:
        key_sql, key_params = self.format_data_type(data_type.key_type)
        val_sql, val_params = self.format_data_type(data_type.value_type)
        return f"Map({key_sql}, {val_sql})", key_params + val_params

    def format_data_type_clickhouse_tuple(self, data_type: ClickHouseTupleType) -> Tuple[str, tuple]:
        parts = []
        params = []
        for i, elem_type in enumerate(data_type.element_types):
            elem_sql, elem_params = self.format_data_type(elem_type)
            if data_type.element_names:
                parts.append(f"{data_type.element_names[i]} {elem_sql}")
            else:
                parts.append(elem_sql)
            params.extend(elem_params)
        return f"Tuple({', '.join(parts)})", tuple(params)

    def format_data_type_clickhouse_nullable(self, data_type: ClickHouseNullableType) -> Tuple[str, tuple]:
        inner_sql, inner_params = self.format_data_type(data_type.inner_type)
        return f"Nullable({inner_sql})", inner_params

    def format_data_type_clickhouse_low_cardinality(self, data_type: ClickHouseLowCardinalityType) -> Tuple[str, tuple]:
        inner_sql, inner_params = self.format_data_type(data_type.inner_type)
        return f"LowCardinality({inner_sql})", inner_params

    def format_data_type_clickhouse_json(self, data_type: ClickHouseJSONType) -> Tuple[str, tuple]:
        return "JSON", ()

    def format_data_type_clickhouse_aggregate_function(self, data_type: ClickHouseAggregateFunctionType) -> Tuple[str, tuple]:
        args = ", ".join(self.format_data_type(t)[0] for t in data_type.arg_types)
        return f"AggregateFunction({data_type.function_name}, {args})", ()

    def format_data_type_clickhouse_simple_aggregate_function(
        self, data_type: ClickHouseSimpleAggregateFunctionType
    ) -> Tuple[str, tuple]:
        args = ", ".join(self.format_data_type(t)[0] for t in data_type.arg_types)
        return f"SimpleAggregateFunction({data_type.function_name}, {args})", ()

    def format_data_type_clickhouse_geometry(self, data_type: ClickHouseGeometryType) -> Tuple[str, tuple]:
        if data_type.srid is not None:
            return f"GEOMETRY SRID {data_type.srid}", ()
        return "GEOMETRY", ()

    def format_data_type_clickhouse_point(self, data_type: ClickHousePointType) -> Tuple[str, tuple]:
        if data_type.srid is not None:
            return f"POINT SRID {data_type.srid}", ()
        return "POINT", ()

    def format_data_type_clickhouse_linestring(self, data_type: ClickHouseLineStringType) -> Tuple[str, tuple]:
        if data_type.srid is not None:
            return f"LINESTRING SRID {data_type.srid}", ()
        return "LINESTRING", ()

    def format_data_type_clickhouse_polygon(self, data_type: ClickHousePolygonType) -> Tuple[str, tuple]:
        if data_type.srid is not None:
            return f"POLYGON SRID {data_type.srid}", ()
        return "POLYGON", ()

    def format_data_type_clickhouse_multipoint(self, data_type: ClickHouseMultiPointType) -> Tuple[str, tuple]:
        if data_type.srid is not None:
            return f"MULTIPOINT SRID {data_type.srid}", ()
        return "MULTIPOINT", ()

    def format_data_type_clickhouse_multilinestring(self, data_type: ClickHouseMultiLineStringType) -> Tuple[str, tuple]:
        if data_type.srid is not None:
            return f"MULTILINESTRING SRID {data_type.srid}", ()
        return "MULTILINESTRING", ()

    def format_data_type_clickhouse_multipolygon(self, data_type: ClickHouseMultiPolygonType) -> Tuple[str, tuple]:
        if data_type.srid is not None:
            return f"MULTIPOLYGON SRID {data_type.srid}", ()
        return "MULTIPOLYGON", ()

    def format_data_type_clickhouse_geometrycollection(self, data_type: ClickHouseGeometryCollectionType) -> Tuple[str, tuple]:
        if data_type.srid is not None:
            return f"GEOMETRYCOLLECTION SRID {data_type.srid}", ()
        return "GEOMETRYCOLLECTION", ()

    def format_data_type_clickhouse_vector(self, data_type: ClickHouseVectorType) -> Tuple[str, tuple]:
        return f"VECTOR({data_type.dim})", ()

    # ------------------------------------------------------------------
    # DDLTypeSupport — supports_data_type_* (1:1 with format_data_type_*)
    # ------------------------------------------------------------------

    def supports_data_type_clickhouse_int8(self) -> bool:
        return True

    def supports_data_type_clickhouse_int16(self) -> bool:
        return True

    def supports_data_type_clickhouse_int32(self) -> bool:
        return True

    def supports_data_type_clickhouse_int64(self) -> bool:
        return True

    def supports_data_type_clickhouse_uint8(self) -> bool:
        return True

    def supports_data_type_clickhouse_uint16(self) -> bool:
        return True

    def supports_data_type_clickhouse_uint32(self) -> bool:
        return True

    def supports_data_type_clickhouse_uint64(self) -> bool:
        return True

    def supports_data_type_clickhouse_float32(self) -> bool:
        return True

    def supports_data_type_clickhouse_float64(self) -> bool:
        return True

    def supports_data_type_clickhouse_decimal(self) -> bool:
        return True

    def supports_data_type_clickhouse_decimal32(self) -> bool:
        return True

    def supports_data_type_clickhouse_decimal64(self) -> bool:
        return True

    def supports_data_type_clickhouse_decimal128(self) -> bool:
        return True

    def supports_data_type_clickhouse_string(self) -> bool:
        return True

    def supports_data_type_clickhouse_fixed_string(self) -> bool:
        return True

    def supports_data_type_clickhouse_date(self) -> bool:
        return True

    def supports_data_type_clickhouse_date32(self) -> bool:
        return True

    def supports_data_type_clickhouse_datetime(self) -> bool:
        return True

    def supports_data_type_clickhouse_datetime64(self) -> bool:
        return True

    def supports_data_type_clickhouse_bool(self) -> bool:
        return True

    def supports_data_type_clickhouse_uuid(self) -> bool:
        return True

    def supports_data_type_clickhouse_ipv4(self) -> bool:
        return True

    def supports_data_type_clickhouse_ipv6(self) -> bool:
        return True

    def supports_data_type_clickhouse_enum8(self) -> bool:
        return True

    def supports_data_type_clickhouse_enum16(self) -> bool:
        return True

    def supports_data_type_clickhouse_array(self) -> bool:
        return True

    def supports_data_type_clickhouse_map(self) -> bool:
        return True

    def supports_data_type_clickhouse_tuple(self) -> bool:
        return True

    def supports_data_type_clickhouse_nullable(self) -> bool:
        return True

    def supports_data_type_clickhouse_low_cardinality(self) -> bool:
        return True

    def supports_data_type_clickhouse_json(self) -> bool:
        return True

    def supports_data_type_clickhouse_aggregate_function(self) -> bool:
        return True

    def supports_data_type_clickhouse_simple_aggregate_function(self) -> bool:
        return True

    def supports_data_type_clickhouse_geometry(self) -> bool:
        return True

    def supports_data_type_clickhouse_point(self) -> bool:
        return True

    def supports_data_type_clickhouse_linestring(self) -> bool:
        return True

    def supports_data_type_clickhouse_polygon(self) -> bool:
        return True

    def supports_data_type_clickhouse_multipoint(self) -> bool:
        return True

    def supports_data_type_clickhouse_multilinestring(self) -> bool:
        return True

    def supports_data_type_clickhouse_multipolygon(self) -> bool:
        return True

    def supports_data_type_clickhouse_geometrycollection(self) -> bool:
        return True

    def supports_data_type_clickhouse_vector(self) -> bool:
        return True

    # Core types that ClickHouse renders natively

    def supports_data_type_integer(self) -> bool:
        return True

    def supports_data_type_bigint(self) -> bool:
        return True

    def supports_data_type_smallint(self) -> bool:
        return True

    def supports_data_type_tinyint(self) -> bool:
        return True

    def supports_data_type_varchar(self) -> bool:
        return True

    def supports_data_type_char(self) -> bool:
        return True

    def supports_data_type_text(self) -> bool:
        return True

    def supports_data_type_boolean(self) -> bool:
        return True

    def supports_data_type_date(self) -> bool:
        return True

    def supports_data_type_datetime(self) -> bool:
        return True

    def supports_data_type_timestamp(self) -> bool:
        return True

    def supports_data_type_time(self) -> bool:
        return True

    def supports_data_type_float(self) -> bool:
        return True

    def supports_data_type_double(self) -> bool:
        return True

    def supports_data_type_real(self) -> bool:
        return True

    def supports_data_type_decimal(self) -> bool:
        return True

    def supports_data_type_json(self) -> bool:
        return True

    def supports_data_type_blob(self) -> bool:
        return True

    def supports_data_type_array(self) -> bool:
        return True

    # ------------------------------------------------------------------
    # DDLTypeSupport — suggested_data_types()
    # ------------------------------------------------------------------

    def suggested_data_types(self) -> Dict[str, type]:
        from rhosocial.activerecord.backend.expression.types import (
            BinaryType,
            EnumType,
            JsonBType,
            VarBinaryType,
        )
        return {
            "binary": ClickHouseStringType,
            "varbinary": ClickHouseStringType,
            "enum": ClickHouseStringType,
            "jsonb": ClickHouseStringType,
        }

    # --- Core types (pure names) rendered to real ClickHouse SQL ---

    def format_data_type_integer(self, data_type: IntegerType) -> Tuple[str, tuple]:
        return "Int32", ()

    def format_data_type_bigint(self, data_type: BigIntType) -> Tuple[str, tuple]:
        return "Int64", ()

    def format_data_type_smallint(self, data_type: SmallIntType) -> Tuple[str, tuple]:
        return "Int16", ()

    def format_data_type_tinyint(self, data_type: TinyIntType) -> Tuple[str, tuple]:
        return "Int8", ()

    def format_data_type_varchar(self, data_type: VarCharType) -> Tuple[str, tuple]:
        return "String", ()

    def format_data_type_char(self, data_type: CharType) -> Tuple[str, tuple]:
        return "String", ()

    def format_data_type_text(self, data_type: TextType) -> Tuple[str, tuple]:
        return "String", ()

    def format_data_type_boolean(self, data_type: BooleanType) -> Tuple[str, tuple]:
        return "Bool", ()

    def format_data_type_date(self, data_type: DateType) -> Tuple[str, tuple]:
        return "Date", ()

    def format_data_type_datetime(self, data_type: DateTimeType) -> Tuple[str, tuple]:
        return "DateTime", ()

    def format_data_type_timestamp(self, data_type: TimestampType) -> Tuple[str, tuple]:
        return "DateTime", ()

    def format_data_type_time(self, data_type: TimeType) -> Tuple[str, tuple]:
        return "DateTime", ()

    def format_data_type_float(self, data_type: FloatType) -> Tuple[str, tuple]:
        return "Float32", ()

    def format_data_type_double(self, data_type: DoubleType) -> Tuple[str, tuple]:
        return "Float64", ()

    def format_data_type_real(self, data_type: RealType) -> Tuple[str, tuple]:
        return "Float32", ()

    def format_data_type_decimal(self, data_type: DecimalType) -> Tuple[str, tuple]:
        p = data_type.precision
        s = data_type.scale
        if p is not None and s is not None:
            return f"Decimal({p}, {s})", ()
        if p is not None:
            return f"Decimal({p})", ()
        return "Decimal(10, 0)", ()

    def format_data_type_json(self, data_type: JsonType) -> Tuple[str, tuple]:
        return "String", ()

    def format_data_type_blob(self, data_type: BlobType) -> Tuple[str, tuple]:
        return "String", ()

    def format_data_type_array(self, data_type: ArrayType) -> Tuple[str, tuple]:
        inner_sql, inner_params = self.format_data_type(data_type.element_type)
        return f"Array({inner_sql})", inner_params

    # ------------------------------------------------------------------
    # DDLTypeSupport — parsing
    # ------------------------------------------------------------------

    _CLICKHOUSE_INTEGER_TYPES = re.compile(
        r"^(?:Int8|Int16|Int32|Int64|UInt8|UInt16|UInt32|UInt64)\b",
        re.IGNORECASE,
    )
    _CLICKHOUSE_FLOAT_TYPES = re.compile(
        r"^(?:Float32|Float64)\b",
        re.IGNORECASE,
    )
    _CLICKHOUSE_DECIMAL_TYPES = re.compile(
        r"^(?:Decimal(?:32|64|128)?(?:\(.*\))?)\b",
        re.IGNORECASE,
    )
    _CLICKHOUSE_STRING_TYPES = re.compile(
        r"^(?:String|FixedString(?:\(.*\))?)\b",
        re.IGNORECASE,
    )
    _CLICKHOUSE_DATE_TYPES = re.compile(
        r"^(?:Date|Date32|DateTime|DateTime64(?:\(.*\))?)\b",
        re.IGNORECASE,
    )
    _CLICKHOUSE_OTHER_TYPES = re.compile(
        r"^(?:Bool|UUID|IPv4|IPv6|JSON)\b",
        re.IGNORECASE,
    )
    _CLICKHOUSE_ENUM_TYPES = re.compile(
        r"^(?:Enum8|Enum16)\b",
        re.IGNORECASE,
    )
    _CLICKHOUSE_CONTAINER_TYPES = re.compile(
        r"^(?:Array|Map|Tuple|Nullable|LowCardinality)\b",
        re.IGNORECASE,
    )
    _CLICKHOUSE_AGGREGATE_TYPES = re.compile(
        r"^(?:AggregateFunction|SimpleAggregateFunction)\b",
        re.IGNORECASE,
    )
    _CLICKHOUSE_SPATIAL_TYPES = re.compile(
        r"^(?:GEOMETRY|POINT|LINESTRING|POLYGON|"
        r"MULTIPOINT|MULTILINESTRING|MULTIPOLYGON|GEOMETRYCOLLECTION)\b",
        re.IGNORECASE,
    )
    _CLICKHOUSE_VECTOR_TYPES = re.compile(
        r"^(?:VECTOR)\b",
        re.IGNORECASE,
    )

    def parse_type(self, raw: str) -> "DataType":
        stripped = raw.strip()
        upper = stripped.upper()

        # Integer family
        if self._CLICKHOUSE_INTEGER_TYPES.match(upper):
            if upper.startswith("INT8"):
                return ClickHouseInt8Type(dialect=self)
            if upper.startswith("INT16"):
                return ClickHouseInt16Type(dialect=self)
            if upper.startswith("INT32"):
                return ClickHouseInt32Type(dialect=self)
            if upper.startswith("INT64"):
                return ClickHouseInt64Type(dialect=self)
            if upper.startswith("UINT8"):
                return ClickHouseUInt8Type(dialect=self)
            if upper.startswith("UINT16"):
                return ClickHouseUInt16Type(dialect=self)
            if upper.startswith("UINT32"):
                return ClickHouseUInt32Type(dialect=self)
            if upper.startswith("UINT64"):
                return ClickHouseUInt64Type(dialect=self)

        # Float family
        if self._CLICKHOUSE_FLOAT_TYPES.match(upper):
            if upper.startswith("FLOAT32"):
                return ClickHouseFloat32Type(dialect=self)
            if upper.startswith("FLOAT64"):
                return ClickHouseFloat64Type(dialect=self)

        # Decimal family
        if self._CLICKHOUSE_DECIMAL_TYPES.match(upper):
            nums = re.findall(r"\d+", stripped)
            if upper.startswith("DECIMAL32"):
                scale = int(nums[0]) if nums else 0
                return ClickHouseDecimal32Type(dialect=self, scale=scale)
            if upper.startswith("DECIMAL64"):
                scale = int(nums[0]) if nums else 0
                return ClickHouseDecimal64Type(dialect=self, scale=scale)
            if upper.startswith("DECIMAL128"):
                scale = int(nums[0]) if nums else 0
                return ClickHouseDecimal128Type(dialect=self, scale=scale)
            # Decimal(P, S)
            if len(nums) >= 2:
                return ClickHouseDecimalType(dialect=self, precision=int(nums[0]), scale=int(nums[1]))
            if len(nums) == 1:
                return ClickHouseDecimalType(dialect=self, precision=int(nums[0]))
            return ClickHouseDecimalType(dialect=self, precision=10, scale=0)

        # String family
        if self._CLICKHOUSE_STRING_TYPES.match(upper):
            if upper.startswith("FIXEDSTRING"):
                nums = re.findall(r"\d+", stripped)
                length = int(nums[0]) if nums else 1
                return ClickHouseFixedStringType(dialect=self, length=length)
            return ClickHouseStringType(dialect=self)

        # Date / Time family
        if self._CLICKHOUSE_DATE_TYPES.match(upper):
            if upper.startswith("DATETIME64"):
                nums = re.findall(r"\((\d+)\)", stripped)
                precision = int(nums[0]) if nums else 3
                return ClickHouseDateTime64Type(dialect=self, precision=precision)
            if upper.startswith("DATETIME"):
                return ClickHouseDateTimeType(dialect=self)
            if upper.startswith("DATE32"):
                return ClickHouseDate32Type(dialect=self)
            if upper.startswith("DATE"):
                return ClickHouseDateType(dialect=self)

        # Other simple types
        if self._CLICKHOUSE_OTHER_TYPES.match(upper):
            if upper.startswith("BOOL"):
                return ClickHouseBoolType(dialect=self)
            if upper.startswith("UUID"):
                return ClickHouseUUIDType(dialect=self)
            if upper.startswith("IPV4"):
                return ClickHouseIPv4Type(dialect=self)
            if upper.startswith("IPV6"):
                return ClickHouseIPv6Type(dialect=self)
            if upper.startswith("JSON"):
                return ClickHouseJSONType(dialect=self)

        # Enum types
        if self._CLICKHOUSE_ENUM_TYPES.match(upper):
            pairs = re.findall(r"'([^']*)'\s*=\s*(-?\d+)", stripped)
            values = [(name, int(num)) for name, num in pairs]
            if upper.startswith("ENUM8"):
                return ClickHouseEnum8Type(dialect=self, values=values)
            return ClickHouseEnum16Type(dialect=self, values=values)

        # Container types
        if self._CLICKHOUSE_CONTAINER_TYPES.match(upper):
            # Extract inner type(s) from parentheses
            inner = self._extract_inner_types(stripped)
            if upper.startswith("ARRAY") and inner:
                inner_type = self.parse_type(inner[0])
                return ClickHouseArrayType(dialect=self, element_type=inner_type)
            if upper.startswith("MAP") and len(inner) >= 2:
                key_type = self.parse_type(inner[0])
                val_type = self.parse_type(inner[1])
                return ClickHouseMapType(dialect=self, key_type=key_type, value_type=val_type)
            if upper.startswith("TUPLE") and inner:
                types = [self.parse_type(t) for t in inner]
                return ClickHouseTupleType(dialect=self, element_types=types)
            if upper.startswith("NULLABLE") and inner:
                inner_type = self.parse_type(inner[0])
                return ClickHouseNullableType(dialect=self, inner_type=inner_type)
            if upper.startswith("LOWCARDINALITY") and inner:
                inner_type = self.parse_type(inner[0])
                return ClickHouseLowCardinalityType(dialect=self, inner_type=inner_type)

        # AggregateFunction
        if self._CLICKHOUSE_AGGREGATE_TYPES.match(upper):
            inner = self._extract_inner_types(stripped)
            if inner:
                func_name = inner[0]
                arg_types = [self.parse_type(t) for t in inner[1:]]
                if upper.startswith("SIMPLEAGGREGATEFUNCTION"):
                    return ClickHouseSimpleAggregateFunctionType(
                        dialect=self, function_name=func_name, arg_types=arg_types)
                return ClickHouseAggregateFunctionType(dialect=self, function_name=func_name, arg_types=arg_types)

        # Spatial
        if self._CLICKHOUSE_SPATIAL_TYPES.match(upper):
            srid = None
            srid_match = re.search(r"SRID\s+(\d+)", upper)
            if srid_match:
                srid = int(srid_match.group(1))
            spatial_map = {
                "GEOMETRY": ClickHouseGeometryType,
                "POINT": ClickHousePointType,
                "LINESTRING": ClickHouseLineStringType,
                "POLYGON": ClickHousePolygonType,
                "MULTIPOINT": ClickHouseMultiPointType,
                "MULTILINESTRING": ClickHouseMultiLineStringType,
                "MULTIPOLYGON": ClickHouseMultiPolygonType,
                "GEOMETRYCOLLECTION": ClickHouseGeometryCollectionType,
            }
            for name, cls in spatial_map.items():
                if upper.startswith(name):
                    return cls(dialect=self, srid=srid)
            return ClickHouseGeometryType(dialect=self, srid=srid)

        # Vector
        if self._CLICKHOUSE_VECTOR_TYPES.match(upper):
            nums = re.findall(r"\d+", stripped)
            dim = int(nums[0]) if nums else 0
            return ClickHouseVectorType(dialect=self, dim=dim)

        # Fallback
        from rhosocial.activerecord.backend.expression.types import CustomType
        return CustomType(dialect=self, raw=stripped)

    @staticmethod
    def _extract_inner_types(raw: str) -> list:
        """Extract comma-separated type arguments from the outermost parentheses.

        Handles nested parentheses like ``Array(Nullable(Int32))``.
        """
        start = raw.find("(")
        if start == -1:
            return []
        depth = 0
        parts = []
        current = []
        for ch in raw[start + 1:]:
            if ch == "(":
                depth += 1
                current.append(ch)
            elif ch == ")":
                if depth == 0:
                    break
                depth -= 1
                current.append(ch)
            elif ch == "," and depth == 0:
                parts.append("".join(current).strip())
                current = []
            else:
                current.append(ch)
        if current:
            parts.append("".join(current).strip())
        return parts

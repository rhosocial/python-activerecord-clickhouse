# src/rhosocial/activerecord/backend/impl/clickhouse/mixins/types.py
"""ClickHouse DataType formatting and parsing mixin."""

from __future__ import annotations

import re
from typing import Tuple

from rhosocial.activerecord.backend.dialect.mixins.ddl_type import DDLTypeMixin
from rhosocial.activerecord.backend.dialect.protocols import DDLTypeSupport
from rhosocial.activerecord.backend.expression.types import (
    ArrayType,
    BigIntType,
    BlobType,
    BooleanType,
    CharType,
    DateType,
    DateTimeType,
    DecimalType,
    DoubleType,
    FloatType,
    IntegerType,
    JsonBType,
    JsonType,
    RealType,
    SmallIntType,
    TextType,
    TimeType,
    TimeTzType,
    TimestampType,
    TimestampTzType,
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
    """

    # ------------------------------------------------------------------
    # DDLTypeSupport — formatting
    # ------------------------------------------------------------------

    # --- Integer types ---

    @DDLTypeMixin.handles(ClickHouseInt8Type)
    def format_data_type_int8(self, data_type: ClickHouseInt8Type) -> Tuple[str, tuple]:
        return "Int8", ()

    @DDLTypeMixin.handles(ClickHouseInt16Type)
    def format_data_type_int16(self, data_type: ClickHouseInt16Type) -> Tuple[str, tuple]:
        return "Int16", ()

    @DDLTypeMixin.handles(ClickHouseInt32Type)
    def format_data_type_int32(self, data_type: ClickHouseInt32Type) -> Tuple[str, tuple]:
        return "Int32", ()

    @DDLTypeMixin.handles(ClickHouseInt64Type)
    def format_data_type_int64(self, data_type: ClickHouseInt64Type) -> Tuple[str, tuple]:
        return "Int64", ()

    @DDLTypeMixin.handles(ClickHouseUInt8Type)
    def format_data_type_uint8(self, data_type: ClickHouseUInt8Type) -> Tuple[str, tuple]:
        return "UInt8", ()

    @DDLTypeMixin.handles(ClickHouseUInt16Type)
    def format_data_type_uint16(self, data_type: ClickHouseUInt16Type) -> Tuple[str, tuple]:
        return "UInt16", ()

    @DDLTypeMixin.handles(ClickHouseUInt32Type)
    def format_data_type_uint32(self, data_type: ClickHouseUInt32Type) -> Tuple[str, tuple]:
        return "UInt32", ()

    @DDLTypeMixin.handles(ClickHouseUInt64Type)
    def format_data_type_uint64(self, data_type: ClickHouseUInt64Type) -> Tuple[str, tuple]:
        return "UInt64", ()

    # --- Float types ---

    @DDLTypeMixin.handles(ClickHouseFloat32Type)
    def format_data_type_float32(self, data_type: ClickHouseFloat32Type) -> Tuple[str, tuple]:
        return "Float32", ()

    @DDLTypeMixin.handles(ClickHouseFloat64Type)
    def format_data_type_float64(self, data_type: ClickHouseFloat64Type) -> Tuple[str, tuple]:
        return "Float64", ()

    # --- Decimal types ---

    @DDLTypeMixin.handles(ClickHouseDecimalType)
    def format_data_type_decimal(self, data_type: ClickHouseDecimalType) -> Tuple[str, tuple]:
        return f"Decimal({data_type.precision}, {data_type.scale})", ()

    @DDLTypeMixin.handles(ClickHouseDecimal32Type)
    def format_data_type_decimal32(self, data_type: ClickHouseDecimal32Type) -> Tuple[str, tuple]:
        return f"Decimal32({data_type.scale})", ()

    @DDLTypeMixin.handles(ClickHouseDecimal64Type)
    def format_data_type_decimal64(self, data_type: ClickHouseDecimal64Type) -> Tuple[str, tuple]:
        return f"Decimal64({data_type.scale})", ()

    @DDLTypeMixin.handles(ClickHouseDecimal128Type)
    def format_data_type_decimal128(self, data_type: ClickHouseDecimal128Type) -> Tuple[str, tuple]:
        return f"Decimal128({data_type.scale})", ()

    # --- String types ---

    @DDLTypeMixin.handles(ClickHouseStringType)
    def format_data_type_string(self, data_type: ClickHouseStringType) -> Tuple[str, tuple]:
        return "String", ()

    @DDLTypeMixin.handles(ClickHouseFixedStringType)
    def format_data_type_fixed_string(self, data_type: ClickHouseFixedStringType) -> Tuple[str, tuple]:
        return f"FixedString({data_type.length})", ()

    # --- Date / Time types ---

    @DDLTypeMixin.handles(ClickHouseDateType)
    def format_data_type_date(self, data_type: ClickHouseDateType) -> Tuple[str, tuple]:
        return "Date", ()

    @DDLTypeMixin.handles(ClickHouseDate32Type)
    def format_data_type_date32(self, data_type: ClickHouseDate32Type) -> Tuple[str, tuple]:
        return "Date32", ()

    @DDLTypeMixin.handles(ClickHouseDateTimeType)
    def format_data_type_datetime(self, data_type: ClickHouseDateTimeType) -> Tuple[str, tuple]:
        return "DateTime", ()

    @DDLTypeMixin.handles(ClickHouseDateTime64Type)
    def format_data_type_datetime64(self, data_type: ClickHouseDateTime64Type) -> Tuple[str, tuple]:
        return f"DateTime64({data_type.precision})", ()

    # --- Bool ---

    @DDLTypeMixin.handles(ClickHouseBoolType)
    def format_data_type_bool(self, data_type: ClickHouseBoolType) -> Tuple[str, tuple]:
        return "Bool", ()

    # --- UUID ---

    @DDLTypeMixin.handles(ClickHouseUUIDType)
    def format_data_type_uuid(self, data_type: ClickHouseUUIDType) -> Tuple[str, tuple]:
        return "UUID", ()

    # --- IP types ---

    @DDLTypeMixin.handles(ClickHouseIPv4Type)
    def format_data_type_ipv4(self, data_type: ClickHouseIPv4Type) -> Tuple[str, tuple]:
        return "IPv4", ()

    @DDLTypeMixin.handles(ClickHouseIPv6Type)
    def format_data_type_ipv6(self, data_type: ClickHouseIPv6Type) -> Tuple[str, tuple]:
        return "IPv6", ()

    # --- Enum types ---

    @DDLTypeMixin.handles(ClickHouseEnum8Type)
    def format_data_type_enum8(self, data_type: ClickHouseEnum8Type) -> Tuple[str, tuple]:
        values_str = ", ".join(f"'{name}' = {num}" for name, num in data_type.values)
        return f"Enum8({values_str})", ()

    @DDLTypeMixin.handles(ClickHouseEnum16Type)
    def format_data_type_enum16(self, data_type: ClickHouseEnum16Type) -> Tuple[str, tuple]:
        values_str = ", ".join(f"'{name}' = {num}" for name, num in data_type.values)
        return f"Enum16({values_str})", ()

    # --- Container types ---

    @DDLTypeMixin.handles(ClickHouseArrayType)
    def format_data_type_array(self, data_type: ClickHouseArrayType) -> Tuple[str, tuple]:
        inner_sql, inner_params = self.format_data_type(data_type.element_type)
        return f"Array({inner_sql})", inner_params

    @DDLTypeMixin.handles(ClickHouseMapType)
    def format_data_type_map(self, data_type: ClickHouseMapType) -> Tuple[str, tuple]:
        key_sql, key_params = self.format_data_type(data_type.key_type)
        val_sql, val_params = self.format_data_type(data_type.value_type)
        return f"Map({key_sql}, {val_sql})", key_params + val_params

    @DDLTypeMixin.handles(ClickHouseTupleType)
    def format_data_type_tuple(self, data_type: ClickHouseTupleType) -> Tuple[str, tuple]:
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

    # --- Type modifiers ---

    @DDLTypeMixin.handles(ClickHouseNullableType)
    def format_data_type_nullable(self, data_type: ClickHouseNullableType) -> Tuple[str, tuple]:
        inner_sql, inner_params = self.format_data_type(data_type.inner_type)
        return f"Nullable({inner_sql})", inner_params

    @DDLTypeMixin.handles(ClickHouseLowCardinalityType)
    def format_data_type_low_cardinality(self, data_type: ClickHouseLowCardinalityType) -> Tuple[str, tuple]:
        inner_sql, inner_params = self.format_data_type(data_type.inner_type)
        return f"LowCardinality({inner_sql})", inner_params

    # --- JSON ---

    @DDLTypeMixin.handles(ClickHouseJSONType)
    def format_data_type_json(self, data_type: ClickHouseJSONType) -> Tuple[str, tuple]:
        return "JSON", ()

    # --- AggregateFunction ---

    @DDLTypeMixin.handles(ClickHouseAggregateFunctionType)
    def format_data_type_aggregate_function(self, data_type: ClickHouseAggregateFunctionType) -> Tuple[str, tuple]:
        args = ", ".join(self.format_data_type(t)[0] for t in data_type.arg_types)
        return f"AggregateFunction({data_type.function_name}, {args})", ()

    @DDLTypeMixin.handles(ClickHouseSimpleAggregateFunctionType)
    def format_data_type_simple_aggregate_function(self, data_type: ClickHouseSimpleAggregateFunctionType) -> Tuple[str, tuple]:
        args = ", ".join(self.format_data_type(t)[0] for t in data_type.arg_types)
        return f"SimpleAggregateFunction({data_type.function_name}, {args})", ()

    # --- Spatial types ---

    @DDLTypeMixin.handles(ClickHouseGeometryType)
    def format_data_type_geometry(self, data_type: ClickHouseGeometryType) -> Tuple[str, tuple]:
        if data_type.srid is not None:
            return f"GEOMETRY SRID {data_type.srid}", ()
        return "GEOMETRY", ()

    @DDLTypeMixin.handles(ClickHousePointType)
    def format_data_type_point(self, data_type: ClickHousePointType) -> Tuple[str, tuple]:
        if data_type.srid is not None:
            return f"POINT SRID {data_type.srid}", ()
        return "POINT", ()

    @DDLTypeMixin.handles(ClickHouseLineStringType)
    def format_data_type_line_string(self, data_type: ClickHouseLineStringType) -> Tuple[str, tuple]:
        if data_type.srid is not None:
            return f"LINESTRING SRID {data_type.srid}", ()
        return "LINESTRING", ()

    @DDLTypeMixin.handles(ClickHousePolygonType)
    def format_data_type_polygon(self, data_type: ClickHousePolygonType) -> Tuple[str, tuple]:
        if data_type.srid is not None:
            return f"POLYGON SRID {data_type.srid}", ()
        return "POLYGON", ()

    @DDLTypeMixin.handles(ClickHouseMultiPointType)
    def format_data_type_multi_point(self, data_type: ClickHouseMultiPointType) -> Tuple[str, tuple]:
        if data_type.srid is not None:
            return f"MULTIPOINT SRID {data_type.srid}", ()
        return "MULTIPOINT", ()

    @DDLTypeMixin.handles(ClickHouseMultiLineStringType)
    def format_data_type_multi_line_string(self, data_type: ClickHouseMultiLineStringType) -> Tuple[str, tuple]:
        if data_type.srid is not None:
            return f"MULTILINESTRING SRID {data_type.srid}", ()
        return "MULTILINESTRING", ()

    @DDLTypeMixin.handles(ClickHouseMultiPolygonType)
    def format_data_type_multi_polygon(self, data_type: ClickHouseMultiPolygonType) -> Tuple[str, tuple]:
        if data_type.srid is not None:
            return f"MULTIPOLYGON SRID {data_type.srid}", ()
        return "MULTIPOLYGON", ()

    @DDLTypeMixin.handles(ClickHouseGeometryCollectionType)
    def format_data_type_geometry_collection(self, data_type: ClickHouseGeometryCollectionType) -> Tuple[str, tuple]:
        if data_type.srid is not None:
            return f"GEOMETRYCOLLECTION SRID {data_type.srid}", ()
        return "GEOMETRYCOLLECTION", ()

    # --- Vector ---

    @DDLTypeMixin.handles(ClickHouseVectorType)
    def format_data_type_vector(self, data_type: ClickHouseVectorType) -> Tuple[str, tuple]:
        return f"VECTOR({data_type.dim})", ()

    # --- Core type overrides (map to ClickHouse equivalents) ---

    @DDLTypeMixin.handles(IntegerType)
    def format_data_type_integer(self, data_type: IntegerType) -> Tuple[str, tuple]:
        return "Int32", ()

    @DDLTypeMixin.handles(BigIntType)
    def format_data_type_bigint(self, data_type: BigIntType) -> Tuple[str, tuple]:
        return "Int64", ()

    @DDLTypeMixin.handles(SmallIntType)
    def format_data_type_smallint(self, data_type: SmallIntType) -> Tuple[str, tuple]:
        return "Int16", ()

    @DDLTypeMixin.handles(TinyIntType)
    def format_data_type_tinyint(self, data_type: TinyIntType) -> Tuple[str, tuple]:
        return "Int8", ()

    @DDLTypeMixin.handles(VarCharType)
    def format_data_type_varchar(self, data_type: VarCharType) -> Tuple[str, tuple]:
        return "String", ()

    @DDLTypeMixin.handles(CharType)
    def format_data_type_char(self, data_type: CharType) -> Tuple[str, tuple]:
        return "String", ()

    @DDLTypeMixin.handles(TextType)
    def format_data_type_text(self, data_type: TextType) -> Tuple[str, tuple]:
        return "String", ()

    @DDLTypeMixin.handles(BooleanType)
    def format_data_type_boolean(self, data_type: BooleanType) -> Tuple[str, tuple]:
        return "Bool", ()

    @DDLTypeMixin.handles(DateType)
    def format_data_type_date_core(self, data_type: DateType) -> Tuple[str, tuple]:
        return "Date", ()

    @DDLTypeMixin.handles(DateTimeType)
    def format_data_type_datetime_core(self, data_type: DateTimeType) -> Tuple[str, tuple]:
        return "DateTime", ()

    @DDLTypeMixin.handles(TimestampType)
    def format_data_type_timestamp(self, data_type: TimestampType) -> Tuple[str, tuple]:
        return "DateTime", ()

    @DDLTypeMixin.handles(TimestampTzType)
    def format_data_type_timestamptz(self, data_type: TimestampTzType) -> Tuple[str, tuple]:
        return "DateTime", ()

    @DDLTypeMixin.handles(TimeType)
    def format_data_type_time(self, data_type: TimeType) -> Tuple[str, tuple]:
        return "DateTime", ()

    @DDLTypeMixin.handles(TimeTzType)
    def format_data_type_timetz(self, data_type: TimeTzType) -> Tuple[str, tuple]:
        return "DateTime", ()

    @DDLTypeMixin.handles(FloatType)
    def format_data_type_float(self, data_type: FloatType) -> Tuple[str, tuple]:
        return "Float32", ()

    @DDLTypeMixin.handles(DoubleType)
    def format_data_type_double(self, data_type: DoubleType) -> Tuple[str, tuple]:
        return "Float64", ()

    @DDLTypeMixin.handles(RealType)
    def format_data_type_real(self, data_type: RealType) -> Tuple[str, tuple]:
        return "Float32", ()

    @DDLTypeMixin.handles(DecimalType)
    def format_data_type_decimal_core(self, data_type: DecimalType) -> Tuple[str, tuple]:
        p = data_type.precision
        s = data_type.scale
        if p is not None and s is not None:
            return f"Decimal({p}, {s})", ()
        if p is not None:
            return f"Decimal({p})", ()
        return "Decimal(10, 0)", ()

    @DDLTypeMixin.handles(JsonType)
    def format_data_type_json_core(self, data_type: JsonType) -> Tuple[str, tuple]:
        return "String", ()

    @DDLTypeMixin.handles(JsonBType)
    def format_data_type_jsonb(self, data_type: JsonBType) -> Tuple[str, tuple]:
        return "String", ()

    @DDLTypeMixin.handles(BlobType)
    def format_data_type_blob(self, data_type: BlobType) -> Tuple[str, tuple]:
        return "String", ()

    @DDLTypeMixin.handles(ArrayType)
    def format_data_type_array_core(self, data_type: ArrayType) -> Tuple[str, tuple]:
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
                return ClickHouseInt8Type()
            if upper.startswith("INT16"):
                return ClickHouseInt16Type()
            if upper.startswith("INT32"):
                return ClickHouseInt32Type()
            if upper.startswith("INT64"):
                return ClickHouseInt64Type()
            if upper.startswith("UINT8"):
                return ClickHouseUInt8Type()
            if upper.startswith("UINT16"):
                return ClickHouseUInt16Type()
            if upper.startswith("UINT32"):
                return ClickHouseUInt32Type()
            if upper.startswith("UINT64"):
                return ClickHouseUInt64Type()

        # Float family
        if self._CLICKHOUSE_FLOAT_TYPES.match(upper):
            if upper.startswith("FLOAT32"):
                return ClickHouseFloat32Type()
            if upper.startswith("FLOAT64"):
                return ClickHouseFloat64Type()

        # Decimal family
        if self._CLICKHOUSE_DECIMAL_TYPES.match(upper):
            nums = re.findall(r"\d+", stripped)
            if upper.startswith("DECIMAL32"):
                scale = int(nums[0]) if nums else 0
                return ClickHouseDecimal32Type(scale)
            if upper.startswith("DECIMAL64"):
                scale = int(nums[0]) if nums else 0
                return ClickHouseDecimal64Type(scale)
            if upper.startswith("DECIMAL128"):
                scale = int(nums[0]) if nums else 0
                return ClickHouseDecimal128Type(scale)
            # Decimal(P, S)
            if len(nums) >= 2:
                return ClickHouseDecimalType(int(nums[0]), int(nums[1]))
            if len(nums) == 1:
                return ClickHouseDecimalType(int(nums[0]))
            return ClickHouseDecimalType(10, 0)

        # String family
        if self._CLICKHOUSE_STRING_TYPES.match(upper):
            if upper.startswith("FIXEDSTRING"):
                nums = re.findall(r"\d+", stripped)
                length = int(nums[0]) if nums else 1
                return ClickHouseFixedStringType(length)
            return ClickHouseStringType()

        # Date / Time family
        if self._CLICKHOUSE_DATE_TYPES.match(upper):
            if upper.startswith("DATETIME64"):
                nums = re.findall(r"\((\d+)\)", stripped)
                precision = int(nums[0]) if nums else 3
                return ClickHouseDateTime64Type(precision)
            if upper.startswith("DATETIME"):
                return ClickHouseDateTimeType()
            if upper.startswith("DATE32"):
                return ClickHouseDate32Type()
            if upper.startswith("DATE"):
                return ClickHouseDateType()

        # Other simple types
        if self._CLICKHOUSE_OTHER_TYPES.match(upper):
            if upper.startswith("BOOL"):
                return ClickHouseBoolType()
            if upper.startswith("UUID"):
                return ClickHouseUUIDType()
            if upper.startswith("IPV4"):
                return ClickHouseIPv4Type()
            if upper.startswith("IPV6"):
                return ClickHouseIPv6Type()
            if upper.startswith("JSON"):
                return ClickHouseJSONType()

        # Enum types
        if self._CLICKHOUSE_ENUM_TYPES.match(upper):
            pairs = re.findall(r"'([^']*)'\s*=\s*(-?\d+)", stripped)
            values = [(name, int(num)) for name, num in pairs]
            if upper.startswith("ENUM8"):
                return ClickHouseEnum8Type(values)
            return ClickHouseEnum16Type(values)

        # Container types
        if self._CLICKHOUSE_CONTAINER_TYPES.match(upper):
            # Extract inner type(s) from parentheses
            inner = self._extract_inner_types(stripped)
            if upper.startswith("ARRAY") and inner:
                inner_type = self.parse_type(inner[0])
                return ClickHouseArrayType(inner_type)
            if upper.startswith("MAP") and len(inner) >= 2:
                key_type = self.parse_type(inner[0])
                val_type = self.parse_type(inner[1])
                return ClickHouseMapType(key_type, val_type)
            if upper.startswith("TUPLE") and inner:
                types = [self.parse_type(t) for t in inner]
                return ClickHouseTupleType(types)
            if upper.startswith("NULLABLE") and inner:
                inner_type = self.parse_type(inner[0])
                return ClickHouseNullableType(inner_type)
            if upper.startswith("LOWCARDINALITY") and inner:
                inner_type = self.parse_type(inner[0])
                return ClickHouseLowCardinalityType(inner_type)

        # AggregateFunction
        if self._CLICKHOUSE_AGGREGATE_TYPES.match(upper):
            inner = self._extract_inner_types(stripped)
            if inner:
                func_name = inner[0]
                arg_types = [self.parse_type(t) for t in inner[1:]]
                if upper.startswith("SIMPLEAGGREGATEFUNCTION"):
                    return ClickHouseSimpleAggregateFunctionType(func_name, arg_types)
                return ClickHouseAggregateFunctionType(func_name, arg_types)

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
                    return cls(srid)
            return ClickHouseGeometryType(srid)

        # Vector
        if self._CLICKHOUSE_VECTOR_TYPES.match(upper):
            nums = re.findall(r"\d+", stripped)
            dim = int(nums[0]) if nums else 0
            return ClickHouseVectorType(dim)

        # Fallback
        from rhosocial.activerecord.backend.expression.types import CustomType
        return CustomType(stripped)

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
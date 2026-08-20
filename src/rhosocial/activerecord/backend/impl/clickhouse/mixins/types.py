# src/rhosocial/activerecord/backend/impl/clickhouse/mixins/types.py
"""ClickHouse DataType formatting and parsing mixin."""

from __future__ import annotations

import re
from typing import Tuple

from rhosocial.activerecord.backend.dialect.mixins.ddl_type import DDLTypeMixin
from rhosocial.activerecord.backend.dialect.protocols import DDLTypeSupport
from rhosocial.activerecord.backend.expression.types import (
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
    ClickHouseBigIntType,
    ClickHouseBinaryType,
    ClickHouseBitType,
    ClickHouseBlobType,
    ClickHouseEnumType,
    ClickHouseGeometryCollectionType,
    ClickHouseGeometryType,
    ClickHouseIntType,
    ClickHouseLineStringType,
    ClickHouseLongBlobType,
    ClickHouseLongTextType,
    ClickHouseMediumBlobType,
    ClickHouseMediumTextType,
    ClickHouseMultiLineStringType,
    ClickHouseMultiPointType,
    ClickHouseMultiPolygonType,
    ClickHousePointType,
    ClickHousePolygonType,
    ClickHouseSetType,
    ClickHouseSmallIntType,
    ClickHouseTextType,
    ClickHouseTinyBlobType,
    ClickHouseTinyIntType,
    ClickHouseTinyTextType,
    ClickHouseVarBinaryType,
    ClickHouseVectorType,
    ClickHouseYearType,
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

    # --- ClickHouse-specific type formatters ---

    @DDLTypeMixin.handles(ClickHouseTinyIntType)
    def format_data_type_tiny_int(self, data_type: ClickHouseTinyIntType) -> Tuple[str, tuple]:
        sql = "TINYINT"
        if data_type.zerofill:
            return f"{sql} ZEROFILL", ()
        if data_type.unsigned:
            return f"{sql} UNSIGNED", ()
        return sql, ()

    @DDLTypeMixin.handles(ClickHouseSmallIntType)
    def format_data_type_small_int(self, data_type: ClickHouseSmallIntType) -> Tuple[str, tuple]:
        sql = "SMALLINT"
        if data_type.zerofill:
            return f"{sql} ZEROFILL", ()
        if data_type.unsigned:
            return f"{sql} UNSIGNED", ()
        return sql, ()

    @DDLTypeMixin.handles(ClickHouseIntType)
    def format_data_type_int(self, data_type: ClickHouseIntType) -> Tuple[str, tuple]:
        sql = "INT"
        if data_type.zerofill:
            return f"{sql} ZEROFILL", ()
        if data_type.unsigned:
            return f"{sql} UNSIGNED", ()
        return sql, ()

    @DDLTypeMixin.handles(ClickHouseBigIntType)
    def format_data_type_big_int(self, data_type: ClickHouseBigIntType) -> Tuple[str, tuple]:
        sql = "BIGINT"
        if data_type.zerofill:
            return f"{sql} ZEROFILL", ()
        if data_type.unsigned:
            return f"{sql} UNSIGNED", ()
        return sql, ()

    @DDLTypeMixin.handles(ClickHouseTinyBlobType)
    def format_data_type_tiny_blob(self, data_type: ClickHouseTinyBlobType) -> Tuple[str, tuple]:
        return "TINYBLOB", ()

    @DDLTypeMixin.handles(ClickHouseBlobType)
    def format_data_type_blob(self, data_type: ClickHouseBlobType) -> Tuple[str, tuple]:
        return "BLOB", ()

    @DDLTypeMixin.handles(ClickHouseMediumBlobType)
    def format_data_type_medium_blob(self, data_type: ClickHouseMediumBlobType) -> Tuple[str, tuple]:
        return "MEDIUMBLOB", ()

    @DDLTypeMixin.handles(ClickHouseLongBlobType)
    def format_data_type_long_blob(self, data_type: ClickHouseLongBlobType) -> Tuple[str, tuple]:
        return "LONGBLOB", ()

    @DDLTypeMixin.handles(ClickHouseTinyTextType)
    def format_data_type_tiny_text(self, data_type: ClickHouseTinyTextType) -> Tuple[str, tuple]:
        return "TINYTEXT", ()

    @DDLTypeMixin.handles(ClickHouseTextType)
    def format_data_type_text(self, data_type: ClickHouseTextType) -> Tuple[str, tuple]:
        return "TEXT", ()

    @DDLTypeMixin.handles(ClickHouseMediumTextType)
    def format_data_type_medium_text(self, data_type: ClickHouseMediumTextType) -> Tuple[str, tuple]:
        return "MEDIUMTEXT", ()

    @DDLTypeMixin.handles(ClickHouseLongTextType)
    def format_data_type_long_text(self, data_type: ClickHouseLongTextType) -> Tuple[str, tuple]:
        return "LONGTEXT", ()

    @DDLTypeMixin.handles(ClickHouseBitType)
    def format_data_type_bit(self, data_type: ClickHouseBitType) -> Tuple[str, tuple]:
        if data_type.n is not None:
            return f"BIT({data_type.n})", ()
        return "BIT", ()

    @DDLTypeMixin.handles(ClickHouseYearType)
    def format_data_type_year(self, data_type: ClickHouseYearType) -> Tuple[str, tuple]:
        if data_type.display_width is not None:
            return f"YEAR({data_type.display_width})", ()
        return "YEAR", ()

    @DDLTypeMixin.handles(ClickHouseBinaryType)
    def format_data_type_binary(self, data_type: ClickHouseBinaryType) -> Tuple[str, tuple]:
        if data_type.length is not None:
            return f"BINARY({data_type.length})", ()
        return "BINARY", ()

    @DDLTypeMixin.handles(ClickHouseVarBinaryType)
    def format_data_type_var_binary(self, data_type: ClickHouseVarBinaryType) -> Tuple[str, tuple]:
        if data_type.length is not None:
            return f"VARBINARY({data_type.length})", ()
        return "VARBINARY", ()

    @DDLTypeMixin.handles(ClickHouseEnumType)
    def format_data_type_enum(self, data_type: ClickHouseEnumType) -> Tuple[str, tuple]:
        values_str = ",".join(f"'{v}'" for v in data_type.values)
        result = f"ENUM({values_str})"
        if data_type.charset:
            result += f" CHARACTER SET {data_type.charset}"
        if data_type.collation:
            result += f" COLLATE {data_type.collation}"
        return result, ()

    @DDLTypeMixin.handles(ClickHouseSetType)
    def format_data_type_set(self, data_type: ClickHouseSetType) -> Tuple[str, tuple]:
        values_str = ",".join(f"'{v}'" for v in data_type.values)
        result = f"SET({values_str})"
        if data_type.charset:
            result += f" CHARACTER SET {data_type.charset}"
        if data_type.collation:
            result += f" COLLATE {data_type.collation}"
        return result, ()

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

    @DDLTypeMixin.handles(ClickHouseVectorType)
    def format_data_type_vector(self, data_type: ClickHouseVectorType) -> Tuple[str, tuple]:
        return f"VECTOR({data_type.dim})", ()

    # --- Core type overrides (ClickHouse-specific SQL) ---

    @DDLTypeMixin.handles(DoubleType)
    def format_data_type_double(self, data_type: DoubleType) -> Tuple[str, tuple]:
        return "DOUBLE", ()

    @DDLTypeMixin.handles(BooleanType)
    def format_data_type_boolean(self, data_type: BooleanType) -> Tuple[str, tuple]:
        return "TINYINT(1)", ()

    @DDLTypeMixin.handles(TimeTzType)
    def format_data_type_timetz(self, data_type: TimeTzType) -> Tuple[str, tuple]:
        return (f"TIME({data_type.precision})" if data_type.precision is not None else "TIME"), ()

    @DDLTypeMixin.handles(TimestampTzType)
    def format_data_type_timestamptz(self, data_type: TimestampTzType) -> Tuple[str, tuple]:
        return (f"TIMESTAMP({data_type.precision})" if data_type.precision is not None else "TIMESTAMP"), ()

    @DDLTypeMixin.handles(JsonBType)
    def format_data_type_jsonb(self, data_type: JsonBType) -> Tuple[str, tuple]:
        return "JSON", ()

    # --- Core type handlers (render standard types to ClickHouse SQL) ---

    @DDLTypeMixin.handles(IntegerType)
    def format_data_type_integer(self, data_type: IntegerType) -> Tuple[str, tuple]:
        return "INT", ()

    @DDLTypeMixin.handles(BigIntType)
    def format_data_type_bigint(self, data_type: BigIntType) -> Tuple[str, tuple]:
        return "BIGINT", ()

    @DDLTypeMixin.handles(SmallIntType)
    def format_data_type_smallint(self, data_type: SmallIntType) -> Tuple[str, tuple]:
        return "SMALLINT", ()

    @DDLTypeMixin.handles(TinyIntType)
    def format_data_type_tinyint(self, data_type: TinyIntType) -> Tuple[str, tuple]:
        return "TINYINT", ()

    @DDLTypeMixin.handles(VarCharType)
    def format_data_type_varchar(self, data_type: VarCharType) -> Tuple[str, tuple]:
        return (f"VARCHAR({data_type.length})" if data_type.length is not None else "VARCHAR"), ()

    @DDLTypeMixin.handles(CharType)
    def format_data_type_char(self, data_type: CharType) -> Tuple[str, tuple]:
        return (f"CHAR({data_type.length})" if data_type.length is not None else "CHAR"), ()

    @DDLTypeMixin.handles(TextType)
    def format_data_type_text_core(self, data_type: TextType) -> Tuple[str, tuple]:
        return "TEXT", ()

    @DDLTypeMixin.handles(DateTimeType)
    def format_data_type_datetime(self, data_type: DateTimeType) -> Tuple[str, tuple]:
        return (f"DATETIME({data_type.precision})" if data_type.precision is not None else "DATETIME"), ()

    @DDLTypeMixin.handles(DateType)
    def format_data_type_date(self, data_type: DateType) -> Tuple[str, tuple]:
        return "DATE", ()

    @DDLTypeMixin.handles(TimeType)
    def format_data_type_time(self, data_type: TimeType) -> Tuple[str, tuple]:
        return (f"TIME({data_type.precision})" if data_type.precision is not None else "TIME"), ()

    @DDLTypeMixin.handles(TimestampType)
    def format_data_type_timestamp(self, data_type: TimestampType) -> Tuple[str, tuple]:
        return (f"TIMESTAMP({data_type.precision})" if data_type.precision is not None else "TIMESTAMP"), ()

    @DDLTypeMixin.handles(FloatType)
    def format_data_type_float(self, data_type: FloatType) -> Tuple[str, tuple]:
        return (f"FLOAT({data_type.precision})" if data_type.precision is not None else "FLOAT"), ()

    @DDLTypeMixin.handles(RealType)
    def format_data_type_real(self, data_type: RealType) -> Tuple[str, tuple]:
        return "REAL", ()

    @DDLTypeMixin.handles(DecimalType)
    def format_data_type_decimal(self, data_type: DecimalType) -> Tuple[str, tuple]:
        if data_type.precision is not None and data_type.scale is not None:
            return f"DECIMAL({data_type.precision}, {data_type.scale})", ()
        if data_type.precision is not None:
            return f"DECIMAL({data_type.precision})", ()
        return "DECIMAL", ()

    @DDLTypeMixin.handles(JsonType)
    def format_data_type_json(self, data_type: JsonType) -> Tuple[str, tuple]:
        return "JSON", ()

    @DDLTypeMixin.handles(BlobType)
    def format_data_type_blob_core(self, data_type: BlobType) -> Tuple[str, tuple]:
        return "BLOB", ()

    # ------------------------------------------------------------------
    # DDLTypeSupport — parsing
    # ------------------------------------------------------------------

    _CLICKHOUSE_INTEGER_TYPES = re.compile(
        r"^(?:TINYINT|SMALLINT|MEDIUMINT|INT|INTEGER|BIGINT)\b",
        re.IGNORECASE,
    )
    _CLICKHOUSE_FLOAT_TYPES = re.compile(
        r"^(?:FLOAT|REAL|DOUBLE)\b",
        re.IGNORECASE,
    )
    _CLICKHOUSE_DECIMAL_TYPES = re.compile(
        r"^(?:DECIMAL|NUMERIC|FIXED)\b",
        re.IGNORECASE,
    )
    _CLICKHOUSE_STRING_TYPES = re.compile(
        r"^(?:CHAR|VARCHAR|TEXT|TINYTEXT|MEDIUMTEXT|LONGTEXT|"
        r"ENUM|SET|BINARY|VARBINARY)\b",
        re.IGNORECASE,
    )
    _CLICKHOUSE_BLOB_TYPES = re.compile(
        r"^(?:BLOB|TINYBLOB|MEDIUMBLOB|LONGBLOB)\b",
        re.IGNORECASE,
    )
    _CLICKHOUSE_DATE_TYPES = re.compile(
        r"^(?:DATE|DATETIME|TIMESTAMP|TIME|YEAR)\b",
        re.IGNORECASE,
    )
    _CLICKHOUSE_JSON_TYPES = re.compile(
        r"^(?:JSON)\b",
        re.IGNORECASE,
    )
    _CLICKHOUSE_SPATIAL_TYPES = re.compile(
        r"^(?:GEOMETRY|POINT|LINESTRING|POLYGON|"
        r"MULTIPOINT|MULTILINESTRING|MULTIPOLYGON|GEOMETRYCOLLECTION)\b",
        re.IGNORECASE,
    )
    _CLICKHOUSE_BIT_TYPES = re.compile(
        r"^(?:BIT)\b",
        re.IGNORECASE,
    )
    _CLICKHOUSE_VECTOR_TYPES = re.compile(
        r"^(?:VECTOR)\b",
        re.IGNORECASE,
    )

    def parse_type(self, raw: str) -> DataType:
        stripped = raw.strip()
        upper = stripped.upper()

        # BIT type
        if self._CLICKHOUSE_BIT_TYPES.match(upper):
            nums = re.findall(r"\d+", stripped)
            n = int(nums[0]) if nums else None
            from ..expression.types import ClickHouseBitType
            return ClickHouseBitType(n)

        # Integer family
        if self._CLICKHOUSE_INTEGER_TYPES.match(upper):
            unsigned = "UNSIGNED" in upper
            zerofill = "ZEROFILL" in upper
            if upper.startswith("TINYINT"):
                nums = re.findall(r"\d+", stripped)
                display_width = int(nums[0]) if nums else None
                from ..expression.types import ClickHouseTinyIntType
                t = ClickHouseTinyIntType()
                t.unsigned = unsigned
                t.zerofill = zerofill
                # TINYINT(1) is commonly used as BOOLEAN
                if display_width == 1 and not unsigned and not zerofill:
                    return BooleanType()
                return t
            if upper.startswith("SMALLINT"):
                from ..expression.types import ClickHouseSmallIntType
                t = ClickHouseSmallIntType()
                t.unsigned = unsigned
                t.zerofill = zerofill
                return t
            if upper.startswith("MEDIUMINT"):
                from ..expression.types import ClickHouseIntType
                t = ClickHouseIntType()
                t.unsigned = unsigned
                t.zerofill = zerofill
                return t
            if upper.startswith("BIGINT"):
                from ..expression.types import ClickHouseBigIntType
                t = ClickHouseBigIntType()
                t.unsigned = unsigned
                t.zerofill = zerofill
                return t
            # INT / INTEGER
            from ..expression.types import ClickHouseIntType
            t = ClickHouseIntType()
            t.unsigned = unsigned
            t.zerofill = zerofill
            return t

        # Float family
        if self._CLICKHOUSE_FLOAT_TYPES.match(upper):
            if upper.startswith("DOUBLE"):
                return DoubleType()
            if upper.startswith("REAL"):
                return RealType()
            # FLOAT
            nums = re.findall(r"\d+", stripped)
            precision = int(nums[0]) if nums else None
            return FloatType(precision)

        # Decimal family
        if self._CLICKHOUSE_DECIMAL_TYPES.match(upper):
            nums = re.findall(r"\d+", stripped)
            if len(nums) >= 2:
                return DecimalType(int(nums[0]), int(nums[1]))
            if len(nums) == 1:
                return DecimalType(int(nums[0]))
            return DecimalType()

        # String family
        if self._CLICKHOUSE_STRING_TYPES.match(upper):
            if upper.startswith("TINYTEXT"):
                from ..expression.types import ClickHouseTinyTextType
                return ClickHouseTinyTextType()
            if upper.startswith("MEDIUMTEXT"):
                from ..expression.types import ClickHouseMediumTextType
                return ClickHouseMediumTextType()
            if upper.startswith("LONGTEXT"):
                from ..expression.types import ClickHouseLongTextType
                return ClickHouseLongTextType()
            if upper.startswith("TEXT"):
                from ..expression.types import ClickHouseTextType
                return ClickHouseTextType()
            if upper.startswith("ENUM"):
                from ..expression.types import ClickHouseEnumType
                values = re.findall(r"'([^']*)'", stripped)
                charset = None
                collation = None
                cs_match = re.search(r"CHARACTER\s+SET\s+(\w+)", upper)
                if cs_match:
                    charset = cs_match.group(1)
                col_match = re.search(r"COLLATE\s+(\w+)", upper)
                if col_match:
                    collation = col_match.group(1)
                return ClickHouseEnumType(values, charset=charset, collation=collation)
            if upper.startswith("SET"):
                from ..expression.types import ClickHouseSetType
                values = re.findall(r"'([^']*)'", stripped)
                charset = None
                collation = None
                cs_match = re.search(r"CHARACTER\s+SET\s+(\w+)", upper)
                if cs_match:
                    charset = cs_match.group(1)
                col_match = re.search(r"COLLATE\s+(\w+)", upper)
                if col_match:
                    collation = col_match.group(1)
                return ClickHouseSetType(values, charset=charset, collation=collation)
            if upper.startswith("BINARY"):
                nums = re.findall(r"\d+", stripped)
                length = int(nums[0]) if nums else None
                from ..expression.types import ClickHouseBinaryType
                return ClickHouseBinaryType(length)
            if upper.startswith("VARBINARY"):
                nums = re.findall(r"\d+", stripped)
                length = int(nums[0]) if nums else None
                from ..expression.types import ClickHouseVarBinaryType
                return ClickHouseVarBinaryType(length)
            # CHAR / VARCHAR
            length_match = re.search(r"\((\d+)\)", stripped)
            length = int(length_match.group(1)) if length_match else None
            if upper.startswith("VARCHAR"):
                return VarCharType(length)
            return CharType(length)

        # BLOB family
        if self._CLICKHOUSE_BLOB_TYPES.match(upper):
            if upper.startswith("TINYBLOB"):
                from ..expression.types import ClickHouseTinyBlobType
                return ClickHouseTinyBlobType()
            if upper.startswith("MEDIUMBLOB"):
                from ..expression.types import ClickHouseMediumBlobType
                return ClickHouseMediumBlobType()
            if upper.startswith("LONGBLOB"):
                from ..expression.types import ClickHouseLongBlobType
                return ClickHouseLongBlobType()
            from ..expression.types import ClickHouseBlobType
            return ClickHouseBlobType()

        # Date/time family
        if self._CLICKHOUSE_DATE_TYPES.match(upper):
            if upper.startswith("YEAR"):
                nums = re.findall(r"\d+", stripped)
                display_width = int(nums[0]) if nums else None
                from ..expression.types import ClickHouseYearType
                return ClickHouseYearType(display_width)
            if upper.startswith("DATE"):
                if upper.strip() == "DATE":
                    return DateType()
                return DateTimeType()
            if upper.startswith("DATETIME"):
                nums = re.findall(r"\d+", stripped)
                precision = int(nums[0]) if nums else None
                return DateTimeType(precision)
            if upper.startswith("TIMESTAMP"):
                nums = re.findall(r"\d+", stripped)
                precision = int(nums[0]) if nums else None
                if "WITH TIME ZONE" in upper:
                    return TimestampTzType(precision)
                return TimestampType(precision)
            if upper.startswith("TIME"):
                nums = re.findall(r"\d+", stripped)
                precision = int(nums[0]) if nums else None
                if "WITH TIME ZONE" in upper:
                    return TimeTzType(precision)
                return TimeType(precision)

        # JSON
        if self._CLICKHOUSE_JSON_TYPES.match(upper):
            return JsonType()

        # Spatial
        if self._CLICKHOUSE_SPATIAL_TYPES.match(upper):
            srid = None
            srid_match = re.search(r"SRID\s+(\d+)", upper)
            if srid_match:
                srid = int(srid_match.group(1))
            from ..expression.types import (
                ClickHouseGeometryCollectionType,
                ClickHouseGeometryType,
                ClickHouseLineStringType,
                ClickHouseMultiLineStringType,
                ClickHouseMultiPointType,
                ClickHouseMultiPolygonType,
                ClickHousePointType,
                ClickHousePolygonType,
            )
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

        # Vector (ClickHouse 9.0+)
        if self._CLICKHOUSE_VECTOR_TYPES.match(upper):
            nums = re.findall(r"\d+", stripped)
            dim = int(nums[0]) if nums else 0
            from ..expression.types import ClickHouseVectorType
            return ClickHouseVectorType(dim)

        # Fallback
        from rhosocial.activerecord.backend.expression.types import CustomType
        return CustomType(stripped)
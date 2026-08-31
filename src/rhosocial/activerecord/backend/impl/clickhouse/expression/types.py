# src/rhosocial/activerecord/backend/impl/clickhouse/expression/types.py
"""ClickHouse-specific DataType subclasses.

Naming convention
-----------------
ClickHouse-specific types use the ``ClickHouse`` prefix to distinguish them from
the core types (which have no prefix).  This avoids ambiguity when both
core and backend types are used together.

Usage scope
-----------
These types are used **only** for ClickHouse backend DDL column definitions,
introspection result parsing, and schema comparison.  They should **not**
be used by application code directly — always use the core types for
DDL definition expressions (``ColumnDefinition.data_type``).
"""

from __future__ import annotations

from typing import List, Optional, Tuple as TupleType

from rhosocial.activerecord.backend.expression.types import DataType
from rhosocial.activerecord.backend.expression.types.array import ArrayType


# ---------------------------------------------------------------------------
# Integer types (signed and unsigned)
# ---------------------------------------------------------------------------

class ClickHouseInt8Type(DataType):
    """ClickHouse ``Int8`` — signed 8-bit integer."""


class ClickHouseInt16Type(DataType):
    """ClickHouse ``Int16`` — signed 16-bit integer."""


class ClickHouseInt32Type(DataType):
    """ClickHouse ``Int32`` — signed 32-bit integer."""


class ClickHouseInt64Type(DataType):
    """ClickHouse ``Int64`` — signed 64-bit integer."""


class ClickHouseUInt8Type(DataType):
    """ClickHouse ``UInt8`` — unsigned 8-bit integer (also used for Boolean)."""


class ClickHouseUInt16Type(DataType):
    """ClickHouse ``UInt16`` — unsigned 16-bit integer."""


class ClickHouseUInt32Type(DataType):
    """ClickHouse ``UInt32`` — unsigned 32-bit integer."""


class ClickHouseUInt64Type(DataType):
    """ClickHouse ``UInt64`` — unsigned 64-bit integer."""


# ---------------------------------------------------------------------------
# Float types
# ---------------------------------------------------------------------------

class ClickHouseFloat32Type(DataType):
    """ClickHouse ``Float32`` — 32-bit floating point."""


class ClickHouseFloat64Type(DataType):
    """ClickHouse ``Float64`` — 64-bit floating point."""


# ---------------------------------------------------------------------------
# Decimal types
# ---------------------------------------------------------------------------

class ClickHouseDecimalType(DataType):
    """ClickHouse ``Decimal(P, S)`` — fixed-point number."""

    precision: int
    scale: int

    def __init__(self, dialect=None, *, precision: int, scale: int = 0):
        super().__init__(dialect)
        self.precision = precision
        self.scale = scale

    def __eq__(self, other: object) -> bool:
        if type(self) is not type(other):
            return False
        return self.precision == other.precision and self.scale == other.scale

    def __hash__(self) -> int:
        return hash((type(self), self.precision, self.scale))


class ClickHouseDecimal32Type(DataType):
    """ClickHouse ``Decimal32(S)`` — 32-bit decimal with 9 digits."""

    scale: int

    def __init__(self, dialect=None, *, scale: int = 0):
        super().__init__(dialect)
        self.scale = scale

    def __eq__(self, other: object) -> bool:
        if type(self) is not type(other):
            return False
        return self.scale == other.scale

    def __hash__(self) -> int:
        return hash((type(self), self.scale))


class ClickHouseDecimal64Type(DataType):
    """ClickHouse ``Decimal64(S)`` — 64-bit decimal with 18 digits."""

    scale: int

    def __init__(self, dialect=None, *, scale: int = 0):
        super().__init__(dialect)
        self.scale = scale

    def __eq__(self, other: object) -> bool:
        if type(self) is not type(other):
            return False
        return self.scale == other.scale

    def __hash__(self) -> int:
        return hash((type(self), self.scale))


class ClickHouseDecimal128Type(DataType):
    """ClickHouse ``Decimal128(S)`` — 128-bit decimal with 38 digits."""

    scale: int

    def __init__(self, dialect=None, *, scale: int = 0):
        super().__init__(dialect)
        self.scale = scale

    def __eq__(self, other: object) -> bool:
        if type(self) is not type(other):
            return False
        return self.scale == other.scale

    def __hash__(self) -> int:
        return hash((type(self), self.scale))


# ---------------------------------------------------------------------------
# String / Binary types
# ---------------------------------------------------------------------------

class ClickHouseStringType(DataType):
    """ClickHouse ``String`` — variable-length binary/string."""


class ClickHouseFixedStringType(DataType):
    """ClickHouse ``FixedString(N)`` — fixed-length binary/string."""

    length: int

    def __init__(self, dialect=None, *, length: int):
        super().__init__(dialect)
        if length < 1:
            raise ValueError("FixedString length must be >= 1")
        self.length = length

    def __eq__(self, other: object) -> bool:
        if type(self) is not type(other):
            return False
        return self.length == other.length

    def __hash__(self) -> int:
        return hash((type(self), self.length))


# ---------------------------------------------------------------------------
# Date / Time types
# ---------------------------------------------------------------------------

class ClickHouseDateType(DataType):
    """ClickHouse ``Date`` — date (2 bytes, 1970-2149)."""


class ClickHouseDate32Type(DataType):
    """ClickHouse ``Date32`` — extended date (4 bytes, 1900-2299)."""


class ClickHouseDateTimeType(DataType):
    """ClickHouse ``DateTime`` — date and time (4 bytes, seconds precision)."""


class ClickHouseDateTime64Type(DataType):
    """ClickHouse ``DateTime64(P)`` — date and time with sub-second precision."""

    precision: int

    def __init__(self, dialect=None, *, precision: int = 3):
        super().__init__(dialect)
        if precision < 0 or precision > 9:
            raise ValueError("DateTime64 precision must be between 0 and 9")
        self.precision = precision

    def __eq__(self, other: object) -> bool:
        if type(self) is not type(other):
            return False
        return self.precision == other.precision

    def __hash__(self) -> int:
        return hash((type(self), self.precision))


# ---------------------------------------------------------------------------
# Boolean type
# ---------------------------------------------------------------------------

class ClickHouseBoolType(DataType):
    """ClickHouse ``Bool`` — Boolean type (actually UInt8)."""


# ---------------------------------------------------------------------------
# UUID
# ---------------------------------------------------------------------------

class ClickHouseUUIDType(DataType):
    """ClickHouse ``UUID`` — universally unique identifier."""


# ---------------------------------------------------------------------------
# IP types
# ---------------------------------------------------------------------------

class ClickHouseIPv4Type(DataType):
    """ClickHouse ``IPv4`` — IPv4 address."""


class ClickHouseIPv6Type(DataType):
    """ClickHouse ``IPv6`` — IPv6 address."""


# ---------------------------------------------------------------------------
# Enum types (ClickHouse native Enum8 / Enum16)
# ---------------------------------------------------------------------------

class ClickHouseEnum8Type(DataType):
    """ClickHouse ``Enum8`` — 8-bit enum with explicit string-value pairs."""

    values: List[TupleType[str, int]]

    def __init__(self, dialect=None, *, values: List[TupleType[str, int]]):
        super().__init__(dialect)
        if not values:
            raise ValueError("Enum8 must have at least one value")
        seen = set()
        for name, num in values:
            if num < -128 or num > 127:
                raise ValueError(f"Enum8 value {num} out of range [-128, 127]")
            pair = (name, num)
            if pair in seen:
                raise ValueError(f"Duplicate Enum8 pair: {pair}")
            seen.add(pair)
        self.values = list(values)

    def __eq__(self, other: object) -> bool:
        if type(self) is not type(other):
            return False
        return self.values == other.values

    def __hash__(self) -> int:
        return hash((type(self), tuple(self.values)))


class ClickHouseEnum16Type(DataType):
    """ClickHouse ``Enum16`` — 16-bit enum with explicit string-value pairs."""

    values: List[TupleType[str, int]]

    def __init__(self, dialect=None, *, values: List[TupleType[str, int]]):
        super().__init__(dialect)
        if not values:
            raise ValueError("Enum16 must have at least one value")
        seen = set()
        for name, num in values:
            if num < -32768 or num > 32767:
                raise ValueError(f"Enum16 value {num} out of range [-32768, 32767]")
            pair = (name, num)
            if pair in seen:
                raise ValueError(f"Duplicate Enum16 pair: {pair}")
            seen.add(pair)
        self.values = list(values)

    def __eq__(self, other: object) -> bool:
        if type(self) is not type(other):
            return False
        return self.values == other.values

    def __hash__(self) -> int:
        return hash((type(self), tuple(self.values)))


# ---------------------------------------------------------------------------
# Container types (Array, Map, Tuple)
# ---------------------------------------------------------------------------

class ClickHouseArrayType(ArrayType):
    """ClickHouse ``Array(T)`` — array of elements."""


class ClickHouseMapType(DataType):
    """ClickHouse ``Map(K, V)`` — key-value map."""

    key_type: DataType
    value_type: DataType

    def __init__(self, dialect=None, *, key_type: DataType, value_type: DataType):
        super().__init__(dialect)
        self.key_type = key_type
        self.value_type = value_type

    def __eq__(self, other: object) -> bool:
        if type(self) is not type(other):
            return False
        return (self.key_type == other.key_type and
                self.value_type == other.value_type)

    def __hash__(self) -> int:
        return hash((type(self), self.key_type, self.value_type))


class ClickHouseTupleType(DataType):
    """ClickHouse ``Tuple(T1, T2, ...)`` — named or unnamed tuple."""

    element_types: List[DataType]
    element_names: Optional[List[str]] = None

    def __init__(self, dialect=None, *, element_types: List[DataType], element_names: Optional[List[str]] = None):
        super().__init__(dialect)
        if not element_types:
            raise ValueError("Tuple must have at least one element")
        if element_names and len(element_names) != len(element_types):
            raise ValueError("element_names length must match element_types")
        self.element_types = list(element_types)
        self.element_names = list(element_names) if element_names else None

    def __eq__(self, other: object) -> bool:
        if type(self) is not type(other):
            return False
        return (self.element_types == other.element_types and
                self.element_names == other.element_names)

    def __hash__(self) -> int:
        return hash((type(self), tuple(self.element_types),
                     tuple(self.element_names) if self.element_names else None))


# ---------------------------------------------------------------------------
# Type modifiers (Nullable, LowCardinality)
# ---------------------------------------------------------------------------

class ClickHouseNullableType(DataType):
    """ClickHouse ``Nullable(T)`` — allows NULL values for the inner type."""

    inner_type: DataType

    def __init__(self, dialect=None, *, inner_type: DataType):
        super().__init__(dialect)
        self.inner_type = inner_type

    def __eq__(self, other: object) -> bool:
        if type(self) is not type(other):
            return False
        return self.inner_type == other.inner_type

    def __hash__(self) -> int:
        return hash((type(self), self.inner_type))


class ClickHouseLowCardinalityType(DataType):
    """ClickHouse ``LowCardinality(T)`` — dictionary-encoded type."""

    inner_type: DataType

    def __init__(self, dialect=None, *, inner_type: DataType):
        super().__init__(dialect)
        self.inner_type = inner_type

    def __eq__(self, other: object) -> bool:
        if type(self) is not type(other):
            return False
        return self.inner_type == other.inner_type

    def __hash__(self) -> int:
        return hash((type(self), self.inner_type))


# ---------------------------------------------------------------------------
# JSON type
# ---------------------------------------------------------------------------

class ClickHouseJSONType(DataType):
    """ClickHouse ``JSON`` — native JSON type (experimental in 26.x)."""


# ---------------------------------------------------------------------------
# Aggregation function types
# ---------------------------------------------------------------------------

class ClickHouseAggregateFunctionType(DataType):
    """ClickHouse ``AggregateFunction(name, T...)``."""

    function_name: str
    arg_types: List[DataType]

    def __init__(self, dialect=None, *, function_name: str, arg_types: List[DataType]):
        super().__init__(dialect)
        self.function_name = function_name
        self.arg_types = list(arg_types)

    def __eq__(self, other: object) -> bool:
        if type(self) is not type(other):
            return False
        return (self.function_name == other.function_name and
                self.arg_types == other.arg_types)

    def __hash__(self) -> int:
        return hash((type(self), self.function_name, tuple(self.arg_types)))


class ClickHouseSimpleAggregateFunctionType(DataType):
    """ClickHouse ``SimpleAggregateFunction(name, T...)``."""

    function_name: str
    arg_types: List[DataType]

    def __init__(self, dialect=None, *, function_name: str, arg_types: List[DataType]):
        super().__init__(dialect)
        self.function_name = function_name
        self.arg_types = list(arg_types)

    def __eq__(self, other: object) -> bool:
        if type(self) is not type(other):
            return False
        return (self.function_name == other.function_name and
                self.arg_types == other.arg_types)

    def __hash__(self) -> int:
        return hash((type(self), self.function_name, tuple(self.arg_types)))


# ---------------------------------------------------------------------------
# Spatial / Geometry types (preserved from MySQL template, CH supports via
# clickhouse-connect tuple representation)
# ---------------------------------------------------------------------------

class ClickHouseGeometryType(DataType):
    """ClickHouse ``GEOMETRY`` with optional SRID."""

    srid: Optional[int] = None

    def __init__(self, dialect=None, *, srid: Optional[int] = None):
        super().__init__(dialect)
        self.srid = srid

    def __eq__(self, other: object) -> bool:
        if type(self) is not type(other):
            return False
        return self.srid == other.srid

    def __hash__(self) -> int:
        return hash((type(self), self.srid))


class ClickHousePointType(ClickHouseGeometryType):
    """ClickHouse ``POINT`` with optional SRID."""


class ClickHouseLineStringType(ClickHouseGeometryType):
    """ClickHouse ``LINESTRING`` with optional SRID."""


class ClickHousePolygonType(ClickHouseGeometryType):
    """ClickHouse ``POLYGON`` with optional SRID."""


class ClickHouseMultiPointType(ClickHouseGeometryType):
    """ClickHouse ``MULTIPOINT`` with optional SRID."""


class ClickHouseMultiLineStringType(ClickHouseGeometryType):
    """ClickHouse ``MULTILINESTRING`` with optional SRID."""


class ClickHouseMultiPolygonType(ClickHouseGeometryType):
    """ClickHouse ``MULTIPOLYGON`` with optional SRID."""


class ClickHouseGeometryCollectionType(ClickHouseGeometryType):
    """ClickHouse ``GEOMETRYCOLLECTION`` with optional SRID."""


# ---------------------------------------------------------------------------
# VECTOR type (ClickHouse 9.0+)
# ---------------------------------------------------------------------------

class ClickHouseVectorType(DataType):
    """ClickHouse ``VECTOR(n)`` — vector type (ClickHouse 9.0+)."""

    dim: int

    def __init__(self, dialect=None, *, dim: int):
        super().__init__(dialect)
        self.dim = dim

    def __eq__(self, other: object) -> bool:
        if type(self) is not type(other):
            return False
        return self.dim == other.dim

    def __hash__(self) -> int:
        return hash((type(self), self.dim))
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

from typing import List, Optional, Set

from rhosocial.activerecord.backend.expression.types import (
    BigIntType,
    BlobType,
    DataType,
    IntegerType,
    SmallIntType,
    TextType,
    TinyIntType,
)


# ---------------------------------------------------------------------------
# Integer variants with UNSIGNED / ZEROFILL
# ---------------------------------------------------------------------------

class ClickHouseIntType(IntegerType, backend="clickhouse"):
    """ClickHouse ``INTEGER`` / ``INT`` with optional UNSIGNED / ZEROFILL."""

    unsigned: bool = False
    zerofill: bool = False

    def __eq__(self, other: object) -> bool:
        if type(self) is not type(other):
            return False
        return (self.unsigned == other.unsigned and
                self.zerofill == other.zerofill)

    def __hash__(self) -> int:
        return hash((type(self), self.unsigned, self.zerofill))

    @classmethod
    def synonyms(cls) -> Set[str]:
        return {'IntegerType'}


class ClickHouseTinyIntType(TinyIntType, backend="clickhouse"):
    """ClickHouse ``TINYINT`` with optional UNSIGNED / ZEROFILL."""

    unsigned: bool = False
    zerofill: bool = False

    def __eq__(self, other: object) -> bool:
        if type(self) is not type(other):
            return False
        return (self.unsigned == other.unsigned and
                self.zerofill == other.zerofill)

    def __hash__(self) -> int:
        return hash((type(self), self.unsigned, self.zerofill))

    @classmethod
    def synonyms(cls) -> Set[str]:
        return {'TinyIntType'}


class ClickHouseSmallIntType(SmallIntType, backend="clickhouse"):
    """ClickHouse ``SMALLINT`` with optional UNSIGNED / ZEROFILL."""

    unsigned: bool = False
    zerofill: bool = False

    def __eq__(self, other: object) -> bool:
        if type(self) is not type(other):
            return False
        return (self.unsigned == other.unsigned and
                self.zerofill == other.zerofill)

    def __hash__(self) -> int:
        return hash((type(self), self.unsigned, self.zerofill))

    @classmethod
    def synonyms(cls) -> Set[str]:
        return {'SmallIntType'}


class ClickHouseBigIntType(BigIntType, backend="clickhouse"):
    """ClickHouse ``BIGINT`` with optional UNSIGNED / ZEROFILL."""

    unsigned: bool = False
    zerofill: bool = False

    def __eq__(self, other: object) -> bool:
        if type(self) is not type(other):
            return False
        return (self.unsigned == other.unsigned and
                self.zerofill == other.zerofill)

    def __hash__(self) -> int:
        return hash((type(self), self.unsigned, self.zerofill))

    @classmethod
    def synonyms(cls) -> Set[str]:
        return {'BigIntType'}


# ---------------------------------------------------------------------------
# BLOB size variants
# ---------------------------------------------------------------------------

class ClickHouseTinyBlobType(BlobType, backend="clickhouse"):
    """ClickHouse ``TINYBLOB`` — maximum 255 bytes."""


class ClickHouseBlobType(BlobType, backend="clickhouse"):
    """ClickHouse ``BLOB`` — maximum 65,535 bytes."""


class ClickHouseMediumBlobType(BlobType, backend="clickhouse"):
    """ClickHouse ``MEDIUMBLOB`` — maximum 16,777,215 bytes."""


class ClickHouseLongBlobType(BlobType, backend="clickhouse"):
    """ClickHouse ``LONGBLOB`` — maximum 4,294,967,295 bytes."""


# ---------------------------------------------------------------------------
# TEXT size variants
# ---------------------------------------------------------------------------

class ClickHouseTinyTextType(TextType, backend="clickhouse"):
    """ClickHouse ``TINYTEXT`` — maximum 255 bytes."""


class ClickHouseTextType(TextType, backend="clickhouse"):
    """ClickHouse ``TEXT`` — maximum 65,535 bytes."""


class ClickHouseMediumTextType(TextType, backend="clickhouse"):
    """ClickHouse ``MEDIUMTEXT`` — maximum 16,777,215 bytes."""


class ClickHouseLongTextType(TextType, backend="clickhouse"):
    """ClickHouse ``LONGTEXT`` — maximum 4,294,967,295 bytes."""


# ---------------------------------------------------------------------------
# Bit type
# ---------------------------------------------------------------------------

class ClickHouseBitType(DataType, backend="clickhouse"):
    """ClickHouse ``BIT[(n)]`` — bit-field type."""

    n: Optional[int] = None

    def __init__(self, n: Optional[int] = None):
        super().__init__()
        self.n = n

    def __eq__(self, other: object) -> bool:
        if type(self) is not type(other):
            return False
        return self.n == other.n

    def __hash__(self) -> int:
        return hash((type(self), self.n))


# ---------------------------------------------------------------------------
# Year type
# ---------------------------------------------------------------------------

class ClickHouseYearType(DataType, backend="clickhouse"):
    """ClickHouse ``YEAR[(4)]`` — year type (``YEAR(4)`` is legacy)."""

    display_width: Optional[int] = None

    def __init__(self, display_width: Optional[int] = None):
        super().__init__()
        self.display_width = display_width

    def __eq__(self, other: object) -> bool:
        if type(self) is not type(other):
            return False
        return self.display_width == other.display_width

    def __hash__(self) -> int:
        return hash((type(self), self.display_width))


# ---------------------------------------------------------------------------
# Binary / VarBinary
# ---------------------------------------------------------------------------

class ClickHouseBinaryType(DataType, backend="clickhouse"):
    """ClickHouse ``BINARY[(n)]`` — fixed-length binary."""

    length: Optional[int] = None

    def __init__(self, length: Optional[int] = None):
        super().__init__()
        self.length = length

    def __eq__(self, other: object) -> bool:
        if type(self) is not type(other):
            return False
        return self.length == other.length

    def __hash__(self) -> int:
        return hash((type(self), self.length))


class ClickHouseVarBinaryType(DataType, backend="clickhouse"):
    """ClickHouse ``VARBINARY(n)`` — variable-length binary."""

    length: Optional[int] = None

    def __init__(self, length: Optional[int] = None):
        super().__init__()
        self.length = length

    def __eq__(self, other: object) -> bool:
        if type(self) is not type(other):
            return False
        return self.length == other.length

    def __hash__(self) -> int:
        return hash((type(self), self.length))


# ---------------------------------------------------------------------------
# ENUM
# ---------------------------------------------------------------------------

class ClickHouseEnumType(DataType, backend="clickhouse"):
    """ClickHouse ``ENUM('val', ...)`` with optional CHARACTER SET / COLLATE."""

    values: List[str]
    charset: Optional[str] = None
    collation: Optional[str] = None

    def __init__(self, values: List[str], charset: Optional[str] = None,
                 collation: Optional[str] = None):
        super().__init__()
        if not values:
            raise ValueError("ENUM must have at least one value")
        self.values = list(values)
        self.charset = charset
        self.collation = collation

    def __eq__(self, other: object) -> bool:
        if type(self) is not type(other):
            return False
        return (self.values == other.values and
                self.charset == other.charset and
                self.collation == other.collation)

    def __hash__(self) -> int:
        return hash((type(self), tuple(self.values), self.charset, self.collation))

    def __repr__(self) -> str:
        return (f"{type(self).__name__}(values={self.values!r}, "
                f"charset={self.charset!r}, collation={self.collation!r})")


# ---------------------------------------------------------------------------
# SET
# ---------------------------------------------------------------------------

class ClickHouseSetType(DataType, backend="clickhouse"):
    """ClickHouse ``SET('val', ...)`` with optional CHARACTER SET / COLLATE."""

    values: List[str]
    charset: Optional[str] = None
    collation: Optional[str] = None

    def __init__(self, values: List[str], charset: Optional[str] = None,
                 collation: Optional[str] = None):
        super().__init__()
        if not values:
            raise ValueError("SET must have at least one value")
        self.values = list(values)
        self.charset = charset
        self.collation = collation

    def __eq__(self, other: object) -> bool:
        if type(self) is not type(other):
            return False
        return (self.values == other.values and
                self.charset == other.charset and
                self.collation == other.collation)

    def __hash__(self) -> int:
        return hash((type(self), tuple(self.values), self.charset, self.collation))

    def __repr__(self) -> str:
        return (f"{type(self).__name__}(values={self.values!r}, "
                f"charset={self.charset!r}, collation={self.collation!r})")


# ---------------------------------------------------------------------------
# Spatial / Geometry types
# ---------------------------------------------------------------------------

class ClickHouseGeometryType(DataType, backend="clickhouse"):
    """ClickHouse ``GEOMETRY`` with optional SRID."""

    srid: Optional[int] = None

    def __init__(self, srid: Optional[int] = None):
        super().__init__()
        self.srid = srid

    def __eq__(self, other: object) -> bool:
        if type(self) is not type(other):
            return False
        return self.srid == other.srid

    def __hash__(self) -> int:
        return hash((type(self), self.srid))


class ClickHousePointType(ClickHouseGeometryType, backend="clickhouse"):
    """ClickHouse ``POINT`` with optional SRID."""


class ClickHouseLineStringType(ClickHouseGeometryType, backend="clickhouse"):
    """ClickHouse ``LINESTRING`` with optional SRID."""


class ClickHousePolygonType(ClickHouseGeometryType, backend="clickhouse"):
    """ClickHouse ``POLYGON`` with optional SRID."""


class ClickHouseMultiPointType(ClickHouseGeometryType, backend="clickhouse"):
    """ClickHouse ``MULTIPOINT`` with optional SRID."""


class ClickHouseMultiLineStringType(ClickHouseGeometryType, backend="clickhouse"):
    """ClickHouse ``MULTILINESTRING`` with optional SRID."""


class ClickHouseMultiPolygonType(ClickHouseGeometryType, backend="clickhouse"):
    """ClickHouse ``MULTIPOLYGON`` with optional SRID."""


class ClickHouseGeometryCollectionType(ClickHouseGeometryType, backend="clickhouse"):
    """ClickHouse ``GEOMETRYCOLLECTION`` with optional SRID."""


# ---------------------------------------------------------------------------
# VECTOR type (ClickHouse 9.0+)
# ---------------------------------------------------------------------------

class ClickHouseVectorType(DataType, backend="clickhouse"):
    """ClickHouse ``VECTOR(n)`` — vector type (ClickHouse 9.0+)."""

    dim: int

    def __init__(self, dim: int):
        super().__init__()
        self.dim = dim

    def __eq__(self, other: object) -> bool:
        if type(self) is not type(other):
            return False
        return self.dim == other.dim

    def __hash__(self) -> int:
        return hash((type(self), self.dim))
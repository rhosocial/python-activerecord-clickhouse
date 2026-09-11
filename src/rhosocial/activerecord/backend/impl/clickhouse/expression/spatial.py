# src/rhosocial/activerecord/backend/impl/clickhouse/expression/spatial.py
"""
ClickHouse-specific spatial expression functions.

This module provides expression classes for ClickHouse spatial functions:
- ClickHouseSTGeomFromTextExpression
- ClickHouseSTGeomFromWKBExpression
- ClickHouseSTAsTextExpression
- ClickHouseSTAsGeoJSONExpression
- ClickHouseSTDistanceExpression
- ClickHouseSTWithinExpression
- ClickHouseSTContainsExpression
- ClickHouseSpatialLiteralExpression
- ClickHouseCreateSpatialIndexExpression
"""

from typing import TYPE_CHECKING, Optional

from rhosocial.activerecord.backend.expression.bases import SQLValueExpression
from rhosocial.activerecord.backend.expression.mixins import (
    AliasableMixin,
    ComparisonMixin,
)

if TYPE_CHECKING:
    from rhosocial.activerecord.backend.dialect import SQLDialectBase


class ClickHouseSpatialLiteralExpression(AliasableMixin, SQLValueExpression):
    """ClickHouse spatial literal expression.

    Creates a geometry value from WKT.

    Example:
        >>> expr = ClickHouseSpatialLiteralExpression(dialect, 'POINT(1 1)')
    """

    def __init__(
        self,
        dialect: "SQLDialectBase",
        wkt: str,
        *,
        srid: Optional[int] = None,
        alias: Optional[str] = None,
    ):
        super().__init__(dialect)
        self.wkt = wkt
        self.srid = srid
        self.alias = alias

    @property
    def format_method(self) -> str:
        """The dialect formatting method that renders this expression."""
        return "format_spatial_literal"


class ClickHouseSTGeomFromTextExpression(AliasableMixin, SQLValueExpression):
    """ClickHouse ST_GeomFromText expression.

    Creates a geometry value from WKT.

    Example:
        >>> expr = ClickHouseSTGeomFromTextExpression(dialect, 'POINT(1 1)')
    """

    def __init__(
        self,
        dialect: "SQLDialectBase",
        wkt: str,
        *,
        srid: Optional[int] = None,
        alias: Optional[str] = None,
    ):
        super().__init__(dialect)
        self.wkt = wkt
        self.srid = srid
        self.alias = alias

    @property
    def format_method(self) -> str:
        """The dialect formatting method that renders this expression."""
        return "format_st_geom_from_text"


class ClickHouseSTGeomFromWKBExpression(AliasableMixin, SQLValueExpression):
    """ClickHouse ST_GeomFromWKB expression.

    Creates a geometry value from WKB.

    Example:
        >>> expr = ClickHouseSTGeomFromWKBExpression(dialect, b'\\x01\\x01...')
    """

    def __init__(
        self,
        dialect: "SQLDialectBase",
        wkb: bytes,
        *,
        srid: Optional[int] = None,
        alias: Optional[str] = None,
    ):
        super().__init__(dialect)
        self.wkb = wkb
        self.srid = srid
        self.alias = alias

    @property
    def format_method(self) -> str:
        """The dialect formatting method that renders this expression."""
        return "format_st_geom_from_wkb"


class ClickHouseSTAsTextExpression(AliasableMixin, SQLValueExpression):
    """ClickHouse ST_AsText expression.

    Converts a geometry to WKT.

    Example:
        >>> expr = ClickHouseSTAsTextExpression(dialect, 'geom')
    """

    def __init__(
        self,
        dialect: "SQLDialectBase",
        geom: str,
        *,
        alias: Optional[str] = None,
    ):
        super().__init__(dialect)
        self.geom = geom
        self.alias = alias

    @property
    def format_method(self) -> str:
        """The dialect formatting method that renders this expression."""
        return "format_st_as_text"


class ClickHouseSTAsGeoJSONExpression(AliasableMixin, SQLValueExpression):
    """ClickHouse ST_AsGeoJSON expression.

    Converts a geometry to GeoJSON.

    Example:
        >>> expr = ClickHouseSTAsGeoJSONExpression(dialect, 'geom')
    """

    def __init__(
        self,
        dialect: "SQLDialectBase",
        geom: str,
        *,
        alias: Optional[str] = None,
    ):
        super().__init__(dialect)
        self.geom = geom
        self.alias = alias

    @property
    def format_method(self) -> str:
        """The dialect formatting method that renders this expression."""
        return "format_st_as_geojson"


class ClickHouseSTDistanceExpression(AliasableMixin, ComparisonMixin, SQLValueExpression):
    """ClickHouse ST_Distance expression.

    Returns the distance between two geometries.

    Example:
        >>> expr = ClickHouseSTDistanceExpression(dialect, 'geom1', 'geom2')
    """

    def __init__(
        self,
        dialect: "SQLDialectBase",
        geom1: str,
        geom2: str,
        *,
        alias: Optional[str] = None,
    ):
        super().__init__(dialect)
        self.geom1 = geom1
        self.geom2 = geom2
        self.alias = alias

    @property
    def format_method(self) -> str:
        """The dialect formatting method that renders this expression."""
        return "format_st_distance"


class ClickHouseSTWithinExpression(AliasableMixin, ComparisonMixin, SQLValueExpression):
    """ClickHouse ST_Within expression.

    Returns whether one geometry is within another.

    Example:
        >>> expr = ClickHouseSTWithinExpression(dialect, 'geom1', 'geom2')
    """

    def __init__(
        self,
        dialect: "SQLDialectBase",
        geom1: str,
        geom2: str,
        *,
        alias: Optional[str] = None,
    ):
        super().__init__(dialect)
        self.geom1 = geom1
        self.geom2 = geom2
        self.alias = alias

    @property
    def format_method(self) -> str:
        """The dialect formatting method that renders this expression."""
        return "format_st_within"


class ClickHouseSTContainsExpression(AliasableMixin, ComparisonMixin, SQLValueExpression):
    """ClickHouse ST_Contains expression.

    Returns whether one geometry contains another.

    Example:
        >>> expr = ClickHouseSTContainsExpression(dialect, 'geom1', 'geom2')
    """

    def __init__(
        self,
        dialect: "SQLDialectBase",
        geom1: str,
        geom2: str,
        *,
        alias: Optional[str] = None,
    ):
        super().__init__(dialect)
        self.geom1 = geom1
        self.geom2 = geom2
        self.alias = alias

    @property
    def format_method(self) -> str:
        """The dialect formatting method that renders this expression."""
        return "format_st_contains"


class ClickHouseCreateSpatialIndexExpression(SQLValueExpression):
    """ClickHouse CREATE SPATIAL INDEX expression.

    Example:
        >>> expr = ClickHouseCreateSpatialIndexExpression(dialect, 'idx', 'table', 'column')
    """

    def __init__(
        self,
        dialect: "SQLDialectBase",
        index_name: str,
        table_name: str,
        column_name: str,
    ):
        super().__init__(dialect)
        self.index_name = index_name
        self.table_name = table_name
        self.column_name = column_name

    @property
    def format_method(self) -> str:
        """The dialect formatting method that renders this expression."""
        return "format_create_spatial_index"


__all__ = [
    "ClickHouseSpatialLiteralExpression",
    "ClickHouseSTGeomFromTextExpression",
    "ClickHouseSTGeomFromWKBExpression",
    "ClickHouseSTAsTextExpression",
    "ClickHouseSTAsGeoJSONExpression",
    "ClickHouseSTDistanceExpression",
    "ClickHouseSTWithinExpression",
    "ClickHouseSTContainsExpression",
    "ClickHouseCreateSpatialIndexExpression",
]

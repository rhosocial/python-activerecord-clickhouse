# src/rhosocial/activerecord/backend/impl/clickhouse/protocols/spatial.py
"""ClickHouse spatial data type protocol.

Split out of the former single-module ``clickhouse/protocols.py``; one
concern per module so the protocol surface stays legible.
"""

from typing import Protocol, runtime_checkable, Tuple, TYPE_CHECKING

@runtime_checkable
class ClickHouseSpatialSupport(Protocol):
    """ClickHouse spatial data type protocol.

    Feature Source: ClickHouse 5.7+ with InnoDB, all versions with MyISAM

    ClickHouse spatial features:
    - SPATIAL data types: GEOMETRY, POINT, LINESTRING, POLYGON, etc.
    - Spatial indexes (only for MyISAM with NOT NULL)
    - SPATIAL KEY/MULTIPLE KEY for indexes

    Official Documentation:
    - Spatial Data Types: https://dev.clickhouse.com/doc/refman/8.0/en/spatial-type.html

    Version Requirements:
    - Basic spatial types: ClickHouse 5.7+ (InnoDB), all versions (MyISAM)
    - Spatial index restrictions: ClickHouse 5.7.5+ for correct SRID handling
    """

    def supports_spatial_type(self, type_name: str) -> bool:
        """Whether a specific spatial data type is supported.

        Args:
            type_name: Spatial type name (e.g. 'POINT', 'LINESTRING')

        Returns:
            True if the spatial type is supported
        """
        ...

    def supports_spatial_index(self) -> bool:
        """Whether SPATIAL index is supported."""
        ...

    def supports_geojson(self) -> bool:
        """Whether GeoJSON functions (ST_AsGeoJSON) are supported (ClickHouse 5.7+)."""
        ...

    def supports_geometry_type(self) -> bool:
        """Whether GEOMETRY type is supported."""
        ...

    def supports_point_type(self) -> bool:
        """Whether POINT type is supported."""
        ...

    def supports_curve_type(self) -> bool:
        """Whether curve types (LINESTRING, MULTILINESTRING) are supported."""
        ...

    def supports_surface_type(self) -> bool:
        """Whether surface types (POLYGON, MULTIPOLYGON) are supported."""
        ...

    def supports_geometry_collection_type(self) -> bool:
        """Whether GEOMETRYCOLLECTION is supported."""
        ...

    def format_spatial_literal(self, expr) -> Tuple[str, tuple]:
        """Format spatial literal from WKT."""
        ...

    def format_st_geom_from_text(self, expr) -> Tuple[str, tuple]:
        """Format ST_GeomFromText function call."""
        ...

    def format_st_geom_from_wkb(self, expr) -> Tuple[str, tuple]:
        """Format ST_GeomFromWKB function call."""
        ...

    def format_st_as_text(self, expr) -> Tuple[str, tuple]:
        """Format ST_AsText function call."""
        ...

    def format_st_as_geojson(self, expr) -> Tuple[str, tuple]:
        """Format ST_AsGeoJSON function call."""
        ...

    def format_st_distance(self, expr) -> Tuple[str, tuple]:
        """Format ST_Distance function call."""
        ...

    def format_st_within(self, expr) -> Tuple[str, tuple]:
        """Format ST_Within function call."""
        ...

    def format_st_contains(self, expr) -> Tuple[str, tuple]:
        """Format ST_Contains function call."""
        ...

    def format_create_spatial_index(self, expr) -> Tuple[str, tuple]:
        """Format CREATE SPATIAL INDEX statement."""
        ...

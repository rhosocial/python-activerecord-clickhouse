# src/rhosocial/activerecord/backend/impl/clickhouse/mixins/spatial.py
from typing import Optional, Tuple


class ClickHouseSpatialMixin:
    """ClickHouse spatial data type implementation."""

    def supports_spatial_type(self, type_name: str) -> bool:
        valid_types = {
            "GEOMETRY", "POINT", "LINESTRING", "POLYGON",
            "MULTIPOINT", "MULTILINESTRING", "MULTIPOLYGON", "GEOMETRYCOLLECTION",
        }
        if type_name.upper() not in valid_types:
            return False
        return self.version >= (5, 7, 0)

    def supports_spatial_index(self) -> bool:
        return self.version >= (5, 7, 0)

    def supports_geojson(self) -> bool:
        return self.version >= (5, 7, 5)

    def supports_geometry_type(self) -> bool:
        return self.version >= (5, 7, 0)

    def supports_point_type(self) -> bool:
        return self.version >= (5, 7, 0)

    def supports_curve_type(self) -> bool:
        return self.version >= (5, 7, 0)

    def supports_surface_type(self) -> bool:
        return self.version >= (5, 7, 0)

    def supports_geometry_collection_type(self) -> bool:
        return self.version >= (5, 7, 0)

    def format_spatial_literal(self, wkt: str, srid: Optional[int] = None) -> Tuple[str, tuple]:
        if srid is not None:
            return "ST_GeomFromText(%s, %s)", (wkt, srid)
        return "ST_GeomFromText(%s)", (wkt,)

    def format_st_geom_from_text(self, wkt: str, srid: Optional[int] = None) -> Tuple[str, tuple]:
        if srid is not None:
            return "ST_GeomFromText(%s, %s)", (wkt, srid)
        return "ST_GeomFromText(%s)", (wkt,)

    def format_st_geom_from_wkb(self, wkb: bytes, srid: Optional[int] = None) -> Tuple[str, tuple]:
        if srid is not None:
            return "ST_GeomFromWKB(%s, %s)", (wkb, srid)
        return "ST_GeomFromWKB(%s)", (wkb,)

    def format_st_as_text(self, geom: str) -> Tuple[str, tuple]:
        return f"ST_AsText({geom})", ()

    def format_st_as_geojson(self, geom: str) -> Tuple[str, tuple]:
        """Format ST_AsGeoJSON function (ClickHouse 5.7.5+)."""
        if not self.supports_geojson():
            from rhosocial.activerecord.backend.dialect.exceptions import UnsupportedFeatureError
            raise UnsupportedFeatureError(self.name, "GeoJSON functions (requires ClickHouse 5.7.5+)")
        return f"ST_AsGeoJSON({geom})", ()

    def format_st_distance(self, geom1: str, geom2: str) -> Tuple[str, tuple]:
        return f"ST_Distance({geom1}, {geom2})", ()

    def format_st_within(self, geom1: str, geom2: str) -> Tuple[str, tuple]:
        return f"ST_Within({geom1}, {geom2})", ()

    def format_st_contains(self, geom1: str, geom2: str) -> Tuple[str, tuple]:
        return f"ST_Contains({geom1}, {geom2})", ()

    def format_create_spatial_index(self, index_name: str, table_name: str, column: str) -> Tuple[str, tuple]:
        """Format CREATE SPATIAL INDEX statement."""
        if not self.supports_spatial_index():
            from rhosocial.activerecord.backend.dialect.exceptions import UnsupportedFeatureError
            raise UnsupportedFeatureError(self.name, "SPATIAL indexes (requires ClickHouse 5.7+)")
        return (
            f"CREATE SPATIAL INDEX {self.format_identifier(index_name)} "
            f"ON {self.format_identifier(table_name)} "
            f"({self.format_identifier(column)})",
            (),
        )

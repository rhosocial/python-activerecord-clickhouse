# src/rhosocial/activerecord/backend/impl/clickhouse/mixins/spatial.py
from typing import Optional, Tuple

from rhosocial.activerecord.backend.dialect.exceptions import UnsupportedFeatureError


class ClickHouseSpatialMixin:
    """ClickHouse does not support MySQL spatial types or ``ST_*`` functions.

    ClickHouse has no ``GEOMETRY``/``POINT``/``POLYGON`` column types and no
    ``ST_GeomFromText``/``ST_Distance`` function family. Store geometry as
    ``String`` WKT or a ``Tuple``/``Array`` of coordinates and compute with
    ClickHouse functions. All methods fail fast.
    """

    def supports_spatial_type(self, type_name: str) -> bool:
        return False

    def supports_spatial_index(self) -> bool:
        return False

    def supports_geojson(self) -> bool:
        return False

    def supports_geometry_type(self) -> bool:
        return False

    def supports_point_type(self) -> bool:
        return False

    def supports_curve_type(self) -> bool:
        return False

    def supports_surface_type(self) -> bool:
        return False

    def supports_geometry_collection_type(self) -> bool:
        return False

    def format_spatial_literal(self, expr) -> Tuple[str, tuple]:
        raise UnsupportedFeatureError(
            self.name, "spatial types",
            suggestion="ClickHouse has no spatial types; store WKT as String.",
        )

    def format_st_geom_from_text(self, expr) -> Tuple[str, tuple]:
        raise UnsupportedFeatureError(
            self.name, "ST_GeomFromText",
            suggestion="ClickHouse has no ST_* spatial function family.",
        )

    def format_st_geom_from_wkb(self, expr) -> Tuple[str, tuple]:
        raise UnsupportedFeatureError(
            self.name, "ST_GeomFromWKB",
            suggestion="ClickHouse has no ST_* spatial function family.",
        )

    def format_st_as_text(self, expr) -> Tuple[str, tuple]:
        raise UnsupportedFeatureError(
            self.name, "ST_AsText",
            suggestion="ClickHouse has no ST_* spatial function family.",
        )

    def format_st_as_geojson(self, expr) -> Tuple[str, tuple]:
        raise UnsupportedFeatureError(
            self.name, "ST_AsGeoJSON",
            suggestion="ClickHouse has no ST_* spatial function family.",
        )

    def format_st_distance(self, expr) -> Tuple[str, tuple]:
        raise UnsupportedFeatureError(
            self.name, "ST_Distance",
            suggestion="ClickHouse has no ST_* spatial function family.",
        )

    def format_st_within(self, expr) -> Tuple[str, tuple]:
        raise UnsupportedFeatureError(
            self.name, "ST_Within",
            suggestion="ClickHouse has no ST_* spatial function family.",
        )

    def format_st_contains(self, expr) -> Tuple[str, tuple]:
        raise UnsupportedFeatureError(
            self.name, "ST_Contains",
            suggestion="ClickHouse has no ST_* spatial function family.",
        )

    def format_create_spatial_index(self, expr) -> Tuple[str, tuple]:
        raise UnsupportedFeatureError(
            self.name, "SPATIAL indexes",
            suggestion="ClickHouse has no SPATIAL indexes; use skip indexes (INDEX ... USING).",
        )

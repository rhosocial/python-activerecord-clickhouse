# src/rhosocial/activerecord/backend/impl/clickhouse/functions/spatial.py
"""
ClickHouse spatial function factories.

Functions: st_geom_from_text, st_geom_from_wkb, st_as_text, st_as_geojson,
st_distance, st_within, st_contains, st_intersects

.. warning::
    This module was copied from the MySQL backend template and contains
    MySQL-style SQL functions/show commands. ClickHouse uses different
    function names (e.g. ``JSONExtract*``) and a different SHOW command
    subset. May generate non-ClickHouse SQL; verify before use.
"""

from typing import Union, Optional, TYPE_CHECKING

from rhosocial.activerecord.backend.expression import bases, core

if TYPE_CHECKING:  # pragma: no cover
    from rhosocial.activerecord.backend.dialect import SQLDialectBase
    from .dialect import ClickHouseDialect


def _convert_to_expression(
    dialect: "SQLDialectBase",
    expr: Union[str, "bases.BaseExpression"],
    handle_numeric_literals: bool = True,
) -> "bases.BaseExpression":
    """
    Helper function to convert an input value to an appropriate BaseExpression.

    Args:
        dialect: The SQL dialect instance
        expr: The expression to convert
        handle_numeric_literals: Whether to treat numeric values as literals

    Returns:
        A BaseExpression instance
    """
    if isinstance(expr, bases.BaseExpression):
        return expr
    elif handle_numeric_literals and isinstance(expr, (int, float)):
        return core.Literal(dialect, expr)
    else:
        return core.Column(dialect, expr)


def st_geom_from_text(
    dialect: "ClickHouseDialect",
    wkt: str,
    srid: Optional[int] = None,
) -> "core.FunctionCall":
    """
    Creates an ST_GeomFromText function call.

    Constructs a geometry value from a WKT (Well-Known Text) representation.

    Args:
        dialect: The ClickHouse dialect instance
        wkt: Well-Known Text string
        srid: Optional SRID (Spatial Reference System Identifier)

    Returns:
        A FunctionCall instance representing ST_GeomFromText

    Version: ClickHouse 5.7+
    """
    wkt_expr = core.Literal(dialect, wkt)
    if srid is not None:
        srid_expr = core.Literal(dialect, srid)
        return core.FunctionCall(dialect, "ST_GeomFromText", wkt_expr, srid_expr)
    return core.FunctionCall(dialect, "ST_GeomFromText", wkt_expr)


def st_geom_from_wkb(
    dialect: "ClickHouseDialect",
    wkb: bytes,
    srid: Optional[int] = None,
) -> "core.FunctionCall":
    """
    Creates an ST_GeomFromWKB function call.

    Constructs a geometry value from a WKB (Well-Known Binary) representation.

    Args:
        dialect: The ClickHouse dialect instance
        wkb: Well-Known Binary data
        srid: Optional SRID (Spatial Reference System Identifier)

    Returns:
        A FunctionCall instance representing ST_GeomFromWKB

    Version: ClickHouse 5.7+
    """
    wkb_expr = core.Literal(dialect, wkb)
    if srid is not None:
        srid_expr = core.Literal(dialect, srid)
        return core.FunctionCall(dialect, "ST_GeomFromWKB", wkb_expr, srid_expr)
    return core.FunctionCall(dialect, "ST_GeomFromWKB", wkb_expr)


def st_as_text(
    dialect: "ClickHouseDialect",
    geom: Union[str, "bases.BaseExpression"],
) -> "core.FunctionCall":
    """
    Creates an ST_AsText function call.

    Returns the WKT (Well-Known Text) representation of a geometry.

    Args:
        dialect: The ClickHouse dialect instance
        geom: Geometry value or column

    Returns:
        A FunctionCall instance representing ST_AsText

    Version: ClickHouse 5.7+
    """
    geom_expr = _convert_to_expression(dialect, geom)
    return core.FunctionCall(dialect, "ST_AsText", geom_expr)


def st_as_geojson(
    dialect: "ClickHouseDialect",
    geom: Union[str, "bases.BaseExpression"],
) -> "core.FunctionCall":
    """
    Creates an ST_AsGeoJSON function call.

    Returns the GeoJSON representation of a geometry.

    Args:
        dialect: The ClickHouse dialect instance
        geom: Geometry value or column

    Returns:
        A FunctionCall instance representing ST_AsGeoJSON

    Version: ClickHouse 5.7.5+
    """
    geom_expr = _convert_to_expression(dialect, geom)
    return core.FunctionCall(dialect, "ST_AsGeoJSON", geom_expr)


def st_distance(
    dialect: "ClickHouseDialect",
    geom1: Union[str, "bases.BaseExpression"],
    geom2: Union[str, "bases.BaseExpression"],
) -> "core.FunctionCall":
    """
    Creates an ST_Distance function call.

    Returns the distance between two geometries.

    Args:
        dialect: The ClickHouse dialect instance
        geom1: First geometry
        geom2: Second geometry

    Returns:
        A FunctionCall instance representing ST_Distance

    Version: ClickHouse 5.7+
    """
    geom1_expr = _convert_to_expression(dialect, geom1)
    geom2_expr = _convert_to_expression(dialect, geom2)
    return core.FunctionCall(dialect, "ST_Distance", geom1_expr, geom2_expr)


def st_within(
    dialect: "ClickHouseDialect",
    geom1: Union[str, "bases.BaseExpression"],
    geom2: Union[str, "bases.BaseExpression"],
) -> "core.FunctionCall":
    """
    Creates an ST_Within function call.

    Checks if geom1 is spatially within geom2.

    Args:
        dialect: The ClickHouse dialect instance
        geom1: First geometry
        geom2: Second geometry

    Returns:
        A FunctionCall instance representing ST_Within

    Version: ClickHouse 5.7+
    """
    geom1_expr = _convert_to_expression(dialect, geom1)
    geom2_expr = _convert_to_expression(dialect, geom2)
    return core.FunctionCall(dialect, "ST_Within", geom1_expr, geom2_expr)


def st_contains(
    dialect: "ClickHouseDialect",
    geom1: Union[str, "bases.BaseExpression"],
    geom2: Union[str, "bases.BaseExpression"],
) -> "core.FunctionCall":
    """
    Creates an ST_Contains function call.

    Checks if geom1 spatially contains geom2.

    Args:
        dialect: The ClickHouse dialect instance
        geom1: First geometry
        geom2: Second geometry

    Returns:
        A FunctionCall instance representing ST_Contains

    Version: ClickHouse 5.7+
    """
    geom1_expr = _convert_to_expression(dialect, geom1)
    geom2_expr = _convert_to_expression(dialect, geom2)
    return core.FunctionCall(dialect, "ST_Contains", geom1_expr, geom2_expr)


def st_intersects(
    dialect: "ClickHouseDialect",
    geom1: Union[str, "bases.BaseExpression"],
    geom2: Union[str, "bases.BaseExpression"],
) -> "core.FunctionCall":
    """
    Creates an ST_Intersects function call.

    Checks if two geometries spatially intersect.

    Args:
        dialect: The ClickHouse dialect instance
        geom1: First geometry
        geom2: Second geometry

    Returns:
        A FunctionCall instance representing ST_Intersects

    Version: ClickHouse 5.7+
    """
    geom1_expr = _convert_to_expression(dialect, geom1)
    geom2_expr = _convert_to_expression(dialect, geom2)
    return core.FunctionCall(dialect, "ST_Intersects", geom1_expr, geom2_expr)


__all__ = [
    "st_geom_from_text",
    "st_geom_from_wkb",
    "st_as_text",
    "st_as_geojson",
    "st_distance",
    "st_within",
    "st_contains",
    "st_intersects",
]

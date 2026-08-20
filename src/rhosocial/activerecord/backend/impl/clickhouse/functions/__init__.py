# src/rhosocial/activerecord/backend/impl/clickhouse/functions/__init__.py
"""
ClickHouse-specific SQL function factories.

This module provides factory functions for creating ClickHouse-specific SQL expression
objects, organized into submodules by category:

- json: JSON functions (json_extract, json_object, etc.)
- spatial: Spatial/geometric functions (st_geom_from_text, st_distance, etc.)
- fulltext: Full-text search functions (match_against)
- enum_set: SET and Enum type functions (find_in_set, elt, field)
- math_enhanced: Enhanced math functions (round, pow, sqrt, ceil, floor, etc.)

Usage:
    from rhosocial.activerecord.backend.impl.clickhouse.functions import json_extract
    from rhosocial.activerecord.backend.impl.clickhouse.functions import st_distance
    from rhosocial.activerecord.backend.impl.clickhouse.functions import match_against
    from rhosocial.activerecord.backend.impl.clickhouse.functions import round_

Or import directly from submodules:
    from rhosocial.activerecord.backend.impl.clickhouse.functions.json import json_extract
    from rhosocial.activerecord.backend.impl.clickhouse.functions.spatial import st_distance
    from rhosocial.activerecord.backend.impl.clickhouse.functions.fulltext import match_against
    from rhosocial.activerecord.backend.impl.clickhouse.functions.math_enhanced import round_

Version Requirements:
- JSON functions: ClickHouse 5.7.8+
- Spatial functions: ClickHouse 5.7+
- GeoJSON functions: ClickHouse 5.7.5+
- Full-text search: ClickHouse 5.6+ (with some features requiring 5.7+)
- SET type: All ClickHouse versions
- Math functions: All ClickHouse versions
"""

from .json import (
    json_extract,
    json_unquote,
    json_object,
    json_array,
    json_contains,
    json_set,
    json_remove,
    json_type,
    json_valid,
    json_search,
)

from .math_enhanced import (
    round_,
    pow,
    power,
    sqrt,
    mod,
    ceil,
    floor,
    trunc,
    max_,
    min_,
    avg,
)

from .spatial import (
    st_geom_from_text,
    st_geom_from_wkb,
    st_as_text,
    st_as_geojson,
    st_distance,
    st_within,
    st_contains,
    st_intersects,
)

from .fulltext import (
    match_against,
)

from .enum_set import (
    find_in_set,
    elt,
    field,
)

from .bitwise import (
    bit_and,
    bit_or,
    bit_xor,
    bit_count,
    bit_get_bit,
    bit_shift_left,
    bit_shift_right,
)

__all__ = [
    # JSON functions
    "json_extract",
    "json_unquote",
    "json_object",
    "json_array",
    "json_contains",
    "json_set",
    "json_remove",
    "json_type",
    "json_valid",
    "json_search",
    # Spatial functions
    "st_geom_from_text",
    "st_geom_from_wkb",
    "st_as_text",
    "st_as_geojson",
    "st_distance",
    "st_within",
    "st_contains",
    "st_intersects",
    # Full-text search
    "match_against",
    # SET type functions
    "find_in_set",
    # Enum type functions
    "elt",
    "field",
    # Math enhanced functions
    "round_",
    "pow",
    "power",
    "sqrt",
    "mod",
    "ceil",
    "floor",
    "trunc",
    "max_",
    "min_",
    "avg",
    # Bitwise functions
    "bit_and",
    "bit_or",
    "bit_xor",
    "bit_count",
    "bit_get_bit",
    "bit_shift_left",
    "bit_shift_right",
]

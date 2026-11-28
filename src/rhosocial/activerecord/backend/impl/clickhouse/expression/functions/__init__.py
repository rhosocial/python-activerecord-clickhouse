# src/rhosocial/activerecord/backend/impl/clickhouse/expression/functions/__init__.py
"""Lazy re-exports of ClickHouse ``functions`` expressions (PEP 562).

Leaf modules are imported on first attribute access, never at package import
time. Public names stay reachable from this package exactly as before.
"""

from __future__ import annotations

import importlib as _importlib

_PKG = "rhosocial.activerecord.backend.impl.clickhouse.expression"

__all__ = [
    "ClickHouseCreateSpatialIndexStatement",
    "ClickHouseEngineFunctionExpression",
    "ClickHouseJSONArrayExpression",
    "ClickHouseJSONContainsExpression",
    "ClickHouseJSONExtractExpression",
    "ClickHouseJSONObjectExpression",
    "ClickHouseJSONRemoveExpression",
    "ClickHouseJSONSearchExpression",
    "ClickHouseJSONSetExpression",
    "ClickHouseJSONTypeExpression",
    "ClickHouseJSONUnquoteExpression",
    "ClickHouseJSONValidExpression",
    "ClickHouseMatchAgainstExpression",
    "ClickHouseSTAsGeoJSONExpression",
    "ClickHouseSTAsTextExpression",
    "ClickHouseSTContainsExpression",
    "ClickHouseSTDistanceExpression",
    "ClickHouseSTGeomFromTextExpression",
    "ClickHouseSTGeomFromWKBExpression",
    "ClickHouseSTWithinExpression",
    "ClickHouseSpatialLiteralExpression",
    "MatchAgainstMode",
]

# name -> defining module, relative to the expression package
_NAME_TO_MODULE = {
    "ClickHouseCreateSpatialIndexStatement": "functions.spatial",
    "ClickHouseEngineFunctionExpression": "functions.engine_function",
    "ClickHouseJSONArrayExpression": "functions.json",
    "ClickHouseJSONContainsExpression": "functions.json",
    "ClickHouseJSONExtractExpression": "functions.json",
    "ClickHouseJSONObjectExpression": "functions.json",
    "ClickHouseJSONRemoveExpression": "functions.json",
    "ClickHouseJSONSearchExpression": "functions.json",
    "ClickHouseJSONSetExpression": "functions.json",
    "ClickHouseJSONTypeExpression": "functions.json",
    "ClickHouseJSONUnquoteExpression": "functions.json",
    "ClickHouseJSONValidExpression": "functions.json",
    "ClickHouseMatchAgainstExpression": "functions.match_against",
    "ClickHouseSTAsGeoJSONExpression": "functions.spatial",
    "ClickHouseSTAsTextExpression": "functions.spatial",
    "ClickHouseSTContainsExpression": "functions.spatial",
    "ClickHouseSTDistanceExpression": "functions.spatial",
    "ClickHouseSTGeomFromTextExpression": "functions.spatial",
    "ClickHouseSTGeomFromWKBExpression": "functions.spatial",
    "ClickHouseSTWithinExpression": "functions.spatial",
    "ClickHouseSpatialLiteralExpression": "functions.spatial",
    "MatchAgainstMode": "functions.match_against",
}


def __getattr__(name: str) -> object:
    module = _NAME_TO_MODULE.get(name)
    if module is None:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    value = _importlib.import_module(_PKG + "." + module).__dict__[name]
    globals()[name] = value
    return value


def __dir__() -> list[str]:
    return sorted(set(globals()) | set(__all__))

# src/rhosocial/activerecord/backend/impl/clickhouse/expression/types/__init__.py
"""Lazy re-exports of ClickHouse ``types`` expressions (PEP 562).

Leaf modules are imported on first attribute access, never at package import
time. Public names stay reachable from this package exactly as before.
"""

from __future__ import annotations

import importlib as _importlib

_PKG = "rhosocial.activerecord.backend.impl.clickhouse.expression"

__all__ = [
    "ClickHouseAggregateFunctionType",
    "ClickHouseArrayType",
    "ClickHouseBoolType",
    "ClickHouseDate32Type",
    "ClickHouseDateTime64Type",
    "ClickHouseDateTimeType",
    "ClickHouseDateType",
    "ClickHouseDecimal128Type",
    "ClickHouseDecimal32Type",
    "ClickHouseDecimal64Type",
    "ClickHouseDecimalType",
    "ClickHouseEnum16Type",
    "ClickHouseEnum8Type",
    "ClickHouseFixedStringType",
    "ClickHouseFloat32Type",
    "ClickHouseFloat64Type",
    "ClickHouseGeometryCollectionType",
    "ClickHouseGeometryType",
    "ClickHouseIPv4Type",
    "ClickHouseIPv6Type",
    "ClickHouseInt16Type",
    "ClickHouseInt32Type",
    "ClickHouseInt64Type",
    "ClickHouseInt8Type",
    "ClickHouseJSONType",
    "ClickHouseLineStringType",
    "ClickHouseLowCardinalityType",
    "ClickHouseMapType",
    "ClickHouseMultiLineStringType",
    "ClickHouseMultiPointType",
    "ClickHouseMultiPolygonType",
    "ClickHouseNullableType",
    "ClickHousePointType",
    "ClickHousePolygonType",
    "ClickHouseSimpleAggregateFunctionType",
    "ClickHouseStringType",
    "ClickHouseTupleType",
    "ClickHouseUInt16Type",
    "ClickHouseUInt32Type",
    "ClickHouseUInt64Type",
    "ClickHouseUInt8Type",
    "ClickHouseUUIDType",
    "ClickHouseVectorType",
]

# name -> defining module, relative to the expression package
_NAME_TO_MODULE = {
    "ClickHouseAggregateFunctionType": "types.types",
    "ClickHouseArrayType": "types.types",
    "ClickHouseBoolType": "types.types",
    "ClickHouseDate32Type": "types.types",
    "ClickHouseDateTime64Type": "types.types",
    "ClickHouseDateTimeType": "types.types",
    "ClickHouseDateType": "types.types",
    "ClickHouseDecimal128Type": "types.types",
    "ClickHouseDecimal32Type": "types.types",
    "ClickHouseDecimal64Type": "types.types",
    "ClickHouseDecimalType": "types.types",
    "ClickHouseEnum16Type": "types.types",
    "ClickHouseEnum8Type": "types.types",
    "ClickHouseFixedStringType": "types.types",
    "ClickHouseFloat32Type": "types.types",
    "ClickHouseFloat64Type": "types.types",
    "ClickHouseGeometryCollectionType": "types.types",
    "ClickHouseGeometryType": "types.types",
    "ClickHouseIPv4Type": "types.types",
    "ClickHouseIPv6Type": "types.types",
    "ClickHouseInt16Type": "types.types",
    "ClickHouseInt32Type": "types.types",
    "ClickHouseInt64Type": "types.types",
    "ClickHouseInt8Type": "types.types",
    "ClickHouseJSONType": "types.types",
    "ClickHouseLineStringType": "types.types",
    "ClickHouseLowCardinalityType": "types.types",
    "ClickHouseMapType": "types.types",
    "ClickHouseMultiLineStringType": "types.types",
    "ClickHouseMultiPointType": "types.types",
    "ClickHouseMultiPolygonType": "types.types",
    "ClickHouseNullableType": "types.types",
    "ClickHousePointType": "types.types",
    "ClickHousePolygonType": "types.types",
    "ClickHouseSimpleAggregateFunctionType": "types.types",
    "ClickHouseStringType": "types.types",
    "ClickHouseTupleType": "types.types",
    "ClickHouseUInt16Type": "types.types",
    "ClickHouseUInt32Type": "types.types",
    "ClickHouseUInt64Type": "types.types",
    "ClickHouseUInt8Type": "types.types",
    "ClickHouseUUIDType": "types.types",
    "ClickHouseVectorType": "types.types",
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

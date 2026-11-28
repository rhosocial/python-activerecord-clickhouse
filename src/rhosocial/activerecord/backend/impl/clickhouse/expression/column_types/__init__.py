# src/rhosocial/activerecord/backend/impl/clickhouse/expression/column_types/__init__.py
"""Lazy re-exports of ClickHouse ``column_types`` expressions (PEP 562).

Leaf modules are imported on first attribute access, never at package import
time. Public names stay reachable from this package exactly as before.
"""

from __future__ import annotations

import importlib as _importlib

_PKG = "rhosocial.activerecord.backend.impl.clickhouse.expression"

__all__ = [
    "ClickHouseColumnDefinition",
    "ClickHouseColumnOptions",
    "ClickHouseVectorColumn",
]

# name -> defining module, relative to the expression package
_NAME_TO_MODULE = {
    "ClickHouseColumnDefinition": "column_types.column",
    "ClickHouseColumnOptions": "column_types.column",
    "ClickHouseVectorColumn": "column_types.column_types",
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

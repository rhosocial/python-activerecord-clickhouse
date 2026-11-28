# src/rhosocial/activerecord/backend/impl/clickhouse/expression/introspection/__init__.py
"""Lazy re-exports of ClickHouse ``introspection`` expressions (PEP 562).

Leaf modules are imported on first attribute access, never at package import
time. Public names stay reachable from this package exactly as before.
"""

from __future__ import annotations

import importlib as _importlib

_PKG = "rhosocial.activerecord.backend.impl.clickhouse.expression"

__all__ = [
    "ClickHouseAsynchronousMetricsQuery",
    "ClickHouseClusterListQuery",
    "ClickHouseConnectionGaugesQuery",
    "ClickHouseConnectionProbeQuery",
    "ClickHouseConstraintStateListQuery",
    "ClickHouseCurrentUserQuery",
    "ClickHouseDatabaseTotalSizeQuery",
    "ClickHouseDictionaryListQuery",
    "ClickHouseDiskListQuery",
    "ClickHouseEventsQuery",
    "ClickHouseFunctionListQuery",
    "ClickHouseGrantListQuery",
    "ClickHouseIndexStateListQuery",
    "ClickHouseIntrospectionUserListQuery",
    "ClickHouseMaterializedViewListQuery",
    "ClickHouseMetricsQuery",
    "ClickHouseProcessListQuery",
    "ClickHouseProjectionListQuery",
    "ClickHouseQuotaListQuery",
    "ClickHouseReplicaListQuery",
    "ClickHouseRoleGrantListQuery",
    "ClickHouseRoleListQuery",
    "ClickHouseRowCountQuery",
    "ClickHouseSchemaListQuery",
    "ClickHouseServerSettingQuery",
    "ClickHouseServerSettingsQuery",
    "ClickHouseSettingQuery",
    "ClickHouseSettingsQuery",
    "ClickHouseTableCountQuery",
    "ClickHouseTableEngineQuery",
    "ClickHouseTablePartitionsQuery",
    "ClickHouseUserListQuery",
    "ClickHouseVersionQuery",
]

# name -> defining module, relative to the expression package
_NAME_TO_MODULE = {
    "ClickHouseAsynchronousMetricsQuery": "introspection.status",
    "ClickHouseClusterListQuery": "introspection.introspection",
    "ClickHouseConnectionGaugesQuery": "introspection.status",
    "ClickHouseConnectionProbeQuery": "introspection.status",
    "ClickHouseConstraintStateListQuery": "introspection.introspection",
    "ClickHouseCurrentUserQuery": "introspection.status",
    "ClickHouseDatabaseTotalSizeQuery": "introspection.status",
    "ClickHouseDictionaryListQuery": "introspection.introspection",
    "ClickHouseDiskListQuery": "introspection.status",
    "ClickHouseEventsQuery": "introspection.status",
    "ClickHouseFunctionListQuery": "introspection.introspection",
    "ClickHouseGrantListQuery": "introspection.status",
    "ClickHouseIndexStateListQuery": "introspection.introspection",
    "ClickHouseIntrospectionUserListQuery": "introspection.introspection",
    "ClickHouseMaterializedViewListQuery": "introspection.introspection",
    "ClickHouseMetricsQuery": "introspection.status",
    "ClickHouseProcessListQuery": "introspection.status",
    "ClickHouseProjectionListQuery": "introspection.introspection",
    "ClickHouseQuotaListQuery": "introspection.introspection",
    "ClickHouseReplicaListQuery": "introspection.status",
    "ClickHouseRoleGrantListQuery": "introspection.status",
    "ClickHouseRoleListQuery": "introspection.introspection",
    "ClickHouseRowCountQuery": "introspection.status",
    "ClickHouseSchemaListQuery": "introspection.introspection",
    "ClickHouseServerSettingQuery": "introspection.status",
    "ClickHouseServerSettingsQuery": "introspection.status",
    "ClickHouseSettingQuery": "introspection.status",
    "ClickHouseSettingsQuery": "introspection.status",
    "ClickHouseTableCountQuery": "introspection.status",
    "ClickHouseTableEngineQuery": "introspection.introspection",
    "ClickHouseTablePartitionsQuery": "introspection.introspection",
    "ClickHouseUserListQuery": "introspection.status",
    "ClickHouseVersionQuery": "introspection.status",
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

# src/rhosocial/activerecord/backend/impl/clickhouse/introspection/__init__.py
"""
ClickHouse introspection package.

Provides:
  ClickHouseIntrospector   — synchronous introspector for ClickHouse databases
  AsyncClickHouseIntrospector  — asynchronous introspector for ClickHouse databases
  ShowIntrospector    — synchronous ClickHouse-specific SHOW command sub-introspector
  AsyncShowIntrospector   — asynchronous ClickHouse-specific SHOW command sub-introspector
  ClickHouseStatusIntrospector  — synchronous ClickHouse status introspector
  AsyncClickHouseStatusIntrospector -- asynchronous ClickHouse status introspector

Also re-exports the ClickHouse-specific result types (`ClickHousePartitionInfo`,
`ClickHouseTableEngineInfo`, `ClickHouseColumnDataProfile`) the two introspectors
return, plus the server-wide catalogue result types (`ClickHouseFunctionInfo`,
`ClickHouseDictionaryInfo`, `ClickHouseClusterInfo`, `ClickHouseQuotaInfo`,
`ClickHouseUserInfo`, `ClickHouseRoleInfo`).
"""

from .introspector import (
    AsyncClickHouseIntrospector,
    ClickHouseIntrospector,
)
from .show_introspector import (
    AsyncShowIntrospector,
    ShowIntrospector,
)
from .status_introspector import (
    AsyncClickHouseStatusIntrospector,
    ClickHouseStatusIntrospector,
)
from .types import (
    ClickHouseClusterInfo,
    ClickHouseColumnDataProfile,
    ClickHouseDictionaryInfo,
    ClickHouseFunctionInfo,
    ClickHousePartitionInfo,
    ClickHouseQuotaInfo,
    ClickHouseRoleInfo,
    ClickHouseTableEngineInfo,
    ClickHouseUserInfo,
)

__all__ = [
    "ClickHouseIntrospector",
    "AsyncClickHouseIntrospector",
    "ShowIntrospector",
    "AsyncShowIntrospector",
    "ClickHouseStatusIntrospector",
    "AsyncClickHouseStatusIntrospector",
    "ClickHousePartitionInfo",
    "ClickHouseTableEngineInfo",
    "ClickHouseColumnDataProfile",
    "ClickHouseFunctionInfo",
    "ClickHouseDictionaryInfo",
    "ClickHouseClusterInfo",
    "ClickHouseQuotaInfo",
    "ClickHouseUserInfo",
    "ClickHouseRoleInfo",
]

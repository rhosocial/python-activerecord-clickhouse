# src/rhosocial/activerecord/backend/impl/clickhouse/introspection/__init__.py
"""
ClickHouse introspection package.

Provides:
  SyncClickHouseIntrospector   — synchronous introspector for ClickHouse databases
  AsyncClickHouseIntrospector  — asynchronous introspector for ClickHouse databases
  SyncShowIntrospector    — synchronous ClickHouse-specific SHOW command sub-introspector
  AsyncShowIntrospector   — asynchronous ClickHouse-specific SHOW command sub-introspector
  SyncClickHouseStatusIntrospector  — synchronous ClickHouse status introspector
  AsyncClickHouseStatusIntrospector -- asynchronous ClickHouse status introspector

Also re-exports the ClickHouse-specific result types (`ClickHousePartitionInfo`,
`ClickHouseTableEngineInfo`) the two introspectors return.
"""

from .introspector import (
    SyncClickHouseIntrospector,
    AsyncClickHouseIntrospector,
)
from .show_introspector import (
    SyncShowIntrospector,
    AsyncShowIntrospector,
)
from .status_introspector import (
    SyncClickHouseStatusIntrospector,
    AsyncClickHouseStatusIntrospector,
)
from .types import (
    ClickHousePartitionInfo,
    ClickHouseTableEngineInfo,
)

__all__ = [
    "SyncClickHouseIntrospector",
    "AsyncClickHouseIntrospector",
    "SyncShowIntrospector",
    "AsyncShowIntrospector",
    "SyncClickHouseStatusIntrospector",
    "AsyncClickHouseStatusIntrospector",
    "ClickHousePartitionInfo",
    "ClickHouseTableEngineInfo",
]

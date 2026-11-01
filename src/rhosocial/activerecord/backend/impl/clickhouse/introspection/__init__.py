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
`ClickHouseTableEngineInfo`) the two introspectors return.
"""

from .introspector import (
    ClickHouseIntrospector,
    AsyncClickHouseIntrospector,
)
from .show_introspector import (
    ShowIntrospector,
    AsyncShowIntrospector,
)
from .status_introspector import (
    ClickHouseStatusIntrospector,
    AsyncClickHouseStatusIntrospector,
)
from .types import (
    ClickHousePartitionInfo,
    ClickHouseTableEngineInfo,
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
]

# src/rhosocial/activerecord/backend/impl/clickhouse/expression/query_parts/__init__.py
"""Lazy re-exports of ClickHouse ``query_parts`` expressions (PEP 562).

Leaf modules are imported on first attribute access, never at package import
time. Public names stay reachable from this package exactly as before.
"""

from __future__ import annotations

import importlib as _importlib

_PKG = "rhosocial.activerecord.backend.impl.clickhouse.expression"

__all__ = [
    "CLICKHOUSE_STORAGE_CLAUSE_ORDER",
    "ClickHouseAttachPartitionStatement",
    "ClickHouseClearInPartitionStatement",
    "ClickHouseCreateTableOptions",
    "ClickHouseDetachPartitionStatement",
    "ClickHouseDropPartitionStatement",
    "ClickHouseEngineSpec",
    "ClickHouseFreezePartitionStatement",
    "ClickHouseMovePartitionStatement",
    "ClickHouseOptimizePartitionStatement",
    "ClickHouseOptimizerHintExpression",
    "ClickHouseReplacePartitionStatement",
    "ClickHouseSetting",
    "ClickHouseStorageOptionKind",
    "ClickHouseTableStorageOption",
    "ClickHouseUnfreezePartitionStatement",
    "OptimizerHintType",
    "SetVarHint",
]

# name -> defining module, relative to the expression package
_NAME_TO_MODULE = {
    "CLICKHOUSE_STORAGE_CLAUSE_ORDER": "query_parts.storage_option",
    "ClickHouseAttachPartitionStatement": "query_parts.partition",
    "ClickHouseClearInPartitionStatement": "query_parts.partition",
    "ClickHouseCreateTableOptions": "query_parts.create_table_options",
    "ClickHouseDetachPartitionStatement": "query_parts.partition",
    "ClickHouseDropPartitionStatement": "query_parts.partition",
    "ClickHouseEngineSpec": "query_parts.storage_option",
    "ClickHouseFreezePartitionStatement": "query_parts.partition",
    "ClickHouseMovePartitionStatement": "query_parts.partition",
    "ClickHouseOptimizePartitionStatement": "query_parts.partition",
    "ClickHouseOptimizerHintExpression": "query_parts.optimizer_hint",
    "ClickHouseReplacePartitionStatement": "query_parts.partition",
    "ClickHouseSetting": "query_parts.storage_option",
    "ClickHouseStorageOptionKind": "query_parts.storage_option",
    "ClickHouseTableStorageOption": "query_parts.storage_option",
    "ClickHouseUnfreezePartitionStatement": "query_parts.partition",
    "OptimizerHintType": "query_parts.optimizer_hint",
    "SetVarHint": "query_parts.optimizer_hint",
    "_ClickHousePartitionIdExpression": "query_parts.partition",
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

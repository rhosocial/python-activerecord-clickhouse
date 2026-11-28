# src/rhosocial/activerecord/backend/impl/clickhouse/expression/operators/__init__.py
"""Lazy re-exports of ClickHouse ``operators`` expressions (PEP 562).

Leaf modules are imported on first attribute access, never at package import
time. Public names stay reachable from this package exactly as before.
"""

from __future__ import annotations

import importlib as _importlib

_PKG = "rhosocial.activerecord.backend.impl.clickhouse.expression"

__all__ = [
    "CheckTableOption",
    "ChecksumTableOption",
    "ClickHouseAddColumnAction",
    "ClickHouseAnalyzeTableExpression",
    "ClickHouseAttachPartitionStatement",
    "ClickHouseCheckTableExpression",
    "ClickHouseChecksumTableExpression",
    "ClickHouseClearInPartitionStatement",
    "ClickHouseDetachPartitionStatement",
    "ClickHouseDropPartitionStatement",
    "ClickHouseFreezePartitionStatement",
    "ClickHouseMovePartitionStatement",
    "ClickHouseOptimizePartitionStatement",
    "ClickHouseOptimizeTableExpression",
    "ClickHouseRepairTableExpression",
    "ClickHouseReplacePartitionStatement",
    "ClickHouseTableMaintenanceStatement",
    "ClickHouseUnfreezePartitionStatement",
    "NoWriteToBinlogOption",
    "RepairTableOption",
]

# name -> defining module, relative to the expression package
_NAME_TO_MODULE = {
    "CheckTableOption": "statements.maintenance",
    "ChecksumTableOption": "statements.maintenance",
    "ClickHouseAddColumnAction": "operators.alter_column",
    "ClickHouseAnalyzeTableExpression": "statements.maintenance",
    "ClickHouseAttachPartitionStatement": "query_parts.partition",
    "ClickHouseCheckTableExpression": "statements.maintenance",
    "ClickHouseChecksumTableExpression": "statements.maintenance",
    "ClickHouseClearInPartitionStatement": "query_parts.partition",
    "ClickHouseDetachPartitionStatement": "query_parts.partition",
    "ClickHouseDropPartitionStatement": "query_parts.partition",
    "ClickHouseFreezePartitionStatement": "query_parts.partition",
    "ClickHouseMovePartitionStatement": "query_parts.partition",
    "ClickHouseOptimizePartitionStatement": "query_parts.partition",
    "ClickHouseOptimizeTableExpression": "statements.maintenance",
    "ClickHouseRepairTableExpression": "statements.maintenance",
    "ClickHouseReplacePartitionStatement": "query_parts.partition",
    "ClickHouseTableMaintenanceStatement": "statements.maintenance",
    "ClickHouseUnfreezePartitionStatement": "query_parts.partition",
    "NoWriteToBinlogOption": "statements.maintenance",
    "RepairTableOption": "statements.maintenance",
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

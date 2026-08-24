# src/rhosocial/activerecord/backend/impl/clickhouse/expression/__init__.py
"""
ClickHouse-specific expression classes.

Only ClickHouse-native expressions are exported from this package:

- ``json``       — ClickHouse ``JSONExtract*`` / ``JSONObject`` / ``JSONArray``
                   function expressions (ClickHouse JSON is accessed via
                   functions, not MySQL arrow operators).
- ``partition``  — MySQL declarative partitioning expression classes, kept as
                   fail-fast stubs (ClickHouse uses ``PARTITION BY <expr>``
                   inside ``CREATE TABLE``, handled by the table-engine layer,
                   not MySQL ``PARTITION ... VALUES`` syntax).
- ``rename_table`` — ClickHouse ``RENAME TABLE``.
- ``types``      — ClickHouse-native ``DataType`` subclasses for DDL.

MySQL-only expressions (``LOAD DATA``, ``JSON_TABLE``, ``MATCH ... AGAINST``,
``ST_*`` spatial, ``VECTOR``, ``JSON Duality View``, optimizer hints,
``TABLE``/``VALUES`` constructors, ``ANALYZE``/``CHECK``/``CHECKSUM``/
``REPAIR TABLE`` maintenance, stored ``PROCEDURE``/``FUNCTION``/``CALL``,
``LOAD XML``, and the ``FLUSH``/``RESET``/``KILL``/``GRANT`` admin command
set) are intentionally **not** exported: ClickHouse does not support them and
the corresponding dialect mixins fail fast with ``UnsupportedFeatureError``.
"""

from .json import (
    ClickHouseJSONExtractExpression,
    ClickHouseJSONObjectExpression,
    ClickHouseJSONArrayExpression,
    ClickHouseJSONContainsExpression,
)
from .partition import (
    ClickHousePartitionStrategy,
    ClickHousePartitionClause,
    ClickHousePartitionMaxValue,
    ClickHousePartitionValue,
    ClickHousePartitionDefinition,
    ClickHousePartitionByRange,
    ClickHousePartitionByRangeColumns,
    ClickHousePartitionByList,
    ClickHousePartitionByListColumns,
    ClickHousePartitionByHash,
    ClickHousePartitionByKey,
    ClickHouseAddPartitionExpression,
    ClickHouseDropPartitionExpression,
    ClickHouseTruncatePartitionExpression,
    ClickHouseReorganizePartitionExpression,
    ClickHouseExchangePartitionExpression,
    ClickHouseRemovePartitioningExpression,
    ClickHouseCoalescePartitionExpression,
    ClickHouseAnalyzePartitionExpression,
    ClickHouseCheckPartitionExpression,
    ClickHouseOptimizePartitionExpression,
    ClickHouseRebuildPartitionExpression,
    ClickHouseRepairPartitionExpression,
    ClickHouseGetPartitionsExpression,
    ClickHouseSubpartitionStrategy,
    ClickHouseSubpartitionDefinition,
    ClickHouseSubpartitionClause,
)
from .rename_table import ClickHouseRenameTableExpression

# DataType subclasses for DDL
from .types import (
    ClickHouseAggregateFunctionType,
    ClickHouseArrayType,
    ClickHouseBoolType,
    ClickHouseDate32Type,
    ClickHouseDateType,
    ClickHouseDateTime64Type,
    ClickHouseDateTimeType,
    ClickHouseDecimal32Type,
    ClickHouseDecimal64Type,
    ClickHouseDecimal128Type,
    ClickHouseDecimalType,
    ClickHouseEnum16Type,
    ClickHouseEnum8Type,
    ClickHouseFixedStringType,
    ClickHouseFloat32Type,
    ClickHouseFloat64Type,
    ClickHouseInt16Type,
    ClickHouseInt32Type,
    ClickHouseInt64Type,
    ClickHouseInt8Type,
    ClickHouseIPv4Type,
    ClickHouseIPv6Type,
    ClickHouseJSONType,
    ClickHouseLowCardinalityType,
    ClickHouseMapType,
    ClickHouseNullableType,
    ClickHouseSimpleAggregateFunctionType,
    ClickHouseStringType,
    ClickHouseTupleType,
    ClickHouseUInt16Type,
    ClickHouseUInt32Type,
    ClickHouseUInt64Type,
    ClickHouseUInt8Type,
    ClickHouseUUIDType,
)

__all__ = [
    "ClickHouseJSONExtractExpression",
    "ClickHouseJSONObjectExpression",
    "ClickHouseJSONArrayExpression",
    "ClickHouseJSONContainsExpression",
    "ClickHousePartitionStrategy",
    "ClickHousePartitionClause",
    "ClickHousePartitionMaxValue",
    "ClickHousePartitionValue",
    "ClickHousePartitionDefinition",
    "ClickHousePartitionByRange",
    "ClickHousePartitionByRangeColumns",
    "ClickHousePartitionByList",
    "ClickHousePartitionByListColumns",
    "ClickHousePartitionByHash",
    "ClickHousePartitionByKey",
    "ClickHouseAddPartitionExpression",
    "ClickHouseDropPartitionExpression",
    "ClickHouseTruncatePartitionExpression",
    "ClickHouseReorganizePartitionExpression",
    "ClickHouseExchangePartitionExpression",
    "ClickHouseRemovePartitioningExpression",
    "ClickHouseCoalescePartitionExpression",
    "ClickHouseAnalyzePartitionExpression",
    "ClickHouseCheckPartitionExpression",
    "ClickHouseOptimizePartitionExpression",
    "ClickHouseRebuildPartitionExpression",
    "ClickHouseRepairPartitionExpression",
    "ClickHouseGetPartitionsExpression",
    "ClickHouseSubpartitionStrategy",
    "ClickHouseSubpartitionDefinition",
    "ClickHouseSubpartitionClause",
    "ClickHouseRenameTableExpression",
    # DataType subclasses for DDL
    "ClickHouseAggregateFunctionType",
    "ClickHouseArrayType",
    "ClickHouseBoolType",
    "ClickHouseDate32Type",
    "ClickHouseDateType",
    "ClickHouseDateTime64Type",
    "ClickHouseDateTimeType",
    "ClickHouseDecimal32Type",
    "ClickHouseDecimal64Type",
    "ClickHouseDecimal128Type",
    "ClickHouseDecimalType",
    "ClickHouseEnum16Type",
    "ClickHouseEnum8Type",
    "ClickHouseFixedStringType",
    "ClickHouseFloat32Type",
    "ClickHouseFloat64Type",
    "ClickHouseInt16Type",
    "ClickHouseInt32Type",
    "ClickHouseInt64Type",
    "ClickHouseInt8Type",
    "ClickHouseIPv4Type",
    "ClickHouseIPv6Type",
    "ClickHouseJSONType",
    "ClickHouseLowCardinalityType",
    "ClickHouseMapType",
    "ClickHouseNullableType",
    "ClickHouseSimpleAggregateFunctionType",
    "ClickHouseStringType",
    "ClickHouseTupleType",
    "ClickHouseUInt16Type",
    "ClickHouseUInt32Type",
    "ClickHouseUInt64Type",
    "ClickHouseUInt8Type",
    "ClickHouseUUIDType",
]

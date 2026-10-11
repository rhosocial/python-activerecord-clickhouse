# src/rhosocial/activerecord/backend/impl/clickhouse/expression/__init__.py
"""
ClickHouse-specific expression classes.

Only ClickHouse-native expressions are exported from this package:

- ``json``       — ClickHouse ``JSONExtract*`` / ``JSONObject`` / ``JSONArray``
                   function expressions (ClickHouse JSON is accessed via
                   functions, not MySQL arrow operators).
- ``partition``  — ClickHouse's own partition maintenance, addressed by
                   partition id (``DROP`` / ``DETACH`` / ``ATTACH PARTITION ID``).
                   ClickHouse has no declarative partitioning: it partitions a
                   MergeTree table with ``PARTITION BY <expr>`` inside
                   ``CREATE TABLE``, rendered by the table-engine layer, and a
                   partition appears when a row lands in it.
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

from .alter_column import ClickHouseAddColumn
from .column import ClickHouseColumnDefinition, ClickHouseColumnOptions
from .database import (
    ClickHouseCreateDatabaseExpression,
    ClickHouseDropDatabaseExpression,
)
from .dml import ClickHouseInsertExpression
from .materialized_view import (
    ClickHouseCreateMaterializedViewExpression,
    ClickHouseDropMaterializedViewExpression,
    ClickHouseIntervalUnit,
    ClickHouseModifyMaterializedViewRefreshExpression,
    ClickHouseRefreshMaterializedViewExpression,
    ClickHouseRefreshSchedule,
)
from .index import ClickHouseIndexDefinition
from .json import (
    ClickHouseJSONExtractExpression,
    ClickHouseJSONObjectExpression,
    ClickHouseJSONArrayExpression,
    ClickHouseJSONContainsExpression,
    ClickHouseJSONUnquoteExpression,
    ClickHouseJSONSetExpression,
    ClickHouseJSONRemoveExpression,
    ClickHouseJSONTypeExpression,
    ClickHouseJSONValidExpression,
    ClickHouseJSONSearchExpression,
)
from .partition import (
    ClickHouseDropPartitionExpression,
    ClickHouseDetachPartitionExpression,
    ClickHouseAttachPartitionExpression,
)
from .rename_table import ClickHouseRenameTableExpression
from .spatial import (
    ClickHouseCreateSpatialIndexExpression,
    ClickHouseSTAsGeoJSONExpression,
    ClickHouseSTAsTextExpression,
    ClickHouseSTContainsExpression,
    ClickHouseSTDistanceExpression,
    ClickHouseSTGeomFromTextExpression,
    ClickHouseSTGeomFromWKBExpression,
    ClickHouseSTWithinExpression,
    ClickHouseSpatialLiteralExpression,
)

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
    # Index expressions
    "ClickHouseIndexDefinition",
    "ClickHouseAddColumn",
    "ClickHouseColumnDefinition",
    "ClickHouseColumnOptions",
    # Database / DML expressions
    "ClickHouseCreateDatabaseExpression",
    "ClickHouseDropDatabaseExpression",
    "ClickHouseInsertExpression",
    # JSON expressions
    "ClickHouseJSONExtractExpression",
    "ClickHouseJSONObjectExpression",
    "ClickHouseJSONArrayExpression",
    "ClickHouseJSONContainsExpression",
    "ClickHouseJSONUnquoteExpression",
    "ClickHouseJSONSetExpression",
    "ClickHouseJSONRemoveExpression",
    "ClickHouseJSONTypeExpression",
    "ClickHouseJSONValidExpression",
    "ClickHouseJSONSearchExpression",
    # Spatial expressions
    "ClickHouseCreateSpatialIndexExpression",
    "ClickHouseSTAsGeoJSONExpression",
    "ClickHouseSTAsTextExpression",
    "ClickHouseSTContainsExpression",
    "ClickHouseSTDistanceExpression",
    "ClickHouseSTGeomFromTextExpression",
    "ClickHouseSTGeomFromWKBExpression",
    "ClickHouseSTWithinExpression",
    "ClickHouseSpatialLiteralExpression",
    # Partition
    "ClickHouseDropPartitionExpression",
    "ClickHouseDetachPartitionExpression",
    "ClickHouseAttachPartitionExpression",
    # Rename table
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
    # Materialized views
    "ClickHouseCreateMaterializedViewExpression",
    "ClickHouseDropMaterializedViewExpression",
    "ClickHouseRefreshMaterializedViewExpression",
    "ClickHouseModifyMaterializedViewRefreshExpression",
    "ClickHouseRefreshSchedule",
    "ClickHouseIntervalUnit",
]

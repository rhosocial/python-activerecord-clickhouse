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

from .alter_column import ClickHouseAddColumnAction
from .column import ClickHouseColumnDefinition, ClickHouseColumnOptions
from .create_table_options import ClickHouseCreateTableOptions
from .database import (
    ClickHouseCreateDatabaseExpression,
    ClickHouseDropDatabaseExpression,
)
from .dml import ClickHouseInsertExpression
from .materialized_view import (
    ClickHouseCreateMaterializedViewStatement,
    ClickHouseDropMaterializedViewStatement,
    ClickHouseModifyMaterializedViewRefreshStatement,
    ClickHouseRefreshMaterializedViewStatement,
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
    ClickHouseDropPartitionStatement,
    ClickHouseDetachPartitionStatement,
    ClickHouseAttachPartitionStatement,
)
from .rename_table import ClickHouseRenameTableStatement
from .wildcard import ClickHouseRowCountDistinctWildcard
from .spatial import (
    ClickHouseCreateSpatialIndexStatement,
    ClickHouseSTAsGeoJSONExpression,
    ClickHouseSTAsTextExpression,
    ClickHouseSTContainsExpression,
    ClickHouseSTDistanceExpression,
    ClickHouseSTGeomFromTextExpression,
    ClickHouseSTGeomFromWKBExpression,
    ClickHouseSTWithinExpression,
    ClickHouseSpatialLiteralExpression,
)
from .storage_option import (
    ClickHouseEngineSpec,
    ClickHouseSetting,
    ClickHouseStorageOptionKind,
    ClickHouseTableStorageOption,
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
    "ClickHouseAddColumnAction",
    "ClickHouseColumnDefinition",
    "ClickHouseColumnOptions",
    # CREATE TABLE storage clauses
    "ClickHouseCreateTableOptions",
    "ClickHouseStorageOptionKind",
    "ClickHouseTableStorageOption",
    "ClickHouseEngineSpec",
    "ClickHouseSetting",
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
    "ClickHouseCreateSpatialIndexStatement",
    "ClickHouseSTAsGeoJSONExpression",
    "ClickHouseSTAsTextExpression",
    "ClickHouseSTContainsExpression",
    "ClickHouseSTDistanceExpression",
    "ClickHouseSTGeomFromTextExpression",
    "ClickHouseSTGeomFromWKBExpression",
    "ClickHouseSTWithinExpression",
    "ClickHouseSpatialLiteralExpression",
    # Partition
    "ClickHouseDropPartitionStatement",
    "ClickHouseDetachPartitionStatement",
    "ClickHouseAttachPartitionStatement",
    # Rename table
    "ClickHouseRenameTableStatement",
    # Row-count wildcard: the COUNT(DISTINCT *) spelling only ClickHouse has
    "ClickHouseRowCountDistinctWildcard",
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
    "ClickHouseCreateMaterializedViewStatement",
    "ClickHouseDropMaterializedViewStatement",
    "ClickHouseRefreshMaterializedViewStatement",
    "ClickHouseModifyMaterializedViewRefreshStatement",
    "ClickHouseRefreshSchedule",
]

# ``ClickHouse`` is one word. The general derivation -- a run of capitals counts
# as a single word -- splits at the camel-case seam instead, so this backend
# shipped ``click_house_flush_expression`` and ``click_house_load_xmle_xpression``:
# two spellings of one identifier, neither of them the word the class is named
# after. The kind is a wire contract (§3), so the identifier is declared whole
# and the kind is derived from that declaration: ``KIND_RESERVED`` is data, not
# behaviour, so no class overrides ``kind()`` and class name, kind and
# formatting entry keep one source.
#
# One word the declaration cannot reach: ``ClickHouseIPv4Type`` and
# ``ClickHouseUInt8Type`` still derive ``clickhouse_i_pv4_type`` and
# ``clickhouse_u_int8_type``, because ``IPv``/``UInt`` are one capital followed
# by lower case and the general rule reads that as two words. A reserved token
# cannot reach it either -- the token is lowercased and joined with a single
# underscore, so a token spelled ``ClickHouseIPv`` yields ``clickhouseipv``. The
# core has the same shape on ``JsonBType`` (``json_b_type``), so the split is
# the rule meeting a mixed-case vendor type spelling rather than a defect
# invented here; it is reported to the rule owner rather than worked around with
# a local spelling table.
#
# The loop walks this package's own modules rather than the ``__all__`` list
# above, for the reason the sqlite package's note gives: a hand-maintained list
# can only ever be out of date, and a node defined but not re-exported here --
# the SHOW family, the private ``_ClickHousePartitionIdExpression`` -- would
# silently keep the split spelling. The leading-underscore node declares the
# token with its underscore so ``name.startswith(token)`` still matches: a
# private name is still a name the artifact carries.
import importlib as _importlib
import pkgutil as _pkgutil

from rhosocial.activerecord.backend.expression.core import BaseExpression as _BaseExpression

_KIND_TOKENS = ("ClickHouse",)

for _module_info in _pkgutil.walk_packages(__path__, prefix=__name__ + ".", onerror=lambda _error: None):
    _module = _importlib.import_module(_module_info.name)
    for _value in vars(_module).values():
        if (
            isinstance(_value, type)
            and issubclass(_value, _BaseExpression)
            and _value.__module__ == _module_info.name
        ):
            _stem = _value.__name__.lstrip("_")
            for _token in _KIND_TOKENS:
                if _stem.startswith(_token):
                    _prefix = _value.__name__[: len(_value.__name__) - len(_stem)]
                    _value.KIND_RESERVED = (_prefix + _token,)
                    break
del _module_info, _module, _value, _importlib, _pkgutil, _BaseExpression, _KIND_TOKENS, _stem, _token, _prefix

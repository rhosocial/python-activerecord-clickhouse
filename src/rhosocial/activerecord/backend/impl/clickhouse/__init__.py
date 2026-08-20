# src/rhosocial/activerecord/backend/impl/clickhouse/__init__.py
"""
ClickHouse backend implementation for the Python ORM.

This module provides:
- ClickHouse synchronous backend with connection management and query execution
- ClickHouse asynchronous backend with async/await support
- ClickHouse-specific connection configuration
- Type mapping and value conversion
- Transaction management with savepoint support (sync and async)
- ClickHouse dialect and expression handling
- ClickHouse-specific type helpers (ENUM, SET)
- ClickHouse-specific SQL function factories (JSON, spatial, full-text, etc.)

Architecture:
- ClickHouseBackend: Synchronous implementation using clickhouse-connector-python
- AsyncClickHouseBackend: Asynchronous implementation using aioclickhouse
- Independent from ORM frameworks - uses only native drivers
"""

from .backend import ClickHouseBackend
from .async_backend import AsyncClickHouseBackend
from .config import ClickHouseConnectionConfig
from .collation import ClickHouseCollation, ClickHouseCollationValidator
from .dialect import ClickHouseDialect
from .transaction import ClickHouseTransactionManager
from .async_transaction import AsyncClickHouseTransactionManager
from .types import ClickHouseEnumType, ClickHouseSetType
from .expression.types import (
    ClickHouseBigIntType,
    ClickHouseBinaryType,
    ClickHouseBitType,
    ClickHouseBlobType,
    ClickHouseEnumType as ClickHouseEnumDataType,
    ClickHouseGeometryCollectionType,
    ClickHouseGeometryType,
    ClickHouseIntType,
    ClickHouseLineStringType,
    ClickHouseLongBlobType,
    ClickHouseLongTextType,
    ClickHouseMediumBlobType,
    ClickHouseMediumTextType,
    ClickHouseMultiLineStringType,
    ClickHouseMultiPointType,
    ClickHouseMultiPolygonType,
    ClickHousePointType,
    ClickHousePolygonType,
    ClickHouseSetType as ClickHouseSetDataType,
    ClickHouseSmallIntType,
    ClickHouseTextType,
    ClickHouseTinyBlobType,
    ClickHouseTinyIntType,
    ClickHouseTinyTextType,
    ClickHouseVarBinaryType,
    ClickHouseVectorType,
    ClickHouseYearType,
)
from .explain import ClickHouseExplainResult, ClickHouseExplainRow

# Import ClickHouse-specific functions directly for convenience
from .functions import (
    # JSON functions
    json_extract,
    json_unquote,
    json_object,
    json_array,
    json_contains,
    json_set,
    json_remove,
    json_type,
    json_valid,
    json_search,
    # Spatial functions
    st_geom_from_text,
    st_geom_from_wkb,
    st_as_text,
    st_as_geojson,
    st_distance,
    st_within,
    st_contains,
    st_intersects,
    # Full-text search
    match_against,
    # SET type functions
    find_in_set,
    # Enum type functions
    elt,
    field,
)

# Import ClickHouse SHOW command expressions
from .show.expressions import (
    ShowExpression,
    ShowCreateTableExpression,
    ShowColumnsExpression,
    ShowTableStatusExpression,
    ShowIndexExpression,
    ShowTablesExpression,
    ShowDatabasesExpression,
    ShowTriggersExpression,
    ShowCreateViewExpression,
    ShowVariablesExpression,
    ShowStatusExpression,
    ShowWarningsExpression,
    ShowErrorsExpression,
    ShowCreateTriggerExpression,
    ShowGrantsExpression,
    ShowProcessListExpression,
    ShowEnginesExpression,
    ShowCharsetExpression,
    ShowCollationExpression,
    ShowPluginsExpression,
)

# Import ClickHouse SHOW command result types
from .show.types import (
    # CREATE statement results
    ShowCreateTableResult,
    ShowCreateViewResult,
    ShowCreateTriggerResult,
    # Column information results
    ShowColumnResult,
    # Table status results
    ShowTableStatusResult,
    # Index information results
    ShowIndexResult,
    # Database and table list results
    ShowTableResult,
    ShowDatabaseResult,
    # Trigger results
    ShowTriggerResult,
    # Variables and status results
    ShowVariableResult,
    ShowStatusResult,
    # Warning and error results
    ShowWarningResult,
    # Grants results
    ShowGrantResult,
    # Process list results
    ShowProcessListResult,
    # Engine results
    ShowEngineResult,
    # Charset and collation results
    ShowCharsetResult,
    ShowCollationResult,
    # Plugin results
    ShowPluginResult,
)


__all__ = [
    # Synchronous Backend
    "ClickHouseBackend",
    # Asynchronous Backend
    "AsyncClickHouseBackend",
    # Configuration
    "ClickHouseConnectionConfig",
    # Dialect related
    "ClickHouseDialect",
    "ClickHouseCollation",
    "ClickHouseCollationValidator",
    # Transaction - Sync and Async
    "ClickHouseTransactionManager",
    "AsyncClickHouseTransactionManager",
    # ClickHouse-specific Type Helpers
    "ClickHouseEnumType",
    "ClickHouseSetType",
    # ClickHouse DataType subclasses for DDL
    "ClickHouseBigIntType",
    "ClickHouseBinaryType",
    "ClickHouseBitType",
    "ClickHouseBlobType",
    "ClickHouseEnumDataType",
    "ClickHouseGeometryCollectionType",
    "ClickHouseGeometryType",
    "ClickHouseIntType",
    "ClickHouseLineStringType",
    "ClickHouseLongBlobType",
    "ClickHouseLongTextType",
    "ClickHouseMediumBlobType",
    "ClickHouseMediumTextType",
    "ClickHouseMultiLineStringType",
    "ClickHouseMultiPointType",
    "ClickHouseMultiPolygonType",
    "ClickHousePointType",
    "ClickHousePolygonType",
    "ClickHouseSetDataType",
    "ClickHouseSmallIntType",
    "ClickHouseTextType",
    "ClickHouseTinyBlobType",
    "ClickHouseTinyIntType",
    "ClickHouseTinyTextType",
    "ClickHouseVarBinaryType",
    "ClickHouseVectorType",
    "ClickHouseYearType",
    # ClickHouse EXPLAIN Result Types
    "ClickHouseExplainResult",
    "ClickHouseExplainRow",
    # ClickHouse-specific Functions - JSON
    "json_extract",
    "json_unquote",
    "json_object",
    "json_array",
    "json_contains",
    "json_set",
    "json_remove",
    "json_type",
    "json_valid",
    "json_search",
    # ClickHouse-specific Functions - Spatial
    "st_geom_from_text",
    "st_geom_from_wkb",
    "st_as_text",
    "st_as_geojson",
    "st_distance",
    "st_within",
    "st_contains",
    "st_intersects",
    # ClickHouse-specific Functions - Full-text Search
    "match_against",
    # ClickHouse-specific Functions - SET/Enum
    "find_in_set",
    "elt",
    "field",
    # ClickHouse SHOW Command Expressions
    "ShowExpression",
    "ShowCreateTableExpression",
    "ShowColumnsExpression",
    "ShowTableStatusExpression",
    "ShowIndexExpression",
    "ShowTablesExpression",
    "ShowDatabasesExpression",
    "ShowTriggersExpression",
    "ShowCreateViewExpression",
    "ShowVariablesExpression",
    "ShowStatusExpression",
    "ShowWarningsExpression",
    "ShowErrorsExpression",
    "ShowCreateTriggerExpression",
    "ShowGrantsExpression",
    "ShowProcessListExpression",
    "ShowEnginesExpression",
    "ShowCharsetExpression",
    "ShowCollationExpression",
    "ShowPluginsExpression",
    # ClickHouse SHOW Command Result Types
    "ShowCreateTableResult",
    "ShowCreateViewResult",
    "ShowCreateTriggerResult",
    "ShowColumnResult",
    "ShowTableStatusResult",
    "ShowIndexResult",
    "ShowTableResult",
    "ShowDatabaseResult",
    "ShowTriggerResult",
    "ShowVariableResult",
    "ShowStatusResult",
    "ShowWarningResult",
    "ShowGrantResult",
    "ShowProcessListResult",
    "ShowEngineResult",
    "ShowCharsetResult",
    "ShowCollationResult",
    "ShowPluginResult",
]

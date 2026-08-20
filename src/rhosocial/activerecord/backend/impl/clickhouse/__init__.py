# src/rhosocial/activerecord/backend/impl/clickhouse/__init__.py
"""
ClickHouse backend implementation for rhosocial-activerecord.

This module provides:
- ClickHouse synchronous backend with connection management and query execution
- ClickHouse-specific connection configuration
- Type mapping and value conversion
- ClickHouse dialect and expression handling
- ClickHouse-specific SQL function factories
"""

from .backend import ClickHouseBackend
from .config import ClickHouseConnectionConfig
from .collation import ClickHouseCollation, ClickHouseCollationValidator
from .dialect import ClickHouseDialect
from .transaction import ClickHouseTransactionManager
from .types import ClickHouseEnumType, ClickHouseSetType
from .explain import ClickHouseExplainResult, ClickHouseExplainRow


__all__ = [
    "ClickHouseBackend",
    "ClickHouseConnectionConfig",
    "ClickHouseDialect",
    "ClickHouseCollation",
    "ClickHouseCollationValidator",
    "ClickHouseTransactionManager",
    "ClickHouseEnumType",
    "ClickHouseSetType",
    "ClickHouseExplainResult",
    "ClickHouseExplainRow",
]

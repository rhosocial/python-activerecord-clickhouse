# src/rhosocial/activerecord/backend/impl/clickhouse/show/__init__.py
"""
ClickHouse SHOW functionality module.

This module provides ClickHouse-specific SHOW command support:
- Expression classes for SHOW commands
- Dialect mixin for SQL generation
- Functionality classes for executing SHOW commands
- Backend mixins for show() method

Usage:
    # Via backend
    result = backend.show().create_table("users")
    columns = backend.show().columns("users", full=True)
    indexes = backend.show().indexes("users")
    tables = backend.show().tables()
    databases = backend.show().databases()
"""

from .expressions import (
    ShowExpression,
    ShowCreateTableExpression,
    ShowCreateViewExpression,
    ShowColumnsExpression,
    ShowIndexExpression,
    ShowTablesExpression,
    ShowDatabasesExpression,
    ShowTableStatusExpression,
    ShowTriggersExpression,
    ShowCreateTriggerExpression,
    ShowVariablesExpression,
    ShowStatusExpression,
    ShowProcessListExpression,
    ShowWarningsExpression,
    ShowErrorsExpression,
    ShowEnginesExpression,
    ShowCharsetExpression,
    ShowCollationExpression,
    ShowGrantsExpression,
    ShowPluginsExpression,
)
from .dialect import ClickHouseShowDialectMixin
from .functionality import ClickHouseShowFunctionality, AsyncClickHouseShowFunctionality
from .backend_mixin import ClickHouseShowMixin, AsyncClickHouseShowMixin

__all__ = [
    # Expression classes
    "ShowExpression",
    "ShowCreateTableExpression",
    "ShowCreateViewExpression",
    "ShowColumnsExpression",
    "ShowIndexExpression",
    "ShowTablesExpression",
    "ShowDatabasesExpression",
    "ShowTableStatusExpression",
    "ShowTriggersExpression",
    "ShowCreateTriggerExpression",
    "ShowVariablesExpression",
    "ShowStatusExpression",
    "ShowProcessListExpression",
    "ShowWarningsExpression",
    "ShowErrorsExpression",
    "ShowEnginesExpression",
    "ShowCharsetExpression",
    "ShowCollationExpression",
    "ShowGrantsExpression",
    "ShowPluginsExpression",
    # Dialect mixin
    "ClickHouseShowDialectMixin",
    # Functionality classes
    "ClickHouseShowFunctionality",
    "AsyncClickHouseShowFunctionality",
    # Backend mixins
    "ClickHouseShowMixin",
    "AsyncClickHouseShowMixin",
]

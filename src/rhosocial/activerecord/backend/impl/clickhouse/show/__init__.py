# src/rhosocial/activerecord/backend/impl/clickhouse/show/__init__.py
"""
ClickHouse SHOW functionality module.

This module provides ClickHouse-specific SHOW command support:
- Expression classes for SHOW commands
- Dialect mixin for SQL generation
- Functionality classes for executing SHOW commands
- Backend mixins for the ``show()`` factory method (see the caveat below)

Usage:
    # The reachable path is the show sub-introspector, which is sync or async
    # according to the backend it was created for:
    create = backend.introspector.show.create_table("users")
    tables = backend.introspector.show.tables()
    databases = backend.introspector.show.databases()
    create = await async_backend.introspector.show.create_table("users")

    # backend.show() is NOT wired up on this backend -- see show/backend_mixin.py.
    # The classes below are still exported for API compatibility.
"""

from ..expression.show import (
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
from .functionality import ClickHouseShowFunctionality
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
    # Backend mixins
    "ClickHouseShowMixin",
    "AsyncClickHouseShowMixin",
]

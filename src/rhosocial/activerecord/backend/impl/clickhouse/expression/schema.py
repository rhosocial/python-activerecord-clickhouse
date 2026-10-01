# src/rhosocial/activerecord/backend/impl/clickhouse/expression/schema.py
"""
ClickHouse schema resolution functions.

Provides a SQL expression factory for asking the server which namespace an
unqualified reference resolves against.

Follows the expression-dialect separation architecture:
- First parameter is always the dialect instance
- Returns an Expression object (FunctionCall)
- Does not concatenate SQL strings directly
"""

from typing import TYPE_CHECKING

from rhosocial.activerecord.backend.expression import core

if TYPE_CHECKING:  # pragma: no cover
    from rhosocial.activerecord.backend.dialect import SQLDialectBase


def current_database(dialect: "SQLDialectBase") -> "core.FunctionCall":
    """Create a function call for the current database.

    ClickHouse has no schema namespace: a qualified reference such as
    ``db.table`` names a database, and an unqualified ``table`` resolves
    against the current database. So the "current schema" of this dialect is
    the current database, read via currentDatabase().

    Usage:
        - current_database(dialect)

    Args:
        dialect: The SQL dialect instance

    Returns:
        A FunctionCall instance that evaluates to the current database name
    """
    return core.FunctionCall(dialect, "currentDatabase")

# src/rhosocial/activerecord/backend/impl/clickhouse/show/expressions.py
"""
ClickHouse SHOW command expression classes.

This module defines expression classes for ClickHouse SHOW commands.
Each expression class collects parameters and delegates SQL generation
to the dialect's format_show_* methods.

Expression classes inherit from BaseExpression and implement to_sql(),
following the expression-dialect pattern used throughout the codebase.

Key design:
- Expressions collect parameters (table_name, schema, options)
- Expressions hold a dialect reference
- to_sql() delegates to dialect.format_show_* methods
- Dialect handles actual SQL generation
"""

from typing import Any, Dict, Optional, TYPE_CHECKING

from rhosocial.activerecord.backend.expression.bases import BaseExpression, SQLQueryAndParams

if TYPE_CHECKING:
    from ...dialect import ClickHouseDialect


class ShowExpression(BaseExpression):
    """Base class for ClickHouse SHOW command expressions.

    All ClickHouse SHOW expressions inherit from this class and provide
    fluent API for setting parameters.
    """

    def __init__(self, dialect: "ClickHouseDialect"):
        super().__init__(dialect)
        self._schema: Optional[str] = None

    def schema(self, name: str) -> "ShowExpression":
        """Set the schema/database name.

        Args:
            name: Schema or database name.

        Returns:
            Self for method chaining.
        """
        self._schema = name
        return self

    def get_params(self) -> Dict[str, Any]:
        """Get all parameters.

        Returns:
            Dictionary containing all parameters.
        """
        params: Dict[str, Any] = {}
        if self._schema is not None:
            params["schema"] = self._schema
        return params

    def to_sql(self) -> SQLQueryAndParams:
        """Generate SQL. Subclasses must implement this method."""
        raise NotImplementedError("Subclasses must implement to_sql() method")


class ShowCreateTableExpression(ShowExpression):
    """Expression for SHOW CREATE TABLE command."""

    def __init__(self, dialect: "ClickHouseDialect", table_name: str):
        super().__init__(dialect)
        self._table_name = table_name

    def get_params(self) -> Dict[str, Any]:
        params = super().get_params()
        params["table_name"] = self._table_name
        return params

    def to_sql(self) -> SQLQueryAndParams:
        return self._dialect.format_show_create_table(self)


class ShowCreateViewExpression(ShowExpression):
    """Expression for SHOW CREATE VIEW command."""

    def __init__(self, dialect: "ClickHouseDialect", view_name: str):
        super().__init__(dialect)
        self._view_name = view_name

    def get_params(self) -> Dict[str, Any]:
        params = super().get_params()
        params["view_name"] = self._view_name
        return params

    def to_sql(self) -> SQLQueryAndParams:
        return self._dialect.format_show_create_view(self)


class ShowColumnsExpression(ShowExpression):
    """Expression for SHOW [FULL] COLUMNS command."""

    def __init__(self, dialect: "ClickHouseDialect", table_name: str):
        super().__init__(dialect)
        self._table_name = table_name
        self._full: bool = False
        self._like_pattern: Optional[str] = None

    def full(self, value: bool = True) -> "ShowColumnsExpression":
        """Include additional column information (privileges, comments)."""
        self._full = value
        return self

    def like(self, pattern: str) -> "ShowColumnsExpression":
        """Filter columns by name pattern."""
        self._like_pattern = pattern
        return self

    def get_params(self) -> Dict[str, Any]:
        params = super().get_params()
        params["table_name"] = self._table_name
        params["full"] = self._full
        if self._like_pattern:
            params["like_pattern"] = self._like_pattern
        return params

    def to_sql(self) -> SQLQueryAndParams:
        return self._dialect.format_show_columns(self)


class ShowIndexExpression(ShowExpression):
    """Expression for SHOW INDEX command."""

    def __init__(self, dialect: "ClickHouseDialect", table_name: str):
        super().__init__(dialect)
        self._table_name = table_name

    def get_params(self) -> Dict[str, Any]:
        params = super().get_params()
        params["table_name"] = self._table_name
        return params

    def to_sql(self) -> SQLQueryAndParams:
        return self._dialect.format_show_index(self)


class ShowTablesExpression(ShowExpression):
    """Expression for SHOW [FULL] TABLES command."""

    def __init__(self, dialect: "ClickHouseDialect"):
        super().__init__(dialect)
        self._full: bool = False
        self._like_pattern: Optional[str] = None

    def full(self, value: bool = True) -> "ShowTablesExpression":
        """Include table type (BASE TABLE or VIEW)."""
        self._full = value
        return self

    def like(self, pattern: str) -> "ShowTablesExpression":
        """Filter tables by name pattern."""
        self._like_pattern = pattern
        return self

    def get_params(self) -> Dict[str, Any]:
        params = super().get_params()
        params["full"] = self._full
        if self._like_pattern:
            params["like_pattern"] = self._like_pattern
        return params

    def to_sql(self) -> SQLQueryAndParams:
        return self._dialect.format_show_tables(self)


class ShowDatabasesExpression(ShowExpression):
    """Expression for SHOW DATABASES command."""

    def __init__(self, dialect: "ClickHouseDialect"):
        super().__init__(dialect)
        self._like_pattern: Optional[str] = None

    def like(self, pattern: str) -> "ShowDatabasesExpression":
        """Filter databases by name pattern."""
        self._like_pattern = pattern
        return self

    def get_params(self) -> Dict[str, Any]:
        params = super().get_params()
        if self._like_pattern:
            params["like_pattern"] = self._like_pattern
        return params

    def to_sql(self) -> SQLQueryAndParams:
        return self._dialect.format_show_databases(self)


class ShowTableStatusExpression(ShowExpression):
    """Expression for SHOW TABLE STATUS command."""

    def __init__(self, dialect: "ClickHouseDialect"):
        super().__init__(dialect)
        self._like_pattern: Optional[str] = None

    def like(self, pattern: str) -> "ShowTableStatusExpression":
        """Filter tables by name pattern."""
        self._like_pattern = pattern
        return self

    def get_params(self) -> Dict[str, Any]:
        params = super().get_params()
        if self._like_pattern:
            params["like_pattern"] = self._like_pattern
        return params

    def to_sql(self) -> SQLQueryAndParams:
        return self._dialect.format_show_table_status(self)


class ShowTriggersExpression(ShowExpression):
    """Expression for SHOW TRIGGERS command."""

    def __init__(self, dialect: "ClickHouseDialect"):
        super().__init__(dialect)
        self._table_name: Optional[str] = None

    def for_table(self, table_name: str) -> "ShowTriggersExpression":
        """Filter triggers for a specific table."""
        self._table_name = table_name
        return self

    def get_params(self) -> Dict[str, Any]:
        params = super().get_params()
        if self._table_name:
            params["table_name"] = self._table_name
        return params

    def to_sql(self) -> SQLQueryAndParams:
        return self._dialect.format_show_triggers(self)


class ShowCreateTriggerExpression(ShowExpression):
    """Expression for SHOW CREATE TRIGGER command."""

    def __init__(self, dialect: "ClickHouseDialect", trigger_name: str):
        super().__init__(dialect)
        self._trigger_name = trigger_name

    def get_params(self) -> Dict[str, Any]:
        params = super().get_params()
        params["trigger_name"] = self._trigger_name
        return params

    def to_sql(self) -> SQLQueryAndParams:
        return self._dialect.format_show_create_trigger(self)


class ShowVariablesExpression(ShowExpression):
    """Expression for SHOW VARIABLES command."""

    def __init__(self, dialect: "ClickHouseDialect"):
        super().__init__(dialect)
        self._like_pattern: Optional[str] = None
        self._session: bool = True

    def like(self, pattern: str) -> "ShowVariablesExpression":
        """Filter variables by name pattern."""
        self._like_pattern = pattern
        return self

    def session(self, value: bool = True) -> "ShowVariablesExpression":
        """Show session variables (default)."""
        self._session = value
        return self

    def global_vars(self) -> "ShowVariablesExpression":
        """Show global variables."""
        self._session = False
        return self

    def get_params(self) -> Dict[str, Any]:
        params = super().get_params()
        params["session"] = self._session
        if self._like_pattern:
            params["like_pattern"] = self._like_pattern
        return params

    def to_sql(self) -> SQLQueryAndParams:
        return self._dialect.format_show_variables(self)


class ShowStatusExpression(ShowExpression):
    """Expression for SHOW STATUS command."""

    def __init__(self, dialect: "ClickHouseDialect"):
        super().__init__(dialect)
        self._like_pattern: Optional[str] = None
        self._session: bool = True

    def like(self, pattern: str) -> "ShowStatusExpression":
        """Filter status by name pattern."""
        self._like_pattern = pattern
        return self

    def session(self, value: bool = True) -> "ShowStatusExpression":
        """Show session status (default)."""
        self._session = value
        return self

    def global_status(self) -> "ShowStatusExpression":
        """Show global status."""
        self._session = False
        return self

    def get_params(self) -> Dict[str, Any]:
        params = super().get_params()
        params["session"] = self._session
        if self._like_pattern:
            params["like_pattern"] = self._like_pattern
        return params

    def to_sql(self) -> SQLQueryAndParams:
        return self._dialect.format_show_status(self)


class ShowProcessListExpression(ShowExpression):
    """Expression for SHOW PROCESSLIST command."""

    def __init__(self, dialect: "ClickHouseDialect"):
        super().__init__(dialect)
        self._full: bool = False

    def full(self, value: bool = True) -> "ShowProcessListExpression":
        """Include full query text."""
        self._full = value
        return self

    def get_params(self) -> Dict[str, Any]:
        params = super().get_params()
        params["full"] = self._full
        return params

    def to_sql(self) -> SQLQueryAndParams:
        return self._dialect.format_show_processlist(self)


class ShowWarningsExpression(ShowExpression):
    """Expression for SHOW WARNINGS command."""

    def __init__(self, dialect: "ClickHouseDialect"):
        super().__init__(dialect)
        self._limit: Optional[int] = None

    def limit(self, count: int) -> "ShowWarningsExpression":
        """Limit number of warnings returned."""
        self._limit = count
        return self

    def get_params(self) -> Dict[str, Any]:
        params = super().get_params()
        if self._limit is not None:
            params["limit"] = self._limit
        return params

    def to_sql(self) -> SQLQueryAndParams:
        return self._dialect.format_show_warnings(self)


class ShowErrorsExpression(ShowExpression):
    """Expression for SHOW ERRORS command."""

    def __init__(self, dialect: "ClickHouseDialect"):
        super().__init__(dialect)
        self._limit: Optional[int] = None

    def limit(self, count: int) -> "ShowErrorsExpression":
        """Limit number of errors returned."""
        self._limit = count
        return self

    def get_params(self) -> Dict[str, Any]:
        params = super().get_params()
        if self._limit is not None:
            params["limit"] = self._limit
        return params

    def to_sql(self) -> SQLQueryAndParams:
        return self._dialect.format_show_errors(self)


class ShowEnginesExpression(ShowExpression):
    """Expression for SHOW ENGINES command."""

    def to_sql(self) -> SQLQueryAndParams:
        return self._dialect.format_show_engines(self)


class ShowCharsetExpression(ShowExpression):
    """Expression for SHOW CHARACTER SET command."""

    def __init__(self, dialect: "ClickHouseDialect"):
        super().__init__(dialect)
        self._like_pattern: Optional[str] = None

    def like(self, pattern: str) -> "ShowCharsetExpression":
        """Filter character sets by name pattern."""
        self._like_pattern = pattern
        return self

    def get_params(self) -> Dict[str, Any]:
        params = super().get_params()
        if self._like_pattern:
            params["like_pattern"] = self._like_pattern
        return params

    def to_sql(self) -> SQLQueryAndParams:
        return self._dialect.format_show_charset(self)


class ShowCollationExpression(ShowExpression):
    """Expression for SHOW COLLATION command."""

    def __init__(self, dialect: "ClickHouseDialect"):
        super().__init__(dialect)
        self._like_pattern: Optional[str] = None

    def like(self, pattern: str) -> "ShowCollationExpression":
        """Filter collations by name pattern."""
        self._like_pattern = pattern
        return self

    def get_params(self) -> Dict[str, Any]:
        params = super().get_params()
        if self._like_pattern:
            params["like_pattern"] = self._like_pattern
        return params

    def to_sql(self) -> SQLQueryAndParams:
        return self._dialect.format_show_collation(self)


class ShowGrantsExpression(ShowExpression):
    """Expression for SHOW GRANTS command."""

    def __init__(self, dialect: "ClickHouseDialect"):
        super().__init__(dialect)
        self._user: Optional[str] = None
        self._host: Optional[str] = None

    def for_user(self, user: str, host: Optional[str] = None) -> "ShowGrantsExpression":
        """Show grants for a specific user."""
        self._user = user
        self._host = host
        return self

    def get_params(self) -> Dict[str, Any]:
        params = super().get_params()
        if self._user:
            params["user"] = self._user
        if self._host:
            params["host"] = self._host
        return params

    def to_sql(self) -> SQLQueryAndParams:
        return self._dialect.format_show_grants(self)


class ShowPluginsExpression(ShowExpression):
    """Expression for SHOW PLUGINS command."""

    def to_sql(self) -> SQLQueryAndParams:
        return self._dialect.format_show_plugins(self)

# src/rhosocial/activerecord/backend/impl/clickhouse/show/dialect.py
"""
ClickHouse SHOW command dialect mixin.

This module provides the ClickHouse-specific SQL generation for SHOW commands.
It implements the format_show_* methods that are called by the expression classes.

The mixin is added to ClickHouseDialect to provide SHOW command support.
All methods follow the pattern:
- Accept an expression parameter
- Extract parameters from expression.get_params()
- Generate SQL string and parameter tuple
- Return (sql, params) tuple

.. warning::
    This module was copied from the MySQL backend template and contains
    MySQL-style SQL functions/show commands. ClickHouse uses different
    function names (e.g. ``JSONExtract*``) and a different SHOW command
    subset. May generate non-ClickHouse SQL; verify before use.
"""

from typing import Tuple, TYPE_CHECKING

from rhosocial.activerecord.backend.dialect.exceptions import UnsupportedFeatureError

if TYPE_CHECKING:
    from .expressions import (
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


class ClickHouseShowDialectMixin:
    """ClickHouse SHOW command SQL generation mixin.

    Provides format_show_* methods for generating ClickHouse SHOW command SQL.
    All methods take an expression parameter and return (sql, params) tuple.

    This mixin is added to ClickHouseDialect to provide SHOW functionality.
    """

    # ========== SHOW CREATE Statements ==========

    def format_show_create_table(self, expr: "ShowCreateTableExpression") -> Tuple[str, tuple]:
        """Format SHOW CREATE TABLE statement."""
        params = expr.get_params()
        table = params["table"]
        schema = params.get("schema")

        if schema:
            sql = f"SHOW CREATE TABLE {self.format_identifier(schema)}.{self.format_identifier(table)}"
        else:
            sql = f"SHOW CREATE TABLE {self.format_identifier(table)}"
        return sql, ()

    def format_show_create_view(self, expr: "ShowCreateViewExpression") -> Tuple[str, tuple]:
        """Format SHOW CREATE VIEW statement."""
        params = expr.get_params()
        view_name = params["view_name"]
        schema = params.get("schema")

        if schema:
            sql = f"SHOW CREATE VIEW {self.format_identifier(schema)}.{self.format_identifier(view_name)}"
        else:
            sql = f"SHOW CREATE VIEW {self.format_identifier(view_name)}"
        return sql, ()

    def format_show_create_trigger(self, expr: "ShowCreateTriggerExpression") -> Tuple[str, tuple]:
        """Format SHOW CREATE TRIGGER statement.

        Note:
            MySQL-only command, not supported by ClickHouse.
        """
        raise UnsupportedFeatureError(
            self.name,
            "SHOW CREATE TRIGGER",
            suggestion="ClickHouse does not support triggers.",
        )

    # ========== SHOW COLUMNS/INDEX ==========

    def format_show_columns(self, expr: "ShowColumnsExpression") -> Tuple[str, tuple]:
        """Format SHOW [FULL] COLUMNS statement.

        Note:
            MySQL-only command, not supported by ClickHouse.
        """
        raise UnsupportedFeatureError(
            self.name,
            "SHOW COLUMNS",
            suggestion="Use DESCRIBE TABLE or query system.columns instead.",
        )

    def format_show_index(self, expr: "ShowIndexExpression") -> Tuple[str, tuple]:
        """Format SHOW INDEX statement.

        Note:
            MySQL-only command, not supported by ClickHouse.
        """
        raise UnsupportedFeatureError(
            self.name,
            "SHOW INDEX",
            suggestion="Query system.data_skipping_indices or system.tables instead.",
        )

    # ========== SHOW TABLES/DATABASES ==========

    def format_show_tables(self, expr: "ShowTablesExpression") -> Tuple[str, tuple]:
        """Format SHOW [FULL] TABLES statement."""
        params = expr.get_params()
        schema = params.get("schema")
        full = params.get("full", False)
        like_pattern = params.get("like_pattern")

        parts = ["SHOW"]
        if full:
            parts.append("FULL")
        parts.append("TABLES")
        if schema:
            parts.append(f"FROM {self.format_identifier(schema)}")

        sql_params = ()
        if like_pattern:
            parts.append("LIKE %s")
            sql_params = (like_pattern,)

        return " ".join(parts), sql_params

    def format_show_databases(self, expr: "ShowDatabasesExpression") -> Tuple[str, tuple]:
        """Format SHOW DATABASES statement."""
        params = expr.get_params()
        like_pattern = params.get("like_pattern")

        if like_pattern:
            return "SHOW DATABASES LIKE %s", (like_pattern,)
        return "SHOW DATABASES", ()

    def format_show_table_status(self, expr: "ShowTableStatusExpression") -> Tuple[str, tuple]:
        """Format SHOW TABLE STATUS statement.

        Note:
            MySQL-only command, not supported by ClickHouse.
        """
        raise UnsupportedFeatureError(
            self.name,
            "SHOW TABLE STATUS",
            suggestion="Query system.tables instead.",
        )

    # ========== SHOW TRIGGERS ==========

    def format_show_triggers(self, expr: "ShowTriggersExpression") -> Tuple[str, tuple]:
        """Format SHOW TRIGGERS statement.

        Note:
            MySQL-only command, not supported by ClickHouse.
        """
        raise UnsupportedFeatureError(
            self.name,
            "SHOW TRIGGERS",
            suggestion="ClickHouse does not support triggers.",
        )

    # ========== SHOW VARIABLES/STATUS ==========

    def format_show_variables(self, expr: "ShowVariablesExpression") -> Tuple[str, tuple]:
        """Format SHOW VARIABLES statement.

        Note:
            MySQL-only command, not supported by ClickHouse.
        """
        raise UnsupportedFeatureError(
            self.name,
            "SHOW VARIABLES",
            suggestion="Query system.settings instead.",
        )

    def format_show_status(self, expr: "ShowStatusExpression") -> Tuple[str, tuple]:
        """Format SHOW STATUS statement.

        Note:
            MySQL-only command, not supported by ClickHouse.
        """
        raise UnsupportedFeatureError(
            self.name,
            "SHOW STATUS",
            suggestion="Query system.metrics, system.events, or system.asynchronous_metrics instead.",
        )

    # ========== SHOW PROCESSLIST/WARNINGS/ERRORS ==========

    def format_show_processlist(self, expr: "ShowProcessListExpression") -> Tuple[str, tuple]:
        """Format SHOW PROCESSLIST statement.

        Note:
            MySQL-only command, not supported by ClickHouse.
        """
        raise UnsupportedFeatureError(
            self.name,
            "SHOW PROCESSLIST",
            suggestion="Query system.processes instead.",
        )

    def format_show_warnings(self, expr: "ShowWarningsExpression") -> Tuple[str, tuple]:
        """Format SHOW WARNINGS statement.

        Note:
            MySQL-only command, not supported by ClickHouse.
        """
        raise UnsupportedFeatureError(
            self.name,
            "SHOW WARNINGS",
            suggestion="Query system.query_log or system.text_log instead.",
        )

    def format_show_errors(self, expr: "ShowErrorsExpression") -> Tuple[str, tuple]:
        """Format SHOW ERRORS statement.

        Note:
            MySQL-only command, not supported by ClickHouse.
        """
        raise UnsupportedFeatureError(
            self.name,
            "SHOW ERRORS",
            suggestion="Query system.errors or system.query_log instead.",
        )

    # ========== SHOW ENGINES/CHARSET/COLLATION ==========

    def format_show_engines(self, expr: "ShowEnginesExpression") -> Tuple[str, tuple]:
        """Format SHOW ENGINES statement.

        Note:
            MySQL-only command, not supported by ClickHouse.
        """
        raise UnsupportedFeatureError(
            self.name,
            "SHOW ENGINES",
            suggestion="Query system.table_engines instead.",
        )

    def format_show_charset(self, expr: "ShowCharsetExpression") -> Tuple[str, tuple]:
        """Format SHOW CHARACTER SET statement.

        Note:
            MySQL-only command, not supported by ClickHouse.
        """
        raise UnsupportedFeatureError(
            self.name,
            "SHOW CHARACTER SET",
            suggestion="ClickHouse does not support MySQL character sets; query system.character_sets instead.",
        )

    def format_show_collation(self, expr: "ShowCollationExpression") -> Tuple[str, tuple]:
        """Format SHOW COLLATION statement.

        Note:
            MySQL-only command, not supported by ClickHouse.
        """
        raise UnsupportedFeatureError(
            self.name,
            "SHOW COLLATION",
            suggestion="ClickHouse does not support MySQL collations; query system.collations instead.",
        )

    # ========== SHOW GRANTS/PLUGINS ==========

    def format_show_grants(self, expr: "ShowGrantsExpression") -> Tuple[str, tuple]:
        """Format SHOW GRANTS statement.

        Note:
            MySQL-only command, not supported by ClickHouse.
        """
        raise UnsupportedFeatureError(
            self.name,
            "SHOW GRANTS",
            suggestion="Query system.grants or other system.* access control tables instead.",
        )

    def format_show_plugins(self, expr: "ShowPluginsExpression") -> Tuple[str, tuple]:
        """Format SHOW PLUGINS statement.

        Note:
            MySQL-only command, not supported by ClickHouse.
        """
        raise UnsupportedFeatureError(
            self.name,
            "SHOW PLUGINS",
            suggestion="Query system.functions for user-defined functions instead.",
        )

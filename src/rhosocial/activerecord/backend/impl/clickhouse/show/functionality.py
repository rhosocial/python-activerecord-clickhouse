# src/rhosocial/activerecord/backend/impl/clickhouse/show/functionality.py
"""
ClickHouse SHOW functionality implementation.

This module provides the ClickHouse-specific implementation of ShowFunctionality.
It uses expression-dialect pattern for SQL generation and backend.execute()
for all SQL execution.

The implementation:
- Creates expression objects with the dialect
- Calls expression.to_sql() to get SQL
- Executes SQL via backend.execute()
- Parses results into typed dataclasses

What this module renders, and what it refuses
---------------------------------------------
Nine of these commands are ClickHouse statements and are rendered, each read
back from the column names the 26.7.3.19 server actually sends:

======================  ========================================
``SHOW CREATE TABLE``   ``ClickHouseShowDialectMixin``
``SHOW CREATE VIEW``    (single ``statement`` output column —
                        verified on 26.7.3.19)
``SHOW [FULL] TABLES``  ``name`` / ``engine`` output columns
``SHOW DATABASES``      ``name`` output column
``SHOW [FULL] COLUMNS`` ``field`` / ``type`` / ``null`` / ``key`` /
                        ``default`` / ``extra`` (+ ``collation``,
                        ``comment``, ``privileges`` under FULL)
``SHOW INDEX``          ``table`` / ``key_name`` / ``pk_col`` /
                        ``index_type`` / ``expression`` / ...
``SHOW PROCESSLIST``    ``system.processes``' 43 columns
``SHOW ENGINES``        ``name`` + eight ``supports_*`` flags +
                        ``description`` / ``syntax`` / ``introduced_in``
``SHOW GRANTS``         one column named after the statement text
======================  ========================================

Every other command in the MySQL ``SHOW`` set is ClickHouse's to not have,
and its ``format_show_*`` raises ``UnsupportedFeatureError`` naming the
ClickHouse replacement — ``SHOW TABLE STATUS`` → ``system.tables``,
``SHOW VARIABLES`` → ``system.settings``, ``SHOW WARNINGS`` →
``system.query_log``, and so on. Their result dataclasses stay declared so the
API is complete, but nothing can reach them.

``version`` is taken from the connection the caller already opened (the
backend reports it through ``get_server_version()``); it is not compared
against a capability threshold anywhere in this file.
"""

from typing import Optional, Tuple, TYPE_CHECKING

from rhosocial.activerecord.backend.dialect.exceptions import UnsupportedFeatureError

from ..expression.show import (
    ShowColumnsExpression,
    ShowCreateTableExpression,
    ShowCreateViewExpression,
    ShowDatabasesExpression,
    ShowEnginesExpression,
    ShowGrantsExpression,
    ShowIndexExpression,
    ShowProcessListExpression,
    ShowTablesExpression,
)

if TYPE_CHECKING:
    from ..backend import ClickHouseBackend


class ClickHouseShowFunctionality:
    """ClickHouse-specific SHOW functionality implementation.

    Provides the nine SHOW commands ClickHouse has, using the
    expression-dialect pattern; every other one refuses.

    No capability here is gated on a version. The ``version`` argument is kept
    for interface symmetry with the other backends' show functionality and for
    logging, not for feature detection: this module previously held a
    "ClickHouse 5.7 vs 8.0" distinction and an ``_supports_invisible_columns``
    flag tested as ``version >= (8, 0, 0)``. ClickHouse's numbering has never
    had a 5.7 or an 8.0, no SHOW command was branched on either, and the flag
    was read by nothing in this repository.
    """

    def __init__(self, backend: "ClickHouseBackend", version: Optional[Tuple[int, ...]] = None):
        """Initialize ClickHouse SHOW functionality.

        Args:
            backend: ClickHouseBackend instance for executing queries.
            version: ClickHouse server version tuple as the backend reports it,
                e.g. ``(26, 7, 3)`` for 26.7.3.19. Recorded, not compared.
        """
        self._backend = backend
        self._version = version
        self.dialect = backend.dialect

    # ========== Parsing Helper Methods ==========
    #
    # Every one of these delegates to the corresponding parser on
    # :class:`...introspection.show_introspector.ShowMixin`, so there is exactly
    # one implementation of "which ClickHouse column goes in which field" in this
    # package — reachable from both the sync/async show sub-introspector and this
    # ``ShowFunctionality`` surface, without the two drifting apart.

    @staticmethod
    def _show_parser():
        from ..introspection.show_introspector import ShowMixin

        return ShowMixin

    def _parse_create_table_result(self, result, table: str):
        """Parse ``SHOW CREATE TABLE`` — a single ``statement`` column."""
        return self._show_parser()._parse_create_table(result.data, table)

    def _parse_create_view_result(self, result, view_name: str):
        """Parse ``SHOW CREATE VIEW`` — a single ``statement`` column, as above."""
        return self._show_parser()._parse_create_view(result.data, view_name)

    def _parse_columns_result(self, result):
        """Parse ``SHOW [FULL] COLUMNS`` — ``field`` / ``type`` / ``null`` /
        ``key`` / ``default`` / ``extra``, plus the three ``FULL`` columns."""
        return self._show_parser()._parse_columns(result.data)

    def _parse_indexes_result(self, result):
        """Parse ``SHOW INDEX`` — ``table`` / ``key_name`` / ``pk_col`` / ..."""
        return self._show_parser()._parse_indexes(result.data)

    def _parse_tables_result(self, result):
        """Parse ``SHOW [FULL] TABLES`` — columns ``name`` and, under ``FULL``, ``engine``.

        ``ShowTableResult.table_type`` therefore carries the ClickHouse storage
        engine name, not MySQL's ``BASE TABLE`` / ``VIEW``.
        """
        from .types import ShowTableResult

        return [
            ShowTableResult(name=row.get("name"), table_type=row.get("engine"))
            for row in result.data
        ]

    def _parse_databases_result(self, result):
        """Parse ``SHOW DATABASES`` — the column is ``name``, not ``Database``."""
        from .types import ShowDatabaseResult

        return [ShowDatabaseResult(name=row.get("name")) for row in result.data]

    def _parse_table_status_result(self, result):
        """Parse SHOW TABLE STATUS result."""
        from .types import ShowTableStatusResult

        statuses = []
        for row in result.data:
            statuses.append(
                ShowTableStatusResult(
                    name=row.get("Name"),
                    engine=row.get("Engine"),
                    version=row.get("Version"),
                    row_format=row.get("Row_format"),
                    rows=row.get("Rows"),
                    avg_row_length=row.get("Avg_row_length"),
                    data_length=row.get("Data_length"),
                    max_data_length=row.get("Max_data_length"),
                    index_length=row.get("Index_length"),
                    data_free=row.get("Data_free"),
                    auto_increment=row.get("Auto_increment"),
                    create_time=str(row["Create_time"]) if row.get("Create_time") else None,
                    update_time=str(row["Update_time"]) if row.get("Update_time") else None,
                    check_time=str(row["Check_time"]) if row.get("Check_time") else None,
                    collation=row.get("Collation"),
                    checksum=row.get("Checksum"),
                    create_options=row.get("Create_options"),
                    comment=row.get("Comment"),
                )
            )
        return statuses

    def _parse_triggers_result(self, result):
        """Parse SHOW TRIGGERS result."""
        from .types import ShowTriggerResult

        triggers = []
        for row in result.data:
            triggers.append(
                ShowTriggerResult(
                    trigger_name=row.get("Trigger", row.get("TRIGGER_NAME")),
                    event=row.get("Event", row.get("EVENT_MANIPULATION")),
                    table_name=row.get("Table", row.get("EVENT_OBJECT_TABLE")),
                    statement=row.get("Statement", row.get("ACTION_STATEMENT")),
                    timing=row.get("Timing", row.get("ACTION_TIMING")),
                    created=row.get("Created"),
                    sql_mode=row.get("sql_mode"),
                    definer=row.get("Definer"),
                    character_set_client=row.get("character_set_client"),
                    collation_connection=row.get("collation_connection"),
                    database_collation=row.get("Database Collation"),
                )
            )
        return triggers

    def _parse_create_trigger_result(self, result, trigger: str):
        """Parse SHOW CREATE TRIGGER result."""
        from .types import ShowCreateTriggerResult

        if not result.data or len(result.data) == 0:
            return None

        row = result.data[0]
        return ShowCreateTriggerResult(
            trigger_name=row.get("Trigger", row.get("TRIGGER", trigger)),
            create_statement=row.get("SQL Original Statement", row.get("CREATE TRIGGER", "")),
            character_set_client=row.get("character_set_client"),
            collation_connection=row.get("collation_connection"),
            database_collation=row.get("Database Collation"),
        )

    def _parse_variables_result(self, result):
        """Parse SHOW VARIABLES result."""
        from .types import ShowVariableResult

        return [
            ShowVariableResult(
                variable_name=row.get("Variable_name"),
                value=row.get("Value"),
            )
            for row in result.data
        ]

    def _parse_status_result(self, result):
        """Parse SHOW STATUS result."""
        from .types import ShowStatusResult

        return [
            ShowStatusResult(
                variable_name=row.get("Variable_name"),
                value=row.get("Value"),
            )
            for row in result.data
        ]

    def _parse_processlist_result(self, result):
        """Parse ``SHOW PROCESSLIST`` — ``system.processes``' own columns."""
        return self._show_parser()._parse_processlist(result.data)

    def _parse_warnings_result(self, result):
        """Parse SHOW WARNINGS result."""
        from .types import ShowWarningResult

        return [
            ShowWarningResult(
                level=row.get("Level"),
                code=row.get("Code"),
                message=row.get("Message"),
            )
            for row in result.data
        ]

    def _parse_errors_result(self, result):
        """Parse SHOW ERRORS result."""
        from .types import ShowWarningResult

        return [
            ShowWarningResult(
                level=row.get("Level"),
                code=row.get("Code"),
                message=row.get("Message"),
            )
            for row in result.data
        ]

    def _parse_engines_result(self, result):
        """Parse ``SHOW ENGINES`` — ``name`` plus the eight ``supports_*`` flags."""
        return self._show_parser()._parse_engines(result.data)

    def _parse_charset_result(self, result):
        """Parse SHOW CHARACTER SET result."""
        from .types import ShowCharsetResult

        return [
            ShowCharsetResult(
                charset=row.get("Charset"),
                description=row.get("Description"),
                default_collation=row.get("Default collation"),
                maxlen=row.get("Maxlen"),
            )
            for row in result.data
        ]

    def _parse_collation_result(self, result):
        """Parse SHOW COLLATION result."""
        from .types import ShowCollationResult

        return [
            ShowCollationResult(
                collation=row.get("Collation"),
                charset=row.get("Charset"),
                id=row.get("Id"),
                default=row.get("Default"),
                compiled=row.get("Compiled"),
                sortlen=row.get("Sortlen"),
            )
            for row in result.data
        ]

    def _parse_grants_result(self, result):
        """Parse ``SHOW GRANTS`` — one column, named after the statement text."""
        return self._show_parser()._parse_grants(result.data)

    def _parse_plugins_result(self, result):
        """Parse SHOW PLUGINS result."""
        from .types import ShowPluginResult

        plugins = []
        for row in result.data:
            plugins.append(
                ShowPluginResult(
                    name=row.get("Name"),
                    status=row.get("Status"),
                    type=row.get("Type"),
                    library=row.get("Library"),
                    license=row.get("License"),
                )
            )
        return plugins

    # ========== SHOW CREATE TABLE ==========

    def create_table(self, table: str, schema: Optional[str] = None):
        """Get CREATE TABLE statement for a table.

        Args:
            table: Name of the table.
            schema: Database/schema name (optional).

        Returns:
            ShowCreateTableResult with table name and CREATE statement,
            or None if table doesn't exist.
        """
        expr = ShowCreateTableExpression(self.dialect, table)
        if schema:
            expr.schema(schema)
        sql, params = expr.to_sql()
        result = self._backend.execute(sql, params)
        return self._parse_create_table_result(result, table)

    # ========== SHOW CREATE VIEW ==========

    def create_view(self, view_name: str, schema: Optional[str] = None):
        """Get CREATE VIEW statement for a view.

        Args:
            view_name: Name of the view.
            schema: Database/schema name (optional).

        Returns:
            ShowCreateViewResult with view details, or None if view doesn't exist.
        """
        expr = ShowCreateViewExpression(self.dialect, view_name)
        if schema:
            expr.schema(schema)
        sql, params = expr.to_sql()
        result = self._backend.execute(sql, params)
        return self._parse_create_view_result(result, view_name)

    # ========== SHOW COLUMNS ==========

    def columns(
        self,
        table: str,
        schema: Optional[str] = None,
        full: bool = False,
        like: Optional[str] = None,
    ):
        """Get column information for a table.

        Renders ``SHOW [FULL] COLUMNS FROM [<schema>.]<table> [LIKE <pattern>]``
        and reads ClickHouse's own output columns. See
        ``https://clickhouse.com/docs/reference/statements/show``.
        """
        expr = ShowColumnsExpression(self.dialect, table)
        if schema:
            expr.schema(schema)
        if full:
            expr.full()
        if like:
            expr.like(like)
        sql, params = expr.to_sql()
        result = self._backend.execute(sql, params)
        return self._parse_columns_result(result)

    # ========== SHOW INDEX ==========

    def indexes(self, table: str, schema: Optional[str] = None):
        """Get index information for a table.

        Renders ``SHOW INDEX FROM [<schema>.]<table>`` and reads ClickHouse's own
        output columns — the primary key columns plus one row per data skipping
        index. See ``https://clickhouse.com/docs/reference/statements/show``.
        """
        expr = ShowIndexExpression(self.dialect, table)
        if schema:
            expr.schema(schema)
        sql, params = expr.to_sql()
        result = self._backend.execute(sql, params)
        return self._parse_indexes_result(result)

    # ========== SHOW TABLES ==========

    def tables(
        self,
        schema: Optional[str] = None,
        like: Optional[str] = None,
        full: bool = False,
    ):
        """List tables in the database.

        Args:
            schema: Database/schema name (optional).
            like: Filter tables by name pattern.
            full: Include table type (BASE TABLE or VIEW).

        Returns:
            List of ShowTableResult objects.
        """
        expr = ShowTablesExpression(self.dialect)
        if schema:
            expr.schema(schema)
        if like:
            expr.like(like)
        if full:
            expr.full()

        sql, params = expr.to_sql()
        result = self._backend.execute(sql, params)
        return self._parse_tables_result(result)

    # ========== SHOW DATABASES ==========

    def databases(self, like: Optional[str] = None):
        """List databases.

        Args:
            like: Filter databases by name pattern.

        Returns:
            List of ShowDatabaseResult objects.
        """
        expr = ShowDatabasesExpression(self.dialect)
        if like:
            expr.like(like)

        sql, params = expr.to_sql()
        result = self._backend.execute(sql, params)
        return self._parse_databases_result(result)

    # ========== SHOW TABLE STATUS ==========

    def table_status(self, schema: Optional[str] = None, like: Optional[str] = None):
        """Get table status information.

        Note:
            MySQL-only command, not supported by ClickHouse.
        """
        raise UnsupportedFeatureError(
            self._backend.dialect.name,
            "SHOW TABLE STATUS",
            suggestion="Query system.tables instead.",
        )

    # ========== SHOW TRIGGERS ==========

    def triggers(self, schema: Optional[str] = None, table: Optional[str] = None):
        """List triggers.

        Note:
            MySQL-only command, not supported by ClickHouse.
        """
        raise UnsupportedFeatureError(
            self._backend.dialect.name,
            "SHOW TRIGGERS",
            suggestion="ClickHouse does not support triggers.",
        )

    def create_trigger(self, trigger: str, schema: Optional[str] = None):
        """Get CREATE TRIGGER statement.

        Note:
            MySQL-only command, not supported by ClickHouse.
        """
        raise UnsupportedFeatureError(
            self._backend.dialect.name,
            "SHOW CREATE TRIGGER",
            suggestion="ClickHouse does not support triggers.",
        )

    # ========== SHOW VARIABLES ==========

    def variables(self, like: Optional[str] = None, session: bool = True):
        """Show server variables.

        Note:
            MySQL-only command, not supported by ClickHouse.
        """
        raise UnsupportedFeatureError(
            self._backend.dialect.name,
            "SHOW VARIABLES",
            suggestion="Query system.settings instead.",
        )

    # ========== SHOW STATUS ==========

    def status(self, like: Optional[str] = None, session: bool = True):
        """Show server status.

        Note:
            MySQL-only command, not supported by ClickHouse.
        """
        raise UnsupportedFeatureError(
            self._backend.dialect.name,
            "SHOW STATUS",
            suggestion="Query system.metrics, system.events, or system.asynchronous_metrics instead.",
        )

    # ========== SHOW PROCESSLIST ==========

    def processlist(self, full: bool = False):
        """Show process list.

        Renders ``SHOW PROCESSLIST``, which in ClickHouse is
        ``SELECT * FROM system.processes``. ``full`` is accepted for interface
        symmetry and ignored: the statement has no ``FULL`` variant and already
        reports the full query text in ``query``.
        """
        expr = ShowProcessListExpression(self.dialect)
        if full:
            expr.full()
        sql, params = expr.to_sql()
        result = self._backend.execute(sql, params)
        return self._parse_processlist_result(result)

    # ========== SHOW WARNINGS/ERRORS ==========

    def warnings(self, limit: Optional[int] = None):
        """Show warnings.

        Note:
            MySQL-only command, not supported by ClickHouse.
        """
        raise UnsupportedFeatureError(
            self._backend.dialect.name,
            "SHOW WARNINGS",
            suggestion="Query system.query_log or system.text_log instead.",
        )

    def errors(self, limit: Optional[int] = None):
        """Show errors.

        Note:
            MySQL-only command, not supported by ClickHouse.
        """
        raise UnsupportedFeatureError(
            self._backend.dialect.name,
            "SHOW ERRORS",
            suggestion="Query system.errors or system.query_log instead.",
        )

    # ========== SHOW ENGINES ==========

    def engines(self):
        """Show storage engines.

        Renders ``SHOW ENGINES``, which in ClickHouse is
        ``SELECT * FROM system.table_engines``; the result carries the engine name,
        the eight ``supports_*`` capability flags and the engine's own
        ``description`` / ``syntax`` / ``introduced_in`` documentation columns.
        """
        expr = ShowEnginesExpression(self.dialect)
        sql, params = expr.to_sql()
        result = self._backend.execute(sql, params)
        return self._parse_engines_result(result)

    # ========== SHOW CHARSET ==========

    def charset(self, like: Optional[str] = None):
        """Show character sets.

        Note:
            MySQL-only command, not supported by ClickHouse.
        """
        raise UnsupportedFeatureError(
            self._backend.dialect.name,
            "SHOW CHARACTER SET",
            suggestion="ClickHouse does not support MySQL character sets; query system.character_sets instead.",
        )

    # ========== SHOW COLLATION ==========

    def collation(self, like: Optional[str] = None):
        """Show collations.

        Note:
            MySQL-only command, not supported by ClickHouse.
        """
        raise UnsupportedFeatureError(
            self._backend.dialect.name,
            "SHOW COLLATION",
            suggestion="ClickHouse does not support MySQL collations; query system.collations instead.",
        )

    # ========== SHOW GRANTS ==========

    def grants(self, user: Optional[str] = None, host: Optional[str] = None):
        """Show grants.

        Renders ``SHOW GRANTS`` or ``SHOW GRANTS FOR <user>``. ClickHouse
        identifies access entities by role name alone and has no ``user@host``
        form — ``SHOW GRANTS FOR root@localhost`` is
        ``Code: 511. DB::Exception: There is no role `root@localhost` in `user
        directories`. (UNKNOWN_ROLE)`` on 26.7.3.19 — so a supplied ``host`` is
        not rendered.

        The statement returns a single column whose name follows the output
        format, so the parser reads the column's value rather than a named key.
        """
        expr = ShowGrantsExpression(self.dialect)
        if user:
            expr.for_user(user, host)
        sql, params = expr.to_sql()
        result = self._backend.execute(sql, params)
        return self._parse_grants_result(result)

    # ========== SHOW PLUGINS ==========

    def plugins(self):
        """Show plugins.

        Note:
            MySQL-only command, not supported by ClickHouse.
        """
        raise UnsupportedFeatureError(
            self._backend.dialect.name,
            "SHOW PLUGINS",
            suggestion="Query system.functions for user-defined functions instead.",
        )

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

.. warning::
    This module was copied from the MySQL backend template and contains
    MySQL-style SQL functions/show commands. ClickHouse uses different
    function names (e.g. ``JSONExtract*``) and a different SHOW command
    subset. May generate non-ClickHouse SQL; verify before use.
"""

from typing import Optional, Tuple, TYPE_CHECKING

from rhosocial.activerecord.backend.dialect.exceptions import UnsupportedFeatureError

from .expressions import (
    ShowCreateTableExpression,
    ShowCreateViewExpression,
    ShowTablesExpression,
    ShowDatabasesExpression,
)

if TYPE_CHECKING:
    from ..backend import ClickHouseBackend


class ClickHouseShowFunctionality:
    """ClickHouse-specific SHOW functionality implementation.

    Provides all ClickHouse SHOW commands using expression-dialect pattern.
    Supports version-aware feature detection for ClickHouse 5.7 vs 8.0 differences.
    """

    def __init__(self, backend: "ClickHouseBackend", version: Optional[Tuple[int, ...]] = None):
        """Initialize ClickHouse SHOW functionality.

        Args:
            backend: ClickHouseBackend instance for executing queries.
            version: ClickHouse server version tuple, e.g., (8, 0, 0) for ClickHouse 8.0.
        """
        self._backend = backend
        self._version = version
        self.dialect = backend.dialect
        # ClickHouse 8.0+ supports invisible columns
        self._supports_invisible_columns = version >= (8, 0, 0) if version else True

    # ========== Parsing Helper Methods ==========

    def _parse_create_table_result(self, result, table_name: str):
        """Parse SHOW CREATE TABLE result."""
        from .types import ShowCreateTableResult

        if not result.data or len(result.data) == 0:
            return None

        row = result.data[0]
        return ShowCreateTableResult(
            table_name=row.get("Table", row.get("TABLE", table_name)),
            create_statement=row.get("Create Table", row.get("CREATE TABLE", "")),
        )

    def _parse_create_view_result(self, result, view_name: str):
        """Parse SHOW CREATE VIEW result."""
        from .types import ShowCreateViewResult

        if not result.data or len(result.data) == 0:
            return None

        row = result.data[0]
        return ShowCreateViewResult(
            view_name=row.get("View", row.get("VIEW", view_name)),
            create_statement=row.get("Create View", row.get("CREATE VIEW", "")),
            character_set_client=row.get("character_set_client"),
            collation_connection=row.get("collation_connection"),
        )

    def _parse_columns_result(self, result):
        """Parse SHOW COLUMNS result."""
        from .types import ShowColumnResult

        columns = []
        for row in result.data:
            col = ShowColumnResult(
                field=row.get("Field", row.get("COLUMN_NAME")),
                type=row.get("Type", row.get("COLUMN_TYPE")),
                null=row.get("Null", row.get("IS_NULLABLE")),
                key=row.get("Key", row.get("COLUMN_KEY")),
                default=row.get("Default", row.get("COLUMN_DEFAULT")),
                extra=row.get("Extra", row.get("EXTRA")),
            )
            # FULL mode additional fields
            if "Collation" in row or "Privileges" in row:
                col.privileges = row.get("Privileges")
                col.comment = row.get("Comment")
            columns.append(col)
        return columns

    def _parse_indexes_result(self, result):
        """Parse SHOW INDEX result."""
        from .types import ShowIndexResult

        indexes = []
        for row in result.data:
            indexes.append(
                ShowIndexResult(
                    table=row.get("Table", row.get("TABLE_NAME")),
                    non_unique=row.get("Non_unique", row.get("NON_UNIQUE")),
                    key_name=row.get("Key_name", row.get("INDEX_NAME")),
                    seq_in_index=row.get("Seq_in_index", row.get("SEQ_IN_INDEX")),
                    column_name=row.get("Column_name", row.get("COLUMN_NAME")),
                    collation=row.get("Collation", row.get("COLLATION")),
                    cardinality=row.get("Cardinality", row.get("CARDINALITY")),
                    sub_part=row.get("Sub_part", row.get("SUB_PART")),
                    packed=row.get("Packed", row.get("PACKED")),
                    null=row.get("Null", row.get("NULLABLE")),
                    index_type=row.get("Index_type") or row.get("INDEX_TYPE") or "BTREE",
                    comment=row.get("Comment", row.get("INDEX_COMMENT")),
                    index_comment=row.get("Index_comment", row.get("INDEX_COMMENT")),
                    visible=row.get("Visible", row.get("IS_VISIBLE")),
                    expression=row.get("Expression", row.get("EXPRESSION")),
                )
            )
        return indexes

    def _parse_tables_result(self, result):
        """Parse SHOW TABLES result."""
        from .types import ShowTableResult

        tables = []
        for row in result.data:
            if len(row) == 1:
                tables.append(ShowTableResult(name=list(row.values())[0], table_type=None))
            else:
                name_key = next((k for k in row.keys() if k.startswith("Tables_in_")), None)
                if name_key:
                    tables.append(ShowTableResult(name=row[name_key], table_type=row.get("Table_type")))
        return tables

    def _parse_databases_result(self, result):
        """Parse SHOW DATABASES result."""
        from .types import ShowDatabaseResult

        return [ShowDatabaseResult(name=row.get("Database")) for row in result.data]

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
                    trigger=row.get("Trigger", row.get("TRIGGER_NAME")),
                    event=row.get("Event", row.get("EVENT_MANIPULATION")),
                    table=row.get("Table", row.get("EVENT_OBJECT_TABLE")),
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

    def _parse_create_trigger_result(self, result, trigger_name: str):
        """Parse SHOW CREATE TRIGGER result."""
        from .types import ShowCreateTriggerResult

        if not result.data or len(result.data) == 0:
            return None

        row = result.data[0]
        return ShowCreateTriggerResult(
            trigger_name=row.get("Trigger", row.get("TRIGGER", trigger_name)),
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
        """Parse SHOW PROCESSLIST result."""
        from .types import ShowProcessListResult

        processes = []
        for row in result.data:
            processes.append(
                ShowProcessListResult(
                    id=row.get("Id", row.get("ID")),
                    user=row.get("User"),
                    host=row.get("Host"),
                    command=row.get("Command"),
                    time=row.get("Time"),
                    db=row.get("db"),
                    state=row.get("State"),
                    info=row.get("Info"),
                )
            )
        return processes

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
        """Parse SHOW ENGINES result."""
        from .types import ShowEngineResult

        engines = []
        for row in result.data:
            engines.append(
                ShowEngineResult(
                    engine=row.get("Engine"),
                    support=row.get("Support"),
                    transactions=row.get("Transactions"),
                    xa=row.get("XA"),
                    savepoints=row.get("Savepoints"),
                )
            )
        return engines

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
        """Parse SHOW GRANTS result."""
        from .types import ShowGrantResult

        return [ShowGrantResult(grants=row.get("Grants for")) for row in result.data]

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

    def create_table(self, table_name: str, schema: Optional[str] = None):
        """Get CREATE TABLE statement for a table.

        Args:
            table_name: Name of the table.
            schema: Database/schema name (optional).

        Returns:
            ShowCreateTableResult with table name and CREATE statement,
            or None if table doesn't exist.
        """
        expr = ShowCreateTableExpression(self.dialect, table_name)
        if schema:
            expr.schema(schema)
        sql, params = expr.to_sql()
        result = self._backend.execute(sql, params)
        return self._parse_create_table_result(result, table_name)

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
        table_name: str,
        schema: Optional[str] = None,
        full: bool = False,
        like: Optional[str] = None,
    ):
        """Get column information for a table.

        Note:
            MySQL-only command, not supported by ClickHouse.
        """
        raise UnsupportedFeatureError(
            self._backend.dialect.name,
            "SHOW COLUMNS",
            suggestion="Use DESCRIBE TABLE or query system.columns instead.",
        )

    # ========== SHOW INDEX ==========

    def indexes(self, table_name: str, schema: Optional[str] = None):
        """Get index information for a table.

        Note:
            MySQL-only command, not supported by ClickHouse.
        """
        raise UnsupportedFeatureError(
            self._backend.dialect.name,
            "SHOW INDEX",
            suggestion="Query system.data_skipping_indices or system.tables instead.",
        )

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

    def triggers(self, schema: Optional[str] = None, table_name: Optional[str] = None):
        """List triggers.

        Note:
            MySQL-only command, not supported by ClickHouse.
        """
        raise UnsupportedFeatureError(
            self._backend.dialect.name,
            "SHOW TRIGGERS",
            suggestion="ClickHouse does not support triggers.",
        )

    def create_trigger(self, trigger_name: str, schema: Optional[str] = None):
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

        Note:
            MySQL-only command, not supported by ClickHouse.
        """
        raise UnsupportedFeatureError(
            self._backend.dialect.name,
            "SHOW PROCESSLIST",
            suggestion="Query system.processes instead.",
        )

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

        Note:
            MySQL-only command, not supported by ClickHouse.
        """
        raise UnsupportedFeatureError(
            self._backend.dialect.name,
            "SHOW ENGINES",
            suggestion="Query system.table_engines instead.",
        )

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

        Note:
            MySQL-only command, not supported by ClickHouse.
        """
        raise UnsupportedFeatureError(
            self._backend.dialect.name,
            "SHOW GRANTS",
            suggestion="Query system.grants or other system.* access control tables instead.",
        )

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

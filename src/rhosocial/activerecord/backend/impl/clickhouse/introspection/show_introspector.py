# src/rhosocial/activerecord/backend/impl/clickhouse/introspection/show_introspector.py
"""
ClickHouse SHOW command sub-introspectors.

Provides ClickHouse-specific SHOW commands as sub-introspectors accessible via
``backend.introspector.show``. Execution is delegated to the executor,
keeping the class I/O-free except for the executor calls.

Design principle: Sync and Async are separate and cannot coexist.
- SyncShowIntrospector: for synchronous backends (method names without _async suffix)
- AsyncShowIntrospector: for asynchronous backends (method names without _async suffix)
"""

from typing import Any, Dict, List, Optional

from rhosocial.activerecord.backend.introspection.executor import (
    SyncIntrospectorExecutor,
    AsyncIntrospectorExecutor,
)
from ..expression.show import (
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


class ShowMixin:
    """Mixin providing shared SHOW command logic.

    Both SyncShowIntrospector and AsyncShowIntrospector inherit
    from this mixin to share:
    - Dialect access
    - SQL generation helpers
    - _parse_* static methods
    """

    @property
    def dialect(self):
        """Get the SQL dialect from the backend."""
        return self._backend.dialect

    # ------------------------------------------------------------------ #
    # Pure parse helpers (shared by sync and async, no I/O)
    # ------------------------------------------------------------------ #

    @staticmethod
    def _parse_create_table(rows: List[Dict], table: str):
        """Parse ``SHOW CREATE TABLE``.

        ClickHouse answers with a single column named ``statement``
        (verified on 26.7.3.19: ``SHOW CREATE TABLE t FORMAT JSONEachRow``
        yields ``{"statement":"CREATE TABLE default.t\\n(...)"}``), where MySQL
        answers with two columns, ``Table`` and ``Create Table``. Reading the
        MySQL names here would return an empty statement rather than fail, so
        the ClickHouse column is read and MySQL's are not consulted.
        """
        from ..show.types import ShowCreateTableResult

        if not rows:
            return None
        row = rows[0]
        return ShowCreateTableResult(
            table_name=table,
            create_statement=row.get("statement", ""),
        )

    @staticmethod
    def _parse_create_view(rows: List[Dict], view_name: str):
        """Parse ``SHOW CREATE VIEW``.

        Single ``statement`` column, as for ``SHOW CREATE TABLE``; the
        ``character_set_client`` / ``collation_connection`` fields ClickHouse
        does not report stay ``None``.
        """
        from ..show.types import ShowCreateViewResult

        if not rows:
            return None
        row = rows[0]
        return ShowCreateViewResult(
            view_name=view_name,
            create_statement=row.get("statement", ""),
        )

    @staticmethod
    def _parse_columns(rows: List[Dict]):
        """Parse ``SHOW [FULL] COLUMNS``.

        ClickHouse's columns are lower-cased: ``field``, ``type``, ``null``,
        ``key``, ``default``, ``extra``, plus ``collation``, ``comment`` and
        ``privileges`` under ``FULL`` (verified on 26.7.3.19 against
        ``SHOW FULL COLUMNS FROM test_db.t``). MySQL's ``Field`` / ``Type`` /
        ``Null`` / ``Key`` / ``Default`` / ``Extra`` / ``Collation`` /
        ``Privileges`` / ``Comment`` are read nowhere here, because reading them
        yields ``None`` for every field instead of failing.

        Two ClickHouse-specific readings worth stating, both from the ``SHOW``
        reference page and both reproduced by the live rows:

        * ``key`` is ``'PRI SOR'`` for a column in the sorting key, ``'PRI'`` for
          a primary-key-only column and ``''`` otherwise — not MySQL's
          ``PRI``/``UNI``/``MUL``.
        * ``default`` carries the expression of an ``ALIAS``, ``DEFAULT`` **or**
          ``MATERIALIZED`` column (ClickHouse reports all three through this one
          column), and ``extra`` is always ``''`` because the server documents
          it as unused.

        The rows come back ordered by column **name**, not by declaration order:
        a table declared ``(id UInt32, created_at DateTime)`` yields
        ``created_at`` then ``id``. Declaration order lives in
        ``SHOW CREATE TABLE`` / ``system.columns``.
        """
        from ..show.types import ShowColumnResult

        return [
            ShowColumnResult(
                field=row.get("field"),
                type=row.get("type"),
                null=row.get("null"),
                key=row.get("key"),
                default=row.get("default"),
                extra=row.get("extra"),
                collation=row.get("collation"),
                comment=row.get("comment"),
                privileges=row.get("privileges"),
            )
            for row in rows
        ]

    @staticmethod
    def _parse_indexes(rows: List[Dict]):
        """Parse ``SHOW INDEX``.

        ClickHouse answers with its own names, which differ from MySQL's in one
        place that matters: ``pk_col`` where MySQL says ``Column_name``
        (verified on 26.7.3.19 — ``SHOW INDEX FROM test_db.t`` reports ``table``,
        ``non_unique``, ``key_name``, ``seq_in_index``, ``pk_col``, ``collation``,
        ``cardinality``, ``sub_part``, ``packed``, ``null``, ``index_type``,
        ``comment``, ``index_comment``, ``visible``, ``expression``; the
        ``SHOW`` reference page still documents that column as ``column_name``,
        which the server no longer sends).

        The rows are the table's **primary key columns** (``key_name='PRIMARY'``,
        ``pk_col`` holding the column name, ``collation='A'``) plus one row per
        **data skipping index** (``key_name=<index name>``, ``pk_col=''`` and the
        index expression in ``expression``).
        """
        from ..show.types import ShowIndexResult

        return [
            ShowIndexResult(
                table_name=row.get("table"),
                non_unique=row.get("non_unique"),
                key_name=row.get("key_name"),
                seq_in_index=row.get("seq_in_index"),
                column_name=row.get("pk_col"),
                collation=row.get("collation"),
                cardinality=row.get("cardinality"),
                sub_part=row.get("sub_part"),
                packed=row.get("packed"),
                null=row.get("null"),
                index_type=row.get("index_type"),
                comment=row.get("comment"),
                index_comment=row.get("index_comment"),
                visible=row.get("visible"),
                expression=row.get("expression"),
            )
            for row in rows
        ]

    @staticmethod
    def _parse_tables(rows: List[Dict]):
        """Parse ``SHOW [FULL] TABLES``.

        ClickHouse names the column ``name`` in both modes and adds an
        ``engine`` column under ``FULL`` — verified on 26.7.3.19, where
        ``SHOW TABLES LIMIT 1 FORMAT JSONCompact`` reports
        ``[{"name": "String"}]`` and the ``FULL`` form adds
        ``{"name": "String", "engine": "String"}``. MySQL instead names the
        first column after the database (``Tables_in_<db>``) and calls the
        second ``Table_type``; reading those names here dropped every ``FULL``
        row, so the ClickHouse names are used.

        ``ShowTableResult.table_type`` therefore carries the **storage engine**
        name (``MergeTree``, ``ReplicatedMergeTree``, ``View``, ...) on this
        backend, which is what ClickHouse reports there, not MySQL's
        ``BASE TABLE`` / ``VIEW``.
        """
        from ..show.types import ShowTableResult

        return [
            ShowTableResult(name=row.get("name"), table_type=row.get("engine"))
            for row in rows
        ]

    @staticmethod
    def _parse_databases(rows: List[Dict]):
        """Parse ``SHOW DATABASES``.

        The column is ``name`` (verified on 26.7.3.19); MySQL calls it
        ``Database``.
        """
        from ..show.types import ShowDatabaseResult

        return [ShowDatabaseResult(name=row.get("name")) for row in rows]

    @staticmethod
    def _parse_table_status(rows: List[Dict]):
        from ..show.types import ShowTableStatusResult

        return [
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
            for row in rows
        ]

    @staticmethod
    def _parse_triggers(rows: List[Dict]):
        from ..show.types import ShowTriggerResult

        return [
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
            for row in rows
        ]

    @staticmethod
    def _parse_create_trigger(rows: List[Dict], trigger: str):
        from ..show.types import ShowCreateTriggerResult

        if not rows:
            return None
        row = rows[0]
        return ShowCreateTriggerResult(
            trigger_name=row.get("Trigger", row.get("TRIGGER", trigger)),
            create_statement=row.get("SQL Original Statement", row.get("CREATE TRIGGER", "")),
            character_set_client=row.get("character_set_client"),
            collation_connection=row.get("collation_connection"),
            database_collation=row.get("Database Collation"),
        )

    @staticmethod
    def _parse_variables(rows: List[Dict]):
        from ..show.types import ShowVariableResult

        return [ShowVariableResult(variable_name=row.get("Variable_name"), value=row.get("Value")) for row in rows]

    @staticmethod
    def _parse_status(rows: List[Dict]):
        from ..show.types import ShowStatusResult

        return [ShowStatusResult(variable_name=row.get("Variable_name"), value=row.get("Value")) for row in rows]

    @staticmethod
    def _parse_processlist(rows: List[Dict]):
        """Parse ``SHOW PROCESSLIST``.

        ClickHouse's ``SHOW PROCESSLIST`` is ``system.processes`` verbatim, so the
        columns are that table's 43 lower-cased names (``query_id``, ``user``,
        ``address``, ``port``, ``elapsed``, ``current_database``, ``query``,
        ...) rather than MySQL's ``Id`` / ``User`` / ``Host`` / ``Command`` /
        ``Time`` / ``db`` / ``State`` / ``Info``.

        Mapping, and the three fields with no ClickHouse counterpart:

        ====================================  =================================
        ``ShowProcessListResult``              ClickHouse column
        ====================================  =================================
        ``id``                                 ``query_id`` (a UUID string, not
                                               MySQL's integer thread id)
        ``user``                               ``user``
        ``host``                               ``address`` + ``port`` joined,
                                               as MySQL's ``Host`` does
        ``command``                            **none** — every row in
                                               ``system.processes`` *is* a
                                               running query; stays ``None``
        ``time``                               ``elapsed`` (Float64 seconds)
        ``db``                                 ``current_database``
        ``state``                              **none** — no per-process state
                                               column exists; stays ``None``
        ``info``                               ``query``
        ====================================  =================================
        """
        from ..show.types import ShowProcessListResult

        results = []
        for row in rows:
            address = row.get("address")
            port = row.get("port")
            host = None
            if address is not None and port is not None:
                host = f"{address}:{port}"
            elif address is not None:
                host = str(address)
            results.append(
                ShowProcessListResult(
                    id=row.get("query_id"),
                    user=row.get("user"),
                    host=host,
                    command=None,
                    time=row.get("elapsed"),
                    db=row.get("current_database"),
                    state=None,
                    info=row.get("query"),
                )
            )
        return results

    @staticmethod
    def _parse_warnings(rows: List[Dict]):
        from ..show.types import ShowWarningResult

        return [
            ShowWarningResult(level=row.get("Level"), code=row.get("Code"), message=row.get("Message")) for row in rows
        ]

    @staticmethod
    def _parse_engines(rows: List[Dict]):
        """Parse ``SHOW ENGINES``.

        ClickHouse's columns are its own, read here as the server sends them:
        ``name``, the eight ``supports_*`` flags (``supports_settings``,
        ``supports_skipping_indices``, ``supports_projections``,
        ``supports_sort_order``, ``supports_ttl``, ``supports_replication``,
        ``supports_deduplication``, ``supports_parallel_insert`` — each ``UInt8``
        0/1), then ``description``, ``syntax``, ``examples``, ``introduced_in``
        and ``related`` — the last five only where the server has them.

        Measured: 25.8.33.6 and 26.3.28.5 carry ``name`` plus the eight flags
        and nothing else, and a literal ``SELECT syntax FROM system.table_engines``
        on 25.8 is refused with ``UNKNOWN_IDENTIFIER``; 26.7.3.19 and 26.7.21.2
        carry all fourteen. (Which release added them was not determined — only
        the 25.8/26.3 versus 26.7 boundary was.) The older versions therefore
        yield ``None`` for ``description`` / ``syntax`` / ``examples`` /
        ``introduced_in`` / ``related``, which is the only honest answer — the
        statement does not produce them, so no value may be invented for them.

        ``introduced_in`` is the only version-shaped column in the whole ``SHOW``
        set, and 26.7 leaves it empty: ``SELECT count() FROM
        system.table_engines WHERE introduced_in != ''`` returns 0 across all 83
        engines on 26.7.3.19. MySQL's ``Support`` / ``Transactions`` / ``XA`` /
        ``Savepoints`` are not produced by this statement and are not read.
        """
        from ..show.types import ShowEngineResult

        return [
            ShowEngineResult(
                engine=row.get("name"),
                supports_settings=row.get("supports_settings"),
                supports_skipping_indices=row.get("supports_skipping_indices"),
                supports_projections=row.get("supports_projections"),
                supports_sort_order=row.get("supports_sort_order"),
                supports_ttl=row.get("supports_ttl"),
                supports_replication=row.get("supports_replication"),
                supports_deduplication=row.get("supports_deduplication"),
                supports_parallel_insert=row.get("supports_parallel_insert"),
                description=row.get("description"),
                syntax=row.get("syntax"),
                examples=row.get("examples"),
                introduced_in=row.get("introduced_in"),
                related=row.get("related"),
            )
            for row in rows
        ]

    @staticmethod
    def _parse_charset(rows: List[Dict]):
        from ..show.types import ShowCharsetResult

        return [
            ShowCharsetResult(
                charset=row.get("Charset"),
                description=row.get("Description"),
                default_collation=row.get("Default collation"),
                maxlen=row.get("Maxlen"),
            )
            for row in rows
        ]

    @staticmethod
    def _parse_collation(rows: List[Dict]):
        from ..show.types import ShowCollationResult

        return [
            ShowCollationResult(
                collation=row.get("Collation"),
                charset=row.get("Charset"),
                id=row.get("Id"),
                default=row.get("Default"),
                compiled=row.get("Compiled"),
                sortlen=row.get("Sortlen"),
            )
            for row in rows
        ]

    @staticmethod
    def _parse_grants(rows: List[Dict]):
        """Parse ``SHOW GRANTS``.

        The statement returns **one column whose name is not a name at all**:
        ClickHouse labels it after the statement text plus whatever output format
        the client asked for. Measured on 26.7.3.19:

        * ``SHOW GRANTS`` over HTTP with ``default_format=JSONEachRow`` →
          column ``GRANTS``
        * ``SHOW GRANTS FORMAT JSONEachRow`` → column ``GRANTS FORMAT JSONEachRow``
        * ``SHOW GRANTS`` over the native protocol (clickhouse-connect, which
          appends ``FORMAT Native``) → column ``GRANTS FORMAT Native``
        * ``SHOW GRANTS FOR root`` → column ``GRANTS FOR root``

        So there is no fixed identifier to look for, and MySQL's ``Grants for``
        never appears. The statement has exactly one column, so the single value
        in each row is read: first by the ``GRANTS``-prefix rule the server's own
        naming obeys, then positionally if even that does not match.
        """
        from ..show.types import ShowGrantResult

        results = []
        for row in rows:
            grants = None
            grants_key = next((k for k in row if k.upper().startswith("GRANTS")), None)
            if grants_key is not None:
                grants = row[grants_key]
            elif len(row) == 1:
                # Exactly one column, whatever it is called: take its value.
                grants = next(iter(row.values()))
            results.append(ShowGrantResult(grants=grants))
        return results

    @staticmethod
    def _parse_plugins(rows: List[Dict]):
        from ..show.types import ShowPluginResult

        return [
            ShowPluginResult(
                name=row.get("Name"),
                status=row.get("Status"),
                type=row.get("Type"),
                library=row.get("Library"),
                license=row.get("License"),
            )
            for row in rows
        ]


class SyncShowIntrospector(ShowMixin):
    """Synchronous SHOW command sub-introspector for ClickHouse backends.

    All methods are synchronous. Method names do NOT have an _async suffix.

    Access via ``backend.introspector.show``::

        tables    = backend.introspector.show.tables()
        create    = backend.introspector.show.create_table("users")
        variables = backend.introspector.show.variables(like="max_%")
    """

    def __init__(self, backend: Any, executor: SyncIntrospectorExecutor) -> None:
        self._backend = backend
        self._executor = executor

    def _exec(self, sql: str, params: tuple) -> List[Dict[str, Any]]:
        """Execute SQL synchronously."""
        return self._executor.execute(sql, params)

    # ------------------------------------------------------------------ #
    # Public synchronous API
    # ------------------------------------------------------------------ #

    def create_table(self, table: str, schema: Optional[str] = None):
        """Get CREATE TABLE statement for a table."""
        expr = ShowCreateTableExpression(self.dialect, table)
        if schema:
            expr.schema(schema)
        sql, params = expr.to_sql()
        return self._parse_create_table(self._exec(sql, params), table)

    def create_view(self, view_name: str, schema: Optional[str] = None):
        """Get CREATE VIEW statement for a view."""
        expr = ShowCreateViewExpression(self.dialect, view_name)
        if schema:
            expr.schema(schema)
        sql, params = expr.to_sql()
        return self._parse_create_view(self._exec(sql, params), view_name)

    def columns(
        self,
        table: str,
        schema: Optional[str] = None,
        full: bool = False,
        like: Optional[str] = None,
    ):
        """Get column information for a table."""
        expr = ShowColumnsExpression(self.dialect, table)
        if schema:
            expr.schema(schema)
        if full:
            expr.full()
        if like:
            expr.like(like)
        sql, params = expr.to_sql()
        return self._parse_columns(self._exec(sql, params))

    def indexes(self, table: str, schema: Optional[str] = None):
        """Get index information for a table."""
        expr = ShowIndexExpression(self.dialect, table)
        if schema:
            expr.schema(schema)
        sql, params = expr.to_sql()
        return self._parse_indexes(self._exec(sql, params))

    def tables(
        self,
        schema: Optional[str] = None,
        like: Optional[str] = None,
        full: bool = False,
    ):
        """List tables in the database."""
        expr = ShowTablesExpression(self.dialect)
        if schema:
            expr.schema(schema)
        if like:
            expr.like(like)
        if full:
            expr.full()
        sql, params = expr.to_sql()
        return self._parse_tables(self._exec(sql, params))

    def databases(self, like: Optional[str] = None):
        """List databases."""
        expr = ShowDatabasesExpression(self.dialect)
        if like:
            expr.like(like)
        sql, params = expr.to_sql()
        return self._parse_databases(self._exec(sql, params))

    def table_status(self, schema: Optional[str] = None, like: Optional[str] = None):
        """Get table status information."""
        expr = ShowTableStatusExpression(self.dialect)
        if schema:
            expr.schema(schema)
        if like:
            expr.like(like)
        sql, params = expr.to_sql()
        return self._parse_table_status(self._exec(sql, params))

    def triggers(self, schema: Optional[str] = None, table: Optional[str] = None):
        """List triggers."""
        expr = ShowTriggersExpression(self.dialect)
        if schema:
            expr.schema(schema)
        if table:
            expr.for_table(table)
        sql, params = expr.to_sql()
        return self._parse_triggers(self._exec(sql, params))

    def create_trigger(self, trigger: str, schema: Optional[str] = None):
        """Get CREATE TRIGGER statement."""
        expr = ShowCreateTriggerExpression(self.dialect, trigger)
        if schema:
            expr.schema(schema)
        sql, params = expr.to_sql()
        return self._parse_create_trigger(self._exec(sql, params), trigger)

    def variables(self, like: Optional[str] = None, session: bool = True):
        """Show server variables."""
        expr = ShowVariablesExpression(self.dialect)
        if like:
            expr.like(like)
        if not session:
            expr.global_vars()
        sql, params = expr.to_sql()
        return self._parse_variables(self._exec(sql, params))

    def status(self, like: Optional[str] = None, session: bool = True):
        """Show server status."""
        expr = ShowStatusExpression(self.dialect)
        if like:
            expr.like(like)
        if not session:
            expr.global_status()
        sql, params = expr.to_sql()
        return self._parse_status(self._exec(sql, params))

    def processlist(self, full: bool = False):
        """Show process list."""
        expr = ShowProcessListExpression(self.dialect)
        if full:
            expr.full()
        sql, params = expr.to_sql()
        return self._parse_processlist(self._exec(sql, params))

    def warnings(self, limit: Optional[int] = None):
        """Show warnings."""
        expr = ShowWarningsExpression(self.dialect)
        if limit is not None:
            expr.limit(limit)
        sql, params = expr.to_sql()
        return self._parse_warnings(self._exec(sql, params))

    def errors(self, limit: Optional[int] = None):
        """Show errors."""
        expr = ShowErrorsExpression(self.dialect)
        if limit is not None:
            expr.limit(limit)
        sql, params = expr.to_sql()
        return self._parse_warnings(self._exec(sql, params))

    def engines(self):
        """Show storage engines."""
        expr = ShowEnginesExpression(self.dialect)
        sql, params = expr.to_sql()
        return self._parse_engines(self._exec(sql, params))

    def charset(self, like: Optional[str] = None):
        """Show character sets."""
        expr = ShowCharsetExpression(self.dialect)
        if like:
            expr.like(like)
        sql, params = expr.to_sql()
        return self._parse_charset(self._exec(sql, params))

    def collation(self, like: Optional[str] = None):
        """Show collations."""
        expr = ShowCollationExpression(self.dialect)
        if like:
            expr.like(like)
        sql, params = expr.to_sql()
        return self._parse_collation(self._exec(sql, params))

    def grants(self, user: Optional[str] = None, host: Optional[str] = None):
        """Show grants."""
        expr = ShowGrantsExpression(self.dialect)
        if user:
            expr.for_user(user, host)
        sql, params = expr.to_sql()
        return self._parse_grants(self._exec(sql, params))

    def plugins(self):
        """Show plugins."""
        expr = ShowPluginsExpression(self.dialect)
        sql, params = expr.to_sql()
        return self._parse_plugins(self._exec(sql, params))


class AsyncShowIntrospector(ShowMixin):
    """Asynchronous SHOW command sub-introspector for ClickHouse backends.

    All methods are async. Method names match the sync version (no _async suffix).

    Access via ``backend.introspector.show``::

        tables    = await backend.introspector.show.tables()
        create    = await backend.introspector.show.create_table("users")
        variables = await backend.introspector.show.variables(like="max_%")
    """

    def __init__(self, backend: Any, executor: AsyncIntrospectorExecutor) -> None:
        self._backend = backend
        self._executor = executor

    async def _exec(self, sql: str, params: tuple) -> List[Dict[str, Any]]:
        """Execute SQL asynchronously."""
        return await self._executor.execute(sql, params)

    # ------------------------------------------------------------------ #
    # Public asynchronous API
    # Method names match the sync version (no _async suffix).
    # ------------------------------------------------------------------ #

    async def create_table(self, table: str, schema: Optional[str] = None):
        """Get CREATE TABLE statement for a table."""
        expr = ShowCreateTableExpression(self.dialect, table)
        if schema:
            expr.schema(schema)
        sql, params = expr.to_sql()
        return self._parse_create_table(await self._exec(sql, params), table)

    async def create_view(self, view_name: str, schema: Optional[str] = None):
        """Get CREATE VIEW statement for a view."""
        expr = ShowCreateViewExpression(self.dialect, view_name)
        if schema:
            expr.schema(schema)
        sql, params = expr.to_sql()
        return self._parse_create_view(await self._exec(sql, params), view_name)

    async def columns(
        self,
        table: str,
        schema: Optional[str] = None,
        full: bool = False,
        like: Optional[str] = None,
    ):
        """Get column information for a table."""
        expr = ShowColumnsExpression(self.dialect, table)
        if schema:
            expr.schema(schema)
        if full:
            expr.full()
        if like:
            expr.like(like)
        sql, params = expr.to_sql()
        return self._parse_columns(await self._exec(sql, params))

    async def indexes(self, table: str, schema: Optional[str] = None):
        """Get index information for a table."""
        expr = ShowIndexExpression(self.dialect, table)
        if schema:
            expr.schema(schema)
        sql, params = expr.to_sql()
        return self._parse_indexes(await self._exec(sql, params))

    async def tables(
        self,
        schema: Optional[str] = None,
        like: Optional[str] = None,
        full: bool = False,
    ):
        """List tables in the database."""
        expr = ShowTablesExpression(self.dialect)
        if schema:
            expr.schema(schema)
        if like:
            expr.like(like)
        if full:
            expr.full()
        sql, params = expr.to_sql()
        return self._parse_tables(await self._exec(sql, params))

    async def databases(self, like: Optional[str] = None):
        """List databases."""
        expr = ShowDatabasesExpression(self.dialect)
        if like:
            expr.like(like)
        sql, params = expr.to_sql()
        return self._parse_databases(await self._exec(sql, params))

    async def table_status(self, schema: Optional[str] = None, like: Optional[str] = None):
        """Get table status information."""
        expr = ShowTableStatusExpression(self.dialect)
        if schema:
            expr.schema(schema)
        if like:
            expr.like(like)
        sql, params = expr.to_sql()
        return self._parse_table_status(await self._exec(sql, params))

    async def triggers(self, schema: Optional[str] = None, table: Optional[str] = None):
        """List triggers."""
        expr = ShowTriggersExpression(self.dialect)
        if schema:
            expr.schema(schema)
        if table:
            expr.for_table(table)
        sql, params = expr.to_sql()
        return self._parse_triggers(await self._exec(sql, params))

    async def create_trigger(self, trigger: str, schema: Optional[str] = None):
        """Get CREATE TRIGGER statement."""
        expr = ShowCreateTriggerExpression(self.dialect, trigger)
        if schema:
            expr.schema(schema)
        sql, params = expr.to_sql()
        return self._parse_create_trigger(await self._exec(sql, params), trigger)

    async def variables(self, like: Optional[str] = None, session: bool = True):
        """Show server variables."""
        expr = ShowVariablesExpression(self.dialect)
        if like:
            expr.like(like)
        if not session:
            expr.global_vars()
        sql, params = expr.to_sql()
        return self._parse_variables(await self._exec(sql, params))

    async def status(self, like: Optional[str] = None, session: bool = True):
        """Show server status."""
        expr = ShowStatusExpression(self.dialect)
        if like:
            expr.like(like)
        if not session:
            expr.global_status()
        sql, params = expr.to_sql()
        return self._parse_status(await self._exec(sql, params))

    async def processlist(self, full: bool = False):
        """Show process list."""
        expr = ShowProcessListExpression(self.dialect)
        if full:
            expr.full()
        sql, params = expr.to_sql()
        return self._parse_processlist(await self._exec(sql, params))

    async def warnings(self, limit: Optional[int] = None):
        """Show warnings."""
        expr = ShowWarningsExpression(self.dialect)
        if limit is not None:
            expr.limit(limit)
        sql, params = expr.to_sql()
        return self._parse_warnings(await self._exec(sql, params))

    async def errors(self, limit: Optional[int] = None):
        """Show errors."""
        expr = ShowErrorsExpression(self.dialect)
        if limit is not None:
            expr.limit(limit)
        sql, params = expr.to_sql()
        return self._parse_warnings(await self._exec(sql, params))

    async def engines(self):
        """Show storage engines."""
        expr = ShowEnginesExpression(self.dialect)
        sql, params = expr.to_sql()
        return self._parse_engines(await self._exec(sql, params))

    async def charset(self, like: Optional[str] = None):
        """Show character sets."""
        expr = ShowCharsetExpression(self.dialect)
        if like:
            expr.like(like)
        sql, params = expr.to_sql()
        return self._parse_charset(await self._exec(sql, params))

    async def collation(self, like: Optional[str] = None):
        """Show collations."""
        expr = ShowCollationExpression(self.dialect)
        if like:
            expr.like(like)
        sql, params = expr.to_sql()
        return self._parse_collation(await self._exec(sql, params))

    async def grants(self, user: Optional[str] = None, host: Optional[str] = None):
        """Show grants."""
        expr = ShowGrantsExpression(self.dialect)
        if user:
            expr.for_user(user, host)
        sql, params = expr.to_sql()
        return self._parse_grants(await self._exec(sql, params))

    async def plugins(self):
        """Show plugins."""
        expr = ShowPluginsExpression(self.dialect)
        sql, params = expr.to_sql()
        return self._parse_plugins(await self._exec(sql, params))

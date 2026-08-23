# src/rhosocial/activerecord/backend/impl/clickhouse/backend.py
"""
ClickHouse-specific implementation of the StorageBackend.

This module provides the concrete implementation for interacting with ClickHouse databases,
handling connections, queries, transactions, and type adaptations tailored for ClickHouse's
specific behaviors and SQL dialect.
"""

import datetime
import logging
from typing import Any, List, Optional, Tuple

try:
    import clickhouse_connect
    from clickhouse_connect.dbapi import connect as clickhouse_connect_dbapi_connect
    from clickhouse_connect.driver.exceptions import (
        DatabaseError as ClickHouseDatabaseError,
        Error as ClickHouseError,
        IntegrityError as ClickHouseIntegrityError,
        OperationalError as ClickHouseOperationalError,
    )
except ImportError:  # pragma: no cover
    clickhouse_connect = None  # type: ignore
    clickhouse_connect_dbapi_connect = None  # type: ignore
    ClickHouseDatabaseError = Exception
    ClickHouseError = Exception
    ClickHouseIntegrityError = Exception
    ClickHouseOperationalError = Exception

from rhosocial.activerecord.backend.base import StorageBackend
from rhosocial.activerecord.backend.errors import (
    ConnectionError,
    DatabaseError,
    IntegrityError,
    QueryError,
)
from rhosocial.activerecord.backend.options import (
    BulkInsertOptions,
    BulkUpdateOptions,
    DeleteOptions,
    ExecutionOptions,
    InsertOptions,
    UpdateOptions,
)
from rhosocial.activerecord.backend.result import QueryResult
from rhosocial.activerecord.backend.introspection.backend_mixin import IntrospectorBackendMixin
from rhosocial.activerecord.backend.explain import SyncExplainBackendMixin
from .config import ClickHouseConnectionConfig
from .dialect import ClickHouseDialect
from .transaction import ClickHouseTransactionManager
from .mixins import ClickHouseBackendMixin, ClickHouseConcurrencyMixin
from .id_generator import generate_id, generate_id_sequence


class ClickHouseBackend(
    SyncExplainBackendMixin,
    IntrospectorBackendMixin,
    ClickHouseBackendMixin,
    ClickHouseConcurrencyMixin,
    StorageBackend,
):
    """ClickHouse-specific backend implementation."""

    def __init__(self, **kwargs: Any) -> None:
        """Initialize ClickHouse backend with connection configuration.

        Args:
            version: Expected ClickHouse server version tuple (major, minor, patch).
                    Used for dialect and type adapter initialization.
                    If None, actual version will be detected via introspect_and_adapt().
                    Can be passed as 'version' in kwargs.
        """
        # Extract version from kwargs if provided
        version = kwargs.pop("version", None)

        # Ensure we have proper ClickHouse configuration
        connection_config = kwargs.get("connection_config")

        if connection_config is None:
            # Extract ClickHouse-specific parameters from kwargs
            config_params = {}
            clickhouse_specific_params = [
                "host",
                "port",
                "database",
                "username",
                "password",
                "timezone",
                "version",
                "ssl_ca",
                "ssl_cert",
                "ssl_key",
                "ssl_verify_cert",
                "ssl_verify_identity",
                "log_queries",
                "log_level",
                "autocommit",
                "connect_timeout",
                "send_receive_timeout",
                "compress",
                "settings",
                "dsn",
            ]

            for param in clickhouse_specific_params:
                if param in kwargs:
                    config_params[param] = kwargs[param]

            # Set defaults if not provided
            if "autocommit" not in config_params:
                config_params["autocommit"] = True
            if "host" not in config_params:
                config_params["host"] = "localhost"
            if "port" not in config_params:
                config_params["port"] = 8123

            kwargs["connection_config"] = ClickHouseConnectionConfig(**config_params)

        super().__init__(**kwargs)

        # Store the expected ClickHouse server version
        self._version = version
        # Initialize ClickHouse-specific components (lazy load dialect)
        self._dialect = None
        # Initialize transaction manager (will use backend.execute())
        self._transaction_manager = ClickHouseTransactionManager(self, self.logger)

        # Register ClickHouse-specific type adapters (uses self._version)
        self._register_clickhouse_adapters()

        self.log(logging.INFO, "ClickHouseBackend initialized")

    def _create_introspector(self) -> Any:
        """Create a SyncClickHouseIntrospector backed by a SyncIntrospectorExecutor."""
        from rhosocial.activerecord.backend.introspection.executor import SyncIntrospectorExecutor
        from .introspection import SyncClickHouseIntrospector

        return SyncClickHouseIntrospector(self, SyncIntrospectorExecutor(self))

    def introspect_and_adapt(self) -> None:
        """Introspect backend and adapt backend instance to actual server capabilities.

        This method ensures a connection exists, queries the actual ClickHouse server version,
        and updates the backend's internal state (version, dialect, type adapters) accordingly.
        """
        # Ensure connection exists
        if not self._connection:
            self.connect()
        actual_version = self.get_server_version()
        if self._version != actual_version:
            self._version = actual_version
            self._dialect = ClickHouseDialect(actual_version)
            self._register_clickhouse_adapters()
            self.log(logging.INFO, f"Adapted to ClickHouse server version {actual_version}")

    def insert(self, options: InsertOptions) -> QueryResult:
        """Insert a record, generating an integer primary key if needed.

        ClickHouse has no ``AUTO_INCREMENT`` and no ``INSERT ... RETURNING``,
        so when the model relies on an auto-generated integer primary key
        (``__pk_auto_generated__``), the backend generates a snowflake-style
        ID in the client, includes it in the INSERT, and reports it through
        ``QueryResult.last_insert_id`` for the model layer to assign back.
        """
        pk = options.primary_key
        generated_id = None
        if pk and not isinstance(pk, tuple):
            col = pk
            if options.data.get(col) is None:
                generated_id = generate_id()
                options.data = {**options.data, col: generated_id}

        result = super().insert(options)

        if generated_id is not None:
            result.last_insert_id = generated_id
        if result.affected_rows == 0:
            result.affected_rows = 1
        return result

    def bulk_insert(self, options: BulkInsertOptions) -> QueryResult:
        """Bulk-insert rows, generating consecutive integer primary keys if needed.

        ClickHouse has no ``AUTO_INCREMENT`` and no ``INSERT ... RETURNING``, so
        when the model relies on auto-generated integer primary keys, the backend
        generates consecutive snowflake-style IDs in the client, injects them as a
        new leading column, and reports the first ID through
        ``QueryResult.last_insert_id`` so the model layer can assign ids as
        ``last_insert_id + j``.
        """
        pk = options.primary_key
        generated_ids = None
        if pk and not isinstance(pk, tuple) and pk not in options.columns:
            count = len(options.rows)
            generated_ids = generate_id_sequence(count)
            new_columns = [pk] + list(options.columns)
            new_rows = [[gid] + list(row) for gid, row in zip(generated_ids, options.rows)]
            options = BulkInsertOptions(
                table=options.table,
                schema_name=options.schema_name,
                columns=new_columns,
                rows=new_rows,
                column_adapters=options.column_adapters,
                column_mapping=options.column_mapping,
                returning_columns=options.returning_columns,
                auto_commit=options.auto_commit,
                primary_key=options.primary_key,
            )

        result = super().bulk_insert(options)

        if generated_ids:
            result.last_insert_id = generated_ids[0]
        if result.affected_rows == 0 and options.rows:
            result.affected_rows = len(options.rows)
        return result

    def update(self, options: UpdateOptions) -> QueryResult:
        """Update records, stripping primary key columns from SET clause.

        ClickHouse refuses to UPDATE a column that is part of the table's
        ``ORDER BY`` (sorting key).  Some model mixins (e.g. ``UUIDMixin``)
        re-inject the primary key into the update data, which would fail.
        We drop any primary-key column from the SET assignments before
        executing the UPDATE.
        """
        pk = options.primary_key
        if pk:
            pk_cols = (pk,) if isinstance(pk, str) else pk
            stripped = {k: v for k, v in options.data.items() if k not in pk_cols}
            if len(stripped) != len(options.data):
                options = UpdateOptions(
                    table=options.table,
                    schema_name=options.schema_name,
                    data=stripped,
                    where=options.where,
                    column_adapters=options.column_adapters,
                    column_mapping=options.column_mapping,
                    returning_columns=options.returning_columns,
                    auto_commit=options.auto_commit,
                    primary_key=options.primary_key,
                )
        # ClickHouse cannot report how many rows a mutation affected, so capture
        # the matching-row count BEFORE running the mutation (the WHERE columns
        # may be modified by the UPDATE itself).
        expected = self._count_predicate_rows(options.table, options.schema_name, options.where) if options.where else 0
        result = super().update(options)
        if expected >= 0 and options.where is not None:
            result.affected_rows = expected
        return result

    def delete(self, options: DeleteOptions) -> QueryResult:
        """Delete records, recalculating the affected-row count.

        ClickHouse DELETE is an asynchronous mutation whose reported
        ``rowcount`` is always 0/1, so the real number of deleted rows is
        derived from a pre-count on the same WHERE predicate.
        """
        expected = self._count_predicate_rows(options.table, options.schema_name, options.where) if options.where else 0
        result = super().delete(options)
        if options.where is not None:
            result.affected_rows = expected
        return result

    def bulk_update(self, options: BulkUpdateOptions) -> QueryResult:
        """Bulk-update via a single UPDATE, recalculating the affected-row count.

        ClickHouse mutations report ``rowcount=1`` no matter how many rows were
        touched, so we count the rows matched by the ``IN (pk, ...)`` predicate
        and use that value as the affected-row count.
        """
        expected = 0
        if options.pk_values:
            from rhosocial.activerecord.backend.expression import Column
            from rhosocial.activerecord.backend.expression.core import Literal
            from rhosocial.activerecord.backend.expression.predicates import InPredicate

            pk_col = Column(self.dialect, options.pk_column)
            pk_literals = Literal(self.dialect, options.pk_values)
            predicate = InPredicate(self.dialect, pk_col, pk_literals)
            expected = self._count_predicate_rows(options.table, options.schema_name, predicate)
        result = super().bulk_update(options)
        if options.pk_values:
            result.affected_rows = expected
        return result

    def _count_predicate_rows(self, table: str, schema_name: Optional[str], where) -> int:
        """Count rows matched by a WHERE predicate without running a mutation.

        ClickHouse cannot report how many rows an UPDATE/DELETE mutation
        affected, so we translate the same predicate into a ``SELECT count()``
        and use its result as the affected-row count.
        """
        if where is None:
            return 0
        table_sql, _ = self.dialect.format_table(table, schema_name=schema_name)
        if hasattr(where, "to_sql"):
            where_sql, where_params = where.to_sql()
            if where_sql.lstrip().upper().startswith("WHERE"):
                where_sql = where_sql.lstrip()[len("WHERE"):]
        else:
            where_sql, where_params = str(where), ()
        count_sql = f"SELECT count() FROM {table_sql} WHERE {where_sql}"
        result = self.execute(count_sql, where_params)
        if result.data and result.data[0]:
            return int(next(iter(result.data[0].values())))
        return 0

    def _execute_query(self, cursor, sql: str, params: Optional[Tuple]):
        """Execute a query with ClickHouse compatibility settings.

        - ``mutations_sync=1``: UPDATE/DELETE are asynchronous mutations by
          default; the ``rowcount`` is meaningless and subsequent reads may
          not observe the change. This makes each statement block until the
          mutation is applied.
        - ``joined_subquery_requires_alias=0``: ClickHouse requires JOINed
          subqueries to have aliases, which the generic query builder does
          not emit (e.g. when a join chain is wrapped as a subquery).
        """
        settings = {"mutations_sync": 1, "joined_subquery_requires_alias": 0}
        if params:
            cursor.execute(sql, params, settings=settings)
        else:
            cursor.execute(sql, settings=settings)
        return cursor

    def connect(self) -> None:
        """Establish connection to ClickHouse database.

        Uses clickhouse-connect's DB-API 2.0 layer (HTTP interface).
        """
        try:
            # Prepare connection parameters from config
            conn_params = {
                "host": self.config.host,
                "port": self.config.port if self.config.port else 8123,
                "database": self.config.database,
                "username": self.config.username,
                "password": self.config.password or "",
            }

            # Add SSL parameters if provided
            if getattr(self.config, "ssl_ca", None):
                conn_params["ca_cert"] = self.config.ssl_ca
            if getattr(self.config, "ssl_cert", None):
                conn_params["client_cert"] = self.config.ssl_cert
            if getattr(self.config, "ssl_key", None):
                conn_params["client_cert_key"] = self.config.ssl_key
            if getattr(self.config, "ssl_verify_cert", None):
                conn_params["verify"] = self.config.ssl_verify_cert

            # Add driver settings
            connect_timeout = getattr(self.config, "connect_timeout", None)
            if connect_timeout:
                conn_params["connect_timeout"] = connect_timeout
            send_receive_timeout = getattr(self.config, "send_receive_timeout", None)
            if send_receive_timeout:
                conn_params["send_receive_timeout"] = send_receive_timeout
            compress = getattr(self.config, "compress", None)
            if compress is not None:
                conn_params["compress"] = compress

            # Map generic options into driver settings
            options = getattr(self.config, "options", None)
            if options:
                settings = dict(options.get("settings", {}))
                if "settings" in options:
                    conn_params["settings"] = settings

            self._connection = clickhouse_connect_dbapi_connect(**conn_params)

            self.log(
                logging.INFO,
                f"Connected to ClickHouse database: {self.config.host}:{conn_params['port']}/{self.config.database}",
            )
            self._fetch_concurrency_hint()
        except ClickHouseError as e:
            self.log(logging.ERROR, f"Failed to connect to ClickHouse database: {str(e)}")
            raise ConnectionError(f"Failed to connect to ClickHouse: {str(e)}") from e

    def disconnect(self) -> None:
        """Close connection to ClickHouse database."""
        if self._connection:
            conn = self._connection
            self._connection = None  # Clear reference first to prevent recursion
            try:
                # Rollback any active transaction
                if self.in_transaction:
                    try:
                        self.transaction_manager.rollback()
                    except Exception:
                        pass  # Ignore rollback failure during disconnect

                conn.close()
                self.log(logging.INFO, "Disconnected from ClickHouse database")
            except (ClickHouseError, BrokenPipeError, OSError) as e:
                # ClickHouse 5.6 may raise BrokenPipeError when closing a dead connection
                # after KILL CONNECTION. We treat disconnect as always successful
                # since the reference is already cleared.
                self.log(logging.WARNING, f"Error during disconnection (ignored): {str(e)}")

    def _get_cursor(self) -> Any:
        """Get a database cursor, ensuring connection is active.

        This method implements automatic connection health checking (Plan A):
        - Checks if connection object exists
        - Checks if connection is still valid using is_connected()
        - Automatically reconnects if connection was lost
        """
        if not self._connection:
            self.log(logging.DEBUG, "No connection, connecting...")
            self.connect()
        else:
            # Verify the connection is still alive via a lightweight query.
            try:
                cursor = self._connection.cursor()
                cursor.execute("SELECT 1")
                cursor.fetchone()
                cursor.close()
            except (BrokenPipeError, OSError, ClickHouseError):
                self.log(logging.DEBUG, "Connection lost, reconnecting...")
                self.disconnect()
                self.connect()

        return self._connection.cursor()

    def execute_many(self, sql: str, params_list: List[Tuple]) -> QueryResult:
        """Execute the same SQL statement multiple times with different parameters."""
        if not self._connection:
            self.connect()

        cursor = None
        start_time = datetime.datetime.now()

        try:
            cursor = self._get_cursor()

            # Log the batch operation if logging is enabled
            if getattr(self.config, "log_queries", False):
                self.log(logging.DEBUG, f"Executing batch operation: {sql}")
                self.log(logging.DEBUG, f"With {len(params_list)} parameter sets")

            # Execute multiple statements
            affected_rows = 0
            for params in params_list:
                cursor.execute(sql, params)
                affected_rows += cursor.rowcount

            duration = (datetime.datetime.now() - start_time).total_seconds()

            result = QueryResult(affected_rows=affected_rows, data=None, duration=duration)

            self.log(
                logging.INFO, f"Batch operation completed, affected {affected_rows} rows, duration={duration:.3f}s"
            )
            return result

        except ClickHouseIntegrityError as e:
            self.log(logging.ERROR, f"Integrity error in batch: {str(e)}")
            raise IntegrityError(str(e)) from e
        except ClickHouseError as e:
            self.log(logging.ERROR, f"ClickHouse error in batch: {str(e)}")
            raise DatabaseError(str(e)) from e
        except Exception as e:
            self.log(logging.ERROR, f"Unexpected error during batch execution: {str(e)}")
            raise QueryError(str(e)) from e
        finally:
            if cursor:
                cursor.close()

    def get_server_version(self) -> Tuple[int, int, int]:
        """Get ClickHouse server version."""
        if self._version and self._version != (0, 0, 0):
            return self._version
        if not self._connection:
            self.connect()

        cursor = None
        try:
            cursor = self._get_cursor()
            cursor.execute("SELECT version()")
            version_row = cursor.fetchone()
            version_str = version_row[0] if version_row else "26.0.0"

            # Parse version string (e.g., "26.7.3.19" or "26.7.3.19-alpine")
            version_clean = version_str.split("-")[0]  # Remove suffix like "-alpine"
            version_parts = version_clean.split(".")

            major = int(version_parts[0]) if len(version_parts) > 0 else 0
            minor = int(version_parts[1]) if len(version_parts) > 1 else 0
            patch = int(version_parts[2]) if len(version_parts) > 2 else 0

            version_tuple = (major, minor, patch)

            self.log(logging.INFO, f"ClickHouse server version: {major}.{minor}.{patch}")
            return version_tuple
        except Exception as e:
            self.log(logging.WARNING, f"Could not determine ClickHouse version: {str(e)}, defaulting to 26.0.0")
            return (26, 0, 0)  # Default to a recent version
        finally:
            if cursor:
                cursor.close()

    def ping(self, reconnect: bool = True) -> bool:
        """
        Ping the ClickHouse server to check if the connection is alive.

        Args:
            reconnect: If True, attempt to reconnect if the connection is dead.
                      If False, just return the current connection status.

        Returns:
            True if the connection is alive (or was successfully reconnected),
            False if the connection is dead and reconnect is False or reconnection failed.
        """
        try:
            if not self._connection:
                if reconnect:
                    self.connect()
                    return True
                else:
                    return False

            # Verify connection with SELECT 1
            try:
                cursor = self._connection.cursor()
                cursor.execute("SELECT 1")
                cursor.fetchone()
                cursor.close()
                return True
            except (BrokenPipeError, OSError, ClickHouseError):
                if reconnect:
                    self.disconnect()
                    self.connect()
                    return True
                return False

        except (ClickHouseError, OSError) as e:
            self.log(logging.WARNING, f"ClickHouse connection ping failed: {str(e)}")
            if reconnect:
                try:
                    self.disconnect()
                    self.connect()
                    return True
                except Exception as connect_error:
                    self.log(logging.ERROR, f"Failed to reconnect after ping failure: {str(connect_error)}")
                    return False
            return False

    def _reconnect(self) -> bool:
        """
        Attempt to reconnect to the ClickHouse server.

        This method safely disconnects and reconnects, handling any errors
        that might occur during the process.

        Returns:
            True if reconnection was successful, False otherwise
        """
        try:
            self.log(logging.INFO, "Attempting to reconnect...")
            self.disconnect()
            self.connect()
            self.log(logging.INFO, "Reconnection successful")
            return True
        except Exception as e:
            self.log(logging.ERROR, f"Reconnection failed: {str(e)}")
            return False

    def _handle_auto_commit(self) -> None:
        """Handle auto commit based on ClickHouse connection and transaction state.

        This method will commit the current connection if:
        1. The connection exists and is open
        2. There is no active transaction managed by transaction_manager

        It's used by insert/update/delete operations to ensure changes are
        persisted immediately when auto_commit=True is specified.
        """
        try:
            # Check if connection exists
            if not self._connection:
                return

            # Check if we're not in an active transaction
            if not self.in_transaction:
                # For ClickHouse, if autocommit is disabled, we need to commit explicitly
                if not getattr(self.config, "autocommit", True):
                    self._connection.commit()
                    self.log(logging.DEBUG, "Auto-committed operation (not in active transaction)")
        except Exception as e:
            # Just log the error but don't raise - this is a convenience feature
            self.log(logging.WARNING, f"Failed to auto-commit: {str(e)}")

    def _handle_auto_commit_if_needed(self) -> None:
        """
        Handle auto-commit for ClickHouse.

        ClickHouse respects the autocommit setting, but we also need to handle explicit commits.
        """
        if not self.in_transaction and self._connection:
            if not getattr(self.config, "autocommit", True):
                self._connection.commit()
                self.log(logging.DEBUG, "Auto-committed operation (not in active transaction)")

    def execute(
        self,
        sql: str,
        params: Optional[Tuple] = None,
        *,
        options: Optional[ExecutionOptions] = None,
        max_retries: int = 2,
        **kwargs: Any,
    ) -> QueryResult:
        """Execute a SQL statement with automatic reconnection and options construction.

        This method combines:
        1. Automatic ExecutionOptions construction when none is provided
        2. Retry logic for connection errors (Plan B error recovery)

        Plan B: If a connection error occurs during execution, it will automatically
        attempt to reconnect and retry the query up to max_retries times.

        Args:
            sql: The SQL statement to execute
            params: Optional tuple of parameter values
            options: ExecutionOptions object (constructed automatically if None)
            max_retries: Maximum number of retry attempts (default: 2)
            **kwargs: Additional keyword arguments (column_mapping, column_adapters)

        Returns:
            QueryResult object containing execution results

        Raises:
            DatabaseError: If execution fails after all retries
        """
        from rhosocial.activerecord.backend.options import StatementType

        # If no options provided, create default options from kwargs
        if options is None:
            # Determine statement type based on SQL
            sql_upper = sql.strip().upper()
            if sql_upper.startswith(("SELECT", "WITH", "SHOW", "DESCRIBE", "PRAGMA", "EXPLAIN")):
                stmt_type = StatementType.DQL
            elif sql_upper.startswith(("INSERT", "UPDATE", "DELETE", "REPLACE")):
                stmt_type = StatementType.DML
            else:
                stmt_type = StatementType.DDL

            # Extract column_mapping and column_adapters from kwargs if present
            column_mapping = kwargs.get("column_mapping")
            column_adapters = kwargs.get("column_adapters")

            options = ExecutionOptions(
                stmt_type=stmt_type,
                process_result_set=None,  # Let the base logic determine this based on stmt_type
                column_adapters=column_adapters,
                column_mapping=column_mapping,
            )
        else:
            # If options is provided but column_mapping or column_adapters are explicitly passed in kwargs,
            # update the options with these values
            if "column_mapping" in kwargs:
                options.column_mapping = kwargs["column_mapping"]
            if "column_adapters" in kwargs:
                options.column_adapters = kwargs["column_adapters"]

        # Execute with retry logic for connection errors
        last_error = None

        for attempt in range(max_retries + 1):
            try:
                return super().execute(sql, params, options=options)
            except (ClickHouseOperationalError, ClickHouseError) as e:
                last_error = e

                # Check if this is a connection error that warrants retry
                if self._is_connection_error(e) and attempt < max_retries:
                    self.log(logging.WARNING, f"Connection error on attempt {attempt + 1}/{max_retries + 1}: {str(e)}")

                    # Attempt to reconnect
                    if self._reconnect():
                        continue
                    else:
                        self.log(logging.ERROR, "Reconnection failed, aborting retry")
                        break
                else:
                    # Not a connection error or max retries reached
                    break

        # All retries exhausted or non-connection error
        if last_error:
            self._handle_error(last_error)

        # This should not be reached, but for type safety
        raise DatabaseError(f"Execution failed after {max_retries + 1} attempts")

    def executescript(self, sql_script: str) -> None:
        """Execute a multi-statement SQL script.

        Handles clickhouse-connector-python version differences:
        - 9.2.0+: Uses execute() + nextset() (multi parameter removed)
        - < 9.2.0: Uses execute(sql, multi=True)

        Args:
            sql_script: A string containing one or more SQL statements separated
                       by semicolons.
        """
        import time

        self.log(logging.INFO, "Executing SQL script.")
        start_time = time.perf_counter()

        if not self._connection:
            self.connect()

        cursor = None
        try:
            cursor = self._connection.cursor()
            cursor.execute(sql_script)
            if cursor.description:
                cursor.fetchall()

            duration = time.perf_counter() - start_time
            self.log(logging.INFO, f"SQL script executed successfully, duration={duration:.3f}s")

        except ClickHouseError as e:
            self.log(logging.ERROR, f"Error executing SQL script: {str(e)}")
            self._handle_error(e)
        finally:
            if cursor:
                cursor.close()

    def _parse_explain_result(self, raw_rows, sql, duration):
        """Return a typed ClickHouseExplainResult for ClickHouse's tabular EXPLAIN output.

        Note: This method must be defined on the backend class directly (not in
        ClickHouseBackendMixin) because _ExplainMixinBase appears earlier in the MRO
        and would otherwise take precedence.
        """
        from .explain import ClickHouseExplainResult, ClickHouseExplainRow

        rows = [ClickHouseExplainRow(**r) for r in raw_rows]
        return ClickHouseExplainResult(raw_rows=raw_rows, sql=sql, duration=duration, rows=rows)

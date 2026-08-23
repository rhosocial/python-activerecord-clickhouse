# src/rhosocial/activerecord/backend/impl/clickhouse/introspection/status_introspector.py
"""
ClickHouse server status introspector.

Provides server status information by querying ClickHouse's SHOW VARIABLES,
SHOW STATUS, and other system commands.

Design principle: Sync and Async are separate and cannot coexist.
- SyncClickHouseStatusIntrospector: for synchronous backends
- AsyncClickHouseStatusIntrospector: for asynchronous backends
"""

from typing import Any, Dict, List, Optional

from rhosocial.activerecord.backend.introspection.status import (
    StatusItem,
    StatusCategory,
    ServerOverview,
    DatabaseBriefInfo,
    UserInfo,
    ConnectionInfo,
    StorageInfo,
    SessionInfo,
    ProcessInfo,
    InnoDBInfo,
    BinaryLogInfo,
    SlowQueryInfo,
    SyncAbstractStatusIntrospector,
    AsyncAbstractStatusIntrospector,
)


# ClickHouse variables to include in status overview
# Format: (variable_name, category, description, unit, is_readonly)
CLICKHOUSE_CONFIG_VARIABLES = [
    # Configuration
    ("version", StatusCategory.CONFIGURATION, "ClickHouse server version", None, True),
    ("version_comment", StatusCategory.CONFIGURATION, "Version comment", None, True),
    ("version_compile_machine", StatusCategory.CONFIGURATION, "Compile machine type", None, True),
    ("version_compile_os", StatusCategory.CONFIGURATION, "Compile OS", None, True),
    ("port", StatusCategory.CONFIGURATION, "ClickHouse port", None, True),
    ("socket", StatusCategory.CONFIGURATION, "ClickHouse socket", None, True),
    ("datadir", StatusCategory.STORAGE, "Data directory", None, True),
    ("basedir", StatusCategory.CONFIGURATION, "Base directory", None, True),
    ("tmpdir", StatusCategory.CONFIGURATION, "Temporary directory", None, True),
    ("character_set_server", StatusCategory.CONFIGURATION, "Server character set", None, False),
    ("character_set_database", StatusCategory.CONFIGURATION, "Database character set", None, False),
    ("character_set_client", StatusCategory.CONFIGURATION, "Client character set", None, False),
    ("character_set_connection", StatusCategory.CONFIGURATION, "Connection character set", None, False),
    ("character_set_results", StatusCategory.CONFIGURATION, "Results character set", None, False),
    ("collation_server", StatusCategory.CONFIGURATION, "Server collation", None, False),
    ("collation_database", StatusCategory.CONFIGURATION, "Database collation", None, False),
    ("max_connections", StatusCategory.CONNECTION, "Maximum connections", "connections", False),
    ("max_connect_errors", StatusCategory.SECURITY, "Max connect errors", None, False),
    ("max_user_connections", StatusCategory.CONNECTION, "Max user connections", "connections", False),
    ("connect_timeout", StatusCategory.CONFIGURATION, "Connection timeout", "seconds", False),
    ("wait_timeout", StatusCategory.CONFIGURATION, "Wait timeout", "seconds", False),
    ("interactive_timeout", StatusCategory.CONFIGURATION, "Interactive timeout", "seconds", False),
    ("skip_networking", StatusCategory.SECURITY, "Skip networking", None, True),
    ("skip_name_resolve", StatusCategory.CONFIGURATION, "Skip name resolution", None, False),
    # Performance
    ("innodb_buffer_pool_size", StatusCategory.PERFORMANCE, "InnoDB buffer pool size", "bytes", False),
    ("innodb_buffer_pool_instances", StatusCategory.PERFORMANCE, "Buffer pool instances", None, False),
    ("innodb_log_file_size", StatusCategory.PERFORMANCE, "InnoDB log file size", "bytes", True),
    ("innodb_log_buffer_size", StatusCategory.PERFORMANCE, "InnoDB log buffer size", "bytes", False),
    ("innodb_flush_log_at_trx_commit", StatusCategory.PERFORMANCE, "Flush log at trx commit", None, False),
    ("innodb_lock_wait_timeout", StatusCategory.PERFORMANCE, "Lock wait timeout", "seconds", False),
    ("innodb_read_io_threads", StatusCategory.PERFORMANCE, "Read I/O threads", None, True),
    ("innodb_write_io_threads", StatusCategory.PERFORMANCE, "Write I/O threads", None, True),
    ("key_buffer_size", StatusCategory.PERFORMANCE, "Key buffer size", "bytes", False),
    ("query_cache_size", StatusCategory.PERFORMANCE, "Query cache size", "bytes", False),
    ("query_cache_type", StatusCategory.PERFORMANCE, "Query cache type", None, False),
    ("table_open_cache", StatusCategory.PERFORMANCE, "Table open cache", None, False),
    ("thread_cache_size", StatusCategory.PERFORMANCE, "Thread cache size", None, False),
    ("sort_buffer_size", StatusCategory.PERFORMANCE, "Sort buffer size", "bytes", False),
    ("join_buffer_size", StatusCategory.PERFORMANCE, "Join buffer size", "bytes", False),
    ("read_buffer_size", StatusCategory.PERFORMANCE, "Read buffer size", "bytes", False),
    ("read_rnd_buffer_size", StatusCategory.PERFORMANCE, "Random read buffer size", "bytes", False),
    # Security
    ("sql_mode", StatusCategory.CONFIGURATION, "SQL mode", None, False),
    ("secure_file_priv", StatusCategory.SECURITY, "Secure file privilege", None, True),
    ("local_infile", StatusCategory.SECURITY, "Local infile", None, False),
    # Replication
    ("server_id", StatusCategory.REPLICATION, "Server ID", None, False),
    ("log_bin", StatusCategory.REPLICATION, "Binary logging", None, True),
    ("binlog_format", StatusCategory.REPLICATION, "Binlog format", None, False),
    ("gtid_mode", StatusCategory.REPLICATION, "GTID mode", None, False),
    ("read_only", StatusCategory.REPLICATION, "Read only mode", None, False),
    ("super_read_only", StatusCategory.REPLICATION, "Super read only", None, False),
]

# ClickHouse status variables for performance metrics
# Format: (variable_name, category, description, unit)
CLICKHOUSE_STATUS_VARIABLES = [
    # Connection metrics
    ("Threads_connected", StatusCategory.CONNECTION, "Current connections", "connections"),
    ("Threads_running", StatusCategory.CONNECTION, "Running threads", "threads"),
    ("Threads_cached", StatusCategory.CONNECTION, "Cached threads", "threads"),
    ("Max_used_connections", StatusCategory.CONNECTION, "Max used connections", "connections"),
    ("Aborted_connects", StatusCategory.CONNECTION, "Aborted connects", None),
    ("Aborted_clients", StatusCategory.CONNECTION, "Aborted clients", None),
    ("Connections", StatusCategory.CONNECTION, "Total connections", "connections"),
    # Performance metrics
    ("Queries", StatusCategory.PERFORMANCE, "Total queries", "queries"),
    ("Questions", StatusCategory.PERFORMANCE, "Total questions", None),
    ("Slow_queries", StatusCategory.PERFORMANCE, "Slow queries", "queries"),
    ("Qcache_hits", StatusCategory.PERFORMANCE, "Query cache hits", None),
    ("Qcache_inserts", StatusCategory.PERFORMANCE, "Query cache inserts", None),
    ("Qcache_lowmem_prunes", StatusCategory.PERFORMANCE, "Query cache lowmem prunes", None),
    ("Com_select", StatusCategory.PERFORMANCE, "SELECT statements", None),
    ("Com_insert", StatusCategory.PERFORMANCE, "INSERT statements", None),
    ("Com_update", StatusCategory.PERFORMANCE, "UPDATE statements", None),
    ("Com_delete", StatusCategory.PERFORMANCE, "DELETE statements", None),
    ("Com_replace", StatusCategory.PERFORMANCE, "REPLACE statements", None),
    ("Com_load", StatusCategory.PERFORMANCE, "LOAD DATA statements", None),
    ("Bytes_received", StatusCategory.PERFORMANCE, "Bytes received", "bytes"),
    ("Bytes_sent", StatusCategory.PERFORMANCE, "Bytes sent", "bytes"),
    # InnoDB metrics
    ("Innodb_buffer_pool_read_requests", StatusCategory.PERFORMANCE, "Buffer pool read requests", None),
    ("Innodb_buffer_pool_reads", StatusCategory.PERFORMANCE, "Buffer pool reads", None),
    ("Innodb_buffer_pool_wait_free", StatusCategory.PERFORMANCE, "Buffer pool wait free", None),
    ("Innodb_data_reads", StatusCategory.PERFORMANCE, "Data reads", None),
    ("Innodb_data_writes", StatusCategory.PERFORMANCE, "Data writes", None),
    ("Innodb_data_read", StatusCategory.PERFORMANCE, "Data read", "bytes"),
    ("Innodb_data_written", StatusCategory.PERFORMANCE, "Data written", "bytes"),
    ("Innodb_row_lock_waits", StatusCategory.PERFORMANCE, "Row lock waits", None),
    ("Innodb_row_lock_time", StatusCategory.PERFORMANCE, "Row lock time", "ms"),
    ("Innodb_rows_read", StatusCategory.PERFORMANCE, "Rows read", "rows"),
    ("Innodb_rows_inserted", StatusCategory.PERFORMANCE, "Rows inserted", "rows"),
    ("Innodb_rows_updated", StatusCategory.PERFORMANCE, "Rows updated", "rows"),
    ("Innodb_rows_deleted", StatusCategory.PERFORMANCE, "Rows deleted", "rows"),
]


class ClickHouseStatusIntrospectorMixin:
    """Mixin providing shared ClickHouse status introspection logic."""

    def _get_vendor_name(self) -> str:
        """Get ClickHouse vendor name."""
        return "ClickHouse"

    def _parse_variable_value(self, value: Any) -> Any:
        """Parse variable value to appropriate Python type."""
        if value is None:
            return None
        if isinstance(value, int):
            return value
        if isinstance(value, str):
            try:
                return int(value)
            except ValueError:
                return value
        return value

    def _parse_version_string(self, version_str: str) -> tuple:
        """Parse ClickHouse version string to (major, minor, patch) tuple.

        Examples:
            '9.6.0' -> (9, 6, 0)
            '8.0.36' -> (8, 0, 36)
            '5.7.42-log' -> (5, 7, 42)
        """
        if not version_str:
            return (0, 0, 0)
        # Remove suffix like '-log', '-debug', etc.
        version_part = version_str.split("-")[0]
        parts = version_part.split(".")
        try:
            major = int(parts[0]) if len(parts) > 0 else 0
            minor = int(parts[1]) if len(parts) > 1 else 0
            patch = int(parts[2]) if len(parts) > 2 else 0
            return (major, minor, patch)
        except (ValueError, IndexError):
            return (0, 0, 0)

    def _is_clickhouse_version_at_least(self, version_str: str, major: int, minor: int = 0) -> bool:
        """Check if ClickHouse version is at least the specified version.

        Args:
            version_str: ClickHouse version string (e.g., '9.6.0')
            major: Minimum major version required
            minor: Minimum minor version required (default 0)

        Returns:
            True if version >= major.minor
        """
        parsed = self._parse_version_string(version_str)
        return parsed >= (major, minor, 0)

    def _create_status_item(
        self,
        name: str,
        value: Any,
        category: StatusCategory,
        description: Optional[str] = None,
        unit: Optional[str] = None,
        is_readonly: bool = False,
    ) -> StatusItem:
        """Create a StatusItem with parsed value."""
        return StatusItem(
            name=name,
            value=self._parse_variable_value(value),
            category=category,
            description=description,
            unit=unit,
            is_readonly=is_readonly,
        )

    def _build_server_overview(
        self,
        configuration: List[StatusItem],
        performance: List[StatusItem],
        connections: ConnectionInfo,
        storage: StorageInfo,
        databases: List[DatabaseBriefInfo],
        users: List[UserInfo],
        version: str,
        session: Optional[SessionInfo] = None,
        innodb: Optional[InnoDBInfo] = None,
        binary_log: Optional[BinaryLogInfo] = None,
        processes: Optional[List[ProcessInfo]] = None,
        slow_query: Optional[SlowQueryInfo] = None,
    ) -> ServerOverview:
        """Build ServerOverview from collected data.

        ClickHouse-specific replication details are exposed through
        ``system.replicas`` in ``extra`` rather than a dedicated dataclass.
        """
        replication_summary = None
        try:
            result = self._backend.execute(
                "SELECT database, table, is_leader, is_readonly, total_replicas "
                "FROM system.replicas LIMIT 20"
            )
            replication_summary = result.data
        except Exception:
            pass

        return ServerOverview(
            server_version=version,
            server_vendor=self._get_vendor_name(),
            session=session,
            configuration=configuration,
            performance=performance,
            connections=connections,
            storage=storage,
            databases=databases,
            users=users,
            innodb=innodb,
            binary_log=binary_log,
            processes=processes or [],
            slow_query=slow_query,
            extra={"replicas": replication_summary} if replication_summary else {},
        )


class SyncClickHouseStatusIntrospector(ClickHouseStatusIntrospectorMixin, SyncAbstractStatusIntrospector):
    """Synchronous ClickHouse status introspector.

    Uses SHOW VARIABLES and SHOW STATUS to gather server information.

    Usage::

        backend = ClickHouseBackend(connection_config=config)
        backend.connect()
        status = backend.introspector.status.get_overview()
        print(status.server_version)
    """

    def __init__(self, backend: Any) -> None:
        super().__init__(backend)
        self._show = backend.introspector.show

    def get_overview(self) -> ServerOverview:
        """Get complete ClickHouse status overview.

        MySQL-specific sections (InnoDB, binary log, slow queries) are not
        applicable to ClickHouse and degrade to ``None`` instead of failing.
        """
        configuration = self.list_configuration()
        performance = self.list_performance_metrics()
        connections = self.get_connection_info()
        storage = self.get_storage_info()
        databases = self.list_databases()
        users = self.list_users()
        session = self.get_session_info()
        processes = self.list_processes()

        version = self._get_version_string()

        return self._build_server_overview(
            configuration=configuration,
            performance=performance,
            connections=connections,
            storage=storage,
            databases=databases,
            users=users,
            version=version,
            session=session,
            innodb=None,
            binary_log=None,
            processes=processes,
            slow_query=None,
        )

    def _get_version_string(self) -> str:
        """Get ClickHouse version string."""
        try:
            result = self._backend.execute("SELECT version()")
            if result.data and result.data[0]:
                return str(next(iter(result.data[0].values())))
        except Exception:
            pass
        version_tuple = getattr(self._backend, "_version", (8, 0, 0))
        return ".".join(str(v) for v in version_tuple)

    def list_configuration(self, category: Optional[StatusCategory] = None) -> List[StatusItem]:
        """List ClickHouse configuration parameters via ``system.settings``."""
        items = []

        var_dict = {}
        try:
            result = self._backend.execute(
                "SELECT name, value, changed FROM system.settings"
            )
            for row in result.data or []:
                var_dict[row.get("name")] = row.get("value")
        except Exception:
            return items

        # Build status items for known variables
        for var_name, var_category, description, unit, is_readonly in CLICKHOUSE_CONFIG_VARIABLES:
            if category and var_category != category:
                continue

            if var_name in var_dict:
                item = self._create_status_item(
                    name=var_name,
                    value=var_dict[var_name],
                    category=var_category,
                    description=description,
                    unit=unit,
                    is_readonly=is_readonly,
                )
                items.append(item)

        return items

    def list_performance_metrics(self, category: Optional[StatusCategory] = None) -> List[StatusItem]:
        """List ClickHouse performance metrics via ``system.metrics``."""
        items = []

        status_dict = {}
        try:
            result = self._backend.execute(
                "SELECT metric, value FROM system.metrics"
            )
            for row in result.data or []:
                status_dict[row.get("metric")] = row.get("value")
        except Exception:
            return items

        # Build status items for known status variables
        for var_name, var_category, description, unit in CLICKHOUSE_STATUS_VARIABLES:
            if category and var_category != category:
                continue

            if var_name in status_dict:
                item = self._create_status_item(
                    name=var_name,
                    value=status_dict[var_name],
                    category=var_category,
                    description=description,
                    unit=unit,
                )
                items.append(item)

        return items

    def get_connection_info(self) -> ConnectionInfo:
        """Get connection information from ``system.metrics`` / ``system.settings``."""
        status_dict = {}
        try:
            result = self._backend.execute(
                "SELECT metric, value FROM system.metrics "
                "WHERE metric IN ('Connection', 'HTTPConnection', 'TCPConnection', 'InterserverConnection')"
            )
            for row in result.data or []:
                status_dict[row.get("metric")] = row.get("value")
        except Exception:
            pass

        var_dict = {}
        try:
            result = self._backend.execute(
                "SELECT value FROM system.settings WHERE name = 'max_connections'"
            )
            if result.data:
                var_dict["max_connections"] = next(iter(result.data[0].values()))
        except Exception:
            pass

        active = sum(
            self._parse_variable_value(v) or 0
            for k, v in status_dict.items()
            if "connection" in k.lower()
        )

        return ConnectionInfo(
            active_count=active or None,
            max_connections=self._parse_variable_value(var_dict.get("max_connections")),
            idle_count=None,
            extra={
                "http_connections": self._parse_variable_value(status_dict.get("HTTPConnection")),
                "tcp_connections": self._parse_variable_value(status_dict.get("TCPConnection")),
            },
        )

    def get_storage_info(self) -> StorageInfo:
        """Get storage information from ``system.tables`` / ``system.disks``."""
        total_size = None
        try:
            result = self._backend.execute(
                "SELECT sum(total_bytes) AS total_size FROM system.tables "
                "WHERE database = %s",
                (self._backend.config.database,),
            )
            if result and result.data:
                total_size = result.data[0].get("total_size")
        except Exception:
            pass

        datadir = None
        buffer_size = None
        try:
            result = self._backend.execute(
                "SELECT path, free_space FROM system.disks WHERE name = 'default'"
            )
            if result.data:
                datadir = result.data[0].get("path")
                buffer_size = result.data[0].get("free_space")
        except Exception:
            pass

        return StorageInfo(
            total_size_bytes=self._parse_variable_value(total_size),
            extra={
                "datadir": datadir,
                "free_space": self._parse_variable_value(buffer_size),
            },
        )

    def list_databases(self) -> List[DatabaseBriefInfo]:
        """List databases with table/view counts."""
        databases = []

        db_results = self._show.databases()
        db_names = [db.name for db in db_results]

        # Get table and view counts for all databases from information_schema
        table_counts: Dict[str, int] = {}
        view_counts: Dict[str, int] = {}

        try:
            result = self._backend.execute(
                "SELECT table_schema, table_type, COUNT(*) as count "
                "FROM information_schema.TABLES "
                "WHERE table_schema IN (%s) "
                "GROUP BY table_schema, table_type" % ",".join(["%s"] * len(db_names)),
                tuple(db_names),
            )
            if result and result.data:
                for row in result.data:
                    # ClickHouse returns column names in uppercase
                    schema = row.get("TABLE_SCHEMA") or row.get("table_schema")
                    table_type = row.get("TABLE_TYPE") or row.get("table_type")
                    count = row.get("count", 0) or row.get("COUNT", 0)
                    if table_type == "BASE TABLE":
                        table_counts[schema] = count
                    elif table_type == "VIEW":
                        view_counts[schema] = count
        except Exception:
            pass

        for db_name in db_names:
            db_info = DatabaseBriefInfo(
                name=db_name,
                table_count=table_counts.get(db_name, 0),
                view_count=view_counts.get(db_name, 0),
            )
            databases.append(db_info)

        return databases

    def list_users(self) -> List[UserInfo]:
        """List users from clickhouse.user table."""
        users = []

        try:
            result = self._backend.execute("SELECT User, Host, Super_priv FROM clickhouse.user", ())
            if result and result.data:
                for row in result.data:
                    user = UserInfo(
                        name=row.get("User"),
                        host=row.get("Host"),
                        is_superuser=row.get("Super_priv") == "Y",
                    )
                    users.append(user)
        except Exception:
            # clickhouse.user may not be accessible
            pass

        return users

    def get_session_info(self) -> SessionInfo:
        """Get current session/connection information."""
        session = SessionInfo()

        # Get current user
        try:
            result = self._backend.execute("SELECT currentUser()", ())
            if result and result.data:
                current_user = next(iter(result.data[0].values()))
                if current_user:
                    session.user = str(current_user)
        except Exception:
            pass

        # Get current database
        session.database = self._backend.config.database

        # The HTTP interface reports no TLS session details to the client;
        # ssl_enabled stays at its default (None).

        # Check if password was used (connection was made with password)
        session.password_used = bool(self._backend.config.password)

        return session

    def get_innodb_info(self) -> InnoDBInfo:
        """Get InnoDB storage engine information."""
        innodb = InnoDBInfo()
        # Get buffer pool info
        try:
            result = self._backend.execute("SHOW STATUS LIKE 'Innodb_buffer_pool%'", ())
            if result and result.data:
                for row in result.data:
                    key = row.get("Variable_name")
                    value = row.get("Value")
                    if key == "Innodb_buffer_pool_pages_total":
                        innodb.buffer_pool_pages_total = self._parse_variable_value(value)
                    elif key == "Innodb_buffer_pool_pages_data":
                        innodb.buffer_pool_pages_data = self._parse_variable_value(value)
                    elif key == "Innodb_buffer_pool_pages_dirty":
                        innodb.buffer_pool_pages_dirty = self._parse_variable_value(value)
                    elif key == "Innodb_buffer_pool_pages_free":
                        innodb.buffer_pool_pages_free = self._parse_variable_value(value)
                    elif key == "Innodb_buffer_pool_read_requests":
                        innodb.buffer_pool_read_requests = self._parse_variable_value(value)
                    elif key == "Innodb_buffer_pool_reads":
                        innodb.buffer_pool_reads = self._parse_variable_value(value)
                    elif key == "Innodb_buffer_pool_wait_free":
                        innodb.buffer_pool_wait_free = self._parse_variable_value(value)
        except Exception:
            pass
        # Get InnoDB variables
        try:
            result = self._backend.execute("SHOW VARIABLES LIKE 'innodb%'", ())
            if result and result.data:
                for row in result.data:
                    key = row.get("Variable_name")
                    value = row.get("Value")
                    if key == "innodb_buffer_pool_size":
                        innodb.buffer_pool_size = self._parse_variable_value(value)
                    elif key == "innodb_buffer_pool_instances":
                        innodb.buffer_pool_instances = self._parse_variable_value(value)
                    elif key == "innodb_log_file_size":
                        innodb.log_file_size = self._parse_variable_value(value)
                    elif key == "innodb_log_buffer_size":
                        innodb.log_buffer_size = self._parse_variable_value(value)
                    elif key == "innodb_lock_wait_timeout":
                        innodb.lock_wait_timeout = self._parse_variable_value(value)
        except Exception:
            pass
        # Get InnoDB row lock status
        try:
            result = self._backend.execute("SHOW STATUS LIKE 'Innodb_row_lock%'", ())
            if result and result.data:
                for row in result.data:
                    key = row.get("Variable_name")
                    value = row.get("Value")
                    if key == "Innodb_row_lock_time":
                        innodb.row_lock_time = self._parse_variable_value(value)
                    elif key == "Innodb_row_lock_waits":
                        innodb.row_lock_waits = self._parse_variable_value(value)
                    elif key == "Innodb_row_lock_time_avg":
                        # Calculate average
                        total_lock_time = innodb.row_lock_time or 0
                        lock_waits = innodb.row_lock_waits or 1
                        avg_time = total_lock_time / lock_waits if lock_waits > 0 else 0
                        innodb.row_lock_time_avg = round(avg_time, 2)
                    elif key == "Innodb_rows_read":
                        innodb.rows_read = self._parse_variable_value(value)
                    elif key == "Innodb_rows_inserted":
                        innodb.rows_inserted = self._parse_variable_value(value)
                    elif key == "Innodb_rows_updated":
                        innodb.rows_updated = self._parse_variable_value(value)
                    elif key == "Innodb_rows_deleted":
                        innodb.rows_deleted = self._parse_variable_value(value)
                    elif key == "Innodb_data_reads":
                        innodb.data_reads = self._parse_variable_value(value)
                    elif key == "Innodb_data_writes":
                        innodb.data_writes = self._parse_variable_value(value)
                    elif key == "Innodb_os_log_fsyncs":
                        innodb.os_fsyncs = self._parse_variable_value(value)
                    elif key == "Innodb_os_file_reads":
                        innodb.os_file_reads = self._parse_variable_value(value)
                    elif key == "Innodb_os_file_writes":
                        innodb.os_file_writes = self._parse_variable_value(value)
        except Exception:
            pass
        return innodb

    def get_binary_log_info(self) -> BinaryLogInfo:
        """Get binary log information."""
        binary_log = BinaryLogInfo()
        # Check if binary logging is enabled
        try:
            result = self._backend.execute("SHOW VARIABLES LIKE 'log_bin'", ())
            if result and result.data:
                for row in result.data:
                    key = row.get("Variable_name")
                    value = row.get("Value")
                    if key == "log_bin":
                        binary_log.log_enabled = str(value).lower() in ("on", "1")
                    elif key == "binlog_format":
                        binary_log.log_format = value
        except Exception:
            pass
        # Get binary log files (only if binary logging is enabled)
        if binary_log.log_enabled:
            try:
                result = self._backend.execute("SHOW BINARY LOGS", ())
                if result and result.data:
                    log_files = []
                    total_size = 0
                    for row in result.data:
                        log_file = row.get("Log_name")
                        if log_file:
                            log_files.append(log_file)
                            # Get file size from the File_size column if available
                            file_size = row.get("File_size")
                            if file_size:
                                total_size += self._parse_variable_value(file_size)
                    binary_log.log_files = log_files
                    binary_log.log_size_bytes = total_size
            except Exception:
                pass
        # Get current binary log file and position
        # Only query if binary logging is enabled
        if binary_log.log_enabled:
            # ClickHouse 9.0+ removed SHOW MASTER STATUS, use performance_schema.log_status instead
            try:
                # Get server version first
                version_result = self._backend.execute("SELECT VERSION()", ())
                version_str = (
                    version_result.data[0].get("VERSION()", "") if version_result and version_result.data else ""
                )

                if self._is_clickhouse_version_at_least(version_str, 8, 4):
                    # ClickHouse 8.4+: use performance_schema.log_status
                    result = self._backend.execute(
                        "SELECT JSON_UNQUOTE(JSON_EXTRACT(LOCAL, '$.binary_log_file')) as File, "
                        "JSON_EXTRACT(LOCAL, '$.binary_log_position') as Position, "
                        "JSON_UNQUOTE(JSON_EXTRACT(LOCAL, '$.gtid_executed')) as Gtid "
                        "FROM performance_schema.log_status",
                        (),
                    )
                    if result and result.data:
                        row = result.data[0]
                        binary_log.current_log_file = row.get("File")
                        binary_log.current_log_position = self._parse_variable_value(row.get("Position"))
                        binary_log.gtid_executed = row.get("Gtid")
                else:
                    # ClickHouse < 8.4: use SHOW MASTER STATUS
                    result = self._backend.execute("SHOW MASTER STATUS", ())
                    if result and result.data:
                        row = result.data[0]
                        binary_log.current_log_file = row.get("File")
                        binary_log.current_log_position = self._parse_variable_value(row.get("Position"))
            except Exception:
                pass
        # Get GTID info
        try:
            result = self._backend.execute("SHOW VARIABLES LIKE 'gtid_mode'", ())
            if result and result.data:
                for row in result.data:
                    key = row.get("Variable_name")
                    if key == "gtid_mode":
                        binary_log.gtid_mode = row.get("Value")
        except Exception:
            pass
        try:
            result = self._backend.execute("SHOW GLOBAL VARIABLES LIKE 'gtid_executed'", ())
            if result and result.data:
                for row in result.data:
                    key = row.get("Variable_name")
                    if key == "gtid_executed":
                        binary_log.gtid_executed = row.get("Value")
        except Exception:
            pass
        # Add note if binary logging is disabled
        if binary_log.log_enabled is False:
            binary_log.extra["note"] = "Binary logging is not enabled on this server."
            binary_log.extra["hint"] = (
                "Set log_bin=ON to enable binary logging for replication and point-in-time recovery."
            )
        return binary_log

    def list_processes(self) -> List[ProcessInfo]:
        """List current running processes/queries via ``system.processes``."""
        processes = []
        try:
            result = self._backend.execute(
                "SELECT query_id, user, address, currentDatabase, elapsed, query "
                "FROM system.processes",
                (),
            )
            if result and result.data:
                for row in result.data:
                    proc = ProcessInfo(
                        id=row.get("query_id"),
                        user=row.get("user"),
                        host=str(row.get("address") or "") or None,
                        database=row.get("currentDatabase"),
                        command="QUERY",
                        time=row.get("elapsed"),
                        state=None,
                        info=row.get("query"),
                    )
                    processes.append(proc)
        except Exception:
            pass
        return processes

    def get_slow_query_info(self) -> SlowQueryInfo:
        """Get slow query log configuration."""
        slow_query = SlowQueryInfo()
        # Get slow query log status
        try:
            result = self._backend.execute("SHOW VARIABLES LIKE 'slow_query_log%'", ())
            if result and result.data:
                for row in result.data:
                    key = row.get("Variable_name")
                    value = row.get("Value")
                    if key == "slow_query_log":
                        slow_query.slow_query_log = str(value).lower() in ("on", "1")
                    elif key == "slow_query_log_file":
                        slow_query.slow_query_log_file = value
                    elif key == "long_query_time":
                        slow_query.long_query_time = float(value) if value else 10
                    elif key == "log_queries_not_using_indexes":
                        slow_query.log_queries_not_using_indexes = str(value).lower() in ("on", "1")
                    elif key == "log_slow_admin_statements":
                        slow_query.log_slow_admin_statements = str(value).lower() in ("on", "1")
                    elif key == "min_examined_row_limit":
                        slow_query.min_examined_row_limit = self._parse_variable_value(value)
        except Exception:
            pass
        # Get slow query count
        try:
            result = self._backend.execute("SHOW STATUS LIKE 'Slow_queries'", ())
            if result and result.data:
                for row in result.data:
                    key = row.get("Variable_name")
                    value = row.get("Value")
                    if key == "Slow_queries":
                        slow_query.slow_queries_count = self._parse_variable_value(value)
        except Exception:
            pass
        return slow_query

    def get_clickhouse_replication_info(self) -> ClickHouseReplicationInfo:
        """Get ClickHouse replication status information."""
        repl_info = ClickHouseReplicationInfo()
        # Get server_id
        try:
            result = self._backend.execute("SHOW VARIABLES LIKE 'server_id'", ())
            if result and result.data:
                for row in result.data:
                    key = row.get("Variable_name")
                    if key == "server_id":
                        repl_info.server_id = self._parse_variable_value(row.get("Value"))
        except Exception:
            pass
        # Check if this is a master
        # First check if binary logging is enabled
        log_bin_enabled = False
        try:
            result = self._backend.execute("SHOW VARIABLES LIKE 'log_bin'", ())
            if result and result.data:
                for row in result.data:
                    if row.get("Variable_name") == "log_bin":
                        log_bin_enabled = str(row.get("Value")).lower() in ("on", "1")
                        break
        except Exception:
            pass

        # Only query master status if binary logging is enabled
        if log_bin_enabled:
            # ClickHouse 9.0+ removed SHOW MASTER STATUS, use performance_schema.log_status instead
            try:
                # Get server version first
                version_result = self._backend.execute("SELECT VERSION()", ())
                version_str = (
                    version_result.data[0].get("VERSION()", "") if version_result and version_result.data else ""
                )

                if self._is_clickhouse_version_at_least(version_str, 8, 4):
                    # ClickHouse 9.0+: use performance_schema.log_status
                    result = self._backend.execute(
                        "SELECT JSON_UNQUOTE(JSON_EXTRACT(LOCAL, '$.binary_log_file')) as File, "
                        "JSON_EXTRACT(LOCAL, '$.binary_log_position') as Position, "
                        "JSON_UNQUOTE(JSON_EXTRACT(LOCAL, '$.gtid_executed')) as Gtid "
                        "FROM performance_schema.log_status",
                        (),
                    )
                    if result and result.data:
                        repl_info.is_master = True
                        master_info = ReplicationMasterInfo()
                        row = result.data[0]
                        master_info.binary_log_file = row.get("File")
                        master_info.binary_log_position = self._parse_variable_value(row.get("Position"))
                        repl_info.master_info = master_info
                else:
                    # ClickHouse < 9.0: use SHOW MASTER STATUS
                    result = self._backend.execute("SHOW MASTER STATUS", ())
                    if result and result.data:
                        repl_info.is_master = True
                        master_info = ReplicationMasterInfo()
                        row = result.data[0]
                        master_info.binary_log_file = row.get("File")
                        master_info.binary_log_position = self._parse_variable_value(row.get("Position"))
                        # Parse comma-separated list
                        do_db = row.get("Binlog_Do_DB", "")
                        if do_db:
                            master_info.binlog_do_db = [db.strip() for db in do_db.split(",") if db.strip()]
                        ignore_db = row.get("Binlog_Ignore_DB", "")
                        if ignore_db:
                            master_info.binlog_ignore_db = [db.strip() for db in ignore_db.split(",") if db.strip()]
                        master_info.gtid_executed = row.get("Executed_Gtid_Set")
                        repl_info.master_info = master_info
            except Exception:
                pass
        # Check if this is a slave
        # ClickHouse 9.0+ removed SHOW SLAVE STATUS, use performance_schema tables instead
        try:
            # Get server version first (reuse if already fetched above)
            if "version_str" not in dir() or not version_str:
                version_result = self._backend.execute("SELECT VERSION()", ())
                version_str = (
                    version_result.data[0].get("VERSION()", "") if version_result and version_result.data else ""
                )

            if self._is_clickhouse_version_at_least(version_str, 8, 4):
                # ClickHouse 9.0+: use performance_schema replication tables
                # Check replication connection status
                result = self._backend.execute(
                    "SELECT CHANNEL_NAME, SOURCE_UUID, SERVICE_STATE "
                    "FROM performance_schema.replication_connection_status "
                    "WHERE SERVICE_STATE = 'ON'",
                    (),
                )
                if result and result.data:
                    repl_info.is_slave = True
                    slave_info = ReplicationSlaveInfo()
                    for row in result.data:
                        slave_info.slave_io_running = row.get("SERVICE_STATE") == "ON"
                        break  # Take first active channel
                    repl_info.slave_info = slave_info
            else:
                # ClickHouse < 9.0: use SHOW SLAVE STATUS
                result = self._backend.execute("SHOW SLAVE STATUS", ())
                if result and result.data:
                    repl_info.is_slave = True
                    slave_info = ReplicationSlaveInfo()
                    row = result.data[0]
                    slave_info.master_host = row.get("Master_Host")
                    slave_info.master_port = self._parse_variable_value(row.get("Master_Port"))
                    slave_info.master_user = row.get("Master_User")
                    slave_info.slave_io_running = row.get("Slave_IO_Running")
                    slave_info.slave_sql_running = row.get("Slave_SQL_Running")
                    slave_info.seconds_behind_master = self._parse_variable_value(row.get("Seconds_Behind_Master"))
                    slave_info.master_log_file = row.get("Master_Log_File")
                    slave_info.read_master_log_pos = self._parse_variable_value(row.get("Read_Master_Log_Pos"))
                    slave_info.relay_master_log_file = row.get("Relay_Master_Log_File")
                    slave_info.slave_io_state = row.get("Slave_IO_State")
                    slave_info.last_io_errno = self._parse_variable_value(row.get("Last_IO_Errno"))
                    slave_info.last_io_error = row.get("Last_IO_Error")
                    slave_info.last_sql_errno = self._parse_variable_value(row.get("Last_SQL_Errno"))
                    slave_info.last_sql_error = row.get("Last_SQL_Error")
                    slave_info.relay_log_file = row.get("Relay_Log_File")
                    slave_info.relay_log_pos = self._parse_variable_value(row.get("Relay_Log_Pos"))
                    slave_info.exec_master_log_pos = self._parse_variable_value(row.get("Exec_Master_Log_Pos"))
                    repl_info.slave_info = slave_info
        except Exception:
            pass
        return repl_info


class AsyncClickHouseStatusIntrospector(ClickHouseStatusIntrospectorMixin, AsyncAbstractStatusIntrospector):
    """Asynchronous ClickHouse status introspector.

    Uses SHOW VARIABLES and SHOW STATUS to gather server information.

    Usage::

        backend = AsyncClickHouseBackend(connection_config=config)
        await backend.connect()
        status = await backend.introspector.status.get_overview()
        print(status.server_version)
    """

    def __init__(self, backend: Any) -> None:
        super().__init__(backend)
        self._show = backend.introspector.show

    async def get_overview(self) -> ServerOverview:
        """Get complete ClickHouse status overview.

        MySQL-specific sections (InnoDB, binary log, slow queries) are not
        applicable to ClickHouse and degrade to ``None`` instead of failing.
        """
        configuration = await self.list_configuration()
        performance = await self.list_performance_metrics()
        connections = await self.get_connection_info()
        storage = await self.get_storage_info()
        databases = await self.list_databases()
        users = await self.list_users()
        session = await self.get_session_info()
        processes = await self.list_processes()

        version = await self._get_version_string()

        return self._build_server_overview(
            configuration=configuration,
            performance=performance,
            connections=connections,
            storage=storage,
            databases=databases,
            users=users,
            version=version,
            session=session,
            innodb=None,
            binary_log=None,
            processes=processes,
            slow_query=None,
        )

    async def _get_version_string(self) -> str:
        """Get ClickHouse version string."""
        try:
            result = await self._backend.execute("SELECT version()")
            if result.data and result.data[0]:
                return str(next(iter(result.data[0].values())))
        except Exception:
            pass
        version_tuple = getattr(self._backend, "_version", (8, 0, 0))
        return ".".join(str(v) for v in version_tuple)

    async def list_configuration(self, category: Optional[StatusCategory] = None) -> List[StatusItem]:
        """List ClickHouse configuration parameters via ``system.settings``."""
        items = []

        var_dict = {}
        try:
            result = await self._backend.execute(
                "SELECT name, value, changed FROM system.settings"
            )
            for row in result.data or []:
                var_dict[row.get("name")] = row.get("value")
        except Exception:
            return items

        for var_name, var_category, description, unit, is_readonly in CLICKHOUSE_CONFIG_VARIABLES:
            if category and var_category != category:
                continue

            if var_name in var_dict:
                item = self._create_status_item(
                    name=var_name,
                    value=var_dict[var_name],
                    category=var_category,
                    description=description,
                    unit=unit,
                    is_readonly=is_readonly,
                )
                items.append(item)

        return items

    async def list_performance_metrics(self, category: Optional[StatusCategory] = None) -> List[StatusItem]:
        """List ClickHouse performance metrics via ``system.metrics``."""
        items = []

        status_dict = {}
        try:
            result = await self._backend.execute(
                "SELECT metric, value FROM system.metrics"
            )
            for row in result.data or []:
                status_dict[row.get("metric")] = row.get("value")
        except Exception:
            return items

        for var_name, var_category, description, unit in CLICKHOUSE_STATUS_VARIABLES:
            if category and var_category != category:
                continue

            if var_name in status_dict:
                item = self._create_status_item(
                    name=var_name,
                    value=status_dict[var_name],
                    category=var_category,
                    description=description,
                    unit=unit,
                )
                items.append(item)

        return items

    async def get_connection_info(self) -> ConnectionInfo:
        """Get connection information from ``system.metrics`` / ``system.settings``."""
        status_dict = {}
        try:
            result = await self._backend.execute(
                "SELECT metric, value FROM system.metrics "
                "WHERE metric IN ('Connection', 'HTTPConnection', 'TCPConnection', 'InterserverConnection')"
            )
            for row in result.data or []:
                status_dict[row.get("metric")] = row.get("value")
        except Exception:
            pass

        var_dict = {}
        try:
            result = await self._backend.execute(
                "SELECT value FROM system.settings WHERE name = 'max_connections'"
            )
            if result.data:
                var_dict["max_connections"] = next(iter(result.data[0].values()))
        except Exception:
            pass

        active = sum(
            self._parse_variable_value(v) or 0
            for k, v in status_dict.items()
            if "connection" in k.lower()
        )

        return ConnectionInfo(
            active_count=active or None,
            max_connections=self._parse_variable_value(var_dict.get("max_connections")),
            idle_count=None,
            extra={
                "http_connections": self._parse_variable_value(status_dict.get("HTTPConnection")),
                "tcp_connections": self._parse_variable_value(status_dict.get("TCPConnection")),
            },
        )

    async def get_storage_info(self) -> StorageInfo:
        """Get storage information from ``system.tables`` / ``system.disks``."""
        total_size = None
        try:
            result = await self._backend.execute(
                "SELECT sum(total_bytes) AS total_size FROM system.tables "
                "WHERE database = %s",
                (self._backend.config.database,),
            )
            if result and result.data:
                total_size = result.data[0].get("total_size")
        except Exception:
            pass

        datadir = None
        free_space = None
        try:
            result = await self._backend.execute(
                "SELECT path, free_space FROM system.disks WHERE name = 'default'"
            )
            if result.data:
                datadir = result.data[0].get("path")
                free_space = result.data[0].get("free_space")
        except Exception:
            pass

        return StorageInfo(
            total_size_bytes=self._parse_variable_value(total_size),
            extra={
                "datadir": datadir,
                "free_space": self._parse_variable_value(free_space),
            },
        )

    async def list_databases(self) -> List[DatabaseBriefInfo]:
        """List databases with table/view counts."""
        databases = []

        db_results = await self._show.databases()
        db_names = [db.name for db in db_results]

        # Get table and view counts for all databases from information_schema
        table_counts: Dict[str, int] = {}
        view_counts: Dict[str, int] = {}

        try:
            result = await self._backend.execute(
                "SELECT table_schema, table_type, COUNT(*) as count "
                "FROM information_schema.TABLES "
                "WHERE table_schema IN (%s) "
                "GROUP BY table_schema, table_type" % ",".join(["%s"] * len(db_names)),
                tuple(db_names),
            )
            if result and result.data:
                for row in result.data:
                    # ClickHouse returns column names in uppercase
                    schema = row.get("TABLE_SCHEMA") or row.get("table_schema")
                    table_type = row.get("TABLE_TYPE") or row.get("table_type")
                    count = row.get("count", 0) or row.get("COUNT", 0)
                    if table_type == "BASE TABLE":
                        table_counts[schema] = count
                    elif table_type == "VIEW":
                        view_counts[schema] = count
        except Exception:
            pass

        for db_name in db_names:
            db_info = DatabaseBriefInfo(
                name=db_name,
                table_count=table_counts.get(db_name, 0),
                view_count=view_counts.get(db_name, 0),
            )
            databases.append(db_info)

        return databases

    async def list_users(self) -> List[UserInfo]:
        """List users from clickhouse.user table."""
        users = []

        try:
            result = await self._backend.execute("SELECT User, Host, Super_priv FROM clickhouse.user", ())
            if result and result.data:
                for row in result.data:
                    user = UserInfo(
                        name=row.get("User"),
                        host=row.get("Host"),
                        is_superuser=row.get("Super_priv") == "Y",
                    )
                    users.append(user)
        except Exception:
            pass

        return users

    async def get_session_info(self) -> SessionInfo:
        """Get current session/connection information."""
        session = SessionInfo()

        # Get current user
        try:
            result = await self._backend.execute("SELECT currentUser()", ())
            if result and result.data:
                current_user = next(iter(result.data[0].values()))
                if current_user:
                    session.user = str(current_user)
        except Exception:
            pass

        # Get current database
        session.database = self._backend.config.database

        # The HTTP interface reports no TLS session details to the client;
        # ssl_enabled stays at its default (None).

        # Check if password was used
        session.password_used = bool(self._backend.config.password)

        return session

    async def get_innodb_info(self) -> InnoDBInfo:
        """Get InnoDB storage engine information."""
        innodb = InnoDBInfo()
        # Get buffer pool info
        try:
            result = await self._backend.execute("SHOW STATUS LIKE 'Innodb_buffer_pool%'", ())
            if result and result.data:
                for row in result.data:
                    key = row.get("Variable_name")
                    value = row.get("Value")
                    if key == "Innodb_buffer_pool_pages_total":
                        innodb.buffer_pool_pages_total = self._parse_variable_value(value)
                    elif key == "Innodb_buffer_pool_pages_data":
                        innodb.buffer_pool_pages_data = self._parse_variable_value(value)
                    elif key == "Innodb_buffer_pool_pages_dirty":
                        innodb.buffer_pool_pages_dirty = self._parse_variable_value(value)
                    elif key == "Innodb_buffer_pool_pages_free":
                        innodb.buffer_pool_pages_free = self._parse_variable_value(value)
                    elif key == "Innodb_buffer_pool_read_requests":
                        innodb.buffer_pool_read_requests = self._parse_variable_value(value)
                    elif key == "Innodb_buffer_pool_reads":
                        innodb.buffer_pool_reads = self._parse_variable_value(value)
                    elif key == "Innodb_buffer_pool_wait_free":
                        innodb.buffer_pool_wait_free = self._parse_variable_value(value)
        except Exception:
            pass
        # Get InnoDB variables
        try:
            result = await self._backend.execute("SHOW VARIABLES LIKE 'innodb%'", ())
            if result and result.data:
                for row in result.data:
                    key = row.get("Variable_name")
                    value = row.get("Value")
                    if key == "innodb_buffer_pool_size":
                        innodb.buffer_pool_size = self._parse_variable_value(value)
                    elif key == "innodb_buffer_pool_instances":
                        innodb.buffer_pool_instances = self._parse_variable_value(value)
                    elif key == "innodb_log_file_size":
                        innodb.log_file_size = self._parse_variable_value(value)
                    elif key == "innodb_log_buffer_size":
                        innodb.log_buffer_size = self._parse_variable_value(value)
                    elif key == "innodb_lock_wait_timeout":
                        innodb.lock_wait_timeout = self._parse_variable_value(value)
        except Exception:
            pass
        # Get InnoDB row lock status
        try:
            result = await self._backend.execute("SHOW STATUS LIKE 'Innodb_row_lock%'", ())
            if result and result.data:
                for row in result.data:
                    key = row.get("Variable_name")
                    value = row.get("Value")
                    if key == "Innodb_row_lock_time":
                        innodb.row_lock_time = self._parse_variable_value(value)
                    elif key == "Innodb_row_lock_waits":
                        innodb.row_lock_waits = self._parse_variable_value(value)
                    elif key == "Innodb_row_lock_time_avg":
                        total_lock_time = innodb.row_lock_time or 0
                        lock_waits = innodb.row_lock_waits or 1
                        avg_time = total_lock_time / lock_waits if lock_waits > 0 else 0
                        innodb.row_lock_time_avg = round(avg_time, 2)
                    elif key == "Innodb_rows_read":
                        innodb.rows_read = self._parse_variable_value(value)
                    elif key == "Innodb_rows_inserted":
                        innodb.rows_inserted = self._parse_variable_value(value)
                    elif key == "Innodb_rows_updated":
                        innodb.rows_updated = self._parse_variable_value(value)
                    elif key == "Innodb_rows_deleted":
                        innodb.rows_deleted = self._parse_variable_value(value)
                    elif key == "Innodb_data_reads":
                        innodb.data_reads = self._parse_variable_value(value)
                    elif key == "Innodb_data_writes":
                        innodb.data_writes = self._parse_variable_value(value)
                    elif key == "Innodb_os_log_fsyncs":
                        innodb.os_fsyncs = self._parse_variable_value(value)
                    elif key == "Innodb_os_file_reads":
                        innodb.os_file_reads = self._parse_variable_value(value)
                    elif key == "Innodb_os_file_writes":
                        innodb.os_file_writes = self._parse_variable_value(value)
        except Exception:
            pass
        return innodb

    async def get_binary_log_info(self) -> BinaryLogInfo:
        """Get binary log information."""
        binary_log = BinaryLogInfo()
        # Check if binary logging is enabled
        try:
            result = await self._backend.execute("SHOW VARIABLES LIKE 'log_bin'", ())
            if result and result.data:
                for row in result.data:
                    key = row.get("Variable_name")
                    value = row.get("Value")
                    if key == "log_bin":
                        binary_log.log_enabled = str(value).lower() in ("on", "1")
                    elif key == "binlog_format":
                        binary_log.log_format = value
        except Exception:
            pass
        # Get binary log files (only if binary logging is enabled)
        if binary_log.log_enabled:
            try:
                result = await self._backend.execute("SHOW BINARY LOGS", ())
                if result and result.data:
                    log_files = []
                    total_size = 0
                    for row in result.data:
                        log_file = row.get("Log_name")
                        if log_file:
                            log_files.append(log_file)
                            file_size = row.get("File_size")
                            if file_size:
                                total_size += self._parse_variable_value(file_size)
                    binary_log.log_files = log_files
                    binary_log.log_size_bytes = total_size
            except Exception:
                pass
        # Get current binary log file and position
        # Only query if binary logging is enabled
        if binary_log.log_enabled:
            # ClickHouse 9.0+ removed SHOW MASTER STATUS, use performance_schema.log_status instead
            try:
                # Get server version first
                version_result = await self._backend.execute("SELECT VERSION()", ())
                version_str = (
                    version_result.data[0].get("VERSION()", "") if version_result and version_result.data else ""
                )

                if self._is_clickhouse_version_at_least(version_str, 8, 4):
                    # ClickHouse 8.4+: use performance_schema.log_status
                    result = await self._backend.execute(
                        "SELECT JSON_UNQUOTE(JSON_EXTRACT(LOCAL, '$.binary_log_file')) as File, "
                        "JSON_EXTRACT(LOCAL, '$.binary_log_position') as Position, "
                        "JSON_UNQUOTE(JSON_EXTRACT(LOCAL, '$.gtid_executed')) as Gtid "
                        "FROM performance_schema.log_status",
                        (),
                    )
                    if result and result.data:
                        row = result.data[0]
                        binary_log.current_log_file = row.get("File")
                        binary_log.current_log_position = self._parse_variable_value(row.get("Position"))
                        binary_log.gtid_executed = row.get("Gtid")
                else:
                    # ClickHouse < 8.4: use SHOW MASTER STATUS
                    result = await self._backend.execute("SHOW MASTER STATUS", ())
                    if result and result.data:
                        row = result.data[0]
                        binary_log.current_log_file = row.get("File")
                        binary_log.current_log_position = self._parse_variable_value(row.get("Position"))
            except Exception:
                pass
        # Get GTID info
        try:
            result = await self._backend.execute("SHOW VARIABLES LIKE 'gtid_mode'", ())
            if result and result.data:
                for row in result.data:
                    key = row.get("Variable_name")
                    if key == "gtid_mode":
                        binary_log.gtid_mode = row.get("Value")
        except Exception:
            pass
        # Add note if binary logging is disabled
        if binary_log.log_enabled is False:
            binary_log.extra["note"] = "Binary logging is not enabled on this server."
            binary_log.extra["hint"] = (
                "Set log_bin=ON to enable binary logging for replication and point-in-time recovery."
            )
        return binary_log

    async def list_processes(self) -> List[ProcessInfo]:
        """List current running processes/queries via ``system.processes``."""
        processes = []
        try:
            result = await self._backend.execute(
                "SELECT query_id, user, address, currentDatabase, elapsed, query "
                "FROM system.processes",
                (),
            )
            if result and result.data:
                for row in result.data:
                    proc = ProcessInfo(
                        id=row.get("query_id"),
                        user=row.get("user"),
                        host=str(row.get("address") or "") or None,
                        database=row.get("currentDatabase"),
                        command="QUERY",
                        time=row.get("elapsed"),
                        state=None,
                        info=row.get("query"),
                    )
                    processes.append(proc)
        except Exception:
            pass
        return processes

    async def get_slow_query_info(self) -> SlowQueryInfo:
        slow_query = SlowQueryInfo()
        # Get slow query log settings
        try:
            result = await self._backend.execute("SHOW VARIABLES LIKE 'slow_query_log%'", ())
            if result and result.data:
                for row in result.data:
                    key = row.get("Variable_name")
                    value = row.get("Value")
                    if key == "slow_query_log":
                        slow_query.slow_query_log_enabled = str(value).lower() in ("on", "1")
                    elif key == "slow_query_log_file":
                        slow_query.slow_query_log_file = value
        except Exception:
            pass
        # Get long_query_time
        try:
            result = await self._backend.execute("SHOW VARIABLES LIKE 'long_query_time'", ())
            if result and result.data:
                for row in result.data:
                    value = row.get("Value")
                    if value:
                        slow_query.long_query_time = float(value)
        except Exception:
            pass
        # Get slow query count
        try:
            result = await self._backend.execute("SHOW STATUS LIKE 'Slow_queries'", ())
            if result and result.data:
                for row in result.data:
                    value = row.get("Value")
                    if value:
                        slow_query.slow_queries_count = self._parse_variable_value(value)
        except Exception:
            pass
        return slow_query

    async def get_clickhouse_replication_info(self) -> ClickHouseReplicationInfo:
        """Get ClickHouse replication information."""
        repl = ClickHouseReplicationInfo()
        # Get server version first
        try:
            version_result = await self._backend.execute("SELECT VERSION()", ())
            version_str = version_result.data[0].get("VERSION()", "") if version_result and version_result.data else ""
        except Exception:
            version_str = ""

        # Check if binary logging is enabled first
        log_bin_enabled = False
        try:
            result = await self._backend.execute("SHOW VARIABLES LIKE 'log_bin'", ())
            if result and result.data:
                for row in result.data:
                    if row.get("Variable_name") == "log_bin":
                        log_bin_enabled = str(row.get("Value")).lower() in ("on", "1")
                        break
        except Exception:
            pass

        # Check if server is configured as master (only if binary logging is enabled)
        if log_bin_enabled:
            try:
                if self._is_clickhouse_version_at_least(version_str, 8, 4):
                    # ClickHouse 8.4+: use performance_schema.log_status
                    result = await self._backend.execute(
                        "SELECT JSON_UNQUOTE(JSON_EXTRACT(LOCAL, '$.binary_log_file')) as File, "
                        "JSON_EXTRACT(LOCAL, '$.binary_log_position') as Position "
                        "FROM performance_schema.log_status",
                        (),
                    )
                    if result and result.data:
                        repl.is_master = True
                        row = result.data[0]
                        repl.master_log_file = row.get("File")
                        repl.master_log_position = self._parse_variable_value(row.get("Position"))
                else:
                    # ClickHouse < 8.4: use SHOW MASTER STATUS
                    result = await self._backend.execute("SHOW MASTER STATUS", ())
                    if result and result.data:
                        repl.is_master = True
                        row = result.data[0]
                        repl.master_log_file = row.get("File")
                        repl.master_log_position = self._parse_variable_value(row.get("Position"))
            except Exception:
                pass
        # Check if server is configured as slave
        try:
            if self._is_clickhouse_version_at_least(version_str, 8, 4):
                # ClickHouse 9.0+: use performance_schema replication tables
                result = await self._backend.execute(
                    "SELECT SERVICE_STATE FROM performance_schema.replication_connection_status "
                    "WHERE SERVICE_STATE = 'ON' LIMIT 1",
                    (),
                )
                if result and result.data:
                    repl.is_slave = True
                    repl.slave_io_running = True
            else:
                # ClickHouse < 9.0: use SHOW SLAVE STATUS
                result = await self._backend.execute("SHOW SLAVE STATUS", ())
                if result and result.data:
                    repl.is_slave = True
                    row = result.data[0]
                    repl.slave_io_running = row.get("Slave_IO_Running") == "Yes"
                    repl.slave_sql_running = row.get("Slave_SQL_Running") == "Yes"
                    repl.slave_master_host = row.get("Master_Host")
                    repl.slave_master_port = row.get("Master_Port")
                    repl.slave_relay_log_file = row.get("Relay_Log_File")
                    repl.slave_relay_log_pos = self._parse_variable_value(row.get("Relay_Log_Pos"))
                    repl.slave_last_error = row.get("Last_Error")
        except Exception:
            pass
        return repl

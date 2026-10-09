# src/rhosocial/activerecord/backend/impl/clickhouse/introspection/status_introspector.py
"""
ClickHouse server status introspector.

Every value reported here is read out of a ClickHouse ``system.*`` table.
ClickHouse has **no** ``SHOW VARIABLES`` and **no** ``SHOW STATUS``: on
26.7.3.19 both are rejected by the parser with ``SYNTAX_ERROR ... Expected one
of: CREATE, FULL, DATABASES, CLUSTERS, MERGES, ...``, so the two inventories
below name rows that were read off the server rather than MySQL variables that
were hoped for.

The five inventories are **requests, not claims**. Each is a shortlist of names
worth reporting plus the category each is filed under; what the caller receives
is the intersection of that shortlist with what the connected server actually
holds. A name the server does not have is dropped rather than reported from
memory, so no inventory can ever assert a setting or metric the server lacks.

That is not defensive padding — a fixed name list asserting server contents is
simply false across versions. Measured on this machine, the row counts are:

=================  =========================  ======  ======  ======
constant           source table               25.8   26.3   26.7
=================  =========================  ======  ======  ======
CONFIG_SETTINGS    ``system.settings``         1370   1550   1715
SERVER_SETTINGS    ``system.server_settings``   228    381    439
GAUGE_METRICS      ``system.metrics``           417    469    521
COUNTER_EVENTS     ``system.events``            144*   157*   225*
ASYNC_METRICS      ``system.asynchronous_metrics``  910    921    944
=================  =========================  ======  ======  ======

(*) ``system.events`` is not a fixed catalogue at all: a row appears only once
that event has actually fired, so the count depends on the server's *history*,
not on its version. A freshly started 26.7.21.2 reports 115 event rows and is
missing 20 of the 49 names in :data:`CLICKHOUSE_COUNTER_EVENTS`; the same
container reaches 171 rows once a merge, an insert, a mutation and a failed
query have run. This is why the inventories are requests: there is no version
key under which a fixed event list could be a true statement.

``system.asynchronous_metrics`` likewise grows with the CPU / disk /
network-interface count, which is why that inventory is restricted to names
carrying no device suffix.

Only two things in an entry are this backend's judgement: the **name** and the
:class:`StatusCategory` it is filed under. Descriptions, defaults, units and
read-only flags are all read from the row the server returned —
``system.settings`` and ``system.server_settings`` expose ``description``,
``default``, ``readonly`` / ``changeable_without_restart`` and ``type``, and the
three metric tables expose ``description`` — so nothing here restates the server
in prose that can drift from it. Each item also records its originating table in
``StatusItem.extra['source']``.

The category rule: a setting or metric is filed under ``STORAGE`` if it is about
files, disks, parts or compressed bytes, under ``CONNECTION`` if it is about
connections, sessions or concurrency admission, under ``SECURITY`` if it is about
access or credentials, under ``REPLICATION`` if it is about replicas, quorum or
consistency, under ``PERFORMANCE`` if it is a throughput limit or switch, and
under ``CONFIGURATION`` otherwise.

Design principle: Sync and Async are separate and cannot coexist.
- SyncClickHouseStatusIntrospector: for synchronous backends
- AsyncClickHouseStatusIntrospector: for asynchronous backends
"""
from __future__ import annotations

from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

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
    SyncAbstractStatusIntrospector,
    AsyncAbstractStatusIntrospector,
)


# --------------------------------------------------------------------------- #
# Inventories — (name, StatusCategory).
#
# Each entry is a request for a name plus this backend's judgement about the
# category it belongs to. It is not a claim that the name exists: every list
# below was drawn from a 26.7.3.19 server, and the five tables differ between
# releases (see the module docstring for the measured counts). The assembly
# methods drop any name the connected server does not return, so the caller
# gets the server's answer and never this module's guess.
#
# ``tests/.../introspection/test_status_introspector.py`` pins the resulting
# contract from a live connection on every version: nothing is returned that
# the server does not have, nothing is dropped that it does, and no MySQL name
# survives in any list.
# --------------------------------------------------------------------------- #

# ``system.settings`` — settings a query or the session can change at runtime.
CLICKHOUSE_CONFIG_SETTINGS: Tuple[Tuple[str, StatusCategory], ...] = (
    # execution shape
    ("max_threads", StatusCategory.PERFORMANCE),
    ("max_block_size", StatusCategory.PERFORMANCE),
    ("max_insert_block_size", StatusCategory.PERFORMANCE),
    ("preferred_block_size_bytes", StatusCategory.PERFORMANCE),
    ("max_memory_usage", StatusCategory.PERFORMANCE),
    ("max_execution_time", StatusCategory.PERFORMANCE),
    ("max_result_rows", StatusCategory.PERFORMANCE),
    ("max_result_bytes", StatusCategory.PERFORMANCE),
    ("max_rows_to_read", StatusCategory.PERFORMANCE),
    ("max_columns_to_read", StatusCategory.PERFORMANCE),
    ("max_parser_depth", StatusCategory.CONFIGURATION),
    ("short_circuit_function_evaluation", StatusCategory.CONFIGURATION),
    ("join_algorithm", StatusCategory.PERFORMANCE),
    ("join_use_nulls", StatusCategory.CONFIGURATION),
    ("optimize_move_to_prewhere", StatusCategory.PERFORMANCE),
    ("group_by_two_level_threshold", StatusCategory.PERFORMANCE),
    ("prefer_column_name_to_alias", StatusCategory.CONFIGURATION),
    ("transform_null_in", StatusCategory.CONFIGURATION),
    ("validate_enum_literals_in_operators", StatusCategory.CONFIGURATION),
    ("normalize_function_names", StatusCategory.CONFIGURATION),
    ("print_pretty_type_names", StatusCategory.CONFIGURATION),
    ("use_client_time_zone", StatusCategory.CONFIGURATION),
    ("session_timezone", StatusCategory.CONFIGURATION),
    ("max_download_threads", StatusCategory.PERFORMANCE),
    ("distributed_foreground_insert", StatusCategory.PERFORMANCE),
    # concurrency admission
    ("max_concurrent_queries_for_user", StatusCategory.CONNECTION),
    ("max_concurrent_queries_for_all_users", StatusCategory.CONNECTION),
    # caches
    ("use_query_cache", StatusCategory.PERFORMANCE),
    ("query_cache_max_size_in_bytes", StatusCategory.PERFORMANCE),
    ("query_cache_ttl", StatusCategory.PERFORMANCE),
    ("use_uncompressed_cache", StatusCategory.PERFORMANCE),
    ("max_bytes_before_external_sort", StatusCategory.PERFORMANCE),
    ("max_bytes_before_external_group_by", StatusCategory.PERFORMANCE),
    ("max_bytes_before_external_join", StatusCategory.PERFORMANCE),
    # files and compression
    ("max_compress_block_size", StatusCategory.STORAGE),
    ("min_compress_block_size", StatusCategory.STORAGE),
    ("local_filesystem_read_method", StatusCategory.STORAGE),
    ("storage_file_read_method", StatusCategory.STORAGE),
    ("min_free_disk_bytes_to_perform_insert", StatusCategory.STORAGE),
    ("max_partition_size_to_drop", StatusCategory.STORAGE),
    ("max_table_size_to_drop", StatusCategory.STORAGE),
    # connections
    ("http_connection_timeout", StatusCategory.CONNECTION),
    ("http_receive_timeout", StatusCategory.CONNECTION),
    ("http_send_timeout", StatusCategory.CONNECTION),
    ("receive_timeout", StatusCategory.CONNECTION),
    ("send_timeout", StatusCategory.CONNECTION),
    ("tcp_keep_alive_timeout", StatusCategory.CONNECTION),
    ("idle_connection_timeout", StatusCategory.CONNECTION),
    ("max_distributed_connections", StatusCategory.CONNECTION),
    # access
    ("readonly", StatusCategory.SECURITY),
    ("s3_allow_server_credentials_in_user_queries", StatusCategory.SECURITY),
    # replicas
    ("load_balancing", StatusCategory.REPLICATION),
    ("parallel_replicas_mode", StatusCategory.REPLICATION),
    ("prefer_localhost_replica", StatusCategory.REPLICATION),
    ("insert_quorum", StatusCategory.REPLICATION),
    ("insert_quorum_parallel", StatusCategory.REPLICATION),
    ("insert_quorum_timeout", StatusCategory.REPLICATION),
    ("replication_alter_partitions_sync", StatusCategory.REPLICATION),
    ("replication_wait_for_inactive_replica_timeout", StatusCategory.REPLICATION),
    ("select_sequential_consistency", StatusCategory.REPLICATION),
    ("update_sequential_consistency", StatusCategory.REPLICATION),
)

# ``system.server_settings`` — the ``config.xml`` half of the configuration.
# ``max_connections`` lives here and *only* here: it is not a
# ``system.settings`` row, so a ``system.settings`` lookup for it returns
# nothing at all.
CLICKHOUSE_SERVER_SETTINGS: Tuple[Tuple[str, StatusCategory], ...] = (
    ("max_connections", StatusCategory.CONNECTION),
    ("max_concurrent_queries", StatusCategory.CONNECTION),
    ("listen_backlog", StatusCategory.CONNECTION),
    ("keep_alive_timeout", StatusCategory.CONNECTION),
    ("max_thread_pool_size", StatusCategory.PERFORMANCE),
    ("max_server_memory_usage", StatusCategory.PERFORMANCE),
    ("mark_cache_size", StatusCategory.PERFORMANCE),
    ("uncompressed_cache_size", StatusCategory.PERFORMANCE),
    ("primary_index_cache_size", StatusCategory.PERFORMANCE),
    ("page_cache_size_ratio", StatusCategory.STORAGE),
    ("max_held_snapshots", StatusCategory.STORAGE),
    ("path", StatusCategory.STORAGE),
    ("tmp_path", StatusCategory.STORAGE),
)

# ``system.metrics`` — instantaneous gauges, reset on restart.
CLICKHOUSE_GAUGE_METRICS: Tuple[Tuple[str, StatusCategory], ...] = (
    # running work
    ("Query", StatusCategory.PERFORMANCE),
    ("QueryNonInternal", StatusCategory.PERFORMANCE),
    ("Merge", StatusCategory.PERFORMANCE),
    ("PartMutation", StatusCategory.PERFORMANCE),
    ("BackgroundMergesAndMutationsPoolTask", StatusCategory.PERFORMANCE),
    ("Compressing", StatusCategory.PERFORMANCE),
    ("Decompressing", StatusCategory.PERFORMANCE),
    ("Read", StatusCategory.PERFORMANCE),
    ("Write", StatusCategory.PERFORMANCE),
    ("RemoteRead", StatusCategory.PERFORMANCE),
    ("DistributedSend", StatusCategory.PERFORMANCE),
    ("ConcurrentQueryAcquired", StatusCategory.CONNECTION),
    ("ConcurrentQueryScheduled", StatusCategory.CONNECTION),
    ("RWLockActiveReaders", StatusCategory.CONNECTION),
    ("RWLockActiveWriters", StatusCategory.CONNECTION),
    # memory
    ("MemoryTracking", StatusCategory.PERFORMANCE),
    ("MemoryTrackingUncorrected", StatusCategory.PERFORMANCE),
    ("MemoryReservationDemand", StatusCategory.PERFORMANCE),
    ("MemoryReservationApproved", StatusCategory.PERFORMANCE),
    # caches and query pipeline
    ("QueryCacheBytes", StatusCategory.PERFORMANCE),
    ("QueryCacheEntries", StatusCategory.PERFORMANCE),
    ("AsynchronousInsertQueueSize", StatusCategory.PERFORMANCE),
    ("AsynchronousInsertQueueBytes", StatusCategory.PERFORMANCE),
    ("PendingAsyncInsert", StatusCategory.PERFORMANCE),
    ("DelayedInserts", StatusCategory.PERFORMANCE),
    ("BrokenDistributedBytesToInsert", StatusCategory.PERFORMANCE),
    # parts and files on disk
    ("MergeParts", StatusCategory.STORAGE),
    ("PartsOutdated", StatusCategory.STORAGE),
    ("PartsWide", StatusCategory.STORAGE),
    ("PartsTemporary", StatusCategory.STORAGE),
    ("TablesToDropQueueSize", StatusCategory.STORAGE),
    ("DiskSpaceReservedForMerge", StatusCategory.STORAGE),
    ("TemporaryFilesForSort", StatusCategory.STORAGE),
    ("TotalTemporaryFiles", StatusCategory.STORAGE),
    ("FilesystemCacheSize", StatusCategory.STORAGE),
    ("AttachedTable", StatusCategory.STORAGE),
    ("AttachedDatabase", StatusCategory.STORAGE),
    ("AttachedView", StatusCategory.STORAGE),
    ("AttachedDictionary", StatusCategory.STORAGE),
    ("AttachedReplicatedTable", StatusCategory.STORAGE),
    # connections
    ("HTTPConnection", StatusCategory.CONNECTION),
    ("HTTPConnectionsStored", StatusCategory.CONNECTION),
    ("HTTPConnectionsTotal", StatusCategory.CONNECTION),
    ("TCPConnection", StatusCategory.CONNECTION),
    ("MySQLConnection", StatusCategory.CONNECTION),
    ("PostgreSQLConnection", StatusCategory.CONNECTION),
    # replicas and ZooKeeper / Keeper
    ("InterserverConnection", StatusCategory.CONNECTION),
    ("ReplicatedFetch", StatusCategory.REPLICATION),
    ("ReplicatedSend", StatusCategory.REPLICATION),
    ("ReplicatedChecks", StatusCategory.REPLICATION),
    ("ReplicaReady", StatusCategory.REPLICATION),
    ("ReadonlyReplica", StatusCategory.REPLICATION),
    ("SharedMergeTreeFetch", StatusCategory.REPLICATION),
    ("SharedMergeTreeMaxPartitions", StatusCategory.REPLICATION),
    ("ZooKeeperSession", StatusCategory.REPLICATION),
    ("ZooKeeperWatch", StatusCategory.REPLICATION),
    ("ZooKeeperConnectionLossStartedTimestampSeconds", StatusCategory.REPLICATION),
    ("KeeperAliveConnections", StatusCategory.REPLICATION),
    # server identity / state
    ("Revision", StatusCategory.CONFIGURATION),
    ("VersionInteger", StatusCategory.CONFIGURATION),
    ("IsServerShuttingDown", StatusCategory.CONFIGURATION),
    ("LicenseRemainingSeconds", StatusCategory.CONFIGURATION),
)

# ``system.events`` — monotonic counters since server start.
CLICKHOUSE_COUNTER_EVENTS: Tuple[Tuple[str, StatusCategory], ...] = (
    ("Query", StatusCategory.PERFORMANCE),
    ("InitialQuery", StatusCategory.PERFORMANCE),
    ("SelectQuery", StatusCategory.PERFORMANCE),
    ("InitialSelectQuery", StatusCategory.PERFORMANCE),
    ("InsertQuery", StatusCategory.PERFORMANCE),
    ("FailedQuery", StatusCategory.PERFORMANCE),
    ("FailedSelectQuery", StatusCategory.PERFORMANCE),
    ("FailedInsertQuery", StatusCategory.PERFORMANCE),
    ("QueryTimeMicroseconds", StatusCategory.PERFORMANCE),
    ("SelectQueryTimeMicroseconds", StatusCategory.PERFORMANCE),
    ("InsertQueryTimeMicroseconds", StatusCategory.PERFORMANCE),
    ("RealTimeMicroseconds", StatusCategory.PERFORMANCE),
    ("UserTimeMicroseconds", StatusCategory.PERFORMANCE),
    ("SystemTimeMicroseconds", StatusCategory.PERFORMANCE),
    ("QueryParseMicroseconds", StatusCategory.PERFORMANCE),
    ("QueryAnalysisMicroseconds", StatusCategory.PERFORMANCE),
    ("QueryPlanOptimizeMicroseconds", StatusCategory.PERFORMANCE),
    ("QueryPipelineBuildMicroseconds", StatusCategory.PERFORMANCE),
    ("SelectedRows", StatusCategory.PERFORMANCE),
    ("SelectedBytes", StatusCategory.PERFORMANCE),
    ("SelectedMarks", StatusCategory.PERFORMANCE),
    ("SelectedParts", StatusCategory.PERFORMANCE),
    ("SelectQueriesWithPrimaryKeyUsage", StatusCategory.PERFORMANCE),
    ("InsertedRows", StatusCategory.PERFORMANCE),
    ("InsertedBytes", StatusCategory.PERFORMANCE),
    ("MergedRows", StatusCategory.PERFORMANCE),
    ("MergedUncompressedBytes", StatusCategory.PERFORMANCE),
    ("Merge", StatusCategory.PERFORMANCE),
    ("MutatedRows", StatusCategory.PERFORMANCE),
    ("MarkCacheHits", StatusCategory.PERFORMANCE),
    ("MarkCacheMisses", StatusCategory.PERFORMANCE),
    ("QueryConditionCacheMisses", StatusCategory.PERFORMANCE),
    ("Seek", StatusCategory.PERFORMANCE),
    ("FunctionExecute", StatusCategory.PERFORMANCE),
    ("CompiledFunctionExecute", StatusCategory.PERFORMANCE),
    ("ReadCompressedBytes", StatusCategory.PERFORMANCE),
    ("RowsReadByMainReader", StatusCategory.PERFORMANCE),
    ("RowsReadByPrewhereReaders", StatusCategory.PERFORMANCE),
    ("NetworkReceiveBytes", StatusCategory.PERFORMANCE),
    ("NetworkSendBytes", StatusCategory.PERFORMANCE),
    ("ExternalProcessingFilesTotal", StatusCategory.PERFORMANCE),
    ("MergeTreeDataWriterRows", StatusCategory.STORAGE),
    ("MergeTreeDataWriterCompressedBytes", StatusCategory.STORAGE),
    ("LoadedDataParts", StatusCategory.STORAGE),
    ("LoadedMarksFiles", StatusCategory.STORAGE),
    ("OSReadBytes", StatusCategory.STORAGE),
    ("OSWriteBytes", StatusCategory.STORAGE),
    ("FileOpen", StatusCategory.STORAGE),
    ("FileSync", StatusCategory.STORAGE),
)

# ``system.asynchronous_metrics`` — periodically sampled OS / disk / server
# figures. Restricted to names carrying no device, CPU or interface suffix,
# because those are generated per host (e.g. ``BlockReadBytes_nbd0``,
# ``OSUserTimeCPU7``) and would not be stable names.
CLICKHOUSE_ASYNC_METRICS: Tuple[Tuple[str, StatusCategory], ...] = (
    ("Uptime", StatusCategory.CONFIGURATION),
    ("OSUptime", StatusCategory.CONFIGURATION),
    ("AsynchronousMetricsCalculationTimeSpent", StatusCategory.CONFIGURATION),
    ("LoadAverage1", StatusCategory.PERFORMANCE),
    ("LoadAverage5", StatusCategory.PERFORMANCE),
    ("LoadAverage15", StatusCategory.PERFORMANCE),
    ("Jitter", StatusCategory.PERFORMANCE),
    ("OSOpenFiles", StatusCategory.PERFORMANCE),
    ("OSThreadsTotal", StatusCategory.PERFORMANCE),
    ("MemoryResident", StatusCategory.PERFORMANCE),
    ("MemoryVirtual", StatusCategory.PERFORMANCE),
    ("TrackedMemory", StatusCategory.PERFORMANCE),
    ("UntrackedMemory", StatusCategory.PERFORMANCE),
    ("CGroupMemoryTotal", StatusCategory.PERFORMANCE),
    ("CGroupMemoryUsed", StatusCategory.PERFORMANCE),
    ("OSMemoryTotal", StatusCategory.PERFORMANCE),
    ("OSMemoryAvailable", StatusCategory.PERFORMANCE),
    ("QueriesMemoryUsage", StatusCategory.PERFORMANCE),
    ("QueriesPeakMemoryUsage", StatusCategory.PERFORMANCE),
    ("PSI_CPU_some", StatusCategory.PERFORMANCE),
    ("PSI_IO_some", StatusCategory.PERFORMANCE),
    ("PSI_MEM_some", StatusCategory.PERFORMANCE),
    ("LongestRunningMerge", StatusCategory.PERFORMANCE),
    ("NumberOfDatabases", StatusCategory.STORAGE),
    ("NumberOfTables", StatusCategory.STORAGE),
    ("TotalPartsOfMergeTreeTables", StatusCategory.STORAGE),
    ("TotalRowsOfMergeTreeTables", StatusCategory.STORAGE),
    ("TotalBytesOfMergeTreeTables", StatusCategory.STORAGE),
    ("TotalUncompressedBytesOfMergeTreeTables", StatusCategory.STORAGE),
    ("TotalPrimaryKeyBytesInMemory", StatusCategory.STORAGE),
    ("TotalIndexGranularityBytesInMemory", StatusCategory.STORAGE),
    ("FilesystemCacheBytes", StatusCategory.STORAGE),
    ("FilesystemCacheCapacity", StatusCategory.STORAGE),
    ("FilesystemCacheFiles", StatusCategory.STORAGE),
    ("ReplicasMaxQueueSize", StatusCategory.REPLICATION),
    ("ReplicasMaxAbsoluteDelay", StatusCategory.REPLICATION),
    ("ReplicasMaxRelativeDelay", StatusCategory.REPLICATION),
)

# ``system.settings.type`` names these; anything else is a value type rather
# than a unit, so a byte count stays unitless rather than being guessed at.
_TIME_UNITS = frozenset({"Seconds", "Milliseconds", "Microseconds", "Nanoseconds"})

# The gauges that count connections currently open on the server. ClickHouse has
# no single ``Threads_connected`` analogue — these are its per-listener counts,
# and ``get_connection_info`` sums exactly this set.
OPEN_CONNECTION_METRICS: Tuple[str, ...] = (
    "HTTPConnection",
    "TCPConnection",
    "InterserverConnection",
    "MySQLConnection",
    "PostgreSQLConnection",
)

# ClickHouse has no ``SUPER`` privilege and ``system.users`` carries no such
# column. An account is reported as ``is_superuser`` when it holds the whole
# administrative set, unrestricted: server control, access viewing, role
# administration and user creation. Measured on 26.7.3.19, ``root`` holds all
# four (they are granted individually rather than as ``access_type = 'ALL'``).
_SUPERUSER_ACCESS_TYPES: Tuple[str, ...] = (
    "SYSTEM",
    "SHOW ACCESS",
    "ROLE ADMIN",
    "CREATE USER",
)


class ClickHouseStatusIntrospectorMixin:
    """Mixin providing shared ClickHouse status introspection logic.

    Only non-I/O work lives here: value parsing and the assembly of
    :class:`StatusItem` lists from rows the sync/async classes read. The two
    concrete classes keep identical method names so the sync/async parity
    contract holds.
    """

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

        ClickHouse numbers releases ``YY.M.patch``, so the major component is a
        two-digit year. Examples, using the shape of the string this server
        returns (``SELECT version()`` is ``'26.7.3.19'``) plus the build-suffix
        form:

            '26.7.3.19'     -> (26, 7, 3)
            '25.8.4.13'     -> (25, 8, 4)
            '26.3.1.1-alpine' -> (26, 3, 1)

        The extra fourth component this server reports is dropped; the tuple is
        three wide, as the callers expect.
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
        is_dynamic: bool = True,
        default_value: Any = None,
        extra: Optional[Dict[str, Any]] = None,
    ) -> StatusItem:
        """Create a StatusItem with parsed value."""
        return StatusItem(
            name=name,
            value=self._parse_variable_value(value),
            category=category,
            description=description,
            unit=unit,
            is_readonly=is_readonly,
            is_dynamic=is_dynamic,
            default_value=default_value,
            extra=dict(extra) if extra else {},
        )

    # ------------------------------------------------------------------ #
    # Inventory assembly (pure: rows in, StatusItems out)
    # ------------------------------------------------------------------ #

    @staticmethod
    def _setting_unit(declared_type: Any) -> Optional[str]:
        """Unit for a ``system.settings`` value type, if the type names one.

        ``system.settings.type`` is ``Seconds`` / ``Milliseconds`` for the
        timeout settings and ``UInt64`` / ``Bool`` / ``MaxThreads`` / ... for
        everything else, so only the former yields a unit. A byte-valued
        setting reports ``UInt64`` and is therefore left unitless rather than
        being labelled "bytes" on this backend's own authority.
        """
        return declared_type if declared_type in _TIME_UNITS else None

    def _build_setting_items(
        self,
        rows: Iterable[Dict[str, Any]],
        inventory: Sequence[Tuple[str, StatusCategory]],
        source: str,
        read_only_from: str,
    ) -> List[StatusItem]:
        """Assemble StatusItems for one configuration table.

        ``read_only_from`` names the column that answers "may this change
        without a restart": ``readonly`` on ``system.settings`` (which the
        server documents as "the current user cannot change the setting") or
        ``changeable_without_restart`` on ``system.server_settings``.
        """
        by_name = {row.get("name"): row for row in rows if row.get("name")}
        items: List[StatusItem] = []
        for name, category in inventory:
            row = by_name.get(name)
            if row is None:
                # This version of ClickHouse does not offer the name. Reporting
                # a placeholder would be a claim about a server that did not
                # make it, so the name is simply not reported.
                continue
            is_readonly = self._read_only_flag(row, read_only_from)
            items.append(
                self._create_status_item(
                    name=name,
                    value=row.get("value"),
                    category=category,
                    description=row.get("description"),
                    unit=self._setting_unit(row.get("type")),
                    is_readonly=is_readonly,
                    is_dynamic=not is_readonly,
                    default_value=row.get("default"),
                    extra={
                        "source": source,
                        "type": row.get("type"),
                        "changed": bool(row.get("changed")),
                    },
                )
            )
        return items

    @staticmethod
    def _read_only_flag(row: Dict[str, Any], column: str) -> bool:
        """Read the read-only flag from whichever column the table uses."""
        if column == "readonly":
            return bool(row.get("readonly"))
        # ``changeable_without_restart`` is an enum: 'No' / 'IncreaseOnly' /
        # 'DecreaseOnly' / 'Yes'. Only 'No' means the value is fixed.
        return str(row.get("changeable_without_restart") or "").strip().lower() == "no"

    def _build_gauge_items(
        self,
        rows: Iterable[Dict[str, Any]],
        inventory: Sequence[Tuple[str, StatusCategory]],
        source: str,
    ) -> List[StatusItem]:
        """Assemble StatusItems for a ``system.metrics`` gauge.

        A unit is only claimed for the gauges whose name the server itself ends
        in ``Bytes``; a gauge named ``MemoryTracking`` is bytes too, but the
        server does not say so, so it stays unitless.

        A name this version does not publish is not reported: ``QueryNonInternal``
        and ``MemoryReservationDemand`` are 26.3+ names, so on 25.8 they are
        absent from ``system.metrics`` and absent from the result.
        """
        by_name = {row.get("metric"): row for row in rows if row.get("metric")}
        items: List[StatusItem] = []
        for name, category in inventory:
            row = by_name.get(name)
            if row is None:
                continue
            items.append(
                self._create_status_item(
                    name=name,
                    value=row.get("value"),
                    category=category,
                    description=row.get("description"),
                    unit="bytes" if name.endswith("Bytes") else None,
                    is_readonly=True,
                    is_dynamic=False,
                    extra={"source": source},
                )
            )
        return items

    def _build_event_items(
        self,
        rows: Iterable[Dict[str, Any]],
        inventory: Sequence[Tuple[str, StatusCategory]],
        source: str,
    ) -> List[StatusItem]:
        """Assemble StatusItems for a ``system.events`` counter."""
        by_name = {row.get("event"): row for row in rows if row.get("event")}
        items: List[StatusItem] = []
        for name, category in inventory:
            row = by_name.get(name)
            if row is None:
                continue
            items.append(
                self._create_status_item(
                    name=name,
                    value=row.get("value"),
                    category=category,
                    description=row.get("description"),
                    unit="microseconds" if name.endswith("Microseconds") else None,
                    is_readonly=True,
                    is_dynamic=False,
                    extra={"source": source},
                )
            )
        return items

    def _build_async_metric_items(
        self,
        rows: Iterable[Dict[str, Any]],
        inventory: Sequence[Tuple[str, StatusCategory]],
        source: str,
    ) -> List[StatusItem]:
        """Assemble StatusItems for a ``system.asynchronous_metrics`` sample."""
        by_name = {row.get("metric"): row for row in rows if row.get("metric")}
        items: List[StatusItem] = []
        for name, category in inventory:
            row = by_name.get(name)
            if row is None:
                continue
            items.append(
                self._create_status_item(
                    name=name,
                    value=row.get("value"),
                    category=category,
                    description=row.get("description"),
                    is_readonly=True,
                    is_dynamic=False,
                    extra={"source": source},
                )
            )
        return items

    @staticmethod
    def _filter_category(items: List[StatusItem], category: Optional[StatusCategory]) -> List[StatusItem]:
        if category is None:
            return items
        return [item for item in items if item.category == category]

    @staticmethod
    def _placeholders(count: int, backend: Any) -> str:
        return ", ".join([backend.dialect.p()] * count)

    # ------------------------------------------------------------------ #
    # Overview assembly
    # ------------------------------------------------------------------ #

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
        processes: Optional[List[ProcessInfo]] = None,
    ) -> ServerOverview:
        """Build ServerOverview from collected data.

        ``ServerOverview`` carries three MySQL-named slots that this backend
        never fills: ``innodb`` / ``binary_log`` / ``slow_query``. They are core
        fields, so they are left at their dataclass default rather than being
        passed as ``None`` through a parameter that would name them here too.
        ClickHouse's own storage-engine and replication detail is reported in
        ``extra`` — a ``ReplacingMergeTree`` buffer pool, a binary log and a
        slow-query log do not exist, and ``system.replicas`` / ``system.parts``
        are where the equivalents live.
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
            processes=processes or [],
            extra={"replicas": replication_summary} if replication_summary else {},
        )


class SyncClickHouseStatusIntrospector(ClickHouseStatusIntrospectorMixin, SyncAbstractStatusIntrospector):
    """Synchronous ClickHouse status introspector.

    Reads configuration from ``system.settings`` / ``system.server_settings``
    and metrics from ``system.metrics``, ``system.events`` and
    ``system.asynchronous_metrics``.

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
        """Get complete ClickHouse status overview."""
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
            processes=processes,
        )

    def _get_version_string(self) -> str:
        """Get ClickHouse version string.

        Prefers ``SELECT version()``, which is the authoritative answer. The
        fallback is the backend's adapted version when there is one, and the
        empty string when there is not — never an invented release, so a caller
        cannot mistake a guess for a server-reported version.
        """
        try:
            result = self._backend.execute("SELECT version()")
            if result.data and result.data[0]:
                return str(next(iter(result.data[0].values())))
        except Exception:
            pass
        version_tuple = getattr(self._backend, "_version", None)
        if not version_tuple:
            return ""
        return ".".join(str(v) for v in version_tuple)

    def _rows(self, sql: str, params: Optional[tuple] = None) -> List[Dict[str, Any]]:
        """Run a read and return its rows, or ``[]`` if the server refuses."""
        try:
            result = self._backend.execute(sql, params if params is not None else ())
            return list(result.data or [])
        except Exception:
            return []

    def list_configuration(self, category: Optional[StatusCategory] = None) -> List[StatusItem]:
        """List ClickHouse configuration parameters.

        ClickHouse splits its configuration in two, so both halves are read:
        ``system.settings`` for what a session or query can change, and
        ``system.server_settings`` for the ``config.xml`` values that need a
        restart. Each item's ``extra['source']`` says which it came from.

        The name set follows the server: ``system.server_settings`` on 25.8 has
        no ``path``, ``tmp_path`` or ``listen_backlog`` row, so those are not
        reported there. Each item's value, default, description, unit and
        read-only flag are the row's own columns.
        """
        items: List[StatusItem] = []

        settings_rows = self._rows(
            "SELECT name, value, description, default, readonly, changed, type "
            "FROM system.settings WHERE name IN ("
            + self._placeholders(len(CLICKHOUSE_CONFIG_SETTINGS), self._backend)
            + ")",
            tuple(name for name, _ in CLICKHOUSE_CONFIG_SETTINGS),
        )
        items.extend(
            self._build_setting_items(
                settings_rows, CLICKHOUSE_CONFIG_SETTINGS, "system.settings", "readonly"
            )
        )

        server_rows = self._rows(
            "SELECT name, value, description, default, changed, type, changeable_without_restart "
            "FROM system.server_settings WHERE name IN ("
            + self._placeholders(len(CLICKHOUSE_SERVER_SETTINGS), self._backend)
            + ")",
            tuple(name for name, _ in CLICKHOUSE_SERVER_SETTINGS),
        )
        items.extend(
            self._build_setting_items(
                server_rows,
                CLICKHOUSE_SERVER_SETTINGS,
                "system.server_settings",
                "changeable_without_restart",
            )
        )

        return self._filter_category(items, category)

    def list_performance_metrics(self, category: Optional[StatusCategory] = None) -> List[StatusItem]:
        """List ClickHouse performance metrics.

        Three tables, because ClickHouse reports three different things:
        ``system.metrics`` holds instantaneous gauges, ``system.events`` holds
        monotonic counters since server start, and ``system.asynchronous_metrics``
        holds periodically sampled OS / disk figures.

        What comes back is what *this* server has, out of the names this backend
        asks about — never a name the server cannot produce. Two consequences a
        caller should know:

        * the set is version-dependent, because the tables are;
        * the ``system.events`` part is additionally **history**-dependent: a
          counter only appears once that event has fired at least once, so a
          freshly started server legitimately reports fewer events than one that
          has been running merges, inserts and mutations.
        """
        items: List[StatusItem] = []

        gauge_rows = self._rows(
            "SELECT metric, value, description FROM system.metrics WHERE metric IN ("
            + self._placeholders(len(CLICKHOUSE_GAUGE_METRICS), self._backend)
            + ")",
            tuple(name for name, _ in CLICKHOUSE_GAUGE_METRICS),
        )
        items.extend(self._build_gauge_items(gauge_rows, CLICKHOUSE_GAUGE_METRICS, "system.metrics"))

        event_rows = self._rows(
            "SELECT event, value, description FROM system.events WHERE event IN ("
            + self._placeholders(len(CLICKHOUSE_COUNTER_EVENTS), self._backend)
            + ")",
            tuple(name for name, _ in CLICKHOUSE_COUNTER_EVENTS),
        )
        items.extend(self._build_event_items(event_rows, CLICKHOUSE_COUNTER_EVENTS, "system.events"))

        async_rows = self._rows(
            "SELECT metric, value, description FROM system.asynchronous_metrics WHERE metric IN ("
            + self._placeholders(len(CLICKHOUSE_ASYNC_METRICS), self._backend)
            + ")",
            tuple(name for name, _ in CLICKHOUSE_ASYNC_METRICS),
        )
        items.extend(
            self._build_async_metric_items(async_rows, CLICKHOUSE_ASYNC_METRICS, "system.asynchronous_metrics")
        )

        return self._filter_category(items, category)

    def get_connection_info(self) -> ConnectionInfo:
        """Get connection information from ``system.metrics`` / ``system.server_settings``.

        ``max_connections`` is a ``config.xml`` value, so it is read from
        ``system.server_settings``; a ``system.settings`` lookup for that name
        returns no row at all. ``active_count`` sums the five per-listener
        gauges in :data:`OPEN_CONNECTION_METRICS`, because ClickHouse has no
        single ``Threads_connected`` to report.
        """
        gauge_rows = self._rows(
            "SELECT metric, value FROM system.metrics WHERE metric IN ("
            + self._placeholders(len(OPEN_CONNECTION_METRICS), self._backend)
            + ")",
            OPEN_CONNECTION_METRICS,
        )
        gauges = {row.get("metric"): row.get("value") for row in gauge_rows}

        server_rows = self._rows(
            "SELECT name, value FROM system.server_settings "
            f"WHERE name = {self._backend.dialect.p()}",
            ("max_connections",),
        )
        max_connections = server_rows[0].get("value") if server_rows else None

        def _num(name: str) -> Optional[int]:
            value = self._parse_variable_value(gauges.get(name))
            return value if isinstance(value, int) else None

        active = [v for v in (_num(name) for name in OPEN_CONNECTION_METRICS) if v is not None]

        return ConnectionInfo(
            active_count=sum(active) if active else None,
            max_connections=self._parse_variable_value(max_connections),
            idle_count=None,
            extra={
                "http_connections": _num("HTTPConnection"),
                "tcp_connections": _num("TCPConnection"),
                "interserver_connections": _num("InterserverConnection"),
                "mysql_connections": _num("MySQLConnection"),
                "postgresql_connections": _num("PostgreSQLConnection"),
                "note": (
                    "ClickHouse reports one gauge per listener and no combined "
                    "'Threads_connected'; active_count is the sum of "
                    + ", ".join(OPEN_CONNECTION_METRICS)
                ),
            },
        )

    def get_storage_info(self) -> StorageInfo:
        """Get storage information from ``system.tables`` / ``system.disks``."""
        total_size = None
        try:
            result = self._backend.execute(
                "SELECT sum(total_bytes) AS total_size FROM system.tables "
                f"WHERE database = {self._backend.dialect.p()}",
                (self._backend.config.database,),
            )
            if result and result.data:
                total_size = result.data[0].get("total_size")
        except Exception:
            pass

        disks = self._rows(
            "SELECT name, path, type, total_space, free_space, unreserved_space, keep_free_space, "
            "is_encrypted, is_read_only, is_remote, is_broken FROM system.disks"
        )
        default_disk = next((d for d in disks if d.get("name") == "default"), None)

        return StorageInfo(
            total_size_bytes=self._parse_variable_value(total_size),
            free_space_bytes=self._parse_variable_value(default_disk.get("free_space")) if default_disk else None,
            extra={
                "database": self._backend.config.database,
                "data_path": default_disk.get("path") if default_disk else None,
                "disks": disks,
            },
        )

    def list_databases(self) -> List[DatabaseBriefInfo]:
        """List databases with table/view counts.

        The counts are whatever ``information_schema.TABLES`` says, so a
        database nobody has created a table in reports ``0`` — a fresh
        ClickHouse container's ``default`` database is empty, and says so
        truthfully. A count is never padded with a guess to look populated.
        """
        databases = []

        db_results = self._show.databases()
        db_names = [db.name for db in db_results]

        # Get table and view counts for all databases from information_schema.
        # ClickHouse exposes both spellings of every information_schema column
        # (measured on 26.7.3.19: ``table_schema`` and ``TABLE_SCHEMA`` are both
        # returned), and its ``table_type`` uses the same ``BASE TABLE`` /
        # ``VIEW`` values MySQL does.
        table_counts: Dict[str, int] = {}
        view_counts: Dict[str, int] = {}

        try:
            placeholders = self._placeholders(len(db_names), self._backend)
            result = self._backend.execute(
                "SELECT table_schema, table_type, COUNT(*) as count "
                "FROM information_schema.TABLES "
                f"WHERE table_schema IN ({placeholders}) "
                "GROUP BY table_schema, table_type",
                tuple(db_names),
            )
            if result and result.data:
                for row in result.data:
                    schema = row.get("table_schema") or row.get("TABLE_SCHEMA")
                    table_type = row.get("table_type") or row.get("TABLE_TYPE")
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
        """List users from ``system.users`` with their grants and roles.

        There is no ``clickhouse.user`` database on a stock server (measured on
        26.7.3.19: ``UNKNOWN_DATABASE``), so ``system.users`` is the source.
        It carries no superuser column, so ``is_superuser`` is derived from the
        account's grants against ``system.grants`` and the full set lands in
        ``extra['access_types']``.
        """
        users = []

        user_rows = self._rows(
            "SELECT name, id, auth_type, default_database, host_ip, host_names FROM system.users"
        )
        if not user_rows:
            return users

        grant_rows = self._rows(
            "SELECT user_name, access_type, database, table, grant_option FROM system.grants "
            "WHERE database IS NULL AND table IS NULL"
        )
        grants_by_user: Dict[str, List[str]] = {}
        for row in grant_rows:
            name = row.get("user_name")
            access_type = row.get("access_type")
            if name and access_type:
                grants_by_user.setdefault(name, []).append(str(access_type))

        role_rows = self._rows("SELECT user_name, role_name, granted_role_is_default FROM system.role_grants")
        roles_by_user: Dict[str, List[str]] = {}
        for row in role_rows:
            name = row.get("user_name")
            role_name = row.get("role_name")
            if name and role_name:
                roles_by_user.setdefault(name, []).append(str(role_name))

        for row in user_rows:
            name = row.get("name")
            if not name:
                continue
            access_types = sorted(set(grants_by_user.get(name, [])))
            users.append(
                UserInfo(
                    name=name,
                    roles=sorted(set(roles_by_user.get(name, []))),
                    is_superuser=all(t in access_types for t in _SUPERUSER_ACCESS_TYPES),
                    extra={
                        "id": str(row.get("id")),
                        "auth_type": list(row.get("auth_type") or []),
                        "default_database": row.get("default_database") or None,
                        "host_ip": list(row.get("host_ip") or []),
                        "host_names": list(row.get("host_names") or []),
                        "access_types": access_types,
                        "superuser_test": list(_SUPERUSER_ACCESS_TYPES),
                    },
                )
            )

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

    def list_processes(self) -> List[ProcessInfo]:
        """List current running processes/queries via ``system.processes``."""
        processes = []
        rows = self._rows(
            "SELECT query_id, user, address, current_database, elapsed, query "
            "FROM system.processes"
        )
        for row in rows:
            processes.append(
                ProcessInfo(
                    id=row.get("query_id"),
                    user=row.get("user"),
                    host=str(row.get("address") or "") or None,
                    # ClickHouse spells this ``current_database``; MySQL's
                    # ``currentDatabase`` is not a column here.
                    database=row.get("current_database"),
                    command="QUERY",
                    time=row.get("elapsed"),
                    state=None,
                    info=row.get("query"),
                )
            )
        return processes


class AsyncClickHouseStatusIntrospector(ClickHouseStatusIntrospectorMixin, AsyncAbstractStatusIntrospector):
    """Asynchronous ClickHouse status introspector.

    Reads configuration from ``system.settings`` / ``system.server_settings``
    and metrics from ``system.metrics``, ``system.events`` and
    ``system.asynchronous_metrics``. Same inventories and same method names as
    the synchronous class; only the awaits differ.

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
        """Get complete ClickHouse status overview."""
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
            processes=processes,
        )

    async def _get_version_string(self) -> str:
        """Get ClickHouse version string — see the sync twin for the fallback rule."""
        try:
            result = await self._backend.execute("SELECT version()")
            if result.data and result.data[0]:
                return str(next(iter(result.data[0].values())))
        except Exception:
            pass
        version_tuple = getattr(self._backend, "_version", None)
        if not version_tuple:
            return ""
        return ".".join(str(v) for v in version_tuple)

    async def _rows(self, sql: str, params: Optional[tuple] = None) -> List[Dict[str, Any]]:
        """Run a read and return its rows, or ``[]`` if the server refuses."""
        try:
            result = await self._backend.execute(sql, params if params is not None else ())
            return list(result.data or [])
        except Exception:
            return []

    async def list_configuration(self, category: Optional[StatusCategory] = None) -> List[StatusItem]:
        """List ClickHouse configuration parameters.

        ClickHouse splits its configuration in two, so both halves are read:
        ``system.settings`` for what a session or query can change, and
        ``system.server_settings`` for the ``config.xml`` values that need a
        restart. Each item's ``extra['source']`` says which it came from.

        See the synchronous twin for why the name set follows the server.
        """
        items: List[StatusItem] = []

        settings_rows = await self._rows(
            "SELECT name, value, description, default, readonly, changed, type "
            "FROM system.settings WHERE name IN ("
            + self._placeholders(len(CLICKHOUSE_CONFIG_SETTINGS), self._backend)
            + ")",
            tuple(name for name, _ in CLICKHOUSE_CONFIG_SETTINGS),
        )
        items.extend(
            self._build_setting_items(
                settings_rows, CLICKHOUSE_CONFIG_SETTINGS, "system.settings", "readonly"
            )
        )

        server_rows = await self._rows(
            "SELECT name, value, description, default, changed, type, changeable_without_restart "
            "FROM system.server_settings WHERE name IN ("
            + self._placeholders(len(CLICKHOUSE_SERVER_SETTINGS), self._backend)
            + ")",
            tuple(name for name, _ in CLICKHOUSE_SERVER_SETTINGS),
        )
        items.extend(
            self._build_setting_items(
                server_rows,
                CLICKHOUSE_SERVER_SETTINGS,
                "system.server_settings",
                "changeable_without_restart",
            )
        )

        return self._filter_category(items, category)

    async def list_performance_metrics(self, category: Optional[StatusCategory] = None) -> List[StatusItem]:
        """List ClickHouse performance metrics.

        Three tables, because ClickHouse reports three different things:
        ``system.metrics`` holds instantaneous gauges, ``system.events`` holds
        monotonic counters since server start, and ``system.asynchronous_metrics``
        holds periodically sampled OS / disk figures.

        See the synchronous twin for why the set is version- and
        history-dependent.
        """
        items: List[StatusItem] = []

        gauge_rows = await self._rows(
            "SELECT metric, value, description FROM system.metrics WHERE metric IN ("
            + self._placeholders(len(CLICKHOUSE_GAUGE_METRICS), self._backend)
            + ")",
            tuple(name for name, _ in CLICKHOUSE_GAUGE_METRICS),
        )
        items.extend(self._build_gauge_items(gauge_rows, CLICKHOUSE_GAUGE_METRICS, "system.metrics"))

        event_rows = await self._rows(
            "SELECT event, value, description FROM system.events WHERE event IN ("
            + self._placeholders(len(CLICKHOUSE_COUNTER_EVENTS), self._backend)
            + ")",
            tuple(name for name, _ in CLICKHOUSE_COUNTER_EVENTS),
        )
        items.extend(self._build_event_items(event_rows, CLICKHOUSE_COUNTER_EVENTS, "system.events"))

        async_rows = await self._rows(
            "SELECT metric, value, description FROM system.asynchronous_metrics WHERE metric IN ("
            + self._placeholders(len(CLICKHOUSE_ASYNC_METRICS), self._backend)
            + ")",
            tuple(name for name, _ in CLICKHOUSE_ASYNC_METRICS),
        )
        items.extend(
            self._build_async_metric_items(async_rows, CLICKHOUSE_ASYNC_METRICS, "system.asynchronous_metrics")
        )

        return self._filter_category(items, category)

    async def get_connection_info(self) -> ConnectionInfo:
        """Get connection information from ``system.metrics`` / ``system.server_settings``.

        ``max_connections`` is a ``config.xml`` value, so it is read from
        ``system.server_settings``; a ``system.settings`` lookup for that name
        returns no row at all. ``active_count`` sums the five per-listener
        gauges in :data:`OPEN_CONNECTION_METRICS`, because ClickHouse has no
        single ``Threads_connected`` to report.
        """
        gauge_rows = await self._rows(
            "SELECT metric, value FROM system.metrics WHERE metric IN ("
            + self._placeholders(len(OPEN_CONNECTION_METRICS), self._backend)
            + ")",
            OPEN_CONNECTION_METRICS,
        )
        gauges = {row.get("metric"): row.get("value") for row in gauge_rows}

        server_rows = await self._rows(
            "SELECT name, value FROM system.server_settings "
            f"WHERE name = {self._backend.dialect.p()}",
            ("max_connections",),
        )
        max_connections = server_rows[0].get("value") if server_rows else None

        def _num(name: str) -> Optional[int]:
            value = self._parse_variable_value(gauges.get(name))
            return value if isinstance(value, int) else None

        active = [v for v in (_num(name) for name in OPEN_CONNECTION_METRICS) if v is not None]

        return ConnectionInfo(
            active_count=sum(active) if active else None,
            max_connections=self._parse_variable_value(max_connections),
            idle_count=None,
            extra={
                "http_connections": _num("HTTPConnection"),
                "tcp_connections": _num("TCPConnection"),
                "interserver_connections": _num("InterserverConnection"),
                "mysql_connections": _num("MySQLConnection"),
                "postgresql_connections": _num("PostgreSQLConnection"),
                "note": (
                    "ClickHouse reports one gauge per listener and no combined "
                    "'Threads_connected'; active_count is the sum of "
                    + ", ".join(OPEN_CONNECTION_METRICS)
                ),
            },
        )

    async def get_storage_info(self) -> StorageInfo:
        """Get storage information from ``system.tables`` / ``system.disks``."""
        total_size = None
        try:
            result = await self._backend.execute(
                "SELECT sum(total_bytes) AS total_size FROM system.tables "
                f"WHERE database = {self._backend.dialect.p()}",
                (self._backend.config.database,),
            )
            if result and result.data:
                total_size = result.data[0].get("total_size")
        except Exception:
            pass

        disks = await self._rows(
            "SELECT name, path, type, total_space, free_space, unreserved_space, keep_free_space, "
            "is_encrypted, is_read_only, is_remote, is_broken FROM system.disks"
        )
        default_disk = next((d for d in disks if d.get("name") == "default"), None)

        return StorageInfo(
            total_size_bytes=self._parse_variable_value(total_size),
            free_space_bytes=self._parse_variable_value(default_disk.get("free_space")) if default_disk else None,
            extra={
                "database": self._backend.config.database,
                "data_path": default_disk.get("path") if default_disk else None,
                "disks": disks,
            },
        )

    async def list_databases(self) -> List[DatabaseBriefInfo]:
        """List databases with table/view counts."""
        databases = []

        db_results = await self._show.databases()
        db_names = [db.name for db in db_results]

        # Get table and view counts for all databases from information_schema.
        # ClickHouse exposes both spellings of every information_schema column
        # (measured on 26.7.3.19: ``table_schema`` and ``TABLE_SCHEMA`` are both
        # returned), and its ``table_type`` uses the same ``BASE TABLE`` /
        # ``VIEW`` values MySQL does.
        table_counts: Dict[str, int] = {}
        view_counts: Dict[str, int] = {}

        try:
            placeholders = self._placeholders(len(db_names), self._backend)
            result = await self._backend.execute(
                "SELECT table_schema, table_type, COUNT(*) as count "
                "FROM information_schema.TABLES "
                f"WHERE table_schema IN ({placeholders}) "
                "GROUP BY table_schema, table_type",
                tuple(db_names),
            )
            if result and result.data:
                for row in result.data:
                    schema = row.get("table_schema") or row.get("TABLE_SCHEMA")
                    table_type = row.get("table_type") or row.get("TABLE_TYPE")
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
        """List users from ``system.users`` with their grants and roles.

        There is no ``clickhouse.user`` database on a stock server (measured on
        26.7.3.19: ``UNKNOWN_DATABASE``), so ``system.users`` is the source.
        It carries no superuser column, so ``is_superuser`` is derived from the
        account's grants against ``system.grants`` and the full set lands in
        ``extra['access_types']``.
        """
        users = []

        user_rows = await self._rows(
            "SELECT name, id, auth_type, default_database, host_ip, host_names FROM system.users"
        )
        if not user_rows:
            return users

        grant_rows = await self._rows(
            "SELECT user_name, access_type, database, table, grant_option FROM system.grants "
            "WHERE database IS NULL AND table IS NULL"
        )
        grants_by_user: Dict[str, List[str]] = {}
        for row in grant_rows:
            name = row.get("user_name")
            access_type = row.get("access_type")
            if name and access_type:
                grants_by_user.setdefault(name, []).append(str(access_type))

        role_rows = await self._rows("SELECT user_name, role_name, granted_role_is_default FROM system.role_grants")
        roles_by_user: Dict[str, List[str]] = {}
        for row in role_rows:
            name = row.get("user_name")
            role_name = row.get("role_name")
            if name and role_name:
                roles_by_user.setdefault(name, []).append(str(role_name))

        for row in user_rows:
            name = row.get("name")
            if not name:
                continue
            access_types = sorted(set(grants_by_user.get(name, [])))
            users.append(
                UserInfo(
                    name=name,
                    roles=sorted(set(roles_by_user.get(name, []))),
                    is_superuser=all(t in access_types for t in _SUPERUSER_ACCESS_TYPES),
                    extra={
                        "id": str(row.get("id")),
                        "auth_type": list(row.get("auth_type") or []),
                        "default_database": row.get("default_database") or None,
                        "host_ip": list(row.get("host_ip") or []),
                        "host_names": list(row.get("host_names") or []),
                        "access_types": access_types,
                        "superuser_test": list(_SUPERUSER_ACCESS_TYPES),
                    },
                )
            )

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

        # Check if password was used (connection was made with password)
        session.password_used = bool(self._backend.config.password)

        return session

    async def list_processes(self) -> List[ProcessInfo]:
        """List current running processes/queries via ``system.processes``."""
        processes = []
        rows = await self._rows(
            "SELECT query_id, user, address, current_database, elapsed, query "
            "FROM system.processes"
        )
        for row in rows:
            processes.append(
                ProcessInfo(
                    id=row.get("query_id"),
                    user=row.get("user"),
                    host=str(row.get("address") or "") or None,
                    # ClickHouse spells this ``current_database``; MySQL's
                    # ``currentDatabase`` is not a column here.
                    database=row.get("current_database"),
                    command="QUERY",
                    time=row.get("elapsed"),
                    state=None,
                    info=row.get("query"),
                )
            )
        return processes
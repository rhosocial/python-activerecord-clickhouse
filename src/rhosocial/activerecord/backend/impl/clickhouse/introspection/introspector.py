# src/rhosocial/activerecord/backend/impl/clickhouse/introspection/introspector.py
"""
ClickHouse concrete introspectors.

Implements SyncAbstractIntrospector and AsyncAbstractIntrospector for ClickHouse
databases using the ClickHouse system.* tables for metadata queries.

The introspectors are exposed via ``backend.introspector`` and also provide
ClickHouse-specific access through ``backend.introspector.show``.

Architecture:
  - SQL generation: Delegated to ClickHouseIntrospectionMixin.format_*_query()
    methods in the Dialect layer via Expression.to_sql()
  - Query execution: Handled by IntrospectorExecutor
  - Result parsing: parse_* methods in this module (pure Python, no I/O)

Key behaviours:
  - Queries ClickHouse system.* tables (system.tables, system.columns,
    system.databases, system.parts, system.triggers, etc.)
  - parse_* methods are pure Python — shared by sync and async introspectors

Design principle: Sync and Async are separate and cannot coexist.
- SyncClickHouseIntrospector: for synchronous backends
- AsyncClickHouseIntrospector: for asynchronous backends
"""

import copy
from typing import Any, Dict, List, Optional

from rhosocial.activerecord.backend.introspection.base import (
    IntrospectorMixin,
    SyncAbstractIntrospector,
    AsyncAbstractIntrospector,
)
from rhosocial.activerecord.backend.introspection.cache import IntrospectionCache
from rhosocial.activerecord.backend.introspection.executor import (
    SyncIntrospectorExecutor,
    AsyncIntrospectorExecutor,
)
from rhosocial.activerecord.backend.introspection.types import (
    IntrospectionDatabaseInfo,
    IntrospectionTableInfo,
    TableType,
    IntrospectionColumnInfo,
    ColumnNullable,
    IndexInfo,
    IndexColumnInfo,
    IndexType,
    IntrospectionForeignKeyInfo,
    ReferentialAction,
    IntrospectionViewInfo,
    IntrospectionTriggerInfo,
    IntrospectionScope,
)
from rhosocial.activerecord.backend.expression.types import DataType
from .show_introspector import (
    SyncShowIntrospector,
    AsyncShowIntrospector,
)
from .status_introspector import (
    SyncClickHouseStatusIntrospector,
    AsyncClickHouseStatusIntrospector,
)
from .types import (
    ClickHousePartitionInfo,
    ClickHouseTableEngineInfo,
)
from ..expression.introspection import (
    ClickHouseTableEngineQuery,
    ClickHouseTablePartitionsQuery,
)


class ClickHouseIntrospectorMixin(IntrospectorMixin):
    """Mixin providing shared ClickHouse-specific introspection logic.

    Both SyncClickHouseIntrospector and AsyncClickHouseIntrospector inherit
    from this mixin to share:
    - Default schema handling
    - ClickHouse version detection
    - parse_* implementations

    SQL generation is delegated to the Dialect layer via Expression.to_sql()
    which calls ClickHouseIntrospectionMixin.format_*_query() methods.
    """

    @property
    def default_schema(self) -> str:
        """Return the ClickHouse database name from the backend config."""
        if hasattr(self._backend, "config") and hasattr(self._backend.config, "database"):
            return self._backend.config.database or ""
        return ""

    # ------------------------------------------------------------------ #
    # Parse methods — pure Python, no I/O
    # ------------------------------------------------------------------ #

    def parse_database_info(self, rows: List[Dict[str, Any]]) -> IntrospectionDatabaseInfo:
        """Report what ``system.databases`` answers, and nothing it does not.

        The version comes from :attr:`server_version`, which reads the adapted
        dialect and the backend's cache without I/O and never raises. When
        nothing knows it yet the convention is ``version="unknown"`` with
        ``version_tuple=(0, 0, 0)``: ``0.0.0`` is not a ClickHouse release, so
        reporting it as a version would be a claim the server never made.

        A ClickHouse database has no character set and no collation, so
        ``encoding`` / ``collation`` stay ``None``. The storage engine the row
        does answer is kept in ``extra``.
        """
        db_row = rows[0] if rows else {}
        version = self.server_version
        if version is None:
            version_str = "unknown"
            version_tuple = (0, 0, 0)
        else:
            version_str = ".".join(str(part) for part in version)
            version_tuple = version

        engine = db_row.get("ENGINE")
        extra: Dict[str, Any] = {}
        if engine:
            extra["engine"] = engine

        return IntrospectionDatabaseInfo(
            name=db_row.get("DATABASE_NAME") or self.default_schema,
            version=version_str,
            version_tuple=version_tuple,
            vendor="ClickHouse",
            encoding=None,
            collation=None,
            extra=extra,
        )

    def parse_tables(self, rows: List[Dict[str, Any]], schema: Optional[str]) -> List[IntrospectionTableInfo]:
        """Read the kind of each relation from the engine that stores it.

        ``system.tables`` has no table-type column: what it reports is the
        storage engine. The dialect owns the closed set of view engines, so the
        kind is asked of :meth:`engine_kind` — the same declaration the table
        and view queries filter on — rather than matched against strings here.
        Rows read from the ``system`` database are system tables whatever their
        engine. The engine itself is kept in ``extra``: it is the fact the
        catalogue did answer, and the kind does not replace it.
        """
        target_db = schema if schema is not None else self.default_schema
        tables = []
        for row in rows:
            row_db = row.get("database") or target_db
            engine = row.get("ENGINE") or ""
            kind = TableType.SYSTEM_TABLE if row_db == "system" else self.dialect.engine_kind(engine)
            extra: Dict[str, Any] = {"engine": engine} if engine else {}
            tables.append(
                IntrospectionTableInfo(
                    name=row["TABLE_NAME"],
                    schema=target_db,
                    table_type=kind,
                    comment=row.get("TABLE_COMMENT"),
                    row_count=row.get("TABLE_ROWS"),
                    size_bytes=row.get("DATA_LENGTH"),
                    auto_increment=None,  # ClickHouse has no AUTO_INCREMENT
                    create_time=str(row["CREATE_TIME"]) if row.get("CREATE_TIME") else None,
                    update_time=str(row["UPDATE_TIME"]) if row.get("UPDATE_TIME") else None,
                    extra=extra,
                )
            )
        return tables

    def parse_columns(
        self,
        rows: List[Dict[str, Any]],
        table: str,
        schema: str,
    ) -> List[IntrospectionColumnInfo]:
        columns = []
        for row in rows:
            nullable = ColumnNullable.NULLABLE if row.get("IS_NULLABLE") == "YES" else ColumnNullable.NOT_NULL
            col_type = row.get("COLUMN_TYPE") or row.get("DATA_TYPE") or "VARCHAR"
            parsed = DataType.parse_data_type_str(self._backend.dialect, col_type)
            columns.append(
                IntrospectionColumnInfo(
                    name=row["COLUMN_NAME"],
                    table_name=table,
                    schema=schema,
                    ordinal_position=row["ORDINAL_POSITION"],
                    data_type=col_type.split("(")[0].lower(),
                    data_type_full=col_type,
                    parsed_data_type=parsed,
                    nullable=nullable,
                    default_value=row.get("COLUMN_DEFAULT"),
                    is_primary_key=row.get("COLUMN_KEY") == "PRI",
                    is_unique=row.get("COLUMN_KEY") == "UNI",
                    is_auto_increment="auto_increment" in (row.get("EXTRA") or "").lower(),
                    comment=row.get("COLUMN_COMMENT"),
                    character_maximum_length=row.get("CHARACTER_MAXIMUM_LENGTH"),
                    numeric_precision=row.get("NUMERIC_PRECISION"),
                    numeric_scale=row.get("NUMERIC_SCALE"),
                    charset=row.get("CHARACTER_SET_NAME"),
                    collation=row.get("COLLATION_NAME"),
                )
            )
        return columns

    def parse_indexes(
        self,
        rows: List[Dict[str, Any]],
        table: str,
        schema: str,
    ) -> List[IndexInfo]:
        index_type_map = {
            "BTREE": IndexType.BTREE,
            "HASH": IndexType.HASH,
            "FULLTEXT": IndexType.FULLTEXT,
            "SPATIAL": IndexType.SPATIAL,
            "RTREE": IndexType.SPATIAL,
        }
        index_map: Dict[str, IndexInfo] = {}
        for row in rows:
            idx_name = row.get("INDEX_NAME") or row.get("Key_name", "")
            if idx_name not in index_map:
                idx_type_str = (row.get("INDEX_TYPE") or "BTREE").upper()
                index_map[idx_name] = IndexInfo(
                    name=idx_name,
                    table_name=table,
                    schema=schema,
                    is_unique=int(row.get("NON_UNIQUE", row.get("Non_unique", 1))) == 0,
                    is_primary=idx_name == "PRIMARY",
                    index_type=index_type_map.get(idx_type_str, IndexType.BTREE),
                    columns=[],
                )
            index_map[idx_name].columns.append(
                IndexColumnInfo(
                    name=row.get("COLUMN_NAME") or row.get("Column_name", ""),
                    ordinal_position=int(row.get("SEQ_IN_INDEX") or row.get("Seq_in_index", 1)),
                    is_descending=False,
                )
            )
        return list(index_map.values())

    def parse_foreign_keys(
        self,
        rows: List[Dict[str, Any]],
        table: str,
        schema: str,
    ) -> List[IntrospectionForeignKeyInfo]:
        action_map = {
            "NO_ACTION": ReferentialAction.NO_ACTION,
            "NO ACTION": ReferentialAction.NO_ACTION,
            "RESTRICT": ReferentialAction.RESTRICT,
            "CASCADE": ReferentialAction.CASCADE,
            "SET_NULL": ReferentialAction.SET_NULL,
            "SET NULL": ReferentialAction.SET_NULL,
            "SET_DEFAULT": ReferentialAction.SET_DEFAULT,
            "SET DEFAULT": ReferentialAction.SET_DEFAULT,
        }
        fk_map: Dict[str, IntrospectionForeignKeyInfo] = {}
        for row in rows:
            fk_name = row.get("CONSTRAINT_NAME", "")
            if fk_name not in fk_map:
                on_update_raw = (row.get("UPDATE_RULE") or "NO ACTION").upper()
                on_delete_raw = (row.get("DELETE_RULE") or "NO ACTION").upper()
                fk_map[fk_name] = IntrospectionForeignKeyInfo(
                    name=fk_name,
                    table_name=table,
                    schema=schema,
                    referenced_table=row.get("REFERENCED_TABLE_NAME", ""),
                    on_update=action_map.get(on_update_raw, ReferentialAction.NO_ACTION),
                    on_delete=action_map.get(on_delete_raw, ReferentialAction.NO_ACTION),
                    columns=[],
                    referenced_columns=[],
                )
            fk_map[fk_name].columns.append(row.get("COLUMN_NAME", ""))
            fk_map[fk_name].referenced_columns.append(row.get("REFERENCED_COLUMN_NAME", ""))
        return list(fk_map.values())

    def parse_views(self, rows: List[Dict[str, Any]], schema: str) -> List[IntrospectionViewInfo]:
        return [
            IntrospectionViewInfo(
                name=row.get("TABLE_NAME", row.get("VIEW_NAME", "")),
                schema=schema,
                definition=row.get("VIEW_DEFINITION"),
                check_option=row.get("CHECK_OPTION"),
                is_updatable=row.get("IS_UPDATABLE") == "YES",
            )
            for row in rows
        ]

    def parse_view_info(
        self,
        rows: List[Dict[str, Any]],
        view_name: str,
        schema: str,
    ) -> Optional[IntrospectionViewInfo]:
        if not rows:
            return None
        row = rows[0]
        return IntrospectionViewInfo(
            name=row.get("TABLE_NAME", row.get("VIEW_NAME", view_name)),
            schema=schema,
            definition=row.get("VIEW_DEFINITION"),
            check_option=row.get("CHECK_OPTION"),
            is_updatable=row.get("IS_UPDATABLE") == "YES",
        )

    def parse_triggers(self, rows: List[Dict[str, Any]], schema: str) -> List[IntrospectionTriggerInfo]:
        return [
            IntrospectionTriggerInfo(
                name=row.get("TRIGGER_NAME", ""),
                table_name=row.get("EVENT_OBJECT_TABLE", ""),
                schema=schema,
                timing=row.get("ACTION_TIMING"),
                events=[row["EVENT_MANIPULATION"]] if row.get("EVENT_MANIPULATION") else [],
                definition=row.get("ACTION_STATEMENT"),
            )
            for row in rows
        ]

    def parse_partitions(
        self,
        rows: List[Dict[str, Any]],
        table: str,
        database: str,
    ) -> List[ClickHousePartitionInfo]:
        """Parse the grouped ``system.parts`` rows into partition records.

        The aggregate aliases are the dataclass field names, so each row is read
        by name and nothing is inferred from a position. ``int(... or 0)`` covers
        the empty group a server never returns but a projection alias could still
        report as ``NULL``: a sum over an empty set is ``NULL`` in SQL, so the
        fallback states "no rows" rather than raising on the conversion.
        """
        return [
            ClickHousePartitionInfo(
                partition_id=row.get("partition_id", ""),
                table_name=table,
                database=database,
                engine=row.get("engine") or "",
                partition=row.get("partition"),
                row_count=int(row.get("row_count") or 0),
                bytes_on_disk=int(row.get("bytes_on_disk") or 0),
                active_part_count=int(row.get("active_part_count") or 0),
                min_modification_time=row.get("min_modification_time"),
                max_modification_time=row.get("max_modification_time"),
            )
            for row in rows
        ]

    def parse_table_engine(
        self,
        rows: List[Dict[str, Any]],
        table: str,
        database: str,
    ) -> Optional[ClickHouseTableEngineInfo]:
        """Parse the single ``system.tables`` row, or ``None`` when there is none.

        ``total_rows`` / ``total_bytes`` are ``Nullable(UInt64)`` and are empty
        for engines that do not track them; they stay ``None`` rather than being
        reported as ``0``, which would be a claim the server did not make.
        """
        if not rows:
            return None
        row = rows[0]

        def _number(value: Any) -> Optional[int]:
            return None if value is None else int(value)

        return ClickHouseTableEngineInfo(
            table_name=table,
            database=database,
            engine=row.get("engine") or "",
            sorting_key=row.get("sorting_key"),
            primary_key=row.get("primary_key"),
            partition_key=row.get("partition_key"),
            sampling_key=row.get("sampling_key"),
            total_rows=_number(row.get("total_rows")),
            total_bytes=_number(row.get("total_bytes")),
            comment=row.get("comment"),
        )


class SyncClickHouseIntrospector(ClickHouseIntrospectorMixin, SyncAbstractIntrospector):
    """Synchronous introspector for ClickHouse backends.

    In addition to the standard SyncAbstractIntrospector interface, exposes the
    ``.show`` sub-introspector for direct SHOW command access::

        # Standard API
        tables = backend.introspector.list_tables()

        # ClickHouse-specific
        create_sql = backend.introspector.show.create_table("users")
        variables  = backend.introspector.show.variables(like="max_%")
    """

    def __init__(
        self,
        backend: Any,
        executor: SyncIntrospectorExecutor,
        cache: Optional[IntrospectionCache] = None,
    ) -> None:
        super().__init__(backend, executor, cache)
        self._show_instance: Optional[SyncShowIntrospector] = None
        self._status_instance: Optional[SyncClickHouseStatusIntrospector] = None

    @property
    def show(self) -> SyncShowIntrospector:
        """ClickHouse-specific SHOW sub-introspector (lazily created)."""
        if self._show_instance is None:
            self._show_instance = SyncShowIntrospector(self._backend, self._executor)
        return self._show_instance

    @property
    def status(self) -> SyncClickHouseStatusIntrospector:
        """ClickHouse status introspector (lazily created)."""
        if self._status_instance is None:
            self._status_instance = SyncClickHouseStatusIntrospector(self._backend)
        return self._status_instance

    # ------------------------------------------------------------------ #
    # get_table_info override
    # ------------------------------------------------------------------ #

    def get_table_info(self, table: str, schema: Optional[str] = None) -> Optional[IntrospectionTableInfo]:
        key = self._cache.key(IntrospectionScope.TABLE, table, schema=schema)
        cached = self._cache.get(key)
        if cached is not None:
            return cached

        tables = self.list_tables(schema)
        found = next((t for t in tables if t.name == table), None)
        if found is None:
            return None

        info = copy.copy(found)
        info.columns = self.list_columns(table, schema)
        info.indexes = self.list_indexes(table, schema)
        # ClickHouse has no foreign keys; keep the default empty list.
        info.foreign_keys = []
        self._cache.set(key, info)
        return info

    # ------------------------------------------------------------------ #
    # ClickHouse-specific reads
    # ------------------------------------------------------------------ #

    def list_partitions(
        self,
        table_name: str,
        database: Optional[str] = None,
    ) -> List[ClickHousePartitionInfo]:
        """List a table's partitions, aggregated from its active parts.

        ClickHouse calls its top-level namespace a *database*; this backend has
        no schema layer, so ``database`` is that parameter and ``None`` means the
        connected database. The name is not translated into anything: it is the
        same string ``system.parts.database`` holds.

        The result is cached under ``IntrospectionScope.TABLE`` with
        ``extra="partition"`` — the table scope because a partition belongs to a
        table, and the extra namespace because the same table also answers
        column, index and engine questions and must not answer this one.

        Args:
            table_name: The table to read.
            database: ClickHouse database; defaults to the connected database.

        Returns:
            One :class:`ClickHousePartitionInfo` per ``partition_id``, ordered
            by that id. A table with no parts (empty, or an engine that has none)
            returns an empty list — the server has nothing to report, so nothing
            is invented.
        """
        target = database if database is not None else self.default_schema
        key = self._cache.key(IntrospectionScope.TABLE, table_name, schema=target, extra="partition")
        cached = self._cache.get(key)
        if cached is not None:
            return cached
        sql, params = ClickHouseTablePartitionsQuery(self._backend.dialect, target, table_name).to_sql()
        result = self.parse_partitions(self._executor.execute(sql, params), table_name, target)
        self._cache.set(key, result)
        return result

    def get_table_engine(
        self,
        table_name: str,
        database: Optional[str] = None,
    ) -> Optional[ClickHouseTableEngineInfo]:
        """Read a table's engine and key expressions from ``system.tables``.

        ``database`` follows the same rule as :meth:`list_partitions`: it is a
        ClickHouse database name, and ``None`` means the connected database.

        Cached under ``IntrospectionScope.TABLE`` with ``extra="engine"``. A
        missing table is **not** cached: the cache's ``get`` uses ``None`` for
        "no entry", so caching ``None`` could not be distinguished from a miss
        anyway, and the next call re-asks the server.

        Args:
            table_name: The table to read.
            database: ClickHouse database; defaults to the connected database.

        Returns:
            The table's :class:`ClickHouseTableEngineInfo`, or ``None`` if the
            server has no such table.
        """
        target = database if database is not None else self.default_schema
        key = self._cache.key(IntrospectionScope.TABLE, table_name, schema=target, extra="engine")
        cached = self._cache.get(key)
        if cached is not None:
            return cached
        sql, params = ClickHouseTableEngineQuery(self._backend.dialect, target, table_name).to_sql()
        result = self.parse_table_engine(self._executor.execute(sql, params), table_name, target)
        if result is not None:
            self._cache.set(key, result)
        return result


class AsyncClickHouseIntrospector(ClickHouseIntrospectorMixin, AsyncAbstractIntrospector):
    """Asynchronous introspector for ClickHouse backends.

    In addition to the standard AsyncAbstractIntrospector interface, exposes the
    ``.show`` sub-introspector for direct SHOW command access::

        # Standard API
        tables = await backend.introspector.list_tables()

        # ClickHouse-specific
        create_sql = await backend.introspector.show.create_table("users")
        variables  = await backend.introspector.show.variables(like="max_%")
    """

    def __init__(
        self,
        backend: Any,
        executor: AsyncIntrospectorExecutor,
        cache: Optional[IntrospectionCache] = None,
    ) -> None:
        super().__init__(backend, executor, cache)
        self._show_instance: Optional[AsyncShowIntrospector] = None
        self._status_instance: Optional[AsyncClickHouseStatusIntrospector] = None

    @property
    def show(self) -> AsyncShowIntrospector:
        """ClickHouse-specific SHOW sub-introspector (lazily created)."""
        if self._show_instance is None:
            self._show_instance = AsyncShowIntrospector(self._backend, self._executor)
        return self._show_instance

    @property
    def status(self) -> AsyncClickHouseStatusIntrospector:
        """ClickHouse status introspector (lazily created)."""
        if self._status_instance is None:
            self._status_instance = AsyncClickHouseStatusIntrospector(self._backend)
        return self._status_instance

    # ------------------------------------------------------------------ #
    # get_table_info override
    # ------------------------------------------------------------------ #

    async def get_table_info(self, table: str, schema: Optional[str] = None) -> Optional[IntrospectionTableInfo]:
        key = self._cache.key(IntrospectionScope.TABLE, table, schema=schema)
        cached = self._cache.get(key)
        if cached is not None:
            return cached

        tables = await self.list_tables(schema)
        found = next((t for t in tables if t.name == table), None)
        if found is None:
            return None

        info = copy.copy(found)
        info.columns = await self.list_columns(table, schema)
        info.indexes = await self.list_indexes(table, schema)
        info.foreign_keys = await self.list_foreign_keys(table, schema)
        self._cache.set(key, info)
        return info

    # ------------------------------------------------------------------ #
    # ClickHouse-specific reads
    # ------------------------------------------------------------------ #

    async def list_partitions(
        self,
        table_name: str,
        database: Optional[str] = None,
    ) -> List[ClickHousePartitionInfo]:
        """List a table's partitions, aggregated from its active parts.

        The asynchronous counterpart of the synchronous method: same parameters,
        same result, same cache key. See
        :meth:`SyncClickHouseIntrospector.list_partitions` for the naming rule
        (``database`` is ClickHouse's own top-level namespace) and the scope.
        """
        target = database if database is not None else self.default_schema
        key = self._cache.key(IntrospectionScope.TABLE, table_name, schema=target, extra="partition")
        cached = self._cache.get(key)
        if cached is not None:
            return cached
        sql, params = ClickHouseTablePartitionsQuery(self._backend.dialect, target, table_name).to_sql()
        result = self.parse_partitions(await self._executor.execute(sql, params), table_name, target)
        self._cache.set(key, result)
        return result

    async def get_table_engine(
        self,
        table_name: str,
        database: Optional[str] = None,
    ) -> Optional[ClickHouseTableEngineInfo]:
        """Read a table's engine and key expressions from ``system.tables``.

        The asynchronous counterpart of the synchronous method: same parameters,
        same result, same cache key and the same "missing table is not cached"
        rule.
        """
        target = database if database is not None else self.default_schema
        key = self._cache.key(IntrospectionScope.TABLE, table_name, schema=target, extra="engine")
        cached = self._cache.get(key)
        if cached is not None:
            return cached
        sql, params = ClickHouseTableEngineQuery(self._backend.dialect, target, table_name).to_sql()
        result = self.parse_table_engine(await self._executor.execute(sql, params), table_name, target)
        if result is not None:
            self._cache.set(key, result)
        return result

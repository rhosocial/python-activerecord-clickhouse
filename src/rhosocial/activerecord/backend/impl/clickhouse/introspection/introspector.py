# src/rhosocial/activerecord/backend/impl/clickhouse/introspection/introspector.py
"""
ClickHouse concrete introspectors.

Implements AbstractIntrospector and AsyncAbstractIntrospector for ClickHouse
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
- ClickHouseIntrospector: for synchronous backends
- AsyncClickHouseIntrospector: for asynchronous backends
"""

import copy
from typing import Any, Dict, List, Optional

from rhosocial.activerecord.backend.introspection.base import (
    AbstractIntrospector,
    AsyncAbstractIntrospector,
    IntrospectorMixin,
)
from rhosocial.activerecord.backend.introspection.cache import IntrospectionCache
from rhosocial.activerecord.backend.introspection.executor import (
    AsyncIntrospectorExecutor,
    IntrospectorExecutor,
)
from rhosocial.activerecord.backend.introspection.types import (
    ColumnNullable,
    ConstraintState,
    DerivedObjectState,
    IndexColumnInfo,
    IndexInfo,
    IndexState,
    IndexType,
    IntrospectionColumnInfo,
    IntrospectionDatabaseInfo,
    IntrospectionForeignKeyInfo,
    IntrospectionScope,
    IntrospectionTableInfo,
    IntrospectionTriggerInfo,
    IntrospectionViewInfo,
    ItemKind,
    PartitionBound,
    PartitionScheme,
    PartitionState,
    ReferentialAction,
    StorageOptionsState,
    TableState,
    TableType,
)

from .type_parser import ClickHouseTypeParser
from ..expression.introspection import (
    ClickHouseClusterListQuery,
    ClickHouseConstraintStateListQuery,
    ClickHouseDictionaryListQuery,
    ClickHouseFunctionListQuery,
    ClickHouseIndexStateListQuery,
    ClickHouseMaterializedViewListQuery,
    ClickHouseProjectionListQuery,
    ClickHouseQuotaListQuery,
    ClickHouseRoleListQuery,
    ClickHouseSchemaListQuery,
    ClickHouseTableEngineQuery,
    ClickHouseTablePartitionsQuery,
    ClickHouseIntrospectionUserListQuery,
)
from .show_introspector import (
    AsyncShowIntrospector,
    ShowIntrospector,
)
from .status_introspector import (
    AsyncClickHouseStatusIntrospector,
    ClickHouseStatusIntrospector,
)
from .types import (
    ClickHouseClusterInfo,
    ClickHouseDictionaryInfo,
    ClickHouseFunctionInfo,
    ClickHousePartitionInfo,
    ClickHouseQuotaInfo,
    ClickHouseRoleInfo,
    ClickHouseTableEngineInfo,
    ClickHouseUserInfo,
)


def _string_list(value: Any) -> List[str]:
    """A catalogue array as a list of strings, without inventing members.

    ClickHouse arrays arrive as lists or tuples from the driver; a bare
    string is what a one-element array can look like when a projection came
    back through a client that unwraps it, so it is treated as that one
    member. ``None`` is the empty list: the column is an array on every row,
    and an absent value means the server had nothing to list.
    """
    if value is None:
        return []
    if isinstance(value, str):
        return [value]
    return [str(getattr(item, "value", item)) for item in value]


def _int_list(value: Any) -> List[int]:
    """A catalogue integer array as a list of ints.

    The same shape rule as :func:`_string_list`, with the conversion the
    field's declared type needs. A driver that hands back strings for an
    integer array is tolerated because the value is still the member the
    server reported.
    """
    if value is None:
        return []
    if isinstance(value, (str, bytes)):
        return [int(value)]
    return [int(item) for item in value]


def _optional_int(value: Any) -> Optional[int]:
    """``None`` stays ``None``; anything else is converted with ``int``."""
    return None if value is None else int(value)


def _optional_bool(value: Any) -> Optional[bool]:
    """``None`` stays ``None``; a catalogue ``UInt8`` becomes a boolean."""
    return None if value is None else bool(value)


def _bool(value: Any) -> bool:
    """A non-nullable catalogue ``UInt8`` flag as a boolean."""
    return bool(value)


def _optional_text(value: Any) -> Optional[str]:
    """An empty catalogue string as ``None``, and an enum as its value.

    ClickHouse reports ``''`` rather than ``NULL`` for a text column with no
    value, so the empty string is the server saying "nothing to report".
    Turning it into ``None`` keeps that distinct from a genuinely empty
    answer; passing ``''`` through would look like a value. A driver that
    hands back the enum member rather than its string value is unwrapped so
    the record's type stays ``Optional[str]``.
    """
    if not value:
        return None
    return str(getattr(value, "value", value))


def _ttl_from_engine_full(engine_full: Optional[str]) -> Optional[str]:
    """The table-level ``TTL`` clause out of ``system.tables.engine_full``.

    ``system.tables`` has no ``ttl`` column: the expression is part of the
    storage clause the server normalizes, where it follows ``ORDER BY`` and
    precedes ``SETTINGS``. Reading it from there is a split on two fixed words
    rather than a parse of the clause grammar -- this backend needs the text
    for a caller to inspect, not to evaluate, and a TTL expression can contain
    arbitrary SQL that no local parser should claim to understand.

    ``None`` when the clause is absent, which the server spells as the empty
    string or as an engine definition with no ``TTL`` between its clauses.
    """
    if not engine_full:
        return None
    marker = " TTL "
    if marker not in engine_full:
        return None
    tail = engine_full.split(marker, 1)[1]
    for terminator in (" SETTINGS ", " SAMPLE BY ", " PRIMARY KEY ", " ORDER BY "):
        if terminator in tail:
            tail = tail.split(terminator, 1)[0]
            break
    return tail.strip() or None


def _runtime_type_names(value: Any) -> List[str]:
    """The type names out of the array ``groupUniqArray(toTypeName(...))`` returned.

    Sorted here rather than in SQL: the aggregate's own order is not defined,
    and a profile is read as a set, so two runs of the same query must compare
    equal. A driver that hands the array back as a list and one that hands back
    a tuple both work; a bare string is treated as the single-entry set it is,
    which is what makes a one-type column read the same either way.

    ``None`` is an empty list, not a missing slot: the array exists on every row
    the statement returns, so ``None`` can only mean the column produced no
    values -- an empty table -- and there is no type to name.
    """
    if value is None:
        return []
    if isinstance(value, str):
        return [value]
    return sorted(str(name) for name in value)


class ClickHouseIntrospectorMixin(IntrospectorMixin):
    """Mixin providing shared ClickHouse-specific introspection logic.

    Both ClickHouseIntrospector and AsyncClickHouseIntrospector inherit
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

    def _catalog_key(self, family: str, *parts: str) -> str:
        """A cache key for a server-wide catalogue family.

        ``IntrospectionScope`` has no member for a function, dictionary, cluster,
        quota, user or role, and core is not the place to add one in this
        round. The families still share the ``DATABASE`` scope because they
        describe the server rather than one table, and each passes its own
        family name as ``extra`` so one catalogue cannot answer another's
        question.
        """
        from rhosocial.activerecord.backend.introspection.types import (
            IntrospectionScope,
        )

        return self._cache.key(IntrospectionScope.DATABASE, *parts, schema=None, extra=family)

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

    def parse_tables(
        self, rows: List[Dict[str, Any]], schema: Optional[str]
    ) -> List[IntrospectionTableInfo]:
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
            kind = (
                TableType.SYSTEM_TABLE if row_db == "system" else self.dialect.engine_kind(engine)
            )
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
            nullable = (
                ColumnNullable.NULLABLE
                if row.get("IS_NULLABLE") == "YES"
                else ColumnNullable.NOT_NULL
            )
            col_type = row.get("COLUMN_TYPE") or row.get("DATA_TYPE") or "VARCHAR"
            parsed = ClickHouseTypeParser(self._backend.dialect).parse(col_type)
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

    def parse_triggers(
        self, rows: List[Dict[str, Any]], schema: str
    ) -> List[IntrospectionTriggerInfo]:
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

        engine = row.get("engine") or ""
        engine_full = _optional_text(row.get("engine_full"))

        return ClickHouseTableEngineInfo(
            table_name=table,
            database=database,
            engine=engine,
            sorting_key=row.get("sorting_key"),
            primary_key=row.get("primary_key"),
            partition_key=row.get("partition_key"),
            sampling_key=row.get("sampling_key"),
            total_rows=_number(row.get("total_rows")),
            total_bytes=_number(row.get("total_bytes")),
            comment=row.get("comment"),
            engine_full=engine_full,
            ttl=_ttl_from_engine_full(engine_full),
            is_temporary=_bool(row.get("is_temporary")),
            storage_policy=_optional_text(row.get("storage_policy")),
        )

    def parse_schema_names(self, rows: List[Dict[str, Any]]) -> List[str]:
        """Read the database names out of ``system.databases``."""
        return [str(row["name"]) for row in rows if row.get("name")]

    def parse_index_states(
        self,
        rows: List[Dict[str, Any]],
        table: str,
        schema: str,
    ) -> List[IndexState]:
        """Project ``system.data_skipping_indices`` rows onto ``IndexState``.

        ClickHouse has no unique, invalid or invisible index state: every
        data-skipping index it reports is usable and visible, and uniqueness is
        not a property it enforces. Those slots therefore carry the engine's
        constant answer rather than a guess, and the engine's own figures
        (``type_full``, ``granularity`` and the byte counters) stay in ``raw``.
        """
        found: List[IndexState] = []
        for row in rows:
            name = row.get("name")
            if not name:
                continue
            found.append(
                IndexState(
                    name=str(name),
                    table=table,
                    schema=schema,
                    unique=False,
                    method=_optional_text(row.get("type")),
                    predicate=_optional_text(row.get("expr")),
                    visible=True,
                    usable=True,
                    backs_constraint=None,
                    raw={
                        key: value
                        for key, value in row.items()
                        if key not in {"name", "type", "expr"} and value is not None
                    },
                )
            )
        return found

    def parse_constraint_states(
        self,
        rows: List[Dict[str, Any]],
        table: str,
        schema: str,
    ) -> List[ConstraintState]:
        """Project ``system.constraints`` rows onto ``ConstraintState``.

        The catalogue table exists only on some release lines, and
        :meth:`format_clickhouse_constraint_state_list_query` refuses the
        statement on the lines that lack it. This parser only sees rows from a
        server that has the table, so an empty list here is the real answer
        "the table declares no constraints", not "the catalogue was missing".

        The engine reports two kinds: ``CHECK`` is enforced when rows are
        inserted, while ``ASSUME`` is an optimizer assumption that is never
        validated. There are no per-constraint validation flags, so
        ``validated`` is true for both and ``enforced`` follows the kind. The
        expression is the engine's own text and belongs in ``raw``, because it
        is not one of the neutral slots.
        """
        found: List[ConstraintState] = []
        for row in rows:
            name = row.get("name")
            if not name:
                continue
            kind = _optional_text(row.get("type")) or ""
            expression = _optional_text(row.get("expression"))
            raw: Dict[str, Any] = {}
            if expression is not None:
                raw["expression"] = expression
            found.append(
                ConstraintState(
                    name=str(name),
                    table=table,
                    kind=kind,
                    schema=schema,
                    validated=True,
                    enforced=kind != "ASSUME",
                    deferred=False,
                    disabled=False,
                    backing_index=None,
                    raw=raw,
                )
            )
        return found

    def parse_projection_states(
        self,
        rows: List[Dict[str, Any]],
        table: str,
    ) -> List[DerivedObjectState]:
        """Project ``system.projections`` rows onto ``DerivedObjectState``."""
        found: List[DerivedObjectState] = []
        for row in rows:
            name = row.get("name")
            if not name:
                continue
            found.append(
                DerivedObjectState(
                    kind="projection",
                    name=str(name),
                    owned_by=table,
                    raw={
                        key: value
                        for key, value in row.items()
                        if key != "name" and value is not None
                    },
                )
            )
        return found

    def parse_materialized_view_states(
        self,
        rows: List[Dict[str, Any]],
        table: str,
        database: str,
    ) -> List[DerivedObjectState]:
        """Project materialized views that read from *table*.

        The catalogue reports no source dependency for this engine (the
        dependency arrays are empty even for a view over a MergeTree), so the
        association is read from two facts the catalogue does answer: the
        declared ``dependencies_table`` when the server has it, and the
        qualified table name inside ``as_select``, which ClickHouse normalizes
        to ``database.table``. A view whose definition names the table anywhere
        is reported under it; the caller asked which views consume this table,
        not for a SQL parse.
        """
        found: List[DerivedObjectState] = []
        qualified = f"{database}.{table}"
        for row in rows:
            name = row.get("name")
            if not name:
                continue
            dependencies = _string_list(row.get("dependencies_table"))
            definition = row.get("as_select") or ""
            if table not in dependencies and qualified not in definition:
                continue
            found.append(
                DerivedObjectState(
                    kind="materialized_view",
                    name=str(name),
                    owned_by=table,
                    raw={
                        "database": row.get("database") or database,
                        "as_select": definition or None,
                        "target_table": row.get("target_table") or None,
                    },
                )
            )
        return found

    def parse_functions(self, rows: List[Dict[str, Any]]) -> List[ClickHouseFunctionInfo]:
        """Read ``system.functions`` rows into function records.

        The aliases are the field names, so each row is read by name and
        nothing is inferred from a position. The two flags are ``UInt8`` on
        the server; the text columns use the empty-string convention, which
        is reported as ``None``.
        """
        return [
            ClickHouseFunctionInfo(
                name=row.get("name", ""),
                is_aggregate=_bool(row.get("is_aggregate")),
                case_insensitive=_bool(row.get("case_insensitive")),
                alias_to=_optional_text(row.get("alias_to")),
                origin=_optional_text(row.get("origin")),
                description=_optional_text(row.get("description")),
                syntax=_optional_text(row.get("syntax")),
                arguments=_optional_text(row.get("arguments")),
                categories=_optional_text(row.get("categories")),
            )
            for row in rows
        ]

    def parse_dictionaries(
        self, rows: List[Dict[str, Any]]
    ) -> List[ClickHouseDictionaryInfo]:
        """Read ``system.dictionaries`` rows into dictionary records.

        The driver may hand back ``DateTime`` columns as their native values
        or as strings, and both are passed through unchanged: the catalogue
        answered, and this parser does not restate it as a different type.
        The dotted catalogue columns were aliased by the statement.
        """
        return [
            ClickHouseDictionaryInfo(
                name=row.get("name", ""),
                database=row.get("database") or "",
                uuid=str(row["uuid"]) if row.get("uuid") is not None else None,
                status=_optional_text(row.get("status")),
                is_lazy=_bool(row.get("is_lazy")),
                origin=_optional_text(row.get("origin")),
                type=_optional_text(row.get("type")),
                key_names=_string_list(row.get("key_names")),
                key_types=_string_list(row.get("key_types")),
                attribute_names=_string_list(row.get("attribute_names")),
                attribute_types=_string_list(row.get("attribute_types")),
                bytes_allocated=_optional_int(row.get("bytes_allocated")) or 0,
                element_count=_optional_int(row.get("element_count")) or 0,
                query_count=_optional_int(row.get("query_count")) or 0,
                hit_rate=row.get("hit_rate"),
                found_rate=row.get("found_rate"),
                lifetime_min=_optional_int(row.get("lifetime_min")),
                lifetime_max=_optional_int(row.get("lifetime_max")),
                loading_start_time=row.get("loading_start_time"),
                last_successful_update_time=row.get("last_successful_update_time"),
                error_count=_optional_int(row.get("error_count")) or 0,
                last_exception=_optional_text(row.get("last_exception")),
                comment=_optional_text(row.get("comment")),
            )
            for row in rows
        ]

    def parse_clusters(self, rows: List[Dict[str, Any]]) -> List[ClickHouseClusterInfo]:
        """Read ``system.clusters`` rows into cluster-member records.

        A row is one member, not one cluster, so the one-based shard and
        replica numbers are fields on the record and the listing keeps them.
        ``is_local`` and ``internal_replication`` are booleans here.
        """
        return [
            ClickHouseClusterInfo(
                cluster=row.get("cluster", ""),
                shard_num=_optional_int(row.get("shard_num")) or 0,
                replica_num=_optional_int(row.get("replica_num")) or 0,
                shard_name=_optional_text(row.get("shard_name")),
                shard_weight=_optional_int(row.get("shard_weight")),
                internal_replication=_bool(row.get("internal_replication")),
                host_name=_optional_text(row.get("host_name")),
                host_address=_optional_text(row.get("host_address")),
                port=_optional_int(row.get("port")),
                is_local=_bool(row.get("is_local")),
                user=_optional_text(row.get("user")),
                default_database=_optional_text(row.get("default_database")),
                errors_count=_optional_int(row.get("errors_count")) or 0,
                slowdowns_count=_optional_int(row.get("slowdowns_count")) or 0,
                estimated_recovery_time=_optional_int(row.get("estimated_recovery_time")),
            )
            for row in rows
        ]

    def parse_quotas(self, rows: List[Dict[str, Any]]) -> List[ClickHouseQuotaInfo]:
        """Read ``system.quotas`` rows into quota records.

        ``keys`` is an ``Array(Enum8)`` and ``durations`` an ``Array(UInt32)``;
        both are normalised to plain Python lists so a consumer does not have
        to know which driver shape arrived.
        """
        return [
            ClickHouseQuotaInfo(
                name=row.get("name", ""),
                id=str(row["id"]) if row.get("id") is not None else None,
                storage=_optional_text(row.get("storage")),
                keys=_string_list(row.get("keys")),
                durations=_int_list(row.get("durations")),
                apply_to_all=_bool(row.get("apply_to_all")),
                apply_to_list=_string_list(row.get("apply_to_list")),
                apply_to_except=_string_list(row.get("apply_to_except")),
                ipv4_prefix_bits=_optional_int(row.get("ipv4_prefix_bits")),
                ipv6_prefix_bits=_optional_int(row.get("ipv6_prefix_bits")),
            )
            for row in rows
        ]

    def parse_users(self, rows: List[Dict[str, Any]]) -> List[ClickHouseUserInfo]:
        """Read ``system.users`` rows into account records.

        The authentication *type* list is reported and the credential
        parameters are not: the catalogue's ``auth_params`` column is
        deliberately not projected. The role and grantee arrays are
        normalised to lists of strings.
        """
        return [
            ClickHouseUserInfo(
                name=row.get("name", ""),
                id=str(row["id"]) if row.get("id") is not None else None,
                storage=_optional_text(row.get("storage")),
                auth_type=_string_list(row.get("auth_type")),
                default_roles_all=_bool(row.get("default_roles_all")),
                default_roles_list=_string_list(row.get("default_roles_list")),
                default_roles_except=_string_list(row.get("default_roles_except")),
                grantees_any=_bool(row.get("grantees_any")),
                grantees_list=_string_list(row.get("grantees_list")),
                grantees_except=_string_list(row.get("grantees_except")),
                default_database=_optional_text(row.get("default_database")),
                host_ip=_string_list(row.get("host_ip")),
                host_names=_string_list(row.get("host_names")),
                host_names_regexp=_string_list(row.get("host_names_regexp")),
                host_names_like=_string_list(row.get("host_names_like")),
            )
            for row in rows
        ]

    def parse_roles(self, rows: List[Dict[str, Any]]) -> List[ClickHouseRoleInfo]:
        """Read ``system.roles`` rows into role records."""
        return [
            ClickHouseRoleInfo(
                name=row.get("name", ""),
                id=str(row["id"]) if row.get("id") is not None else None,
                storage=_optional_text(row.get("storage")),
            )
            for row in rows
        ]

    def parse_column_data_profiles(
        self,
        rows: List[Dict[str, Any]],
        schema: str,
        table_name: str,
    ) -> List[Any]:
        """Project the aggregate profile rows, with the runtime types attached.

        The figures are the core parser's job -- it is the one place that turns
        a null count and a row count into a fraction, and duplicating that here
        would give the two shapes a chance to drift apart. So each row is
        handed to the core parser one at a time and the profile it produces is
        then rebuilt as :class:`~.types.ClickHouseColumnDataProfile`, which is
        the same dataclass plus this engine's own slot.

        ``runtime_types`` is lifted out of the row before the core parser sees
        it, because it is not one of the five figures and would otherwise land
        in ``extra`` -- a dictionary key a caller would have to know about by
        reading this file. As a named field it is visible to anyone who knows
        they asked ClickHouse.

        The keys are lower-cased first. The statement writes them lower case
        already, so this is not a repair; it is what keeps the parser reading
        one shape if a driver ever decides to report the manifest name instead
        of the spelled one, which is exactly the ambiguity Snowflake's parser
        has to live with.

        A row the core parser refuses -- no column name -- is skipped rather
        than rebuilt with an invented one, and it takes its runtime types with
        it.
        """
        from rhosocial.activerecord.backend.introspection.base import (
            IntrospectorBase,
        )

        from .types import ClickHouseColumnDataProfile

        profiles: List[Any] = []
        for row in rows or []:
            normalized = {str(key).lower(): value for key, value in row.items()}
            runtime_types = normalized.pop("runtime_types", None)
            base = IntrospectorBase.parse_column_data_profiles(
                self, [normalized], schema, table_name
            )
            if not base:
                continue
            found = base[0]
            profiles.append(
                ClickHouseColumnDataProfile(
                    schema=found.schema,
                    table_name=found.table_name,
                    column_name=found.column_name,
                    null_fraction=found.null_fraction,
                    distinct_count=found.distinct_count,
                    min_value=found.min_value,
                    max_value=found.max_value,
                    row_count=found.row_count,
                    source=found.source,
                    collected_at=found.collected_at,
                    extra=found.extra,
                    runtime_types=_runtime_type_names(runtime_types),
                )
            )
        return profiles


class ClickHouseIntrospector(ClickHouseIntrospectorMixin, AbstractIntrospector):
    """Synchronous introspector for ClickHouse backends.

    In addition to the standard AbstractIntrospector interface, exposes the
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
        executor: IntrospectorExecutor,
        cache: Optional[IntrospectionCache] = None,
    ) -> None:
        super().__init__(backend, executor, cache)
        self._show_instance: Optional[ShowIntrospector] = None
        self._status_instance: Optional[ClickHouseStatusIntrospector] = None

    @property
    def show(self) -> ShowIntrospector:
        """ClickHouse-specific SHOW sub-introspector (lazily created)."""
        if self._show_instance is None:
            self._show_instance = ShowIntrospector(self._backend, self._executor)
        return self._show_instance

    @property
    def status(self) -> ClickHouseStatusIntrospector:
        """ClickHouse status introspector (lazily created)."""
        if self._status_instance is None:
            self._status_instance = ClickHouseStatusIntrospector(self._backend)
        return self._status_instance

    # ------------------------------------------------------------------ #
    # get_table_info override
    # ------------------------------------------------------------------ #

    def get_table_info(
        self, table: str, schema: Optional[str] = None
    ) -> Optional[IntrospectionTableInfo]:
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

    def _partition_entries(
        self,
        table_name: str,
        database: Optional[str] = None,
        include_stats: bool = True,
    ) -> List[ClickHousePartitionInfo]:
        """Read a table's partitions from its active parts.

        This is the backend-specific catalogue read behind the neutral
        :meth:`get_partition_state` and behind the partition-maintenance
        service, which needs the ids the ``ALTER ... PARTITION ID`` verbs take. It
        stays private because it is not a neutral answer: a caller reading
        through the introspection manager uses ``get_partition_state``.

        The filter ``active = 1`` is what makes the aggregate mean what it says;
        ``include_stats=False`` asks only for the partition identity and its
        readable value, because the caller did not ask for a measurement.

        Args:
            table_name: The table to read.
            database: ClickHouse database; defaults to the connected database.
            include_stats: Sum rows and bytes on the server when true.

        Returns:
            One :class:`ClickHousePartitionInfo` per ``partition_id``, ordered
            by that id. A table with no active parts returns an empty list.
        """
        target = database if database is not None else self.default_schema
        cache_extra = "partition-stats" if include_stats else "partition"
        key = self._cache.key(
            IntrospectionScope.TABLE, table_name, schema=target, extra=cache_extra
        )
        cached = self._cache.get(key)
        if cached is not None:
            return cached
        sql, params = ClickHouseTablePartitionsQuery(
            self._backend.dialect, target, table_name, include_stats=include_stats
        ).to_sql()
        result = self.parse_partitions(self._executor.execute(sql, params), table_name, target)
        self._cache.set(key, result)
        return result

    def get_table_engine(
        self,
        table_name: str,
        database: Optional[str] = None,
    ) -> Optional[ClickHouseTableEngineInfo]:
        """Read a table's engine and key expressions from ``system.tables``.

        ``database`` follows the same rule as
        :meth:`ClickHouseIntrospector._partition_entries`: it is a ClickHouse
        database name, and ``None`` means the connected database.

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

    # ------------------------------------------------------------------ #
    # Neutral object state
    # ------------------------------------------------------------------ #

    def get_table_state(
        self,
        table_name: str,
        schema: Optional[str] = None,
    ) -> TableState:
        """Read the table's kind, storage options, comment and partition scheme.

        ``schema`` is ClickHouse's database, the engine's only namespace level.

        Raises:
            LookupError: when the server has no such table. The neutral shape
                is not optional, and an absent table is not a table state.
        """
        target = schema if schema is not None else self.default_schema
        key = self._cache.key(IntrospectionScope.TABLE, table_name, schema=target, extra="state")
        cached = self._cache.get(key)
        if cached is not None:
            return cached
        info = self.get_table_engine(table_name, database=target)
        if info is None:
            raise LookupError(f"Table '{table_name}' not found in database '{target}'")

        engine = info.engine
        kind = "regular"
        if info.is_temporary:
            kind = "temporary"
        elif self.dialect.engine_kind(engine) is TableType.VIEW:
            kind = "view"
        elif self.dialect.engine_kind(engine) is TableType.MATERIALIZED_VIEW:
            kind = "materialized_view"

        traits: tuple = ()
        if info.is_temporary:
            traits += ("temporary",)
        if engine.startswith("Replicated"):
            traits += ("replicated",)
        elif engine == "Distributed":
            traits += ("distributed",)

        storage_raw = {
            "engine_full": info.engine_full,
            "sorting_key": info.sorting_key,
            "primary_key": info.primary_key,
            "partition_key": info.partition_key,
            "sampling_key": info.sampling_key,
            "ttl": info.ttl,
            "storage_policy": info.storage_policy,
        }
        state = TableState(
            name=table_name,
            schema=target,
            kind=kind,
            traits=traits,
            storage=StorageOptionsState(
                engine=info.engine or None,
                raw=storage_raw,
            ),
            comment=info.comment or None,
            partitioning=self.get_partition_state(table_name, schema=target),
            raw={
                "engine_full": info.engine_full,
                "sorting_key": info.sorting_key,
                "primary_key": info.primary_key,
                "partition_key": info.partition_key,
                "sampling_key": info.sampling_key,
                "ttl": info.ttl,
                "total_rows": info.total_rows,
                "total_bytes": info.total_bytes,
                "is_temporary": info.is_temporary,
                "storage_policy": info.storage_policy,
            },
        )
        self._cache.set(key, state)
        return state

    def get_partition_state(
        self,
        table_name: str,
        schema: Optional[str] = None,
        include_stats: bool = False,
    ) -> Optional[PartitionState]:
        """Read the table's partition scheme and bounds.

        **The partition key decides whether a table is partitioned, not
        ``system.parts``.** The parts view always holds at least one row for a
        MergeTree table -- the unpartitioned one reports a single ``'all'``
        partition once it has data -- so treating a non-empty parts list as
        "partitioned" would call every written MergeTree table partitioned. The
        engine's ``partition_key`` is the declaration, and its empty string is
        the answer here: ``scheme`` stays ``None`` and no bounds are reported.

        ``None`` is returned only when the table does not exist. A table that
        exists but declares no partition key is a :class:`PartitionState` with
        ``scheme=None``.

        ``include_stats`` adds per-partition ``row_count`` and ``size_bytes``;
        when it is False the count and byte sums are never queried.
        """
        target = schema if schema is not None else self.default_schema
        key = self._cache.key(
            IntrospectionScope.TABLE,
            table_name,
            schema=target,
            extra=f"partition-state:{int(include_stats)}",
        )
        cached = self._cache.get(key)
        if cached is not None:
            return cached
        info = self.get_table_engine(table_name, database=target)
        if info is None:
            return None

        partition_key = info.partition_key or ""
        if not partition_key:
            state = PartitionState(
                scheme=None,
                raw={
                    "engine": info.engine,
                    "partition_key": "",
                    "sorting_key": info.sorting_key,
                },
            )
            self._cache.set(key, state)
            return state

        entries = self._partition_entries(table_name, database=target, include_stats=include_stats)
        bounds = tuple(
            PartitionBound(
                name=entry.partition_id,
                upper=entry.partition,
                row_count=entry.row_count if include_stats else None,
                size_bytes=entry.bytes_on_disk if include_stats else None,
                is_default=False,
                is_maxvalue=False,
                subpartition_count=0,
                tablespace=None,
            )
            for entry in entries
        )
        state = PartitionState(
            scheme=PartitionScheme.EXPRESSION,
            key_expression=partition_key,
            key_columns=(),
            has_default=False,
            auto_extend=False,
            bounds=bounds,
            raw={
                "engine": info.engine,
                "partition_key": partition_key,
                "sorting_key": info.sorting_key,
                "primary_key": info.primary_key,
                "sampling_key": info.sampling_key,
            },
        )
        self._cache.set(key, state)
        return state

    def list_index_states(
        self,
        table_name: str,
        schema: Optional[str] = None,
    ) -> List[IndexState]:
        """Read the table's data-skipping indices, with expression and size."""
        target = schema if schema is not None else self.default_schema
        key = self._cache.key(
            IntrospectionScope.INDEX, table_name, schema=target, extra="state"
        )
        cached = self._cache.get(key)
        if cached is not None:
            return cached
        sql, params = ClickHouseIndexStateListQuery(
            self._backend.dialect, target, table_name
        ).to_sql()
        result = self.parse_index_states(self._executor.execute(sql, params), table_name, target)
        self._cache.set(key, result)
        return result

    def list_constraint_states(
        self,
        table_name: str,
        schema: Optional[str] = None,
    ) -> List[ConstraintState]:
        """Read the table's ``CHECK`` / ``ASSUME`` constraints.

        Raises:
            IntrospectionNotSupportedError: when the server's release line has
                no ``system.constraints`` catalogue (25.8 and 26.3 do not, by
                measurement). There is no second source this backend reads:
                a refusal naming the missing catalogue is the honest answer,
                and an empty list would claim the table declares no constraint.
        """
        target = schema if schema is not None else self.default_schema
        key = self._cache.key(
            IntrospectionScope.TABLE, table_name, schema=target, extra="constraints"
        )
        cached = self._cache.get(key)
        if cached is not None:
            return cached
        sql, params = ClickHouseConstraintStateListQuery(
            self._backend.dialect, target, table_name
        ).to_sql()
        result = self.parse_constraint_states(self._executor.execute(sql, params), table_name, target)
        self._cache.set(key, result)
        return result

    def list_schemas(self) -> List[str]:
        """Read the database names ``system.databases`` exposes."""
        key = self._cache.key(IntrospectionScope.SCHEMA, extra="names")
        cached = self._cache.get(key)
        if cached is not None:
            return cached
        sql, params = ClickHouseSchemaListQuery(self._backend.dialect).to_sql()
        result = self.parse_schema_names(self._executor.execute(sql, params))
        self._cache.set(key, result)
        return result

    def list_derived_objects(
        self,
        table_name: str,
        schema: Optional[str] = None,
    ) -> List[DerivedObjectState]:
        """Read projections and materialized views that belong to the table."""
        target = schema if schema is not None else self.default_schema
        key = self._cache.key(
            IntrospectionScope.TABLE, table_name, schema=target, extra="derived"
        )
        cached = self._cache.get(key)
        if cached is not None:
            return cached
        projection_sql, projection_params = ClickHouseProjectionListQuery(
            self._backend.dialect, target, table_name
        ).to_sql()
        view_sql, view_params = ClickHouseMaterializedViewListQuery(
            self._backend.dialect, target
        ).to_sql()
        result = self.parse_projection_states(
            self._executor.execute(projection_sql, projection_params), table_name
        ) + self.parse_materialized_view_states(
            self._executor.execute(view_sql, view_params), table_name, target
        )
        self._cache.set(key, result)
        return result

    def item_exists(
        self,
        kind: ItemKind,
        name: str,
        schema: Optional[str] = None,
    ) -> bool:
        """Whether a shared object of this kind exists.

        ClickHouse catalogues databases, tables (views included) and functions.
        The other kinds are not object classes this engine has at all -- there
        are no sequences, named types, domains, extensions, tablespaces,
        partition functions/schemes or full-text catalogues -- so their answer
        is a real ``False`` rather than a refusal.
        """
        if kind is ItemKind.SCHEMA:
            return name in self.list_schemas()
        if kind is ItemKind.TABLE:
            return self.get_table_engine(name, database=schema) is not None
        if kind is ItemKind.FUNCTION:
            return any(function.name == name for function in self.list_functions(name=name))
        return False

    # ------------------------------------------------------------------ #
    # Server-wide catalogue families
    # ------------------------------------------------------------------ #

    def list_functions(self, name: Optional[str] = None) -> List[ClickHouseFunctionInfo]:
        """List the functions ``system.functions`` exposes.

        ``name`` narrows the listing to the rows carrying that name; it does
        not select one row, because a name can be an alias of another function.
        The result includes built-ins and user-defined functions together, and
        ``origin`` on each row says which is which.
        """
        key = self._catalog_key("functions", name or "")
        cached = self._cache.get(key)
        if cached is not None:
            return cached
        sql, params = ClickHouseFunctionListQuery(self._backend.dialect, name=name).to_sql()
        result = self.parse_functions(self._executor.execute(sql, params))
        self._cache.set(key, result)
        return result

    def list_dictionaries(
        self,
        name: Optional[str] = None,
        database: Optional[str] = None,
    ) -> List[ClickHouseDictionaryInfo]:
        """List dictionaries from ``system.dictionaries``.

        ``name`` narrows the listing to one dictionary name. ``database``
        narrows it to one ClickHouse database; ``None`` means the whole
        catalogue, which also includes configuration-file dictionaries whose
        database is the empty string.
        """
        key = self._catalog_key(
            "dictionaries", name or "", "*" if database is None else database
        )
        cached = self._cache.get(key)
        if cached is not None:
            return cached
        sql, params = ClickHouseDictionaryListQuery(
            self._backend.dialect, name=name, database=database
        ).to_sql()
        result = self.parse_dictionaries(self._executor.execute(sql, params))
        self._cache.set(key, result)
        return result

    def list_clusters(self, name: Optional[str] = None) -> List[ClickHouseClusterInfo]:
        """List cluster members from ``system.clusters``.

        The listing is one row per shard/replica member; ``name`` narrows it
        to the members of one cluster rather than to a single server.
        """
        key = self._catalog_key("clusters", name or "")
        cached = self._cache.get(key)
        if cached is not None:
            return cached
        sql, params = ClickHouseClusterListQuery(self._backend.dialect, name=name).to_sql()
        result = self.parse_clusters(self._executor.execute(sql, params))
        self._cache.set(key, result)
        return result

    def list_quotas(self, name: Optional[str] = None) -> List[ClickHouseQuotaInfo]:
        """List quotas from ``system.quotas``, optionally one name."""
        key = self._catalog_key("quotas", name or "")
        cached = self._cache.get(key)
        if cached is not None:
            return cached
        sql, params = ClickHouseQuotaListQuery(self._backend.dialect, name=name).to_sql()
        result = self.parse_quotas(self._executor.execute(sql, params))
        self._cache.set(key, result)
        return result

    def list_users(self, name: Optional[str] = None) -> List[ClickHouseUserInfo]:
        """List accounts from ``system.users``, optionally one name.

        Credentials are not reported; see
        :class:`~.types.ClickHouseUserInfo` for the line this family keeps.
        """
        key = self._catalog_key("users", name or "")
        cached = self._cache.get(key)
        if cached is not None:
            return cached
        sql, params = ClickHouseIntrospectionUserListQuery(self._backend.dialect, name=name).to_sql()
        result = self.parse_users(self._executor.execute(sql, params))
        self._cache.set(key, result)
        return result

    def list_roles(self, name: Optional[str] = None) -> List[ClickHouseRoleInfo]:
        """List roles from ``system.roles``, optionally one name."""
        key = self._catalog_key("roles", name or "")
        cached = self._cache.get(key)
        if cached is not None:
            return cached
        sql, params = ClickHouseRoleListQuery(self._backend.dialect, name=name).to_sql()
        result = self.parse_roles(self._executor.execute(sql, params))
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

    async def get_table_info(
        self, table: str, schema: Optional[str] = None
    ) -> Optional[IntrospectionTableInfo]:
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

    async def _partition_entries(
        self,
        table_name: str,
        database: Optional[str] = None,
        include_stats: bool = True,
    ) -> List[ClickHousePartitionInfo]:
        """Read a table's partitions from its active parts.

        The asynchronous counterpart of
        :meth:`ClickHouseIntrospector._partition_entries`: same parameters,
        same result, same cache key.
        """
        target = database if database is not None else self.default_schema
        cache_extra = "partition-stats" if include_stats else "partition"
        key = self._cache.key(
            IntrospectionScope.TABLE, table_name, schema=target, extra=cache_extra
        )
        cached = self._cache.get(key)
        if cached is not None:
            return cached
        sql, params = ClickHouseTablePartitionsQuery(
            self._backend.dialect, target, table_name, include_stats=include_stats
        ).to_sql()
        result = self.parse_partitions(
            await self._executor.execute(sql, params), table_name, target
        )
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
        result = self.parse_table_engine(
            await self._executor.execute(sql, params), table_name, target
        )
        if result is not None:
            self._cache.set(key, result)
        return result

    # ------------------------------------------------------------------ #
    # Neutral object state
    # ------------------------------------------------------------------ #

    async def get_table_state(
        self,
        table_name: str,
        schema: Optional[str] = None,
    ) -> TableState:
        """Read the table's kind, storage options, comment and partition scheme.

        The asynchronous twin of
        :meth:`ClickHouseIntrospector.get_table_state`.
        """
        target = schema if schema is not None else self.default_schema
        key = self._cache.key(IntrospectionScope.TABLE, table_name, schema=target, extra="state")
        cached = self._cache.get(key)
        if cached is not None:
            return cached
        info = await self.get_table_engine(table_name, database=target)
        if info is None:
            raise LookupError(f"Table '{table_name}' not found in database '{target}'")

        engine = info.engine
        kind = "regular"
        if info.is_temporary:
            kind = "temporary"
        elif self.dialect.engine_kind(engine) is TableType.VIEW:
            kind = "view"
        elif self.dialect.engine_kind(engine) is TableType.MATERIALIZED_VIEW:
            kind = "materialized_view"

        traits: tuple = ()
        if info.is_temporary:
            traits += ("temporary",)
        if engine.startswith("Replicated"):
            traits += ("replicated",)
        elif engine == "Distributed":
            traits += ("distributed",)

        storage_raw = {
            "engine_full": info.engine_full,
            "sorting_key": info.sorting_key,
            "primary_key": info.primary_key,
            "partition_key": info.partition_key,
            "sampling_key": info.sampling_key,
            "ttl": info.ttl,
            "storage_policy": info.storage_policy,
        }
        state = TableState(
            name=table_name,
            schema=target,
            kind=kind,
            traits=traits,
            storage=StorageOptionsState(engine=info.engine or None, raw=storage_raw),
            comment=info.comment or None,
            partitioning=await self.get_partition_state(table_name, schema=target),
            raw={
                "engine_full": info.engine_full,
                "sorting_key": info.sorting_key,
                "primary_key": info.primary_key,
                "partition_key": info.partition_key,
                "sampling_key": info.sampling_key,
                "ttl": info.ttl,
                "total_rows": info.total_rows,
                "total_bytes": info.total_bytes,
                "is_temporary": info.is_temporary,
                "storage_policy": info.storage_policy,
            },
        )
        self._cache.set(key, state)
        return state

    async def get_partition_state(
        self,
        table_name: str,
        schema: Optional[str] = None,
        include_stats: bool = False,
    ) -> Optional[PartitionState]:
        """Read the table's partition scheme and bounds.

        The asynchronous twin of
        :meth:`ClickHouseIntrospector.get_partition_state`: the engine's
        ``partition_key`` decides whether the table is partitioned, never the
        parts view.
        """
        target = schema if schema is not None else self.default_schema
        key = self._cache.key(
            IntrospectionScope.TABLE,
            table_name,
            schema=target,
            extra=f"partition-state:{int(include_stats)}",
        )
        cached = self._cache.get(key)
        if cached is not None:
            return cached
        info = await self.get_table_engine(table_name, database=target)
        if info is None:
            return None

        partition_key = info.partition_key or ""
        if not partition_key:
            state = PartitionState(
                scheme=None,
                raw={
                    "engine": info.engine,
                    "partition_key": "",
                    "sorting_key": info.sorting_key,
                },
            )
            self._cache.set(key, state)
            return state

        entries = await self._partition_entries(
            table_name, database=target, include_stats=include_stats
        )
        bounds = tuple(
            PartitionBound(
                name=entry.partition_id,
                upper=entry.partition,
                row_count=entry.row_count if include_stats else None,
                size_bytes=entry.bytes_on_disk if include_stats else None,
                is_default=False,
                is_maxvalue=False,
                subpartition_count=0,
                tablespace=None,
            )
            for entry in entries
        )
        state = PartitionState(
            scheme=PartitionScheme.EXPRESSION,
            key_expression=partition_key,
            key_columns=(),
            has_default=False,
            auto_extend=False,
            bounds=bounds,
            raw={
                "engine": info.engine,
                "partition_key": partition_key,
                "sorting_key": info.sorting_key,
                "primary_key": info.primary_key,
                "sampling_key": info.sampling_key,
            },
        )
        self._cache.set(key, state)
        return state

    async def list_index_states(
        self,
        table_name: str,
        schema: Optional[str] = None,
    ) -> List[IndexState]:
        """Read the table's data-skipping indices, with expression and size."""
        target = schema if schema is not None else self.default_schema
        key = self._cache.key(
            IntrospectionScope.INDEX, table_name, schema=target, extra="state"
        )
        cached = self._cache.get(key)
        if cached is not None:
            return cached
        sql, params = ClickHouseIndexStateListQuery(
            self._backend.dialect, target, table_name
        ).to_sql()
        result = self.parse_index_states(
            await self._executor.execute(sql, params), table_name, target
        )
        self._cache.set(key, result)
        return result

    async def list_constraint_states(
        self,
        table_name: str,
        schema: Optional[str] = None,
    ) -> List[ConstraintState]:
        """Read the table's ``CHECK`` / ``ASSUME`` constraints.

        Raises:
            IntrospectionNotSupportedError: when the server's release line has
                no ``system.constraints`` catalogue (25.8 and 26.3 do not, by
                measurement). The refusal names the missing catalogue rather
                than answering an empty list for a question it could not ask.
        """
        target = schema if schema is not None else self.default_schema
        key = self._cache.key(
            IntrospectionScope.TABLE, table_name, schema=target, extra="constraints"
        )
        cached = self._cache.get(key)
        if cached is not None:
            return cached
        sql, params = ClickHouseConstraintStateListQuery(
            self._backend.dialect, target, table_name
        ).to_sql()
        result = self.parse_constraint_states(
            await self._executor.execute(sql, params), table_name, target
        )
        self._cache.set(key, result)
        return result

    async def list_schemas(self) -> List[str]:
        """Read the database names ``system.databases`` exposes."""
        key = self._cache.key(IntrospectionScope.SCHEMA, extra="names")
        cached = self._cache.get(key)
        if cached is not None:
            return cached
        sql, params = ClickHouseSchemaListQuery(self._backend.dialect).to_sql()
        result = self.parse_schema_names(await self._executor.execute(sql, params))
        self._cache.set(key, result)
        return result

    async def list_derived_objects(
        self,
        table_name: str,
        schema: Optional[str] = None,
    ) -> List[DerivedObjectState]:
        """Read projections and materialized views that belong to the table."""
        target = schema if schema is not None else self.default_schema
        key = self._cache.key(
            IntrospectionScope.TABLE, table_name, schema=target, extra="derived"
        )
        cached = self._cache.get(key)
        if cached is not None:
            return cached
        projection_sql, projection_params = ClickHouseProjectionListQuery(
            self._backend.dialect, target, table_name
        ).to_sql()
        view_sql, view_params = ClickHouseMaterializedViewListQuery(
            self._backend.dialect, target
        ).to_sql()
        result = self.parse_projection_states(
            await self._executor.execute(projection_sql, projection_params), table_name
        ) + self.parse_materialized_view_states(
            await self._executor.execute(view_sql, view_params), table_name, target
        )
        self._cache.set(key, result)
        return result

    async def item_exists(
        self,
        kind: ItemKind,
        name: str,
        schema: Optional[str] = None,
    ) -> bool:
        """Whether a shared object of this kind exists.

        The asynchronous twin of :meth:`ClickHouseIntrospector.item_exists`.
        """
        if kind is ItemKind.SCHEMA:
            return name in await self.list_schemas()
        if kind is ItemKind.TABLE:
            return await self.get_table_engine(name, database=schema) is not None
        if kind is ItemKind.FUNCTION:
            return any(function.name == name for function in await self.list_functions(name=name))
        return False

    # ------------------------------------------------------------------ #
    # Server-wide catalogue families
    # ------------------------------------------------------------------ #

    async def list_functions(
        self, name: Optional[str] = None
    ) -> List[ClickHouseFunctionInfo]:
        """List functions from ``system.functions``, asynchronously.

        The asynchronous counterpart of
        :meth:`ClickHouseIntrospector.list_functions`: same parameters, same
        result, same cache key.
        """
        key = self._catalog_key("functions", name or "")
        cached = self._cache.get(key)
        if cached is not None:
            return cached
        sql, params = ClickHouseFunctionListQuery(self._backend.dialect, name=name).to_sql()
        result = self.parse_functions(await self._executor.execute(sql, params))
        self._cache.set(key, result)
        return result

    async def list_dictionaries(
        self,
        name: Optional[str] = None,
        database: Optional[str] = None,
    ) -> List[ClickHouseDictionaryInfo]:
        """List dictionaries from ``system.dictionaries``, asynchronously.

        The asynchronous counterpart of
        :meth:`ClickHouseIntrospector.list_dictionaries`: same parameters, same
        result, same cache key.
        """
        key = self._catalog_key(
            "dictionaries", name or "", "*" if database is None else database
        )
        cached = self._cache.get(key)
        if cached is not None:
            return cached
        sql, params = ClickHouseDictionaryListQuery(
            self._backend.dialect, name=name, database=database
        ).to_sql()
        result = self.parse_dictionaries(await self._executor.execute(sql, params))
        self._cache.set(key, result)
        return result

    async def list_clusters(
        self, name: Optional[str] = None
    ) -> List[ClickHouseClusterInfo]:
        """List cluster members from ``system.clusters``, asynchronously.

        The asynchronous counterpart of
        :meth:`ClickHouseIntrospector.list_clusters`: same parameters, same
        result, same cache key.
        """
        key = self._catalog_key("clusters", name or "")
        cached = self._cache.get(key)
        if cached is not None:
            return cached
        sql, params = ClickHouseClusterListQuery(self._backend.dialect, name=name).to_sql()
        result = self.parse_clusters(await self._executor.execute(sql, params))
        self._cache.set(key, result)
        return result

    async def list_quotas(self, name: Optional[str] = None) -> List[ClickHouseQuotaInfo]:
        """List quotas from ``system.quotas``, asynchronously.

        The asynchronous counterpart of
        :meth:`ClickHouseIntrospector.list_quotas`: same parameters, same
        result, same cache key.
        """
        key = self._catalog_key("quotas", name or "")
        cached = self._cache.get(key)
        if cached is not None:
            return cached
        sql, params = ClickHouseQuotaListQuery(self._backend.dialect, name=name).to_sql()
        result = self.parse_quotas(await self._executor.execute(sql, params))
        self._cache.set(key, result)
        return result

    async def list_users(self, name: Optional[str] = None) -> List[ClickHouseUserInfo]:
        """List accounts from ``system.users``, asynchronously.

        The asynchronous counterpart of
        :meth:`ClickHouseIntrospector.list_users`: same parameters, same
        result, same cache key.
        """
        key = self._catalog_key("users", name or "")
        cached = self._cache.get(key)
        if cached is not None:
            return cached
        sql, params = ClickHouseIntrospectionUserListQuery(self._backend.dialect, name=name).to_sql()
        result = self.parse_users(await self._executor.execute(sql, params))
        self._cache.set(key, result)
        return result

    async def list_roles(self, name: Optional[str] = None) -> List[ClickHouseRoleInfo]:
        """List roles from ``system.roles``, asynchronously.

        The asynchronous counterpart of
        :meth:`ClickHouseIntrospector.list_roles`: same parameters, same
        result, same cache key.
        """
        key = self._catalog_key("roles", name or "")
        cached = self._cache.get(key)
        if cached is not None:
            return cached
        sql, params = ClickHouseRoleListQuery(self._backend.dialect, name=name).to_sql()
        result = self.parse_roles(await self._executor.execute(sql, params))
        self._cache.set(key, result)
        return result

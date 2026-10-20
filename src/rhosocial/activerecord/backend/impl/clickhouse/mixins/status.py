# src/rhosocial/activerecord/backend/impl/clickhouse/mixins/status.py
"""ClickHouse format_* entry points for the status-introspection nodes.

Every ``system.*`` read the status introspector performs is a node in
``..expression.status``; this mixin is the dialect side of that pair. Each
formatter writes one statement in full, so the whole query is visible in one
place instead of being assembled by the caller from a prefix, a counted run of
placeholders and a suffix.
"""

from typing import Tuple, TYPE_CHECKING

if TYPE_CHECKING:  # pragma: no cover
    from ..expression.status import (
        ClickHouseAsynchronousMetricsQuery,
        ClickHouseConnectionGaugesQuery,
        ClickHouseConnectionProbeQuery,
        ClickHouseCurrentUserQuery,
        ClickHouseDatabaseTotalSizeQuery,
        ClickHouseDiskListQuery,
        ClickHouseEventsQuery,
        ClickHouseGrantListQuery,
        ClickHouseMetricsQuery,
        ClickHouseProcessListQuery,
        ClickHouseReplicaListQuery,
        ClickHouseRoleGrantListQuery,
        ClickHouseRowCountQuery,
        ClickHouseServerSettingQuery,
        ClickHouseServerSettingsQuery,
        ClickHouseSettingQuery,
        ClickHouseSettingsQuery,
        ClickHouseTableCountQuery,
        ClickHouseUserListQuery,
        ClickHouseVersionQuery,
    )


class ClickHouseStatusQueryMixin:
    """``format_clickhouse_*`` entry points for the status reads."""

    # ========== Shared building blocks ==========

    def _system_source(self, name: str):
        """One ClickHouse ``system`` table as a ``FROM`` source."""
        from rhosocial.activerecord.backend.expression import NamedRelationRef
        from rhosocial.activerecord.backend.expression.objects import Table

        return NamedRelationRef(self, Table(self, name, catalog_name="system"))

    def _relation_source(self, catalog: str, name: str):
        """One table as a ``FROM`` source, in the given catalog."""
        from rhosocial.activerecord.backend.expression import NamedRelationRef
        from rhosocial.activerecord.backend.expression.objects import Table

        return NamedRelationRef(self, Table(self, name, catalog_name=catalog))

    def _column(self, name: str, alias=None):
        """A column reference, optionally projected under another name."""
        from rhosocial.activerecord.backend.expression import Column

        return Column(self, name, alias=alias)

    def _equals(self, left, right):
        """``left = right`` as a predicate node."""
        from rhosocial.activerecord.backend.expression import ComparisonPredicate

        return ComparisonPredicate(self, "eq", left, right)

    def _in(self, column_name: str, values):
        """``<column_name> IN (<values>)`` over bound values."""
        from rhosocial.activerecord.backend.expression import (
            Column,
            InPredicate,
            Literal,
        )

        return InPredicate(self, Column(self, column_name), Literal(self, tuple(values)))

    def _is_null(self, column_name: str):
        """``<column_name> IS NULL``."""
        from rhosocial.activerecord.backend.expression import Column, IsNullPredicate

        return IsNullPredicate(self, Column(self, column_name))

    def _where(self, *predicates):
        """A ``WhereClause`` over the conjunction, or ``None`` when empty."""
        from rhosocial.activerecord.backend.expression import LogicalPredicate, WhereClause

        kept = [p for p in predicates if p is not None]
        if not kept:
            return None
        return WhereClause(self, LogicalPredicate(self, "AND", *kept))

    # ========== Inventory reads ==========

    def format_clickhouse_settings_query(self, expr: "ClickHouseSettingsQuery") -> Tuple[str, tuple]:
        """``system.settings`` rows for the requested names."""
        from rhosocial.activerecord.backend.expression import QueryStatement

        query = QueryStatement(
            self,
            select=[
                self._column("name"),
                self._column("value"),
                self._column("description"),
                self._column("default"),
                self._column("readonly"),
                self._column("changed"),
                self._column("type"),
            ],
            from_=self._system_source("settings"),
            where=self._where(self._in("name", expr.names)),
        )
        return query.to_sql()

    def format_clickhouse_server_settings_query(
        self, expr: "ClickHouseServerSettingsQuery"
    ) -> Tuple[str, tuple]:
        """``system.server_settings`` rows for the requested names."""
        from rhosocial.activerecord.backend.expression import QueryStatement

        query = QueryStatement(
            self,
            select=[
                self._column("name"),
                self._column("value"),
                self._column("description"),
                self._column("default"),
                self._column("changed"),
                self._column("type"),
                self._column("changeable_without_restart"),
            ],
            from_=self._system_source("server_settings"),
            where=self._where(self._in("name", expr.names)),
        )
        return query.to_sql()

    def format_clickhouse_metrics_query(self, expr: "ClickHouseMetricsQuery") -> Tuple[str, tuple]:
        """Gauge rows of ``system.metrics`` for the requested names."""
        from rhosocial.activerecord.backend.expression import QueryStatement

        query = QueryStatement(
            self,
            select=[
                self._column("metric"),
                self._column("value"),
                self._column("description"),
            ],
            from_=self._system_source("metrics"),
            where=self._where(self._in("metric", expr.names)),
        )
        return query.to_sql()

    def format_clickhouse_events_query(self, expr: "ClickHouseEventsQuery") -> Tuple[str, tuple]:
        """Counter rows of ``system.events`` for the requested names."""
        from rhosocial.activerecord.backend.expression import QueryStatement

        query = QueryStatement(
            self,
            select=[
                self._column("event"),
                self._column("value"),
                self._column("description"),
            ],
            from_=self._system_source("events"),
            where=self._where(self._in("event", expr.names)),
        )
        return query.to_sql()

    def format_clickhouse_asynchronous_metrics_query(
        self, expr: "ClickHouseAsynchronousMetricsQuery"
    ) -> Tuple[str, tuple]:
        """Sampled rows of ``system.asynchronous_metrics`` for the requested names."""
        from rhosocial.activerecord.backend.expression import QueryStatement

        query = QueryStatement(
            self,
            select=[
                self._column("metric"),
                self._column("value"),
                self._column("description"),
            ],
            from_=self._system_source("asynchronous_metrics"),
            where=self._where(self._in("metric", expr.names)),
        )
        return query.to_sql()

    def format_clickhouse_connection_gauges_query(
        self, expr: "ClickHouseConnectionGaugesQuery"
    ) -> Tuple[str, tuple]:
        """``metric``/``value`` rows of ``system.metrics`` for the requested names."""
        from rhosocial.activerecord.backend.expression import QueryStatement

        query = QueryStatement(
            self,
            select=[self._column("metric"), self._column("value")],
            from_=self._system_source("metrics"),
            where=self._where(self._in("metric", expr.names)),
        )
        return query.to_sql()

    # ========== Single-value reads ==========

    def format_clickhouse_server_setting_query(
        self, expr: "ClickHouseServerSettingQuery"
    ) -> Tuple[str, tuple]:
        """One ``name``/``value`` row of ``system.server_settings``."""
        from rhosocial.activerecord.backend.expression import Literal, QueryStatement

        query = QueryStatement(
            self,
            select=[self._column("name"), self._column("value")],
            from_=self._system_source("server_settings"),
            where=self._where(self._equals(self._column("name"), Literal(self, expr.name))),
        )
        return query.to_sql()

    def format_clickhouse_database_total_size_query(
        self, expr: "ClickHouseDatabaseTotalSizeQuery"
    ) -> Tuple[str, tuple]:
        """Total on-disk size of one database's tables."""
        from rhosocial.activerecord.backend.expression import Literal, QueryStatement
        from rhosocial.activerecord.backend.expression.functions.aggregate import sum_

        query = QueryStatement(
            self,
            select=[sum_(self, self._column("total_bytes"), alias="total_size")],
            from_=self._system_source("tables"),
            where=self._where(self._equals(self._column("database"), Literal(self, expr.database))),
        )
        return query.to_sql()

    def format_clickhouse_disk_list_query(
        self, expr: "ClickHouseDiskListQuery"
    ) -> Tuple[str, tuple]:
        """Every row of ``system.disks``, with its capacity and flags."""
        from rhosocial.activerecord.backend.expression import QueryStatement

        query = QueryStatement(
            self,
            select=[
                self._column("name"),
                self._column("path"),
                self._column("type"),
                self._column("total_space"),
                self._column("free_space"),
                self._column("unreserved_space"),
                self._column("keep_free_space"),
                self._column("is_encrypted"),
                self._column("is_read_only"),
                self._column("is_remote"),
                self._column("is_broken"),
            ],
            from_=self._system_source("disks"),
        )
        return query.to_sql()

    def format_clickhouse_table_count_query(
        self, expr: "ClickHouseTableCountQuery"
    ) -> Tuple[str, tuple]:
        """Table and view counts per database, from ``information_schema.TABLES``."""
        from rhosocial.activerecord.backend.expression import QueryStatement
        from rhosocial.activerecord.backend.expression.functions.aggregate import count

        query = QueryStatement(
            self,
            select=[
                self._column("table_schema"),
                self._column("table_type"),
                count(self, "*", alias="count"),
            ],
            from_=self._relation_source("information_schema", "TABLES"),
            where=self._where(self._in("table_schema", expr.schemas)),
            group_by_having=self._group_by("table_schema", "table_type"),
        )
        return query.to_sql()

    def _group_by(self, *column_names: str):
        """``GROUP BY`` over the named columns."""
        from rhosocial.activerecord.backend.expression import GroupByHavingClause

        return GroupByHavingClause(self, group_by=[self._column(n) for n in column_names])

    # ========== User / role reads ==========

    def format_clickhouse_user_list_query(
        self, expr: "ClickHouseUserListQuery"
    ) -> Tuple[str, tuple]:
        """Every row of ``system.users``."""
        from rhosocial.activerecord.backend.expression import QueryStatement

        query = QueryStatement(
            self,
            select=[
                self._column("name"),
                self._column("id"),
                self._column("auth_type"),
                self._column("default_database"),
                self._column("host_ip"),
                self._column("host_names"),
            ],
            from_=self._system_source("users"),
        )
        return query.to_sql()

    def format_clickhouse_grant_list_query(
        self, expr: "ClickHouseGrantListQuery"
    ) -> Tuple[str, tuple]:
        """Database- and table-scoped grants, from ``system.grants``.

        ``database IS NULL AND table IS NULL`` is what isolates the
        instance-wide grant rows from the per-database ones: the same table
        holds both, and only the former is what an account's access types are
        read from.
        """
        from rhosocial.activerecord.backend.expression import QueryStatement

        query = QueryStatement(
            self,
            select=[
                self._column("user_name"),
                self._column("access_type"),
                self._column("database"),
                self._column("table"),
                self._column("grant_option"),
            ],
            from_=self._system_source("grants"),
            where=self._where(self._is_null("database"), self._is_null("table")),
        )
        return query.to_sql()

    def format_clickhouse_role_grant_list_query(
        self, expr: "ClickHouseRoleGrantListQuery"
    ) -> Tuple[str, tuple]:
        """Granted roles, from ``system.role_grants``."""
        from rhosocial.activerecord.backend.expression import QueryStatement

        query = QueryStatement(
            self,
            select=[
                self._column("user_name"),
                self._column("role_name"),
                self._column("granted_role_is_default"),
            ],
            from_=self._system_source("role_grants"),
        )
        return query.to_sql()

    # ========== Session / process reads ==========

    def format_clickhouse_current_user_query(
        self, expr: "ClickHouseCurrentUserQuery"
    ) -> Tuple[str, tuple]:
        """The user this session authenticates as."""
        from rhosocial.activerecord.backend.expression import FunctionCall, QueryStatement

        query = QueryStatement(
            self,
            select=[FunctionCall(self, "currentUser")],
        )
        return query.to_sql()

    def format_clickhouse_setting_query(
        self, expr: "ClickHouseSettingQuery"
    ) -> Tuple[str, tuple]:
        """One ``value`` of ``system.settings``.

        The session-level counterpart of the server-settings read: a setting a
        query or the session can change has its row here and none in
        ``system.server_settings``.
        """
        from rhosocial.activerecord.backend.expression import Literal, QueryStatement

        query = QueryStatement(
            self,
            select=[self._column("value")],
            from_=self._system_source("settings"),
            where=self._where(self._equals(self._column("name"), Literal(self, expr.name))),
        )
        return query.to_sql()

    def format_clickhouse_connection_probe_query(
        self, expr: "ClickHouseConnectionProbeQuery"
    ) -> Tuple[str, tuple]:
        """``SELECT 1``: the connection liveness probe.

        A scalar with no relation, so the statement is a ``QueryStatement``
        whose select list is the one constant and whose ``from_`` is absent.
        """
        from rhosocial.activerecord.backend.expression import Literal, QueryStatement

        query = QueryStatement(
            self,
            select=[Literal(self, 1, inline=True)],
        )
        return query.to_sql()

    def format_clickhouse_version_query(self, expr: "ClickHouseVersionQuery") -> Tuple[str, tuple]:
        """The server's own version string."""
        from rhosocial.activerecord.backend.expression import FunctionCall, QueryStatement

        query = QueryStatement(
            self,
            select=[FunctionCall(self, "version")],
        )
        return query.to_sql()

    def format_clickhouse_process_list_query(
        self, expr: "ClickHouseProcessListQuery"
    ) -> Tuple[str, tuple]:
        """The running queries, from ``system.processes``.

        ``current_database`` rather than MySQL's ``currentDatabase``: measured on
        26.7.3.19, ``SELECT currentDatabase FROM system.processes`` resolves as a
        *value* (the string ``default``) on every row, so nothing errors and the
        column quietly holds the same constant six thousand times. The column
        name is the one the table actually has.
        """
        from rhosocial.activerecord.backend.expression import QueryStatement

        query = QueryStatement(
            self,
            select=[
                self._column("query_id"),
                self._column("user"),
                self._column("address"),
                self._column("current_database"),
                self._column("elapsed"),
                self._column("query"),
            ],
            from_=self._system_source("processes"),
        )
        return query.to_sql()

    def format_clickhouse_replica_list_query(
        self, expr: "ClickHouseReplicaListQuery"
    ) -> Tuple[str, tuple]:
        """Replication summary rows from ``system.replicas``.

        The row cap is **inline text**, not a bind parameter: it is an inventory
        cap this backend chose, not caller data, and the concatenated form wrote
        ``LIMIT 20`` into the statement. Binding it would have changed the
        parameter tuple for a value nobody passes in.
        """
        from rhosocial.activerecord.backend.expression import Literal, QueryStatement
        from rhosocial.activerecord.backend.expression.query_parts import LimitOffsetClause

        query = QueryStatement(
            self,
            select=[
                self._column("database"),
                self._column("table"),
                self._column("is_leader"),
                self._column("is_readonly"),
                self._column("total_replicas"),
            ],
            from_=self._system_source("replicas"),
            limit_offset=(
                LimitOffsetClause(self, limit=Literal(self, expr.limit, inline=True))
                if expr.limit is not None
                else None
            ),
        )
        return query.to_sql()

    # ========== Mutation pre-count ==========

    def format_clickhouse_row_count_query(
        self, expr: "ClickHouseRowCountQuery"
    ) -> Tuple[str, tuple]:
        """``SELECT count()`` over the predicate a mutation is about to apply."""
        from rhosocial.activerecord.backend.expression import (
            NamedRelationRef,
            QueryStatement,
            WhereClause,
        )
        from rhosocial.activerecord.backend.expression.functions.aggregate import count
        from rhosocial.activerecord.backend.expression.objects import Table

        query = QueryStatement(
            self,
            select=[count(self, "*")],
            from_=NamedRelationRef(
                self, Table(self, expr.table, catalog_name=expr.schema_name)
            ),
            where=WhereClause(self, expr.where),
        )
        return query.to_sql()

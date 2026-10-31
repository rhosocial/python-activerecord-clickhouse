# src/rhosocial/activerecord/backend/impl/clickhouse/expression/status.py
"""ClickHouse status-introspection expressions.

The status introspector held the catalog SQL itself: f-strings assembled at the
call site, and `SELECT ... WHERE x IN (` + placeholders built by counting a
list's length. A SQL string is a formatting artefact, so it belongs to the
dialect formatter, not to the layer that executes the query
(expression-dialect §16.2): the node collects the parameters, the formatter
writes the text, and the introspector only constructs and executes.

Each node therefore carries only the parameters its query needs. Where the old
text bound a name list, the node binds the same list in the same order; where
the old text compared a name inline, the node takes it as a bound value.

The names are inventories, not claims: every list a caller passes here is a
shortlist, and the server's intersection with it is what comes back.

Every class here declares its own formatter. The five inventory reads share a
shape, but sharing it through a common base would put an intermediate class in
the tree that has no kind and no formatter -- a node-shaped thing that can
never render. The shape is therefore written out per class, which is also what
lets each one's projection differ without a mode parameter.
"""

from typing import List, Optional, Sequence, TYPE_CHECKING

from rhosocial.activerecord.backend.expression.bases import BaseExpression

if TYPE_CHECKING:  # pragma: no cover
    from rhosocial.activerecord.backend.dialect import SQLDialectBase
    from rhosocial.activerecord.backend.expression.bases import SQLPredicate


__all__ = [
    "ClickHouseSettingsQuery",
    "ClickHouseServerSettingsQuery",
    "ClickHouseMetricsQuery",
    "ClickHouseEventsQuery",
    "ClickHouseAsynchronousMetricsQuery",
    "ClickHouseConnectionGaugesQuery",
    "ClickHouseServerSettingQuery",
    "ClickHouseSettingQuery",
    "ClickHouseConnectionProbeQuery",
    "ClickHouseDatabaseTotalSizeQuery",
    "ClickHouseDiskListQuery",
    "ClickHouseTableCountQuery",
    "ClickHouseUserListQuery",
    "ClickHouseGrantListQuery",
    "ClickHouseRoleGrantListQuery",
    "ClickHouseCurrentUserQuery",
    "ClickHouseVersionQuery",
    "ClickHouseProcessListQuery",
    "ClickHouseReplicaListQuery",
    "ClickHouseRowCountQuery",
]


class ClickHouseSettingsQuery(BaseExpression):
    """Rows of ``system.settings`` for the requested names."""

    def __init__(self, dialect: "SQLDialectBase", names: Sequence[str]):
        super().__init__(dialect)
        self.names: List[str] = list(names)

    @property
    def format_method(self) -> str:
        """The dialect formatting method that renders this expression."""
        return "format_clickhouse_settings_query"


class ClickHouseServerSettingsQuery(BaseExpression):
    """Rows of ``system.server_settings`` for the requested names."""

    def __init__(self, dialect: "SQLDialectBase", names: Sequence[str]):
        super().__init__(dialect)
        self.names: List[str] = list(names)

    @property
    def format_method(self) -> str:
        """The dialect formatting method that renders this expression."""
        return "format_clickhouse_server_settings_query"


class ClickHouseMetricsQuery(BaseExpression):
    """Gauge rows of ``system.metrics`` for the requested names."""

    def __init__(self, dialect: "SQLDialectBase", names: Sequence[str]):
        super().__init__(dialect)
        self.names: List[str] = list(names)

    @property
    def format_method(self) -> str:
        """The dialect formatting method that renders this expression."""
        return "format_clickhouse_metrics_query"


class ClickHouseEventsQuery(BaseExpression):
    """Counter rows of ``system.events`` for the requested names."""

    def __init__(self, dialect: "SQLDialectBase", names: Sequence[str]):
        super().__init__(dialect)
        self.names: List[str] = list(names)

    @property
    def format_method(self) -> str:
        """The dialect formatting method that renders this expression."""
        return "format_clickhouse_events_query"


class ClickHouseAsynchronousMetricsQuery(BaseExpression):
    """Sampled rows of ``system.asynchronous_metrics`` for the requested names."""

    def __init__(self, dialect: "SQLDialectBase", names: Sequence[str]):
        super().__init__(dialect)
        self.names: List[str] = list(names)

    @property
    def format_method(self) -> str:
        """The dialect formatting method that renders this expression."""
        return "format_clickhouse_asynchronous_metrics_query"


class ClickHouseConnectionGaugesQuery(BaseExpression):
    """``metric``/``value`` rows of ``system.metrics`` for the requested names.

    Its own node rather than a flag on :class:`ClickHouseMetricsQuery`: the
    projection is narrower (two columns, no description), and a parameter that
    selects a projection is the "mode" field one contract per formatter exists
    to keep out.
    """

    def __init__(self, dialect: "SQLDialectBase", names: Sequence[str]):
        super().__init__(dialect)
        self.names: List[str] = list(names)

    @property
    def format_method(self) -> str:
        """The dialect formatting method that renders this expression."""
        return "format_clickhouse_connection_gauges_query"


class ClickHouseServerSettingQuery(BaseExpression):
    """One ``name``/``value`` row of ``system.server_settings``."""

    def __init__(self, dialect: "SQLDialectBase", name: str):
        super().__init__(dialect)
        self.name = name

    @property
    def format_method(self) -> str:
        """The dialect formatting method that renders this expression."""
        return "format_clickhouse_server_setting_query"


class ClickHouseSettingQuery(BaseExpression):
    """One ``value`` row of ``system.settings``.

    The session-level counterpart of :class:`ClickHouseServerSettingQuery`: a
    setting a query or the session can change lives in ``system.settings``, and
    ``system.server_settings`` returns no row for it.
    """

    def __init__(self, dialect: "SQLDialectBase", name: str):
        super().__init__(dialect)
        self.name = name

    @property
    def format_method(self) -> str:
        """The dialect formatting method that renders this expression."""
        return "format_clickhouse_setting_query"


class ClickHouseConnectionProbeQuery(BaseExpression):
    """The liveness probe: a scalar ``SELECT 1`` with no relation.

    A connection check is a statement like any other, and the backend's health
    check sends it. There is nothing to bind and nothing to name -- just a value
    position -- so the node holds no parameters and the formatter writes the
    constant.
    """

    def __init__(self, dialect: "SQLDialectBase"):
        super().__init__(dialect)

    @property
    def format_method(self) -> str:
        """The dialect formatting method that renders this expression."""
        return "format_clickhouse_connection_probe_query"


class ClickHouseDatabaseTotalSizeQuery(BaseExpression):
    """Total on-disk size of one database's tables."""

    def __init__(self, dialect: "SQLDialectBase", database: str):
        super().__init__(dialect)
        self.database = database

    @property
    def format_method(self) -> str:
        """The dialect formatting method that renders this expression."""
        return "format_clickhouse_database_total_size_query"


class ClickHouseDiskListQuery(BaseExpression):
    """Every row of ``system.disks``, with its capacity and flags."""

    def __init__(self, dialect: "SQLDialectBase"):
        super().__init__(dialect)

    @property
    def format_method(self) -> str:
        """The dialect formatting method that renders this expression."""
        return "format_clickhouse_disk_list_query"


class ClickHouseTableCountQuery(BaseExpression):
    """Table and view counts per database, from ``information_schema.TABLES``."""

    def __init__(self, dialect: "SQLDialectBase", schemas: Sequence[str]):
        super().__init__(dialect)
        self.schemas: List[str] = list(schemas)

    @property
    def format_method(self) -> str:
        """The dialect formatting method that renders this expression."""
        return "format_clickhouse_table_count_query"


class ClickHouseUserListQuery(BaseExpression):
    """Every row of ``system.users``."""

    def __init__(self, dialect: "SQLDialectBase"):
        super().__init__(dialect)

    @property
    def format_method(self) -> str:
        """The dialect formatting method that renders this expression."""
        return "format_clickhouse_user_list_query"


class ClickHouseGrantListQuery(BaseExpression):
    """Database- and table-scoped grants, from ``system.grants``."""

    def __init__(self, dialect: "SQLDialectBase"):
        super().__init__(dialect)

    @property
    def format_method(self) -> str:
        """The dialect formatting method that renders this expression."""
        return "format_clickhouse_grant_list_query"


class ClickHouseRoleGrantListQuery(BaseExpression):
    """Granted roles, from ``system.role_grants``."""

    def __init__(self, dialect: "SQLDialectBase"):
        super().__init__(dialect)

    @property
    def format_method(self) -> str:
        """The dialect formatting method that renders this expression."""
        return "format_clickhouse_role_grant_list_query"


class ClickHouseCurrentUserQuery(BaseExpression):
    """The user this session authenticates as."""

    def __init__(self, dialect: "SQLDialectBase"):
        super().__init__(dialect)

    @property
    def format_method(self) -> str:
        """The dialect formatting method that renders this expression."""
        return "format_clickhouse_current_user_query"


class ClickHouseVersionQuery(BaseExpression):
    """The server's own version string."""

    def __init__(self, dialect: "SQLDialectBase"):
        super().__init__(dialect)

    @property
    def format_method(self) -> str:
        """The dialect formatting method that renders this expression."""
        return "format_clickhouse_version_query"


class ClickHouseProcessListQuery(BaseExpression):
    """The running queries, from ``system.processes``."""

    def __init__(self, dialect: "SQLDialectBase"):
        super().__init__(dialect)

    @property
    def format_method(self) -> str:
        """The dialect formatting method that renders this expression."""
        return "format_clickhouse_process_list_query"


class ClickHouseReplicaListQuery(BaseExpression):
    """Replication summary rows from ``system.replicas``."""

    def __init__(self, dialect: "SQLDialectBase", limit: Optional[int] = None):
        super().__init__(dialect)
        self.limit = limit

    @property
    def format_method(self) -> str:
        """The dialect formatting method that renders this expression."""
        return "format_clickhouse_replica_list_query"


class ClickHouseRowCountQuery(BaseExpression):
    """How many rows a predicate matches, as ``SELECT count()``.

    ClickHouse reports no affected-row count for a mutation, so the backend
    pre-counts with this read. The predicate is the same node the mutation
    carries -- it is not re-derived from text, which is what the concatenated
    form did (it rendered the WHERE clause and then stripped the word back off
    the front).
    """

    def __init__(
        self,
        dialect: "SQLDialectBase",
        table: str,
        where: "SQLPredicate",
        schema_name: Optional[str] = None,
    ):
        super().__init__(dialect)
        self.table = table
        self.where = where
        self.schema_name = schema_name

    @property
    def format_method(self) -> str:
        """The dialect formatting method that renders this expression."""
        return "format_clickhouse_row_count_query"

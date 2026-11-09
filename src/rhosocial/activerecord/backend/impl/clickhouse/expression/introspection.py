# src/rhosocial/activerecord/backend/impl/clickhouse/expression/introspection.py
"""ClickHouse backend-specific introspection expressions.

The core introspection protocol has statements for tables, columns, indexes,
views and triggers. ClickHouse has more facts worth asking its own catalog
about, and no core statement shape for them:

* a table's parts, grouped into partitions (``system.parts``);
* the storage definition a table was created with (``system.tables``);
* the server-wide catalogues: functions, dictionaries, clusters, quotas,
  users and roles.

Each node carries only its parameters, as every other expression in this
backend does (expression-dialect §16.2): the dialect writes the statement, the
introspector constructs and executes it. The formatters live in
``..mixins.introspection``, beside the core introspection formatters they share
their building blocks with.

The parameter is named ``database`` rather than ``schema`` on purpose:
ClickHouse has no schema layer, and its top-level namespace is a database. See
``..introspection.types`` for the full statement of that naming rule.
"""

from typing import TYPE_CHECKING, Optional

from rhosocial.activerecord.backend.expression.bases import BaseExpression

if TYPE_CHECKING:  # pragma: no cover
    from rhosocial.activerecord.backend.dialect import SQLDialectBase


__all__ = [
    "ClickHouseTableEngineQuery",
    "ClickHouseTablePartitionsQuery",
    "ClickHouseFunctionListQuery",
    "ClickHouseDictionaryListQuery",
    "ClickHouseClusterListQuery",
    "ClickHouseQuotaListQuery",
    "ClickHouseUserListQuery",
    "ClickHouseRoleListQuery",
]


class ClickHouseTablePartitionsQuery(BaseExpression):
    """Active parts of one table, aggregated per ``partition_id``."""

    def __init__(self, dialect: "SQLDialectBase", database: str, table: str):
        super().__init__(dialect)
        self.database = database
        self.table = table

    @property
    def format_method(self) -> str:
        """The dialect formatting method that renders this expression."""
        return "format_clickhouse_table_partitions_query"


class ClickHouseTableEngineQuery(BaseExpression):
    """The storage definition of one table, from ``system.tables``."""

    def __init__(self, dialect: "SQLDialectBase", database: str, table: str):
        super().__init__(dialect)
        self.database = database
        self.table = table

    @property
    def format_method(self) -> str:
        """The dialect formatting method that renders this expression."""
        return "format_clickhouse_table_engine_query"


class ClickHouseFunctionListQuery(BaseExpression):
    """Every function the server exposes, or the rows matching one name.

    ``system.functions`` is a server-wide catalogue rather than a
    database-scoped one, so there is no database parameter. A name narrows
    the listing instead of selecting a single row, because a name can also
    be an alias of another function and the catalogue reports both.
    """

    def __init__(self, dialect: "SQLDialectBase", name: Optional[str] = None):
        super().__init__(dialect)
        self.name = name

    @property
    def format_method(self) -> str:
        """The dialect formatting method that renders this expression."""
        return "format_clickhouse_function_list_query"


class ClickHouseDictionaryListQuery(BaseExpression):
    """Every dictionary the server reported, or the rows matching a name.

    ``database`` is an optional filter because the catalogue holds
    configuration-file dictionaries (database ``''``) beside DDL dictionaries
    (a real database name). ``None`` means "do not filter by database".
    """

    def __init__(
        self,
        dialect: "SQLDialectBase",
        name: Optional[str] = None,
        database: Optional[str] = None,
    ):
        super().__init__(dialect)
        self.name = name
        self.database = database

    @property
    def format_method(self) -> str:
        """The dialect formatting method that renders this expression."""
        return "format_clickhouse_dictionary_list_query"


class ClickHouseClusterListQuery(BaseExpression):
    """Every shard/replica member in ``system.clusters``.

    A name narrows the listing to one cluster; it does not select a single
    member, because a cluster is one or more rows and the listing keeps all
    of them together.
    """

    def __init__(self, dialect: "SQLDialectBase", name: Optional[str] = None):
        super().__init__(dialect)
        self.name = name

    @property
    def format_method(self) -> str:
        """The dialect formatting method that renders this expression."""
        return "format_clickhouse_cluster_list_query"


class ClickHouseQuotaListQuery(BaseExpression):
    """Every quota in ``system.quotas``, optionally narrowed by name."""

    def __init__(self, dialect: "SQLDialectBase", name: Optional[str] = None):
        super().__init__(dialect)
        self.name = name

    @property
    def format_method(self) -> str:
        """The dialect formatting method that renders this expression."""
        return "format_clickhouse_quota_list_query"


class ClickHouseUserListQuery(BaseExpression):
    """Every account in ``system.users``, optionally narrowed by name."""

    def __init__(self, dialect: "SQLDialectBase", name: Optional[str] = None):
        super().__init__(dialect)
        self.name = name

    @property
    def format_method(self) -> str:
        """The dialect formatting method that renders this expression."""
        return "format_clickhouse_introspection_user_list_query"


class ClickHouseRoleListQuery(BaseExpression):
    """Every role in ``system.roles``, optionally narrowed by name."""

    def __init__(self, dialect: "SQLDialectBase", name: Optional[str] = None):
        super().__init__(dialect)
        self.name = name

    @property
    def format_method(self) -> str:
        """The dialect formatting method that renders this expression."""
        return "format_clickhouse_role_list_query"

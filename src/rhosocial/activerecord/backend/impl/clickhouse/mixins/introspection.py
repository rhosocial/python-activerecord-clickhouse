# src/rhosocial/activerecord/backend/impl/clickhouse/mixins/introspection.py
from typing import List, Optional, Tuple, TYPE_CHECKING

if TYPE_CHECKING:
    from rhosocial.activerecord.backend.introspection.types import IntrospectionScope
    from rhosocial.activerecord.backend.expression.introspection import (
        DatabaseInfoExpression,
        TableListExpression,
        ColumnInfoExpression,
        IndexInfoExpression,
        ForeignKeyExpression,
        ViewListExpression,
        ViewInfoExpression,
        TriggerListExpression,
    )


class ClickHouseIntrospectionMixin:
    """ClickHouse introspection capability declaration and query formatting.

    This mixin implements the IntrospectionSupport protocol by:
    1. Declaring which introspection features ClickHouse supports (supports_* methods)
    2. Formatting SQL queries for introspection (format_*_query methods)

    The format_*_query methods are called by Expression.to_sql() to generate
    database-specific SQL using the ClickHouse system database
    (system.databases, system.tables, system.columns,
    system.data_skipping_indices).

    Architecture flow:
        Introspector._build_*_sql() [base class]
            → Expression(Dialect).to_sql()
                → Dialect.format_*_query() [this mixin]
                    → Returns SQL and parameters

    Every query here is a :class:`~...expression.statements.dql.QueryStatement`
    tree: the projection, the conjunction of conditions and the ordering are
    nodes, and this module only decides *what* is asked. A string assembled one
    clause at a time showed no single place the query existed, and its bind
    parameters were counted by hand (`offset=len(sql_params)`) -- a count that
    had to be kept in step with every branch above it. The tree carries the
    order instead, because a `Literal` either binds or inlines at its own
    position and the formatter concatenates the parameters in projection order
    (expression-dialect §16.2).

    Which values bind and which inline is exactly what the concatenated form
    did, so the parameter tuples stay byte-identical: the schema/table/view
    names and the engine list are bound, while the fixed SQL words (`'system'`,
    the view-engine exclusion, the constant projection cells) are inline.

    ClickHouse supports introspection via system tables. Foreign key and
    trigger introspection are NOT supported (ClickHouse has neither FKs nor
    triggers), so those supports_* methods return False.

    The projection aliases (``AS TABLE_NAME`` and friends) are kept because the
    result parsers upstream read those names; the sources are ClickHouse's own
    ``system.*`` tables. Foreign-key and trigger queries have no ClickHouse
    system table at all and raise.
    """

    # ========== Capability Detection ==========

    def supports_introspection(self) -> bool:
        """ClickHouse supports introspection via system tables."""
        return True

    def supports_database_info(self) -> bool:
        """ClickHouse supports database info via system.databases."""
        return True

    def supports_table_introspection(self) -> bool:
        """ClickHouse supports table introspection via system.tables."""
        return True

    def supports_column_introspection(self) -> bool:
        """ClickHouse supports column introspection via system.columns."""
        return True

    def supports_index_introspection(self) -> bool:
        """ClickHouse supports index introspection via system.data_skipping_indices."""
        return True

    def supports_foreign_key_introspection(self) -> bool:
        """ClickHouse does not support foreign keys, so no FK introspection."""
        return False

    def supports_view_introspection(self) -> bool:
        """ClickHouse supports view introspection via system.tables."""
        return True

    def supports_trigger_introspection(self) -> bool:
        """ClickHouse does not support triggers, so no trigger introspection."""
        return False

    def get_supported_introspection_scopes(self) -> List["IntrospectionScope"]:
        """Get list of supported introspection scopes."""
        from rhosocial.activerecord.backend.introspection.types import IntrospectionScope

        return [
            IntrospectionScope.DATABASE,
            IntrospectionScope.TABLE,
            IntrospectionScope.COLUMN,
            IntrospectionScope.INDEX,
            IntrospectionScope.VIEW,
        ]

    # ========== Shared building blocks ==========

    def _system_relation(self, name: str):
        """One ClickHouse ``system`` table as a ``FROM`` source.

        ClickHouse qualifies an object with the database alone, and the object
        carries it in ``catalog_name`` (see ``ClickHouseNamespaceMixin``), so
        ``system.tables`` is a table named ``tables`` in the ``system``
        catalog. Writing the dotted name as one opaque string would put a
        namespace into an identifier, which is the one thing the object model
        exists to keep apart.
        """
        from rhosocial.activerecord.backend.expression import NamedRelationRef
        from rhosocial.activerecord.backend.expression.objects import Table

        return NamedRelationRef(self, Table(self, name, catalog_name="system"))

    def _column(self, name: str, alias: Optional[str] = None):
        """A ``system.*`` column, optionally projected under another name."""
        from rhosocial.activerecord.backend.expression import Column

        return Column(self, name, alias=alias)

    def _equals(self, left, right):
        """``left = right`` as a predicate node."""
        from rhosocial.activerecord.backend.expression import ComparisonPredicate

        return ComparisonPredicate(self, "eq", left, right)

    def _not_equals(self, left, right):
        """``left <> right`` as a predicate node."""
        from rhosocial.activerecord.backend.expression import ComparisonPredicate

        return ComparisonPredicate(self, "ne", left, right)

    def _all_of(self, *predicates):
        """The conjunction of the given predicates, or ``None`` when there are none."""
        from rhosocial.activerecord.backend.expression import LogicalPredicate

        kept = [p for p in predicates if p is not None]
        if not kept:
            return None
        return LogicalPredicate(self, "AND", *kept)

    def _where(self, *predicates):
        """A ``WhereClause`` over the conjunction, or ``None`` for an unfiltered read."""
        from rhosocial.activerecord.backend.expression import WhereClause

        condition = self._all_of(*predicates)
        return None if condition is None else WhereClause(self, condition)

    def _order_by(self, *columns: str):
        """``ORDER BY`` over the named columns, in the order given."""
        from rhosocial.activerecord.backend.expression import OrderByClause

        return OrderByClause(self, [self._column(name) for name in columns])

    def _constant(self, value, alias: str, data_type):
        """A constant projection carrying *alias* and its declared type.

        A ``Literal`` has no name to give -- a literal is the one node in the
        tree with nothing to alias, because a bind parameter belongs to the
        driver and inline text is text. So a constant cell is cast to the type
        the position declares and the cast carries the alias. The type is the
        honest half of that: ``0 AS AUTO_INCREMENT`` reads back as whatever the
        engine decides a bare integer literal is, while the cast states the
        column's type as the parser expects it.
        """
        from rhosocial.activerecord.backend.expression import Literal
        from rhosocial.activerecord.backend.expression.core import CastExpression

        return CastExpression(
            self,
            Literal(self, value, inline=True),
            data_type,
            alias=alias,
        )

    def _text_constant(self, value: str, alias: str):
        """A string constant projection, typed ``String``."""
        from ..expression.types import ClickHouseStringType

        return self._constant(value, alias, ClickHouseStringType(self))

    def _int_constant(self, value: int, alias: str):
        """An integer constant projection, typed ``Int64``."""
        from ..expression.types import ClickHouseInt64Type

        return self._constant(value, alias, ClickHouseInt64Type(self))

    # ========== Query Formatting ==========

    def format_database_info_query(self, expr: "DatabaseInfoExpression") -> Tuple[str, tuple]:
        """Format database information query against ClickHouse system.databases.

        The engine is the only database-level "charset" ClickHouse reports, and
        there is no per-database collation, so the second cell is the empty
        string the parser reads as "none".
        """
        from rhosocial.activerecord.backend.expression import Literal, QueryStatement

        params = expr.get_params()
        schema = params.get("schema", "")

        query = QueryStatement(
            self,
            select=[
                self._column("engine", alias="DEFAULT_CHARACTER_SET_NAME"),
                self._text_constant("", "DEFAULT_COLLATION_NAME"),
            ],
            from_=self._system_relation("databases"),
            where=self._where(self._equals(self._column("name"), Literal(self, schema))),
        )
        return query.to_sql()

    def format_table_list_query(self, expr: "TableListExpression") -> Tuple[str, tuple]:
        """Format table list query against ClickHouse system.tables."""
        from rhosocial.activerecord.backend.expression import Literal, QueryStatement

        params = expr.get_params()
        schema = params.get("schema", "")
        include_views = params.get("include_views", True)
        include_system = params.get("include_system", False)
        table_type = params.get("table_type")

        conditions = [self._equals(self._column("database"), Literal(self, schema))]

        if not include_system:
            conditions.append(
                self._not_equals(self._column("database"), Literal(self, "system", inline=True))
            )
        if not include_views:
            # The set of engines that store a view is declared, not guessed at
            # with a substring match: `LIKE '%View'` also matched anything whose
            # engine name merely ended in "View", and said nothing about which
            # kinds were being included when `include_views` was true.
            conditions.append(self.engine_kind_predicate(include_views=False))
        if table_type:
            conditions.append(self._equals(self._column("engine"), Literal(self, table_type)))

        query = QueryStatement(
            self,
            select=[
                self._column("name", alias="TABLE_NAME"),
                self._column("engine", alias="TABLE_TYPE"),
                self._column("comment", alias="TABLE_COMMENT"),
                self._column("total_rows", alias="TABLE_ROWS"),
                self._column("total_bytes", alias="DATA_LENGTH"),
                self._int_constant(0, "AUTO_INCREMENT"),
                self._column("metadata_modification_time", alias="MODIFICATION_TIME"),
            ],
            from_=self._system_relation("tables"),
            where=self._where(*conditions),
            order_by=self._order_by("name"),
        )
        return query.to_sql()

    def format_column_info_query(self, expr: "ColumnInfoExpression") -> Tuple[str, tuple]:
        """Format column information query against ClickHouse system.columns.

        ``IS_NULLABLE`` is derived from the type name: ClickHouse encodes
        nullability in the type (``Nullable(String)``), not in a column flag, so
        the projection tests the rendered type for that prefix. The ``%`` is a
        single character in the pattern and the backend escapes it for the
        driver when it executes the statement -- writing ``%%`` here would be
        escaping for a layer this one does not talk to.
        """
        from rhosocial.activerecord.backend.expression import (
            FunctionCall,
            LikeOperator,
            LikePredicate,
            Literal,
            QueryStatement,
        )

        params = expr.get_params()
        table = params.get("table_name", "")
        schema = params.get("schema", "")

        query = QueryStatement(
            self,
            select=[
                self._column("name", alias="COLUMN_NAME"),
                self._column("position", alias="ORDINAL_POSITION"),
                self._column("default_expression", alias="COLUMN_DEFAULT"),
                FunctionCall(
                    self,
                    "IF",
                    LikePredicate(
                        self,
                        LikeOperator.LIKE,
                        self._column("type"),
                        Literal(self, "Nullable(%", inline=True),
                    ),
                    Literal(self, "YES", inline=True),
                    Literal(self, "NO", inline=True),
                    alias="IS_NULLABLE",
                ),
                self._column("type", alias="DATA_TYPE"),
                self._int_constant(0, "CHARACTER_MAXIMUM_LENGTH"),
                self._column("numeric_precision", alias="NUMERIC_PRECISION"),
                self._column("numeric_scale", alias="NUMERIC_SCALE"),
                self._column("type", alias="COLUMN_TYPE"),
                self._text_constant("", "COLUMN_KEY"),
                self._text_constant("", "EXTRA"),
                self._column("comment", alias="COLUMN_COMMENT"),
                self._text_constant("", "CHARACTER_SET_NAME"),
                self._text_constant("", "COLLATION_NAME"),
            ],
            from_=self._system_relation("columns"),
            where=self._where(
                self._equals(self._column("database"), Literal(self, schema)),
                self._equals(self._column("table"), Literal(self, table)),
            ),
            order_by=self._order_by("position"),
        )
        return query.to_sql()

    def format_index_info_query(self, expr: "IndexInfoExpression") -> Tuple[str, tuple]:
        """Format index information query against ClickHouse system.data_skipping_indices.

        ClickHouse's only index rows are the primary key (reported through
        ``SHOW INDEX``) and data skipping indices, which live here. The six
        constant cells restate what the engine does not have: no uniqueness, no
        prefixes, no packed form, no per-index nullability.
        """
        from rhosocial.activerecord.backend.expression import Literal, QueryStatement
        from ..expression.types import ClickHouseNullableType, ClickHouseStringType

        params = expr.get_params()
        table = params.get("table_name", "")
        schema = params.get("schema", "")

        query = QueryStatement(
            self,
            select=[
                self._column("name", alias="INDEX_NAME"),
                self._int_constant(0, "NON_UNIQUE"),
                self._int_constant(1, "SEQ_IN_INDEX"),
                self._text_constant("", "COLUMN_NAME"),
                self._column("type", alias="INDEX_TYPE"),
                self._constant(
                    None,
                    "SUB_PART",
                    ClickHouseNullableType(self, inner_type=ClickHouseStringType(self)),
                ),
                self._text_constant("YES", "NULLABLE"),
            ],
            from_=self._system_relation("data_skipping_indices"),
            where=self._where(
                self._equals(self._column("database"), Literal(self, schema)),
                self._equals(self._column("table"), Literal(self, table)),
            ),
            order_by=self._order_by("name"),
        )
        return query.to_sql()

    def format_foreign_key_query(self, expr: "ForeignKeyExpression") -> Tuple[str, tuple]:
        """ClickHouse has no foreign keys; raise UnsupportedFeatureError."""
        from rhosocial.activerecord.backend.dialect.exceptions import UnsupportedFeatureError

        raise UnsupportedFeatureError(
            "ClickHouse", "foreign key introspection",
            "ClickHouse does not support foreign keys."
        )

    def format_view_list_query(self, expr: "ViewListExpression") -> Tuple[str, tuple]:
        """Format view list query against ClickHouse system.tables (View engines)."""
        from rhosocial.activerecord.backend.expression import Literal, QueryStatement

        params = expr.get_params()
        schema = params.get("schema", "")
        include_system = params.get("include_system", False)

        conditions = [
            self._equals(self._column("database"), Literal(self, schema)),
            self.engine_kind_predicate(include_views=True),
        ]
        if not include_system:
            conditions.append(
                self._not_equals(self._column("database"), Literal(self, "system", inline=True))
            )

        query = QueryStatement(
            self,
            select=[
                self._column("name", alias="TABLE_NAME"),
                self._column("create_table_query", alias="VIEW_DEFINITION"),
                self._text_constant("NONE", "CHECK_OPTION"),
                self._text_constant("NO", "IS_UPDATABLE"),
            ],
            from_=self._system_relation("tables"),
            where=self._where(*conditions),
            order_by=self._order_by("name"),
        )
        return query.to_sql()

    def format_view_info_query(self, expr: "ViewInfoExpression") -> Tuple[str, tuple]:
        """Format single view information query against ClickHouse system.tables."""
        from rhosocial.activerecord.backend.expression import Literal, QueryStatement

        params = expr.get_params()
        view_name = params.get("view_name", "")
        schema = params.get("schema", "")

        query = QueryStatement(
            self,
            select=[
                self._column("name", alias="TABLE_NAME"),
                self._column("create_table_query", alias="VIEW_DEFINITION"),
                self._text_constant("NONE", "CHECK_OPTION"),
                self._text_constant("NO", "IS_UPDATABLE"),
            ],
            from_=self._system_relation("tables"),
            where=self._where(
                self._equals(self._column("database"), Literal(self, schema)),
                self._equals(self._column("name"), Literal(self, view_name)),
                self.engine_kind_predicate(include_views=True),
            ),
        )
        return query.to_sql()

    def format_trigger_list_query(self, expr: "TriggerListExpression") -> Tuple[str, tuple]:
        """ClickHouse has no triggers; raise UnsupportedFeatureError."""
        from rhosocial.activerecord.backend.dialect.exceptions import UnsupportedFeatureError

        raise UnsupportedFeatureError(
            "ClickHouse", "trigger introspection",
            "ClickHouse does not support triggers."
        )

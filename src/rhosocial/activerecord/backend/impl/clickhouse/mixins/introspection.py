# src/rhosocial/activerecord/backend/impl/clickhouse/mixins/introspection.py
from typing import TYPE_CHECKING, List, Optional, Tuple

from rhosocial.activerecord.backend.introspection.types import ProfileSource

if TYPE_CHECKING:
    from rhosocial.activerecord.backend.expression.introspection import (
        ColumnDataProfileQueryStatement,
        ColumnInfoQueryStatement,
        ColumnValueSampleQueryStatement,
        DatabaseInfoQueryStatement,
        ForeignKeyQueryStatement,
        IndexInfoQueryStatement,
        JoinCoverageQueryStatement,
        TableListQueryStatement,
        TriggerListQueryStatement,
        ViewInfoQueryStatement,
        ViewListQueryStatement,
    )
    from rhosocial.activerecord.backend.introspection.types import IntrospectionScope

    from ..expression.introspection import (
        ClickHouseClusterListQuery,
        ClickHouseDictionaryListQuery,
        ClickHouseFunctionListQuery,
        ClickHouseQuotaListQuery,
        ClickHouseRoleListQuery,
        ClickHouseTableEngineQuery,
        ClickHouseTablePartitionsQuery,
        ClickHouseUserListQuery,
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

    def supports_partition_introspection(self) -> bool:
        """ClickHouse answers for a table's partitions from ``system.parts``.

        The capability for the ``introspect partitions`` family. The
        parts view is live, so a partition with no active parts has
        nothing to report and the answer is aggregated."""
        return True

    def supports_table_engine_introspection(self) -> bool:
        """ClickHouse answers for a table's storage definition.

        The capability for the ``introspect table-engine`` family: the engine
        a table was created with and the key expressions it declares, which
        on this engine are the closest thing a schema has to a primary key.
        """
        return True

    def supports_function_introspection(self) -> bool:
        """The server publishes its function catalogue in ``system.functions``.

        The capability for the ``introspect functions`` family. The catalogue
        carries built-ins and the user-defined flavours in the same relation,
        distinguished by ``origin``; a server that has no functions at all still
        answers an empty list, which is an answer rather than an unsupported
        family.
        """
        return True

    def supports_dictionary_introspection(self) -> bool:
        """The server publishes loaded dictionaries in ``system.dictionaries``."""
        return True

    def supports_cluster_introspection(self) -> bool:
        """The server publishes configured clusters in ``system.clusters``."""
        return True

    def supports_quota_introspection(self) -> bool:
        """The server publishes quotas in ``system.quotas``."""
        return True

    def supports_user_introspection(self) -> bool:
        """The server publishes accounts in ``system.users``.

        Reading this relation needs the account to hold the relevant access
        rights; a server that refuses the query answers with an error rather
        than with an empty listing, and the CLI reports it as a failed query.
        The switch states that the catalogue exists, not that every caller may
        read it.
        """
        return True

    def supports_role_introspection(self) -> bool:
        """The server publishes roles in ``system.roles``."""
        return True

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

    def supports_table_storage_introspection(self) -> bool:
        """``system.tables.total_bytes`` answers a table's on-disk footprint.

        The capability for the per-table storage family. ClickHouse's storage
        is engine-shaped rather than row-plus-index shaped: bytes live in
        parts on disk, and skipping indices are sparse structures the engine
        maintains rather than a second copy of the data, so the common
        minimum's ``size_bytes`` is answered while ``data_size_bytes`` and
        ``index_size_bytes`` stay ``None`` -- which is the honest answer for a
        split this engine does not keep, not a gap. Finer facts (per-part
        ``bytes_on_disk``, the engine's own definition) stay on this
        backend's own types (``.claude/rules/introspection.md`` §5).
        """
        return True

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

    def _group_by(self, *columns: str):
        """``GROUP BY`` over the named columns, in the order given."""
        from rhosocial.activerecord.backend.expression import GroupByHavingClause

        return GroupByHavingClause(self, group_by=[self._column(name) for name in columns])

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

    def format_database_info_query_statement(
        self, expr: "DatabaseInfoQueryStatement"
    ) -> Tuple[str, tuple]:
        """Format database information query against ClickHouse system.databases.

        A ClickHouse database answers its name and its storage engine. It has
        no per-database character set and no per-database collation, so neither
        is projected: the previous form aliased the engine as
        ``DEFAULT_CHARACTER_SET_NAME`` and invented an empty collation, which
        reported two facts the server never answered.
        """
        from rhosocial.activerecord.backend.expression import Literal, QueryStatement

        params = expr.get_params()
        schema = params.get("schema", "")

        query = QueryStatement(
            self,
            select=[
                self._column("name", alias="DATABASE_NAME"),
                self._column("engine", alias="ENGINE"),
            ],
            from_=self._system_relation("databases"),
            where=self._where(self._equals(self._column("name"), Literal(self, schema))),
        )
        return query.to_sql()

    def format_table_list_query_statement(
        self, expr: "TableListQueryStatement"
    ) -> Tuple[str, tuple]:
        """Format table list query against ClickHouse system.tables."""
        from rhosocial.activerecord.backend.expression import Literal, QueryStatement

        params = expr.get_params()
        schema = params.get("schema", "")
        include_views = params.get("include_views", True)
        include_system = params.get("include_system", False)
        table_type = params.get("table_type")

        conditions = [self._equals(self._column("database"), Literal(self, schema))]

        # ``include_system`` excludes the engine's own database. Asking for
        # system tables by kind *is* that request already, so the exclusion is
        # not added: otherwise the two answers ("system" and "not system")
        # conjoin and no row can satisfy both.
        if not include_system and not self.is_system_table_type(table_type):
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
            conditions.append(self.table_type_predicate(table_type))

        query = QueryStatement(
            self,
            select=[
                self._column("name", alias="TABLE_NAME"),
                # The projection names the column the catalogue has. The kind
                # (base table / view / materialized view) is derived from this
                # engine by the parser; aliasing it as TABLE_TYPE made a
                # storage-engine name look like a standard table type.
                self._column("engine", alias="ENGINE"),
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

    def format_column_info_query_statement(
        self, expr: "ColumnInfoQueryStatement"
    ) -> Tuple[str, tuple]:
        """Format column information query against ClickHouse system.columns.

        ``IS_NULLABLE`` is derived from the type name: ClickHouse encodes
        nullability in the type (``Nullable(String)``), not in a column flag, so
        the projection tests the rendered type for that prefix.

        The ``%`` in that pattern is written doubled, and the doubling is
        load-bearing. The introspector executor executes this statement through
        a cursor directly rather than through ``Backend.execute``, so the
        backend's ``_escape_literal_percent`` -- which every other statement
        gains on the way to the driver -- does not run here. A single ``%``
        reaches clickhouse-connect's ``%`` interpolation and is read as the
        start of a format specifier: measured in CI,
        ``ValueError: unsupported format character "'" (0x27) at index 134``.
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
                        # Doubled on purpose. This statement is executed by the
                        # introspector executor, which calls ``cursor.execute``
                        # directly -- it does not pass through
                        # ``Backend.execute``, so the backend's
                        # ``_escape_literal_percent`` never runs on it and the
                        # driver's ``%`` interpolation would read a lone ``%`` as
                        # the start of a format specifier and raise
                        # ``ValueError: unsupported format character "'"``.
                        # Measured in CI on 3.10 / ClickHouse 25.8.
                        Literal(self, "Nullable(%%", inline=True),
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

    def format_index_info_query_statement(
        self, expr: "IndexInfoQueryStatement"
    ) -> Tuple[str, tuple]:
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

    def format_foreign_key_query_statement(
        self, expr: "ForeignKeyQueryStatement"
    ) -> Tuple[str, tuple]:
        """ClickHouse has no foreign keys; raise UnsupportedFeatureError."""
        from rhosocial.activerecord.backend.dialect.exceptions import UnsupportedFeatureError

        raise UnsupportedFeatureError(
            "ClickHouse", "foreign key introspection", "ClickHouse does not support foreign keys."
        )

    def format_view_list_query_statement(self, expr: "ViewListQueryStatement") -> Tuple[str, tuple]:
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

    def format_view_info_query_statement(self, expr: "ViewInfoQueryStatement") -> Tuple[str, tuple]:
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

    def format_trigger_list_query_statement(
        self, expr: "TriggerListQueryStatement"
    ) -> Tuple[str, tuple]:
        """ClickHouse has no triggers; raise UnsupportedFeatureError."""
        from rhosocial.activerecord.backend.dialect.exceptions import UnsupportedFeatureError

        raise UnsupportedFeatureError(
            "ClickHouse", "trigger introspection", "ClickHouse does not support triggers."
        )

    # ========== Data Profiles (row-shaped answers) ==========

    def supports_column_data_profile(self) -> bool:
        """ClickHouse answers a column profile by aggregating the rows.

        Nothing in ``system.*`` holds a per-column distribution to read.
        ``system.columns`` describes a column's declaration -- type, default,
        codec, comment -- ``system.parts`` describes how the data is stored on
        disk (part sizes, row counts, min/max *partition* values), and neither
        answers how many rows are NULL in one column or how many distinct values
        it holds. So the answer is computed from the rows, exact, and paid for
        in time: one arm per column, each a scan of the table.

        ``COUNT(DISTINCT ...)``, exact, rather than ``uniq`` or
        ``uniqCombined``. Those are this engine's approximate distinct counts,
        and the profile has no word for what they produce: ``aggregate`` would
        claim an exact count and ``sample`` would claim a subset of rows was
        read, while the approximation reads every row and rounds the answer.
        The exact form also keeps ``distinct_count == row_count`` usable as the
        uniqueness signal, which no estimate can carry.

        The profile also reports ``runtime_types`` -- the type names grouped
        over ``toTypeName(column)`` -- which is a fact about the data that only
        this backend can answer; see
        :class:`~..introspection.types.ClickHouseColumnDataProfile`.
        """
        return True

    def supports_column_value_sample(self) -> bool:
        """ClickHouse answers a value listing with a grouped scan and a limit.

        Nothing is precomputed, so this costs a ``GROUP BY`` over the column
        plus a sort of the groups. Kept a separate probe from the profile
        because the two are priced differently and one probe for both would
        make the cheap question pay the expensive answer's rate.
        """
        return True

    def supports_join_coverage(self) -> bool:
        """ClickHouse answers overlap by counting distinct values on both sides.

        Exact, and paid for with a scan of each column twice: once for the
        intersection, once for the denominator. ``COUNT(DISTINCT ...)`` is the
        engine's exact spelling, for the reason the profile probe records --
        ``uniq`` would be cheaper and would answer a different question.
        Answering ``True`` says the engine *can* answer, not that it answers
        cheaply.

        One limitation belongs with the probe rather than in a ``False``:
        ClickHouse compares values by their own type, so two columns with
        unrelated types compare as never equal and the fractions come back
        zero rather than failing. The number is then a correct statement about
        a join that would not match, not a measurement of one that would.
        """
        return True

    # ---- The profile's own building blocks ----

    def _user_relation(self, table_name: str, alias: str, database: Optional[str]):
        """A user table as a ``FROM`` source, quoted by the dialect.

        The opposite of :meth:`_system_relation`: a user table is whatever its
        owner declared, so the name and the database are left to the dialect's
        identifier renderer, and the alias is what tells the two sides of a
        coverage measurement apart.
        """
        from rhosocial.activerecord.backend.expression import NamedRelationRef
        from rhosocial.activerecord.backend.expression.objects import Table

        return NamedRelationRef(
            self,
            Table(self, table_name, catalog_name=database or None),
            alias=alias,
        )

    def _profile_label(self, text: Optional[str], alias: str):
        """A constant label as a named select-list entry.

        ``Literal`` is deliberately unaliasable -- a value has nothing to name
        -- so the constant is cast to ``String``, which is the smallest node
        that produces a named result. The cast is not there for its type: it is
        there so the label can be called ``column_name`` or ``source``, which
        is what the parser reads. ``None`` is the same node carrying SQL NULL,
        which is how the empty profile says "the column name is absent" without
        inventing one.
        """
        return self._text_constant(text, alias)

    def _profile_arm(self, table_name: str, database: Optional[str], column_name: str):
        """One column's arm of the profile, as a node.

        The eight entries are the family's contract plus this engine's own
        fact: the column's own name, the null count, the distinct count, the
        two endpoints, the row count the parser divides by, the provenance, and
        the runtime types.

        The null count is a ``SUM`` over a ``CASE`` rather than ``countIf``: the
        shared function formatter renders a name in upper case, and ``SUM`` and
        ``CASE`` are both spelled that way by the engine, while the conditional
        aggregates this engine spells in camel case are not names this
        formatter is known to produce correctly. ``SUM`` also makes an empty
        table answer 0, which the parser reads as "no fraction" because the row
        count is zero -- not as a column that holds no NULLs.

        ``COUNT(*)`` and the null count share a scan because they are two
        halves of one fraction; reading the table twice for them would double
        the cost of the cheapest part of the answer.

        ``groupUniqArray(toTypeName(...))`` is the runtime-type set. It is an
        aggregate over the same scan, so the fact costs no extra pass, and the
        order it returns is not defined -- the parser sorts it so two runs
        compare equal.

        Why the aggregates are spelled as they are is the rule this whole arm
        turns on: ClickHouse resolves a function name through its
        ``FunctionFactory`` / ``AggregateFunctionFactory``, which try an exact
        match first and then a *lowercased* match against a map holding only the
        names registered ``Case::Insensitive``. So ``SUM`` / ``COUNT`` / ``MIN``
        / ``MAX`` upper-case happily -- those four are registered insensitive,
        among a handful of SQL-standard spellings -- while ``GROUPUNIQARRAY``
        does not: ``groupUniqArray`` is registered ``Case::Sensitive``, the
        default, and every combinator suffix (``OrNull``, ``If``, ``State``) is
        matched against the tail of the name *as written*. An upper-cased
        camelCase name therefore matches neither map, and the server answers
        ``Function with name `MINORNULL` does not exist``. The renderer cannot
        know which map a name lands in, so this arm asks for the spellings that
        are registered, verbatim, through :meth:`_engine_function`.
        """
        from rhosocial.activerecord.backend.expression import (
            CaseExpression,
            Column,
            IsNullPredicate,
            Literal,
            QueryStatement,
            RowCountWildcard,
            SumFunction,
        )
        from rhosocial.activerecord.backend.expression.core import CastExpression
        from rhosocial.activerecord.backend.expression.functions import (
            CountFunction,
            max_,
            min_,
        )
        from rhosocial.activerecord.backend.expression.objects import Table

        from ..expression.types import ClickHouseNullableType, ClickHouseStringType

        column = Column(self, column_name)
        endpoint_type = ClickHouseNullableType(self, inner_type=ClickHouseStringType(self))

        def endpoint(aggregate, alias: str):
            """An endpoint as ``Nullable(String)``, for the union's sake.

            The cast is the union's price, explained on the statement formatter.

            ``MIN``/``MAX`` rather than ``minOrNull``/``maxOrNull``, and the
            difference is one figure for one kind of column: the plain
            aggregates answer with the *default of the result type* when no
            non-NULL value was ever accumulated, while the ``OrNull``
            combinator forces the NULL answer. So for a column that is
            entirely NULL -- ``note`` in the profile test, if every row were
            NULL rather than 40% of them -- ``MIN``/``MAX`` produce ``''`` and
            the cast leaves it as the empty string, where ``minOrNull`` would
            have produced NULL and the parser would have read ``None``. The
            profile's other two figures still say what happened: ``null_count``
            equals ``row_count`` and ``null_fraction`` is ``1.0``, so "every
            value is NULL" survives; what is lost is the endpoints' own claim
            to have measured no value. An empty table costs the same figure.

            The spellings are ``MIN``/``MAX`` because those two ``Case``-safe
            names are the ones the aggregate factory registers
            ``Case::Insensitive``, which is why the shared renderer's
            upper-casing is right here and nowhere else in this arm.
            """
            return CastExpression(self, aggregate, endpoint_type, alias=alias)

        return QueryStatement(
            self,
            select=[
                self._profile_label(column_name, "column_name"),
                SumFunction(
                    self,
                    CaseExpression(
                        self,
                        cases=[
                            (
                                IsNullPredicate(self, column),
                                Literal(self, 1, inline=True),
                            )
                        ],
                        else_result=Literal(self, 0, inline=True),
                    ),
                ).as_("null_count"),
                CountFunction(self, column, distinct=True).as_("distinct_count"),
                endpoint(min_(self, column), "min_value"),
                endpoint(max_(self, column), "max_value"),
                CountFunction(self, RowCountWildcard(self)).as_("row_count"),
                self._profile_label(ProfileSource.AGGREGATE.value, "source"),
                self._engine_function(
                    "groupUniqArray",
                    self._engine_function("toTypeName", column),
                    alias="runtime_types",
                ),
            ],
            from_=Table(self, table_name, catalog_name=database or None),
        )

    def format_column_data_profile_query_statement(
        self, expr: "ColumnDataProfileQueryStatement"
    ) -> Tuple[str, tuple]:
        """Format a per-column profile by aggregating the rows themselves.

        One arm per column, over the column list the expression carries: SQL
        cannot pivot ``SUM(CASE WHEN col IS NULL ...)`` across columns it was
        never told about, so an aggregating backend genuinely needs that list
        where a catalogue-based one does not.

        The one place in this module where a set operator is written as text.
        Every arm is a real :class:`~...statements.dql.QueryStatement` -- it
        owns its projection, its identifiers and its relation -- because a
        ``UNION ALL`` over a column list known only at run time has no node to
        represent it: the list is a tuple on the expression, not an operand in
        the tree. So each arm renders on its own, its parameters are
        concatenated in arm order, and the rendered arms are joined by the set
        operator's word.

        The aliases are lower case, unlike the catalogue statements above.
        ClickHouse keeps an identifier's case, so an alias comes back spelled
        exactly as it was written -- which makes the spelling a choice rather
        than something the engine decides, and the choice is the one the core
        parser reads. The catalogue statements are upper case because their
        parsers were written against the engine's own column names.

        An empty column list answers with no rows, read from ``system.one``
        rather than a bare ``SELECT``: ClickHouse allows a ``WHERE`` only over a
        source, and there is no user table to name here. A real table always has
        at least one column, so the branch exists for a statement that has to
        render, not for a case a caller can hit.

        Two consequences of the union are worth reading before the figures are.
        ClickHouse refuses a ``UNION ALL`` whose arms disagree on a column's
        type -- it looks for a supertype and raises when there is none -- so
        ``min_value``/``max_value`` are cast to ``Nullable(String)`` in every
        arm rather than left to be the column's own type. The figures are
        exact; the endpoints arrive as text, and the test reads a numeric one
        back through ``Decimal`` for that reason. One query per column would
        keep each type, at the price of a round trip per column, which is the
        loop this family exists to avoid. And one column whose type these
        aggregates refuse -- ``Array``, ``Map``, ``Tuple`` have no
        ``MIN``/``MAX`` and no ``COUNT(DISTINCT)`` in ClickHouse -- fails the
        whole statement rather than dropping that column's arm; a silently
        missing column would be a profile claiming a table has fewer columns
        than it does.
        """
        from rhosocial.activerecord.backend.expression import (
            Literal,
            QueryStatement,
        )

        params = expr.get_params()
        database = params.get("schema")

        arms = []
        parameters: list = []
        for name in expr.columns:
            sql, arm_parameters = self._profile_arm(
                params.get("table_name"), database, name
            ).to_sql()
            arms.append(sql)
            parameters.extend(arm_parameters)

        if not arms:
            return QueryStatement(
                self,
                select=[self._profile_label(None, "column_name")],
                from_=self._system_relation("one"),
                where=self._where(
                    self._equals(Literal(self, 1, inline=True), Literal(self, 0, inline=True))
                ),
            ).to_sql()

        return " UNION ALL ".join(arms), tuple(parameters)

    def format_column_value_sample_query_statement(
        self, expr: "ColumnValueSampleQueryStatement"
    ) -> Tuple[str, tuple]:
        """Format a most-frequent-values listing with a grouped scan.

        Nothing is precomputed, so this costs a ``GROUP BY`` over the column
        plus a sort of the groups -- the same order as the profile, which is why
        the two are separate probes rather than one call that would make the
        cheap half pay for the dear one.

        ``ORDER BY COUNT(*) DESC`` is what makes the answer "the most frequent
        values" rather than "the first values"; ties break by the value so two
        runs of the same query agree. ClickHouse groups NULLs into a real row,
        so a column holding NULLs has a NULL entry in its listing -- usually
        the most frequent one -- which is a shape the core parser accepts and
        the test pins, rather than a value this formatter filters out.

        The ``LIMIT`` is a bind parameter, as it is everywhere else in this
        dialect: the caller's integer is never spliced into statement text.
        """
        from rhosocial.activerecord.backend.expression import (
            Column,
            GroupByHavingClause,
            LimitOffsetClause,
            OrderByClause,
            QueryStatement,
            RowCountWildcard,
        )
        from rhosocial.activerecord.backend.expression.functions import (
            CountFunction,
        )
        from rhosocial.activerecord.backend.expression.objects import Table

        column = Column(self, expr.column_name)
        rows = CountFunction(self, RowCountWildcard(self))

        return QueryStatement(
            self,
            select=[column.as_("value"), rows.as_("count")],
            from_=Table(self, expr.table_name, catalog_name=expr.schema or None),
            group_by_having=GroupByHavingClause(self, group_by=[column]),
            order_by=OrderByClause(
                self,
                expressions=[
                    (CountFunction(self, RowCountWildcard(self)), "DESC"),
                    (Column(self, expr.column_name), "ASC"),
                ],
            ),
            limit_offset=LimitOffsetClause(self, limit=int(expr.limit)),
        ).to_sql()

    def _coverage_fraction(self, column, source, other_column, other_source):
        """One side of the overlap: the share of *column* the other side holds.

        The numerator counts the *distinct* values of *column* that also occur
        in *other_column*, as a ``COUNT(*)`` over a derived table of those
        distinct values; the denominator counts *column*'s distinct non-NULL
        values. Distinct on both sides is what makes the figure a coverage of
        values rather than of rows -- a key repeated a thousand times that
        matches once would otherwise read as well covered.

        ``IS NOT NULL`` is written on both halves rather than relied upon. In
        the numerator it is load-bearing: a DISTINCT treats a NULL as one
        value, so counting it would credit the tested side with a match it does
        not have. In the divisor ``COUNT(DISTINCT ...)`` skips NULLs on its
        own, but the statement says so explicitly, because the share is of the
        values that could join and that is the fact being measured.
        ``NULLIF(..., 0)`` then makes a column with no value at all answer NULL
        rather than 0, which the parser reads as "no fraction": the difference
        between "nothing matched" and "nothing to match" survives to the
        caller.

        No ``* 1.0`` here: ClickHouse's ``/`` over two integers already answers
        a floating-point share, so multiplying first would only add noise.
        """
        from rhosocial.activerecord.backend.expression import (
            FunctionCall,
            InPredicate,
            Literal,
            QueryStatement,
            RowCountWildcard,
            SelectModifier,
            Subquery,
        )
        from rhosocial.activerecord.backend.expression.functions import (
            CountFunction,
        )
        from rhosocial.activerecord.backend.expression.sources import (
            DerivedTableSource,
        )

        overlap = QueryStatement(
            self,
            select=[column],
            from_=source,
            where=self._where(
                column.is_not_null(),
                InPredicate(
                    self,
                    column,
                    Subquery(
                        self,
                        QueryStatement(
                            self,
                            select=[other_column],
                            from_=other_source,
                            where=self._where(other_column.is_not_null()),
                        ),
                    ),
                ),
            ),
            select_modifier=SelectModifier.DISTINCT,
        )
        covered = Subquery(
            self,
            QueryStatement(
                self,
                select=[CountFunction(self, RowCountWildcard(self))],
                from_=DerivedTableSource(self, overlap, alias="covered"),
            ),
        )
        total = Subquery(
            self,
            QueryStatement(
                self,
                select=[
                    FunctionCall(
                        self,
                        "NULLIF",
                        CountFunction(self, column, distinct=True),
                        Literal(self, 0, inline=True),
                    )
                ],
                from_=source,
                where=self._where(column.is_not_null()),
            ),
        )
        return covered / total

    def format_join_coverage_query_statement(
        self, expr: "JoinCoverageQueryStatement"
    ) -> Tuple[str, tuple]:
        """Format a two-sided measurement of two columns' value domains.

        Unlike every statement above, this one names two user tables rather
        than one ``system.*`` relation: the question is a relation between two
        objects, so both sides are carried explicitly and their identifiers are
        the dialect's to quote (see :meth:`_user_relation`). The aliases ``l``
        and ``r`` are what keep the two columns apart.

        The row carries both fractions because neither is meaningful alone: a
        left share of 1.0 beside a right share of 0.2 says every tested value
        exists on the other side while most of that other domain is
        unaccounted for, and one similarity score would average the two and
        describe neither.

        Both figures are counted over distinct values with NULLs excluded from
        the numerators and the denominators alike -- a NULL is not a value that
        could ever join -- and the denominators are ``NULLIF``-guarded so a
        column with nothing to match answers NULL, which the parser reports as
        "no measurement" instead of a zero overlap that would read as a real
        answer.

        The cost is each side read for its distinct domain plus the
        intersection of the two, which is why the probe is an explicit call and
        belongs in no automatic pass. Types are not reconciled: ClickHouse
        compares values by their own type, so unrelated types simply never
        match and the fractions are a genuine zero for that join, not a
        measurement of a conversion the engine did not perform.
        """
        from rhosocial.activerecord.backend.expression import Column, QueryStatement

        params = expr.get_params()
        database = params.get("schema")

        left_source = self._user_relation(params.get("left_table"), "l", database)
        right_source = self._user_relation(params.get("right_table"), "r", database)
        left_column = Column(self, params.get("left_column"), table="l")
        right_column = Column(self, params.get("right_column"), table="r")

        return QueryStatement(
            self,
            select=[
                self._coverage_fraction(left_column, left_source, right_column, right_source).as_(
                    "left_coverage"
                ),
                self._coverage_fraction(right_column, right_source, left_column, left_source).as_(
                    "right_coverage"
                ),
            ],
        ).to_sql()

    # ========== Backend-specific reads ==========

    def format_clickhouse_table_partitions_query(
        self, expr: "ClickHouseTablePartitionsQuery"
    ) -> Tuple[str, tuple]:
        """One row per partition of a table, aggregated from ``system.parts``.

        The filter ``active = 1`` is what makes the aggregate mean what it says.
        ``system.parts`` keeps a part until its replacement has been written and
        the old one is ready to be removed, so a table that has just merged
        reports both the sources and the result at once. Summing every row would
        then count the same rows twice; summing the active parts counts each row
        once, and ``COUNT(*)`` is the number of parts the partition currently
        consists of.

        ``min(partition)`` and ``min(engine)`` read the two group-invariant
        columns: every part of a partition carries the same readable partition
        value and the same engine, so the minimum is that value. ClickHouse's
        own ``any`` aggregate would say this more directly, but the shared
        function formatter upper-cases every function name and ClickHouse
        rejects ``ANY`` (measured on 26.7.3.19: ``Function with name `ANY` does
        not exist``), while ``MIN`` is accepted; a column outside the ``GROUP BY``
        still has to be aggregated, so it is read this way.
        """
        from rhosocial.activerecord.backend.expression import Literal, QueryStatement
        from rhosocial.activerecord.backend.expression.functions.aggregate import (
            count,
            max_,
            min_,
            sum_,
        )

        query = QueryStatement(
            self,
            select=[
                self._column("partition_id"),
                min_(self, self._column("partition"), alias="partition"),
                min_(self, self._column("engine"), alias="engine"),
                count(self, "*", alias="active_part_count"),
                sum_(self, self._column("rows"), alias="row_count"),
                sum_(self, self._column("bytes_on_disk"), alias="bytes_on_disk"),
                min_(self, self._column("modification_time"), alias="min_modification_time"),
                max_(self, self._column("modification_time"), alias="max_modification_time"),
            ],
            from_=self._system_relation("parts"),
            where=self._where(
                self._equals(self._column("database"), Literal(self, expr.database)),
                self._equals(self._column("table"), Literal(self, expr.table)),
                self._equals(self._column("active"), Literal(self, 1)),
            ),
            group_by_having=self._group_by("partition_id"),
            order_by=self._order_by("partition_id"),
        )
        return query.to_sql()

    def format_clickhouse_table_engine_query(
        self, expr: "ClickHouseTableEngineQuery"
    ) -> Tuple[str, tuple]:
        """The storage definition of one table, from ``system.tables``.

        One row is expected; a name that does not exist yields no rows, which is
        the introspector's ``None``. The key columns come back as the server
        stores them: an absent key is ``''``, not ``NULL``.
        """
        from rhosocial.activerecord.backend.expression import Literal, QueryStatement

        query = QueryStatement(
            self,
            select=[
                self._column("engine"),
                self._column("sorting_key"),
                self._column("primary_key"),
                self._column("partition_key"),
                self._column("sampling_key"),
                self._column("total_rows"),
                self._column("total_bytes"),
                self._column("comment"),
            ],
            from_=self._system_relation("tables"),
            where=self._where(
                self._equals(self._column("database"), Literal(self, expr.database)),
                self._equals(self._column("name"), Literal(self, expr.table)),
            ),
        )
        return query.to_sql()

    def format_clickhouse_function_list_query(
        self, expr: "ClickHouseFunctionListQuery"
    ) -> Tuple[str, tuple]:
        """The function catalogue, or one name's rows, from ``system.functions``.

        A name is a filter, not a key: ``alias_to`` means a single name can
        match an alias row beside the canonical one, and the catalogue is the
        only place that fact lives.
        """
        from rhosocial.activerecord.backend.expression import Literal, QueryStatement

        conditions = []
        if expr.name:
            conditions.append(self._equals(self._column("name"), Literal(self, expr.name)))

        query = QueryStatement(
            self,
            select=[
                self._column("name"),
                self._column("is_aggregate"),
                self._column("case_insensitive"),
                self._column("alias_to"),
                self._column("origin"),
                self._column("description"),
                self._column("syntax"),
                self._column("arguments"),
                self._column("categories"),
            ],
            from_=self._system_relation("functions"),
            where=self._where(*conditions),
            order_by=self._order_by("name"),
        )
        return query.to_sql()

    def format_clickhouse_dictionary_list_query(
        self, expr: "ClickHouseDictionaryListQuery"
    ) -> Tuple[str, tuple]:
        """Dictionary rows, from ``system.dictionaries``.

        The four dotted catalogue columns are aliased to the field names the
        parser reads. Quoting the whole dotted name is what keeps
        ``key.names`` one identifier on ClickHouse rather than a qualification
        the engine would try to resolve.
        """
        from rhosocial.activerecord.backend.expression import Literal, QueryStatement

        conditions = []
        if expr.name:
            conditions.append(self._equals(self._column("name"), Literal(self, expr.name)))
        if expr.database is not None:
            conditions.append(
                self._equals(self._column("database"), Literal(self, expr.database))
            )

        query = QueryStatement(
            self,
            select=[
                self._column("database"),
                self._column("name"),
                self._column("uuid"),
                self._column("status"),
                self._column("is_lazy"),
                self._column("origin"),
                self._column("type"),
                self._column("key.names", alias="key_names"),
                self._column("key.types", alias="key_types"),
                self._column("attribute.names", alias="attribute_names"),
                self._column("attribute.types", alias="attribute_types"),
                self._column("bytes_allocated"),
                self._column("element_count"),
                self._column("query_count"),
                self._column("hit_rate"),
                self._column("found_rate"),
                self._column("lifetime_min"),
                self._column("lifetime_max"),
                self._column("loading_start_time"),
                self._column("last_successful_update_time"),
                self._column("error_count"),
                self._column("last_exception"),
                self._column("comment"),
            ],
            from_=self._system_relation("dictionaries"),
            where=self._where(*conditions),
            order_by=self._order_by("database", "name"),
        )
        return query.to_sql()

    def format_clickhouse_cluster_list_query(
        self, expr: "ClickHouseClusterListQuery"
    ) -> Tuple[str, tuple]:
        """Cluster members, from ``system.clusters``.

        ``system.clusters`` is one row per shard/replica, so the ordering keeps
        a cluster's members adjacent and in the engine's own numbered order.
        """
        from rhosocial.activerecord.backend.expression import Literal, QueryStatement

        conditions = []
        if expr.name:
            conditions.append(self._equals(self._column("cluster"), Literal(self, expr.name)))

        query = QueryStatement(
            self,
            select=[
                self._column("cluster"),
                self._column("shard_num"),
                self._column("shard_name"),
                self._column("shard_weight"),
                self._column("internal_replication"),
                self._column("replica_num"),
                self._column("host_name"),
                self._column("host_address"),
                self._column("port"),
                self._column("is_local"),
                self._column("user"),
                self._column("default_database"),
                self._column("errors_count"),
                self._column("slowdowns_count"),
                self._column("estimated_recovery_time"),
            ],
            from_=self._system_relation("clusters"),
            where=self._where(*conditions),
            order_by=self._order_by("cluster", "shard_num", "replica_num"),
        )
        return query.to_sql()

    def format_clickhouse_quota_list_query(
        self, expr: "ClickHouseQuotaListQuery"
    ) -> Tuple[str, tuple]:
        """Quota rows, from ``system.quotas``, optionally one name."""
        from rhosocial.activerecord.backend.expression import Literal, QueryStatement

        conditions = []
        if expr.name:
            conditions.append(self._equals(self._column("name"), Literal(self, expr.name)))

        query = QueryStatement(
            self,
            select=[
                self._column("name"),
                self._column("id"),
                self._column("storage"),
                self._column("keys"),
                self._column("durations"),
                self._column("apply_to_all"),
                self._column("apply_to_list"),
                self._column("apply_to_except"),
                self._column("ipv4_prefix_bits"),
                self._column("ipv6_prefix_bits"),
            ],
            from_=self._system_relation("quotas"),
            where=self._where(*conditions),
            order_by=self._order_by("name"),
        )
        return query.to_sql()

    def format_clickhouse_introspection_user_list_query(
        self, expr: "ClickHouseUserListQuery"
    ) -> Tuple[str, tuple]:
        """Account rows, from ``system.users``, optionally one name.

        Credential material is not projected: the family reports which
        authentication methods an account accepts, not the parameters that
        would describe a secret.
        """
        from rhosocial.activerecord.backend.expression import Literal, QueryStatement

        conditions = []
        if expr.name:
            conditions.append(self._equals(self._column("name"), Literal(self, expr.name)))

        query = QueryStatement(
            self,
            select=[
                self._column("name"),
                self._column("id"),
                self._column("storage"),
                self._column("auth_type"),
                self._column("default_roles_all"),
                self._column("default_roles_list"),
                self._column("default_roles_except"),
                self._column("grantees_any"),
                self._column("grantees_list"),
                self._column("grantees_except"),
                self._column("default_database"),
                self._column("host_ip"),
                self._column("host_names"),
                self._column("host_names_regexp"),
                self._column("host_names_like"),
            ],
            from_=self._system_relation("users"),
            where=self._where(*conditions),
            order_by=self._order_by("name"),
        )
        return query.to_sql()

    def format_clickhouse_role_list_query(
        self, expr: "ClickHouseRoleListQuery"
    ) -> Tuple[str, tuple]:
        """Role rows, from ``system.roles``, optionally one name."""
        from rhosocial.activerecord.backend.expression import Literal, QueryStatement

        conditions = []
        if expr.name:
            conditions.append(self._equals(self._column("name"), Literal(self, expr.name)))

        query = QueryStatement(
            self,
            select=[
                self._column("name"),
                self._column("id"),
                self._column("storage"),
            ],
            from_=self._system_relation("roles"),
            where=self._where(*conditions),
            order_by=self._order_by("name"),
        )
        return query.to_sql()

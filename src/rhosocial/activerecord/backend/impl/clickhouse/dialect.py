# src/rhosocial/activerecord/backend/impl/clickhouse/dialect.py
"""
ClickHouse backend SQL dialect implementation.

This dialect implements protocols for features that ClickHouse actually supports,
based on the ClickHouse version provided at initialization.
"""

from typing import Optional, Tuple, TYPE_CHECKING

from rhosocial.activerecord.backend.dialect.base import SQLDialectBase
from rhosocial.activerecord.backend.dialect.protocols import (
    CollationSupport,
    CTESupport,
    FilterClauseSupport,
    WindowFunctionSupport,
    ReturningSupport,
    AdvancedGroupingSupport,
    ArraySupport,
    ExplainSupport,
    GraphSupport,
    MergeSupport,
    OrderedSetAggregationSupport,
    QualifyClauseSupport,
    TemporalTableSupport,
    UpsertSupport,
    LateralJoinSupport,
    WildcardSupport,
    JoinSupport,
    # Named objects: naming one, not creating or dropping it.
    ViewObjectSupport,
    MaterializedViewObjectSupport,
    TableObjectSupport,
    IndexObjectSupport,
    SequenceObjectSupport,
    TriggerObjectSupport,
    RoutineObjectSupport,
    TypeObjectSupport,
    SynonymObjectSupport,
    ForeignTableObjectSupport,
    NamespaceSupport,
    # DDL statement protocols
    CreateTypeSupport,
    AlterTypeSupport,
    DropTypeSupport,
    CreateDomainSupport,
    AlterDomainSupport,
    DropDomainSupport,
    AutoIncrementColumnSupport,
    IdentityColumnSupport,
    ConstraintSupport,
    IntrospectionSupport,
    TruncateSupport,
    TransactionControlSupport,
    SQLFunctionSupport,
    DataTypeSupport,
    ColumnAttributeSupport,
)
from rhosocial.activerecord.backend.dialect.mixins import (
    # The object tree: each *NameMixin renders one object kind and inherits
    # NamespaceMixin for the namespace levels, so they precede it.
    RelationSourceMixin,
    NamespaceMixin,
    TableObjectMixin,
    ViewObjectMixin,
    MaterializedViewObjectMixin,
    ForeignTableObjectMixin,
    IndexObjectMixin,
    SequenceObjectMixin,
    TriggerObjectMixin,
    RoutineObjectMixin,
    TypeObjectMixin,
    SynonymObjectMixin,
    SchemaNameMixin,
    DatabaseNameMixin,
    PropertyGraphNameMixin,
    CollationMixin,
    CTEMixin,

    WindowFunctionMixin,
    JSONMixin,

    ArrayMixin,
    ExplainMixin,
    GraphMixin,

    MergeMixin,

    TemporalTableMixin,
    UpsertMixin,
    LateralJoinMixin,
    JoinMixin,
    ViewMixin,
    IndexMixin,
    AutoIncrementColumnMixin,
    IdentityColumnMixin,
    TableMixin,
    ConstraintMixin,
    TriggerMixin,
    TruncateMixin,
    IntrospectionMixin,
    PartitionMixin,
    PredicateMixin,
    ExpressionMixin,
    DateTimeMixin,
    DQLMixin,
    DMLMixin,
    DDLColumnMixin,
    # ColumnAttributeSupport gained two members that no longer come from
    # DDLColumnMixin. Compose core's standalone mixin so ClickHouseDialect
    # still satisfies the protocol it declares; it precedes DDLColumnMixin's
    # format_column_attributes() caller in the MRO.
    ColumnAttributeMixin,
    UserDefinedTypeMixin,
    DomainMixin,
    TransactionControlMixin,
    SetOperationMixin,
    # ``LPAD``/``RPAD``/``REPEAT`` are nodes with default formatters, and
    # ClickHouse spells all three natively -- the aliases ``lpad``/``rpad`` of
    # ``leftPad``/``rightPad`` (21.8+) and ``repeat`` (20.1+) -- so the shared
    # defaults are the answer for those three and no override is needed.
    # ``TRIM`` is the one that differs; see ClickHouseTrimMixin.
    LpadMixin,
    RepeatMixin,
    RpadMixin,
    TrimMixin,
)
from rhosocial.activerecord.backend.suggestion.protocols import (
    ColumnTypeSuggestionSupport,
    CreateTableLayoutSuggestionSupport,
    DataTypeSuggestionSupport,
    StringConcatenationSuggestionSupport,
)
from .protocols import (
    ClickHouseTriggerSupport,
    ClickHouseTableSupport,
    ClickHouseJSONFunctionSupport,
    ClickHouseSpatialSupport,
    ClickHouseDMLOperationSupport,
    ClickHouseFullTextSearchSupport,
    ClickHouseLockingSupport,
    ClickHouseModifyColumnSupport,
    ClickHouseJsonDualityViewSupport,
    ClickHouseOptimizerHintSupport,
    ClickHousePartitionSupport,
    ClickHouseRenameTableSupport,
    ClickHouseTableStatementSupport,
    ClickHouseMaintenanceSupport,
    ClickHouseRoutineSupport,
    ClickHouseLoadXMLSupport,
    ClickHouseAdminCommandSupport,
    ClickHouseTypeSupport,
)
from .mixins import (
    ClickHouseTransactionMixin,
    ClickHouseDMLOperationMixin,
    ClickHouseFullTextSearchMixin,
    ClickHouseTriggerMixin,
    ClickHouseTableMixin,
    ClickHouseJSONFunctionMixin,
    ClickHouseSpatialMixin,
    ClickHouseIntrospectionMixin,
    ClickHouseStatusQueryMixin,
    ClickHouseLockingMixin,
    ClickHouseModifyColumnMixin,
    ClickHouseJsonDualityViewMixin,
    ClickHouseOptimizerHintMixin,
    ClickHousePartitionMixin,
    ClickHouseDataTypeSuggestionsMixin,
    ClickHouseTypeSupportMixin,
    ClickHouseRenameTableMixin,
    ClickHouseTruncateMixin,
    ClickHouseTableStatementMixin,
    ClickHouseMaintenanceMixin,
    ClickHouseRoutineMixin,
    ClickHouseLoadXMLLMixin,
    ClickHouseAdminCommandMixin,
    ClickHouseTableEngineMixin,
    ClickHouseQueryClauseMixin,
    # New feature-specific ClickHouse mixins
    ClickHouseDateTimeMixin,
    ClickHouseCollationMixin,
    ClickHouseCTEMixin,
    ClickHouseAutoIncrementColumnMixin,
    ClickHouseWindowMixin,
    ClickHouseGroupingMixin,
    ClickHouseArrayMixin,
    ClickHouseExplainMixin,
    ClickHouseTemporalMixin,
    ClickHouseUpsertMixin,
    ClickHouseJoinMixin,
    ClickHouseSetOperationMixin,
    ClickHouseDQLMixin,
    ClickHouseWildcardMixin,
    ClickHouseMaterializedViewMixin,  # MV DDL overrides ClickHouseViewMixin and ViewMixin
    ClickHouseViewMixin,
    ClickHouseNamespaceMixin,
    ClickHouseDatabaseMixin,
    ClickHouseIndexMixin,
    ClickHouseSequenceMixin,
    ClickHouseConstraintMixin,
    ClickHouseDDLColumnMixin,
    ClickHouseFunctionMixin,
    ClickHouseColumnTypeMixin,
    # TRIM differs and is overridden by ClickHouseTrimMixin (above) for the
    # reason documented there: the direction is the function name, and the
    # no-characters ANSI form the default renders is a syntax error here.
    ClickHouseTrimMixin,
    ClickHouseLiteralValueMixin,
)
from .suggestion import (
    ClickHouseGeneratedValueSuggestionMixin,
    ClickHouseCreateTableLayoutSuggestionMixin,
    ClickHouseStringConcatenationSuggestionMixin,
    ClickHousePartitionAddSuggestionMixin,
    ClickHousePartitionBuildSuggestionMixin,
    ClickHousePartitionDropSuggestionMixin,
    ClickHousePartitionMergeSuggestionMixin,
    ClickHousePartitionRetentionSuggestionMixin,
    ClickHousePartitionSplitSuggestionMixin,
    ClickHousePartitionTableAlterSuggestionMixin,
    ClickHousePartitionTableDropSuggestionMixin,
)
from .reserved_words import CLICKHOUSE_RESERVED_WORDS
from .show.dialect import ClickHouseShowDialectMixin

if TYPE_CHECKING:
    from rhosocial.activerecord.backend.expression.statements.ddl_alter import (
        ModifyColumnAction as ModifyColumn,
    )


class ClickHouseDialect(
    # Backend suggestions first: no core mixin may shadow their answers. The
    # eight partition-suggestion mixins are the sole owners of ClickHouse's
    # ``suggest_partition_*`` "how" answers (one per lifecycle point, mirroring
    # the firebird/sqlite suggestion package layout). The layout mixin reads
    # the same capability switches the table mixin answers further down, and
    # the generated-value mixin reports that a snowflake id is carried by the
    # plain integer column type (no server-side identity clause exists).
    ClickHouseGeneratedValueSuggestionMixin,
    ClickHouseCreateTableLayoutSuggestionMixin,
    ClickHouseStringConcatenationSuggestionMixin,
    ClickHousePartitionBuildSuggestionMixin,
    ClickHousePartitionTableDropSuggestionMixin,
    ClickHousePartitionTableAlterSuggestionMixin,
    ClickHousePartitionAddSuggestionMixin,
    ClickHousePartitionDropSuggestionMixin,
    ClickHousePartitionSplitSuggestionMixin,
    ClickHousePartitionMergeSuggestionMixin,
    ClickHousePartitionRetentionSuggestionMixin,
    # The bases below come in bundles: a backend mixin, then the core bundle
    # it stands in for. The backend's answer has to come first -- a mixin
    # placed after the class it overrides never wins -- so a new mixin goes
    # immediately before the core mixin it overrides, and the pairing is read
    # off the list. Two positions sit outside that pairing and are called out
    # where they occur: a mixin that overrides a method ``SQLDialectBase``
    # defines has to precede the base, and a mixin that subclasses a core
    # mixin has to precede it too (C3: a subclass precedes its base).
    # Ahead of SQLDialectBase, unlike every other mixin in this list. Those
    # add methods the base does not have, so their position is a readability
    # choice; this one overrides ``format_literal`` -- ClickHouse's two
    # tier-2 spellings, unhex for bytes and the bare quoted text for UUID --
    # and a mixin placed after the class it overrides never wins.
    ClickHouseLiteralValueMixin,
    SQLDialectBase,
    # ClickHouse's own answer to the row-source capabilities core's
    # RelationSourceMixin supplies. It precedes that mixin because a mixin
    # placed after the class it overrides never wins -- and this one was
    # after it, so the override was dead code and core's default answered
    # for ClickHouse.
    ClickHouseTableStatementMixin,
    RelationSourceMixin,
    # The object tree: each *NameMixin renders one object kind and inherits
    # NamespaceMixin for the namespace levels, so they precede it. The object
    # protocols name the format_*_object methods and inherit NamespaceSupport,
    # so they precede it too. Both sit ahead of the DDL mixins because naming an
    # object and changing one are independent capabilities.
    TableObjectMixin,
    ViewObjectMixin,
    MaterializedViewObjectMixin,
    ForeignTableObjectMixin,
    IndexObjectMixin,
    SequenceObjectMixin,
    TriggerObjectMixin,
    RoutineObjectMixin,
    TypeObjectMixin,
    SynonymObjectMixin,
    SchemaNameMixin,
    DatabaseNameMixin,
    PropertyGraphNameMixin,
    # ClickHouse has a database and no inner schema, so the catalog switches
    # answer True and ``supports_schema_qualification`` keeps its default
    # False: a name carrying a schema is reported rather than rendered as a
    # namespace ClickHouse does not have.
    #
    # ORDER IS LOAD-BEARING. This mixin also spells the name in
    # this mixin answers the two catalog switches True -- rather than core's
    # default False -- and spells the one level it has in
    # ``format_qualified_name``. C3 linearisation gives the earlier name in
    # this list priority, so it must stay AHEAD of ``NamespaceMixin``, whose
    # defaults are no catalog and a two-slot spelling. Listed after it,
    # ``CREATE TABLE analytics.users`` silently renders as ``users``: the
    # statement is still well-formed, so nothing about the SQL looks wrong and
    # only a test asserting the qualified spelling catches it.
    ClickHouseNamespaceMixin,
    NamespaceMixin,
    # ClickHouse-specific mixins (must come before corresponding global mixins to override)
    ClickHouseCollationMixin,
    CollationMixin,
    ClickHouseCTEMixin,
    CTEMixin,
    ClickHouseWindowMixin,
    WindowFunctionMixin,
    ClickHouseJSONFunctionMixin,
    JSONMixin,
    ClickHouseGroupingMixin,
    ClickHouseArrayMixin,
    ArrayMixin,
    ClickHouseExplainMixin,
    ExplainMixin,
    GraphMixin,
    ClickHouseLockingMixin,
    MergeMixin,
    ClickHouseTemporalMixin,
    TemporalTableMixin,
    ClickHouseFullTextSearchMixin,
    ClickHouseTriggerMixin,
    TriggerMixin,
    ClickHouseDMLOperationMixin,
    ClickHouseUpsertMixin,
    UpsertMixin,
    LateralJoinMixin,
    ClickHouseJoinMixin,
    JoinMixin,
    ClickHouseMaterializedViewMixin,  # MV DDL must precede ClickHouseViewMixin and ViewMixin
    ClickHouseViewMixin,
    ViewMixin,
    ClickHouseDatabaseMixin,
    ClickHouseIndexMixin,
    IndexMixin,
    # No core SequenceMixin here, and its absence is deliberate rather than an
    # oversight: ClickHouse has no sequence object, so CREATE / DROP / ALTER
    # SEQUENCE is not a statement the server parses -- and the core formatters
    # never consult supports_sequence(), so inheriting them would render
    # well-formed SQL ClickHouse would refuse rather than refuse it here.
    # Leaving the mixin out makes the absence structural: the dispatch finds no
    # formatter and raises UnsupportedFeatureError naming the dialect and the
    # statement. ClickHouseSequenceMixin just below stays, because the two
    # switches it answers are the ones ClickHouse states for itself; and
    # SequenceObjectMixin above stays too, because naming an object and creating
    # one are different jobs -- a Sequence is still accepted as an identifier
    # and Sequence(dialect, "s").to_sql() keeps rendering.
    ClickHouseSequenceMixin,
    ClickHouseAutoIncrementColumnMixin,
    AutoIncrementColumnMixin,
    # IdentityColumnMixin carries the fail-closed identity formatter and the
    # seven probes; ClickHouse answers the mechanism probe False above, so the
    # clause is refused by name instead of rendered and rejected by the server.
    # Added after the namespace pair on purpose: it cannot disturb the MRO
    # order that keeps ClickHouseNamespaceMixin ahead of NamespaceMixin.
    IdentityColumnMixin,
    ClickHousePartitionMixin,
    PartitionMixin,
    ClickHouseTransactionMixin,
    ClickHouseTableMixin,
    ClickHouseRenameTableMixin,
    # Before TableMixin: this answers False where the core answers True, and it
    # sat in the backend block below, so DROP TABLE was rendered with CASCADE
    # and RESTRICT that ClickHouse does not accept.
    ClickHouseConstraintMixin,
    TableMixin,
    ClickHouseTruncateMixin,
    TruncateMixin,
    ConstraintMixin,
    ClickHouseSpatialMixin,
    ClickHouseIntrospectionMixin,
    ClickHouseStatusQueryMixin,
    ClickHouseShowDialectMixin,
    ClickHouseModifyColumnMixin,
    ClickHouseJsonDualityViewMixin,
    # Suggested data types: the DDL half of the type answer. Ahead of the
    # mixin that supplies the DataType defaults, so this dialect's answers win
    # the C3 lookup instead of core's NotImplementedError.
    ClickHouseDataTypeSuggestionsMixin,
    ClickHouseTypeSupportMixin,
    UserDefinedTypeMixin,
    DomainMixin,
    ClickHouseOptimizerHintMixin,
    ClickHouseMaintenanceMixin,
    ClickHouseRoutineMixin,
    ClickHouseLoadXMLLMixin,
    ClickHouseAdminCommandMixin,
    ClickHouseTableEngineMixin,
    ClickHouseQueryClauseMixin,
    IntrospectionMixin,
    # Global new mixins
    PredicateMixin,
    # Before ExpressionMixin: the wildcard split gave the row-count position its
    # own formatter, and ClickHouse spells ``COUNT(DISTINCT *)`` where core
    # spells ``*``. C3 gives the earlier name in this list priority, so this must
    # stay ahead of ``ExpressionMixin`` or the override would never be reached.
    ClickHouseWildcardMixin,
    # Before ExpressionMixin for the same reason: this carries ClickHouse's
    # ``lengthUTF8`` answer for ``CHAR_LENGTH`` (the engine's LENGTH counts
    # bytes), and ExpressionMixin inherits the core's FunctionCallMixin
    # whose ``LENGTH`` default it replaces. Listed after it, the override
    # would be dead code -- which is what it was until the MRO was checked.
    ClickHouseFunctionMixin,
    ExpressionMixin,
    ClickHouseDateTimeMixin,
    DateTimeMixin,
    ClickHouseDQLMixin,
    DQLMixin,
    ClickHouseDDLColumnMixin,
    DDLColumnMixin,
    ColumnAttributeMixin,
    DMLMixin,
    TransactionControlMixin,
    ClickHouseSetOperationMixin,
    SetOperationMixin,
    # Column types: core deleted the old column-type mixin, so this backend mixin now
    # stands alone as the sole answer for the twenty-four-entry table.
    ClickHouseColumnTypeMixin,
    # TRIM is the one of the four string nodes ClickHouse spells differently:
    # the direction lives in the function name, so ClickHouseTrimMixin must
    # outrank core's TrimMixin in the MRO. LPAD, RPAD and REPEAT are the
    # shared spellings verbatim here.
    ClickHouseTrimMixin,
    LpadMixin,
    RepeatMixin,
    RpadMixin,
    TrimMixin,
    # Protocols for type checking
    CollationSupport,
    CTESupport,
    FilterClauseSupport,
    WindowFunctionSupport,
    ClickHouseJSONFunctionSupport,
    ReturningSupport,
    AdvancedGroupingSupport,
    ArraySupport,
    ExplainSupport,
    GraphSupport,
    ClickHouseLockingSupport,
    MergeSupport,
    OrderedSetAggregationSupport,
    QualifyClauseSupport,
    TemporalTableSupport,
    UpsertSupport,
    LateralJoinSupport,
    WildcardSupport,
    JoinSupport,
    CreateTypeSupport,
    AlterTypeSupport,
    DropTypeSupport,
    CreateDomainSupport,
    AlterDomainSupport,
    DropDomainSupport,
    AutoIncrementColumnSupport,
    IdentityColumnSupport,
    ClickHouseTableSupport,
    ConstraintSupport,
    IntrospectionSupport,
    TruncateSupport,
    TransactionControlSupport,
    ClickHouseTriggerSupport,
    ClickHouseSpatialSupport,
    ClickHouseFullTextSearchSupport,
    ClickHouseModifyColumnSupport,
    ClickHouseJsonDualityViewSupport,
    ClickHouseOptimizerHintSupport,
    ClickHousePartitionSupport,
    ClickHouseDMLOperationSupport,
    ClickHouseRenameTableSupport,
    ClickHouseTableStatementSupport,
    ClickHouseMaintenanceSupport,
    ClickHouseRoutineSupport,
    ClickHouseLoadXMLSupport,
    ClickHouseAdminCommandSupport,
    SQLFunctionSupport,
    # Core split ColumnAttributeSupport out of DDLColumnSupport: the standalone
    # ColumnAttributeMixin above supplies its two members.
    ColumnAttributeSupport,
    # Before the generic DataTypeSupport it extends, for the same reason
    # ClickHouseTypeSupportMixin precedes the mixin it completes: the backend
    # protocol refines the generic one and must be seen first in the MRO.
    ClickHouseTypeSupport,
    DataTypeSupport,
    # Suggestion protocols moved to backend.suggestion.protocols in core.
    DataTypeSuggestionSupport,
    ColumnTypeSuggestionSupport,
    CreateTableLayoutSuggestionSupport,
    StringConcatenationSuggestionSupport,
    # Named objects. Each object protocol names the ``format_<kind>_object``
    # method its ``*NameMixin`` provides, and inherits NamespaceSupport, so they
    # precede it. They sit after the ClickHouse protocols that derive from them
    # -- a subclass must precede its base.
    TableObjectSupport,
    ViewObjectSupport,
    MaterializedViewObjectSupport,
    ForeignTableObjectSupport,
    IndexObjectSupport,
    SequenceObjectSupport,
    TriggerObjectSupport,
    RoutineObjectSupport,
    TypeObjectSupport,
    SynonymObjectSupport,
    NamespaceSupport,
):
    """
    ClickHouse dialect implementation that adapts to the ClickHouse version.

    ClickHouse features and support:
    - Native JSON type and JSONExtract function family
    - Window functions and window frame clauses
    - CTEs (Common Table Expressions), recursive and materialized
    - Native Array / Map / Tuple types with array constructor and access
    - Advanced grouping (WITH ROLLUP / WITH CUBE / GROUPING SETS)
    - UNION / UNION ALL / INTERSECT / EXCEPT set operations
    - Materialized views, table partitioning, skip indexes
    - INSERT ... RETURNING (no UPDATE/DELETE RETURNING)
    - QUALIFY clause, ILIKE operator

    Not supported (reported via supports_* = False, callers fail fast):
    - Transactions (BEGIN/COMMIT/ROLLBACK, savepoints)
    - FOREIGN KEY / UNIQUE constraints, CHECK constraints
    - Triggers, sequences, UPSERT / ON CONFLICT / INSERT IGNORE / REPLACE
    - FOR UPDATE row locking, LATERAL JOIN, MERGE, generated columns
    """

    def __init__(self, version: Optional[Tuple[int, int, int]] = None):
        """
        Initialize ClickHouse dialect with specific version.

        Args:
            version: ClickHouse version tuple (major, minor, patch).
                If None, the dialect must be adapted via
                backend.introspect_and_adapt() before version-dependent
                features can be used.
        """
        super().__init__()
        self._reserved_words = CLICKHOUSE_RESERVED_WORDS
        if version is not None:
            self.version = version

    def get_parameter_placeholder(self, position: int = 0) -> str:
        """ClickHouse uses '%s' for placeholders."""
        return "%s"

    def get_server_version(self) -> Tuple[int, int, int]:
        """Return the ClickHouse version this dialect is configured for."""
        return self.version

    def create_schema_differ(self):
        """Return the ClickHouse schema differ (ordinal-position aware)."""
        from rhosocial.activerecord.backend.impl.clickhouse.schema.differ import (
            ClickHouseSchemaDiffer,
        )

        return ClickHouseSchemaDiffer()

    def escape_sql_string(self, value: str) -> str:
        """Escape string for ClickHouse.

        ClickHouse by default treats backslash as an escape character.
        This method properly escapes backslashes first, then single quotes.

        Args:
            value: The string value to escape

        Returns:
            Escaped string safe for use in ClickHouse SQL statements
        """
        value = value.replace("\\", "\\\\")
        value = value.replace("'", "''")
        return value

    def supports_json_type(self) -> bool:
        """ClickHouse has a native JSON type."""
        return True

    def format_identifier(self, identifier: str, need_quote: bool = True) -> str:
        """
        Format identifier using ClickHouse's backtick quoting mechanism.

        Args:
            identifier: Raw identifier string
            need_quote: Whether the identifier needs quoting

        Returns:
            Quoted identifier with escaped internal backticks
        """
        if not need_quote:
            if self.is_reserved_word(identifier):
                import warnings
                from rhosocial.activerecord.backend.warnings import IdentifierQuotingWarning
                warnings.warn(
                    f"Identifier '{identifier}' is a reserved word in {self.name} "
                    f"and may cause SQL errors without quoting.",
                    IdentifierQuotingWarning,
                    stacklevel=2,
                )
            return identifier
        escaped = identifier.replace("`", "``")
        return f"`{escaped}`"

    # region CreateTableStatement.diff() hooks (CreateTableExpressionDiffMixin)
    #
    # ClickHouse-specific policy for the expression-level CREATE TABLE diff:
    #
    # - Column type changes are supported in place via ``MODIFY COLUMN``
    #   (``supports_alter_column_type()`` is True), so the diff emits a
    #   ``ModifyColumn`` action instead of forcing a rebuild.
    # - ``ALTER COLUMN SET/DROP DEFAULT`` and ``SET/DROP NOT NULL`` do not
    #   exist in ClickHouse: DEFAULT is part of the column definition and
    #   nullability is part of the type (``Nullable(T)``). Both require
    #   ``MODIFY COLUMN``, which the generic diff cannot express per
    #   property, so property changes rebuild.
    # - ClickHouse has no traditional secondary indexes — only data skipping
    #   indexes, which require ``TYPE ... GRANULARITY ...`` clauses the
    #   generic ``ADD INDEX`` action cannot express. Index changes rebuild;
    #   the recreated table renders skip indexes inline via
    #   :meth:`format_index_definition`.
    # - ``ALTER TABLE ADD/DROP CONSTRAINT`` is unsupported, so any named
    #   table-constraint change also rebuilds instead of emitting actions
    #   that would raise on render.

    def supports_drop_column(self) -> bool:
        """ClickHouse supports ``ALTER TABLE ... DROP COLUMN``.

        Core's ``ConstraintMixin`` answers False by default, which made the
        shared testsuite's unconditional plain-form DROP COLUMN rendering test
        fail. The engine has supported the clause on every version this backend
        targets, so the honest answer is True; the dialect's core formatter
        then renders it. Declared here, ahead of ``ConstraintMixin`` in the
        MRO, because placing it on a backend mixin below it would be dead code.
        """
        return True

    def supports_alter_column_type(self) -> bool:
        """ClickHouse supports in-place type changes via MODIFY COLUMN."""
        return True

    def alter_column_type_action(self, old_col, new_col) -> "ModifyColumn":
        """Render a column type change as MODIFY COLUMN <new definition>."""
        from rhosocial.activerecord.backend.expression.statements.ddl_alter import (
            ModifyColumnAction,
        )

        return ModifyColumnAction(self, column=new_col)

    def supports_alter_column_properties(self) -> bool:
        """No ``ALTER COLUMN SET/DROP DEFAULT`` / ``SET/DROP NOT NULL`` in ClickHouse."""
        return False

    def supports_alter_table_index_actions(self) -> bool:
        """No traditional indexes; skipping indexes cannot use ADD/DROP INDEX actions."""
        return False

    def _diff_table_constraints(self, old, new):
        """Constraint changes rebuild: ClickHouse has no ADD/DROP CONSTRAINT."""
        drops, adds, rebuild = super()._diff_table_constraints(old, new)
        if rebuild is not None:
            return drops, adds, rebuild
        if drops or adds:
            return [], [], self._build_rebuild_plan(
                old, new,
                reason="table constraint change not supported in-place by ClickHouse",
            )
        return drops, adds, None

    # endregion

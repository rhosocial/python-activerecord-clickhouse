# src/rhosocial/activerecord/backend/impl/clickhouse/dialect.py
"""
ClickHouse backend SQL dialect implementation.

This dialect implements protocols for features that ClickHouse actually supports,
based on the ClickHouse version provided at initialization.
"""

from typing import Any, Dict, List, Optional, Tuple, TYPE_CHECKING

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
    ViewSupport,
    SchemaSupport,
    SequenceSupport,
    AutoIncrementSupport,
    ConstraintSupport,
    IntrospectionSupport,
    TruncateSupport,
    TransactionControlSupport,
    SQLFunctionSupport,
    DDLTypeSupport,
)
from rhosocial.activerecord.backend.dialect.mixins import (
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
    SchemaMixin,
    IndexMixin,
    SequenceMixin,
    AutoIncrementMixin,
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
    TransactionControlMixin,
    SetOperationMixin,
)
from .protocols import (
    ClickHouseTriggerSupport,
    ClickHouseTableSupport,
    ClickHouseJSONFunctionSupport,
    ClickHouseSpatialSupport,
    ClickHouseVectorSupport,
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
)
from .mixins import (
    ClickHouseTransactionMixin,
    ClickHouseDMLOperationMixin,
    ClickHouseFullTextSearchMixin,
    ClickHouseTriggerMixin,
    ClickHouseTableMixin,
    ClickHouseJSONFunctionMixin,
    ClickHouseSpatialMixin,
    ClickHouseVectorMixin,
    ClickHouseIntrospectionMixin,
    ClickHouseLockingMixin,
    ClickHouseModifyColumnMixin,
    ClickHouseJsonDualityViewMixin,
    ClickHouseOptimizerHintMixin,
    ClickHousePartitionMixin,
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
    ClickHouseAutoIncrementMixin,
    ClickHouseWindowMixin,
    ClickHouseGroupingMixin,
    ClickHouseArrayMixin,
    ClickHouseExplainMixin,
    ClickHouseTemporalMixin,
    ClickHouseUpsertMixin,
    ClickHouseJoinMixin,
    ClickHouseSetOperationMixin,
    ClickHouseDQLMixin,
    ClickHouseViewMixin,
    ClickHouseSchemaMixin,
    ClickHouseIndexMixin,
    ClickHouseSequenceMixin,
    ClickHouseConstraintMixin,
    ClickHouseDDLColumnMixin,
    ClickHouseFunctionMixin,
)
from .reserved_words import CLICKHOUSE_RESERVED_WORDS
from .show.dialect import ClickHouseShowDialectMixin


class ClickHouseDialect(
    SQLDialectBase,
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
    ClickHouseViewMixin,
    ViewMixin,
    ClickHouseSchemaMixin,
    SchemaMixin,
    ClickHouseIndexMixin,
    IndexMixin,
    ClickHouseSequenceMixin,
    SequenceMixin,
    ClickHouseAutoIncrementMixin,
    AutoIncrementMixin,
    ClickHousePartitionMixin,
    PartitionMixin,
    ClickHouseTransactionMixin,
    ClickHouseTableMixin,
    ClickHouseRenameTableMixin,
    TableMixin,
    ClickHouseTruncateMixin,
    TruncateMixin,
    ClickHouseConstraintMixin,
    ConstraintMixin,
    ClickHouseSpatialMixin,
    ClickHouseVectorMixin,
    ClickHouseIntrospectionMixin,
    ClickHouseShowDialectMixin,
    ClickHouseModifyColumnMixin,
    ClickHouseJsonDualityViewMixin,
    ClickHouseTypeSupportMixin,
    ClickHouseOptimizerHintMixin,
    ClickHouseTableStatementMixin,
    ClickHouseMaintenanceMixin,
    ClickHouseRoutineMixin,
    ClickHouseLoadXMLLMixin,
    ClickHouseAdminCommandMixin,
    ClickHouseTableEngineMixin,
    ClickHouseQueryClauseMixin,
    IntrospectionMixin,
    # Global new mixins
    PredicateMixin,
    ExpressionMixin,
    ClickHouseDateTimeMixin,
    DateTimeMixin,
    ClickHouseDQLMixin,
    DQLMixin,
    ClickHouseDDLColumnMixin,
    DDLColumnMixin,
    DMLMixin,
    TransactionControlMixin,
    ClickHouseSetOperationMixin,
    SetOperationMixin,
    ClickHouseFunctionMixin,
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
    ViewSupport,
    SchemaSupport,
    SequenceSupport,
    AutoIncrementSupport,
    ClickHouseTableSupport,
    ConstraintSupport,
    IntrospectionSupport,
    TruncateSupport,
    TransactionControlSupport,
    ClickHouseTriggerSupport,
    ClickHouseSpatialSupport,
    ClickHouseVectorSupport,
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
    DDLTypeSupport,
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

    @staticmethod
    def _escape_sql_string(value: str) -> str:
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

    # region CreateTableExpression.diff() hooks (CreateTableExpressionDiffMixin)
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
    #   :meth:`format_inline_index`.
    # - ``ALTER TABLE ADD/DROP CONSTRAINT`` is unsupported, so any named
    #   table-constraint change also rebuilds instead of emitting actions
    #   that would raise on render.

    def _supports_alter_column_type(self) -> bool:
        """ClickHouse supports in-place type changes via MODIFY COLUMN."""
        return True

    def alter_column_type_action(self, old_col, new_col) -> "ModifyColumn":
        """Render a column type change as MODIFY COLUMN <new definition>."""
        from rhosocial.activerecord.backend.expression.statements.ddl_alter import ModifyColumn

        return ModifyColumn(self, column=new_col)

    def _supports_alter_column_properties(self) -> bool:
        """No ``ALTER COLUMN SET/DROP DEFAULT`` / ``SET/DROP NOT NULL`` in ClickHouse."""
        return False

    def _supports_alter_table_index_actions(self) -> bool:
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

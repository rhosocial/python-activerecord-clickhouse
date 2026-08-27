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
    # TRUNCATE TABLE support protocol
    TruncateSupport,
    # Transaction Control Protocol
    TransactionControlSupport,
    # Function Support Protocol
    SQLFunctionSupport,
    # DataType Support Protocol
    DDLTypeSupport,
)
from rhosocial.activerecord.backend.dialect.mixins import (
    CollationMixin,
    CTEMixin,
    FilterClauseMixin,
    WindowFunctionMixin,
    JSONMixin,
    ReturningMixin,
    AdvancedGroupingMixin,
    ArrayMixin,
    ExplainMixin,
    GraphMixin,
    LockingMixin,
    MergeMixin,
    OrderedSetAggregationMixin,
    QualifyClauseMixin,
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
    TruncateMixin,
    IntrospectionMixin,
    PartitionMixin,
    # New Mixins
    IdentifierMixin,
    PredicateMixin,
    ExpressionMixin,
    DateTimeMixin,
    DQLMixin,
    DMLMixin,
    DDLColumnMixin,
    TransactionControlMixin,
    SetOperationMixin,
)
from rhosocial.activerecord.backend.dialect.exceptions import UnsupportedFeatureError
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
)
from .collation import validate_clickhouse_collation_name
from .show.dialect import ClickHouseShowDialectMixin

if TYPE_CHECKING:
    from rhosocial.activerecord.backend.expression import bases
    from rhosocial.activerecord.backend.expression.collation import CollateExpression
    from rhosocial.activerecord.backend.expression.statements import (
        CreateTableExpression,
        CreateViewExpression,
        DropViewExpression,
        TableConstraint,
        IndexDefinition,
        ExplainExpression,
        InsertExpression,
    )
    from rhosocial.activerecord.backend.expression.statements.ddl_trigger import (
        CreateTriggerExpression,
        DropTriggerExpression,
    )
    from rhosocial.activerecord.backend.expression.transaction import (
        SetTransactionExpression,
        BeginTransactionExpression,
    )


class ClickHouseDialect(
    SQLDialectBase,
    # Include mixins for features that ClickHouse supports (with version-dependent implementations)
    CollationMixin,
    CTEMixin,
    FilterClauseMixin,
    WindowFunctionMixin,
    ClickHouseJSONFunctionMixin,  # JSON funcs (before JSONMixin to override)
    JSONMixin,
    ReturningMixin,  # ClickHouse doesn't support RETURNING, but we'll override to indicate this
    AdvancedGroupingMixin,
    ArrayMixin,
    ExplainMixin,
    GraphMixin,
    ClickHouseLockingMixin,  # ClickHouse FOR SHARE/NOWAIT/SKIP LOCKED (before LockingMixin for method override)
    LockingMixin,
    MergeMixin,
    OrderedSetAggregationMixin,
    QualifyClauseMixin,
    TemporalTableMixin,
    ClickHouseFullTextSearchMixin,  # full-text fail-fast (before IndexMixin)
    ClickHouseTriggerMixin,  # ClickHouse trigger support (before IndexMixin to override trigger methods)
    ClickHouseDMLOperationMixin,  # ClickHouse DML operations (before UpsertMixin to override format_on_conflict_clause)
    UpsertMixin,
    LateralJoinMixin,  # ClickHouse 8.0.14+ supports LATERAL
    JoinMixin,
    ViewMixin,
    SchemaMixin,
    IndexMixin,
    SequenceMixin,
    AutoIncrementMixin,
    ClickHousePartitionMixin,
    PartitionMixin,
    # ClickHouse-specific mixins (before generic IntrospectionMixin to override methods)
    ClickHouseTransactionMixin,  # ClickHouse transaction support
    ClickHouseTableMixin,  # Must be before TableMixin/ConstraintMixin to override format methods
    ClickHouseRenameTableMixin,  # ClickHouse RENAME TABLE (before TableMixin to override supports_rename_table)
    TableMixin,
    ClickHouseTruncateMixin,  # ClickHouse TRUNCATE support (before TruncateMixin to override)
    TruncateMixin,
    ConstraintMixin,
    ClickHouseSpatialMixin,
    ClickHouseVectorMixin,  # ClickHouse 9.0+ VECTOR type support
    ClickHouseIntrospectionMixin,  # Must be before IntrospectionMixin
    ClickHouseShowDialectMixin,  # ClickHouse SHOW commands
    ClickHouseModifyColumnMixin,  # ClickHouse MODIFY/CHANGE COLUMN support
    ClickHouseJsonDualityViewMixin,  # JSON Duality Views fail-fast stub
    ClickHouseTypeSupportMixin,  # DataType formatting and parsing
    ClickHouseOptimizerHintMixin,  # ClickHouse optimizer hints (SET_VAR)
    ClickHouseTableStatementMixin,  # ClickHouse TABLE / VALUES statements (8.0.19+)
    ClickHouseMaintenanceMixin,  # ClickHouse ANALYZE/CHECK/CHECKSUM/OPTIMIZE/REPAIR TABLE
    ClickHouseRoutineMixin,  # ClickHouse stored procedures/functions/CALL
    ClickHouseLoadXMLLMixin,  # ClickHouse LOAD XML
    ClickHouseAdminCommandMixin,  # ClickHouse admin/utility commands
    ClickHouseTableEngineMixin,  # ClickHouse ENGINE / ORDER BY / PARTITION BY / TTL
    ClickHouseQueryClauseMixin,  # ClickHouse FINAL / ARRAY JOIN
    IntrospectionMixin,
    # New Mixins
    IdentifierMixin,
    PredicateMixin,
    ExpressionMixin,
    DateTimeMixin,
    DQLMixin,
    DMLMixin,
    DDLColumnMixin,
    TransactionControlMixin,
    SetOperationMixin,
    # Protocols for type checking
    # Note: ClickHouse-specific protocols extend generic protocols,
    # so only ClickHouse-specific protocols are needed for isinstance checks
    CollationSupport,
    CTESupport,
    FilterClauseSupport,
    WindowFunctionSupport,
    ClickHouseJSONFunctionSupport,  # extends JSONSupport
    ReturningSupport,
    AdvancedGroupingSupport,
    ArraySupport,
    ExplainSupport,
    GraphSupport,
    ClickHouseLockingSupport,  # extends LockingSupport
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
    ClickHouseTableSupport,  # extends TableSupport
    ConstraintSupport,
    IntrospectionSupport,
    # TRUNCATE TABLE support protocol
    TruncateSupport,
    # Transaction Control Protocol
    TransactionControlSupport,
    # ClickHouse-specific protocols
    ClickHouseTriggerSupport,
    ClickHouseSpatialSupport,
    ClickHouseVectorSupport,  # ClickHouse 9.0+ VECTOR type support
    ClickHouseFullTextSearchSupport,  # ClickHouse full-text search
    ClickHouseModifyColumnSupport,  # ClickHouse MODIFY/CHANGE COLUMN support
    ClickHouseJsonDualityViewSupport,  # JSON Duality Views fail-fast stub
    ClickHouseOptimizerHintSupport,  # ClickHouse optimizer hints
    ClickHousePartitionSupport,  # ClickHouse table partitioning
    ClickHouseDMLOperationSupport,  # ClickHouse DML ops (INSERT IGNORE, REPLACE INTO, LOAD DATA - unsupported)
    ClickHouseRenameTableSupport,  # ClickHouse RENAME TABLE
    ClickHouseTableStatementSupport,  # ClickHouse TABLE / VALUES statements
    ClickHouseMaintenanceSupport,  # ClickHouse table maintenance
    ClickHouseRoutineSupport,  # ClickHouse stored routines / CALL
    ClickHouseLoadXMLSupport,  # ClickHouse LOAD XML
    ClickHouseAdminCommandSupport,  # ClickHouse admin/utility commands
    # Function Support Protocol
    SQLFunctionSupport,
    # DataType Support Protocol
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

    def format_date_trunc_expression(self, expr: "Any") -> Tuple[str, Tuple]:
        """Format date_trunc using ClickHouse's date_trunc function."""
        source_sql, source_params = expr.source.to_sql()
        field = expr.field.value.upper()
        sql = f"date_trunc(%s, {source_sql})"
        return self._apply_value_expression_modifiers(sql, source_params + (field,), expr)

    def format_interval_expression(self, expr: "Any") -> Tuple[str, Tuple]:
        sql = f"INTERVAL %s {expr.unit.value.upper()}"
        return self._apply_value_expression_modifiers(sql, (expr.value,), expr)

    def format_datetime_add_expression(self, expr: "Any") -> Tuple[str, Tuple]:
        source_sql, source_params = expr.source.to_sql()
        interval_sql, interval_params = expr.interval.to_sql()
        sql = f"date_add({expr.interval.unit.value.upper()}, {interval_sql}, {source_sql})"
        return self._apply_value_expression_modifiers(sql, source_params + interval_params, expr)

    def format_datetime_subtract_expression(self, expr: "Any") -> Tuple[str, Tuple]:
        source_sql, source_params = expr.source.to_sql()
        interval_sql, interval_params = expr.interval.to_sql()
        sql = f"date_sub({expr.interval.unit.value.upper()}, {interval_sql}, {source_sql})"
        return self._apply_value_expression_modifiers(sql, source_params + interval_params, expr)

    def format_datetime_diff_expression(self, expr: "Any") -> Tuple[str, Tuple]:
        start_sql, start_params = expr.start.to_sql()
        end_sql, end_params = expr.end.to_sql()
        sql = f"dateDiff(%s, {start_sql}, {end_sql})"
        return self._apply_value_expression_modifiers(sql, start_params + end_params + (expr.unit.value.upper(),), expr)

    def supports_collate_expression(self) -> bool:
        """ClickHouse does not support expression-level COLLATE."""
        return False

    def validate_collation_name(self, expr: "CollateExpression") -> str:
        """Validate ClickHouse collation names and return their SQL representation."""
        if expr.collation_options:
            unsupported = ", ".join(sorted(expr.collation_options))
            raise UnsupportedFeatureError(self.name, f"COLLATE options: {unsupported}")
        return validate_clickhouse_collation_name(expr.collation_name, getattr(self, "version", None))

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

    # region Protocol Support Checks
    def supports_basic_cte(self) -> bool:
        """Basic CTEs (WITH clause) are supported in ClickHouse."""
        return True

    def supports_recursive_cte(self) -> bool:
        """Recursive CTEs are supported in ClickHouse."""
        return True

    def supports_materialized_cte(self) -> bool:
        """ClickHouse supports MATERIALIZED / NOT MATERIALIZED CTE hints."""
        return True

    def supports_returning_insert(self) -> bool:
        """ClickHouse does not support RETURNING clause for INSERT (26.7 tested)."""
        return False

    def supports_returning_update(self) -> bool:
        """ClickHouse does not support RETURNING clause for UPDATE."""
        return False

    def supports_returning_delete(self) -> bool:
        """ClickHouse does not support RETURNING clause for DELETE."""
        return False

    def supports_auto_increment(self) -> bool:
        """ClickHouse does not natively support AUTO_INCREMENT/IDENTITY primary keys.

        Primary keys must be supplied explicitly (e.g. a snowflake ID or UUID)
        before inserting new records.
        """
        return False

    def supports_window_functions(self) -> bool:
        """Window functions are supported in ClickHouse."""
        return True

    def supports_window_frame_clause(self) -> bool:
        """Whether window frame clauses (ROWS/RANGE/GROUPS) are supported."""
        return True

    def supports_filter_clause(self) -> bool:
        """FILTER clause for aggregate functions is not supported in ClickHouse."""
        return False  # ClickHouse does not support FILTER clause

    def supports_json_type(self) -> bool:
        """ClickHouse has a native JSON type."""
        return True

    def get_json_access_operator(self) -> str:
        """ClickHouse uses '->' for JSON access."""
        return "->"

    def supports_rollup(self) -> bool:
        """ROLLUP is supported using WITH ROLLUP syntax."""
        return True  # Supported via WITH ROLLUP

    def supports_cube(self) -> bool:
        """CUBE is supported using WITH CUBE syntax."""
        return True  # Supported via WITH CUBE

    def supports_grouping_sets(self) -> bool:
        """GROUPING SETS is supported."""
        return True  # Supported via GROUPING SETS

    def supports_array_type(self) -> bool:
        """ClickHouse has native Array types."""
        return True  # Native Array(T) support

    def supports_array_constructor(self) -> bool:
        """ClickHouse supports ARRAY constructor syntax [1, 2, 3]."""
        return True  # Native [a, b, c] syntax

    def supports_array_access(self) -> bool:
        """ClickHouse supports array subscript access arr[1] (1-based)."""
        return True  # Native arr[i] support (1-based)

    def supports_explain_analyze(self) -> bool:
        """Whether EXPLAIN ANALYZE is supported.

        Accepted syntax-wise from ClickHouse 26.7; older maintained lines
        (25.8 LTS, 26.3 LTS) reject the ANALYZE keyword.
        """
        return self.version >= (26, 7, 0)

    def supports_explain_format(self, format_type: str) -> bool:
        """Check if specific EXPLAIN format is supported.

        ClickHouse supports TEXT, JSON, TREE, and TABULAR formats.
        """
        format_type_upper = format_type.upper()
        if format_type_upper in ("TEXT", "JSON", "TREE", "TABULAR", "TSV", "TSVRaw", "CSV"):
            return True
        return False

    def format_explain_statement(self, explain_expr: "ExplainExpression") -> tuple:
        """Build the ClickHouse EXPLAIN SQL string and return (sql, params).

        ClickHouse syntax variants:
        - ``EXPLAIN <stmt>``
        - ``EXPLAIN <stmt> FORMAT=TEXT|JSON|TABULAR|TSV|CSV``
        - ``EXPLAIN ANALYZE <stmt>``
        - ``EXPLAIN PIPELINE <stmt>``
        """
        from rhosocial.activerecord.backend.expression.statements import ExplainType

        statement_sql, statement_params = explain_expr.statement.to_sql()
        options = explain_expr.options
        parts = ["EXPLAIN"]

        if options is not None:
            # ANALYZE goes before FORMAT (ClickHouse ordering)
            if options.analyze:
                parts.append("ANALYZE")

            if options.format is not None:
                fmt_name = options.format.name if hasattr(options.format, "name") else str(options.format)
                parts.append(f"FORMAT={fmt_name.upper()}")
            elif options.type is not None and options.type == ExplainType.QUERY_PLAN:
                # ClickHouse has no QUERY PLAN keyword; fall through to plain EXPLAIN
                pass

        return f"{' '.join(parts)} {statement_sql}", statement_params

    def supports_graph_match(self) -> bool:
        """Whether graph query MATCH clause is supported."""
        return False

    def supports_for_update(self) -> bool:
        """Whether FOR UPDATE clause is supported in SELECT statements.

        ClickHouse does not support FOR UPDATE row locking.
        """
        return False

    def supports_merge_statement(self) -> bool:
        """Whether MERGE statement is supported."""
        return False  # ClickHouse does not support MERGE

    def supports_temporal_tables(self) -> bool:
        """Whether temporal tables are supported."""
        return False

    def supports_qualify_clause(self) -> bool:
        """Whether QUALIFY clause is supported in ClickHouse."""
        return True

    def supports_upsert(self) -> bool:
        """Whether UPSERT (INSERT ... ON CONFLICT) is supported."""
        return False  # ClickHouse does not support UPSERT

    def get_upsert_syntax_type(self) -> str:
        """ClickHouse has no upsert syntax."""
        return "none"

    def supports_on_conflict_clause(self) -> bool:
        """Whether INSERT can carry an ON CONFLICT style clause."""
        return False

    def supports_multiple_on_conflict_clauses(self) -> bool:
        return False

    def supports_lateral_join(self) -> bool:
        """Whether LATERAL joins are supported."""
        return False  # ClickHouse does not support LATERAL JOIN

    def supports_ordered_set_aggregation(self) -> bool:
        """Whether ordered-set aggregate functions are supported."""
        return False  # ClickHouse does not support WITHIN GROUP (ORDER BY ...) syntax

    def supports_inner_join(self) -> bool:
        """INNER JOIN is supported."""
        return True

    def supports_left_join(self) -> bool:
        """LEFT JOIN is supported."""
        return True

    def supports_right_join(self) -> bool:
        """RIGHT JOIN is supported."""
        return True

    def supports_full_join(self) -> bool:
        """FULL JOIN is supported."""
        return True

    def supports_cross_join(self) -> bool:
        """CROSS JOIN is supported."""
        return True

    def supports_natural_join(self) -> bool:
        """NATURAL JOIN is not supported in ClickHouse."""
        return False

    def supports_wildcard(self) -> bool:
        """Wildcard (*) is supported."""
        return True

    # endregion

    # region Set Operation Support
    def supports_union(self) -> bool:
        """UNION is supported."""
        return True

    def supports_union_all(self) -> bool:
        """UNION ALL is supported."""
        return True

    def supports_intersect(self) -> bool:
        """INTERSECT is supported."""
        return True

    def supports_except(self) -> bool:
        """EXCEPT is supported."""
        return True

    def supports_set_operation_order_by(self) -> bool:
        """Set operations support ORDER BY."""
        return True

    def supports_set_operation_limit_offset(self) -> bool:
        """Set operations support LIMIT and OFFSET."""
        return True

    def supports_set_operation_for_update(self) -> bool:
        """Set operations do not support FOR UPDATE."""
        return False

    def format_set_operation_expression(
        self,
        left: "bases.BaseExpression",
        right: "bases.BaseExpression",
        operation: str,
        alias,
        all_: bool,
        order_by_clause=None,
        limit_offset_clause=None,
        for_update_clause=None,
    ) -> Tuple[str, Tuple]:
        """Format set operations with an explicit ALL/DISTINCT modifier.

        ClickHouse rejects a bare ``UNION`` when ``union_default_mode`` is
        empty (the default): ``Expected ALL or DISTINCT in SelectWithUnion
        query``. A bare SQL-standard ``UNION`` means ``UNION DISTINCT``, so
        we always emit the explicit modifier.
        """
        left_sql, left_params = left.to_sql()
        right_sql, right_params = right.to_sql()
        modifier = "ALL" if all_ else "DISTINCT"
        base_sql = f"{left_sql} {operation} {modifier} {right_sql}"
        all_params = list(left_params + right_params)

        sql_parts = [base_sql]
        if alias:
            sql_parts.append(f"AS {self.format_identifier(alias)}")
        if order_by_clause:
            order_by_sql, order_by_params = order_by_clause.to_sql()
            sql_parts.append(order_by_sql)
            all_params.extend(order_by_params)
        if limit_offset_clause:
            limit_offset_sql, limit_offset_params = limit_offset_clause.to_sql()
            sql_parts.append(limit_offset_sql)
            all_params.extend(limit_offset_params)
        # FOR UPDATE is unsupported in ClickHouse; ignore silently.
        return " ".join(sql_parts), tuple(all_params)

    # endregion

    def format_identifier(self, identifier: str) -> str:
        """
        Format identifier using ClickHouse's backtick quoting mechanism.

        Args:
            identifier: Raw identifier string

        Returns:
            Quoted identifier with escaped internal backticks
        """
        # Escape any internal backticks by doubling them
        escaped = identifier.replace("`", "``")
        return f"`{escaped}`"

    def format_column(
        self, name: str, table: Optional[str] = None, alias: Optional[str] = None, schema_name: Optional[str] = None
    ) -> Tuple[str, Tuple]:
        """Format column reference for ClickHouse.

        ClickHouse uses database-qualified references (db.table.column) rather
        than schema-qualified ones, so schema_name is silently ignored
        here. Database qualification is handled separately through
        cross-database query support.
        """
        if table:
            col_sql = f"{self.format_identifier(table)}.{self.format_identifier(name)}"
        else:
            col_sql = self.format_identifier(name)

        if alias:
            col_sql = f"{col_sql} AS {self.format_identifier(alias)}"

        return col_sql, ()

    def format_limit_offset(
        self, limit: Optional[int] = None, offset: Optional[int] = None
    ) -> Tuple[Optional[str], List[Any]]:
        """
        Format LIMIT and OFFSET clause for ClickHouse.

        ClickHouse requires LIMIT when using OFFSET.
        """
        params = []
        sql_parts = []

        if limit is not None:
            sql_parts.append("LIMIT %s")
            params.append(limit)

        if offset is not None:
            if limit is None:
                # ClickHouse requires LIMIT when using OFFSET, use a very large number
                sql_parts.append("LIMIT %s")
                params.append(18446744073709551615)  # ClickHouse maximum value for BIGINT UNSIGNED
            sql_parts.append("OFFSET %s")
            params.append(offset)

        if not sql_parts:
            return None, []

        return " ".join(sql_parts), params

    # region View Support
    def supports_or_replace_view(self) -> bool:
        """Whether CREATE OR REPLACE VIEW is supported."""
        return True  # ClickHouse supports OR REPLACE

    def supports_temporary_view(self) -> bool:
        """Whether TEMPORARY views are supported."""
        return False  # ClickHouse does not support TEMPORARY views

    def supports_materialized_view(self) -> bool:
        """Whether materialized views are supported."""
        return True  # ClickHouse has first-class MATERIALIZED VIEW support

    def supports_if_exists_view(self) -> bool:
        """Whether DROP VIEW IF EXISTS is supported."""
        return True  # ClickHouse supports IF EXISTS

    def supports_view_check_option(self) -> bool:
        """Whether WITH CHECK OPTION is supported."""
        return False  # ClickHouse does not support WITH CHECK OPTION

    def supports_cascade_view(self) -> bool:
        """Whether DROP VIEW CASCADE is supported."""
        return False  # ClickHouse does not support CASCADE for views

    def format_create_view_statement(self, expr: "CreateViewExpression") -> Tuple[str, tuple]:
        """Format CREATE VIEW statement for ClickHouse."""
        parts = ["CREATE"]

        if expr.temporary:
            parts.append("TEMPORARY")

        if expr.replace:
            parts.append("OR REPLACE")

        parts.append("VIEW")
        parts.append(self.format_identifier(expr.view_name))

        if expr.column_aliases:
            cols = ", ".join(self.format_identifier(c) for c in expr.column_aliases)
            parts.append(f"({cols})")

        query_sql, query_params = expr.query.to_sql()
        parts.append(f"AS {query_sql}")

        if expr.options and expr.options.check_option:
            check_option = expr.options.check_option.value
            parts.append(f"WITH {check_option} CHECK OPTION")

        return " ".join(parts), query_params

    def format_drop_view_statement(self, expr: "DropViewExpression") -> Tuple[str, tuple]:
        """Format DROP VIEW statement for ClickHouse."""
        parts = ["DROP VIEW"]
        if expr.if_exists:
            parts.append("IF EXISTS")
        parts.append(self.format_identifier(expr.view_name))
        return " ".join(parts), ()

    # endregion

    # region Schema Support
    def supports_schema(self) -> bool:
        """Whether ClickHouse models named schema namespaces."""
        return False  # ClickHouse uses databases only, no schema namespace layer

    def supports_create_schema(self) -> bool:
        """Whether CREATE SCHEMA is supported."""
        return False  # ClickHouse uses CREATE DATABASE, not CREATE SCHEMA

    def supports_drop_schema(self) -> bool:
        """Whether DROP SCHEMA is supported."""
        return False  # ClickHouse uses DROP DATABASE, not DROP SCHEMA

    def supports_schema_if_not_exists(self) -> bool:
        """Whether CREATE SCHEMA IF NOT EXISTS is supported."""
        return False

    def supports_schema_if_exists(self) -> bool:
        """Whether DROP SCHEMA IF EXISTS is supported."""
        return False

    # endregion

    # region Index Support
    def supports_create_index(self) -> bool:
        """Whether CREATE INDEX is supported."""
        return True  # Skip (data-skipping) indexes

    def supports_drop_index(self) -> bool:
        """Whether DROP INDEX is supported."""
        return True

    def supports_unique_index(self) -> bool:
        """Whether UNIQUE indexes are supported."""
        return False  # ClickHouse cannot enforce uniqueness on indexes

    def supports_index_if_not_exists(self) -> bool:
        """Whether CREATE INDEX IF NOT EXISTS is supported."""
        return True  # ClickHouse supports IF NOT EXISTS for indexes

    def supports_index_if_exists(self) -> bool:
        """Whether DROP INDEX IF EXISTS is supported."""
        return True  # ClickHouse supports IF EXISTS for indexes

    # endregion

    # region Sequence Support
    def supports_create_sequence(self) -> bool:
        """Whether CREATE SEQUENCE is supported."""
        return False  # ClickHouse does not support sequences

    def supports_drop_sequence(self) -> bool:
        """Whether DROP SEQUENCE is supported."""
        return False

    # endregion

    # region Table Support
    def supports_if_not_exists_table(self) -> bool:
        """Whether CREATE TABLE IF NOT EXISTS is supported."""
        return True

    def supports_if_exists_table(self) -> bool:
        """Whether DROP TABLE IF EXISTS is supported."""
        return True

    def supports_temporary_table(self) -> bool:
        """Whether TEMPORARY tables are supported."""
        return True

    # Override inherited TableMixin defaults for ClickHouse
    def supports_primary_key_constraint(self) -> bool:
        """ClickHouse supports PRIMARY KEY in table DDL."""
        return True

    def supports_unique_constraint(self) -> bool:
        """ClickHouse does not support UNIQUE constraints."""
        return False

    def supports_not_null_constraint(self) -> bool:
        """ClickHouse supports NOT NULL constraint syntax."""
        return True

    def supports_foreign_key_constraint(self) -> bool:
        """ClickHouse does not support FOREIGN KEY constraints."""
        return False

    def supports_fk_on_delete(self) -> bool:
        return False

    def supports_fk_on_update(self) -> bool:
        return False

    def supports_add_constraint(self) -> bool:
        """ClickHouse does not support ALTER TABLE ADD CONSTRAINT."""
        return False

    def supports_drop_constraint(self) -> bool:
        """ClickHouse does not support ALTER TABLE DROP CONSTRAINT."""
        return False

    def supports_drop_table_cascade(self) -> bool:
        """ClickHouse DROP TABLE does not support CASCADE."""
        return False

    def supports_drop_table_restrict(self) -> bool:
        """ClickHouse DROP TABLE does not support RESTRICT."""
        return False

    def supports_alter_column_type(self) -> bool:
        """ClickHouse supports MODIFY COLUMN type changes."""
        return True

    def supports_rename_column(self) -> bool:
        """ClickHouse supports RENAME COLUMN."""
        return True

    def supports_rename_table(self) -> bool:
        """ClickHouse supports RENAME TABLE."""
        return True

    def supports_table_like_syntax(self) -> bool:
        """ClickHouse supports CREATE TABLE ... AS SELECT / LIKE."""
        return True

    def supports_ilike(self) -> bool:
        """ClickHouse supports ILIKE operator."""
        return True

    def supports_index_type(self) -> bool:
        """ClickHouse skip indexes support USING keyword for index type."""
        return True

    def format_create_table_statement(self, expr: "CreateTableExpression") -> Tuple[str, tuple]:
        """
        Format CREATE TABLE statement for ClickHouse.

        This method handles ClickHouse-specific syntax including:
        - LIKE syntax (copying table structure)
        - Inline index definitions
        - Storage options (ENGINE, CHARSET, COLLATE)
        - Table-level comments
        - AUTO_INCREMENT in column definitions

        Args:
            expr: CreateTableExpression instance

        Returns:
            Tuple of (SQL string, parameters tuple)
        """
        # Check for LIKE syntax in dialect_options (highest priority)
        if "like_table" in expr.dialect_options:
            return self.format_create_table_like(expr)

        # Build standard CREATE TABLE statement

        all_params: List[Any] = []

        # Build CREATE TABLE header
        parts = ["CREATE TABLE"]
        if expr.temporary:
            parts.append("TEMPORARY")
        if expr.if_not_exists:
            parts.append("IF NOT EXISTS")
        parts.append(self.format_identifier(expr.table_name))

        # Build column definitions
        column_parts = []
        for col_def in expr.columns:
            col_sql, col_params = self.format_column_definition(col_def)
            column_parts.append(col_sql)
            all_params.extend(col_params)

        # Build table constraints
        for t_const in expr.table_constraints:
            const_sql, const_params = self.format_table_constraint(t_const)
            column_parts.append(const_sql)
            all_params.extend(const_params)

        # Build inline indexes (ClickHouse-specific)
        for idx_def in expr.indexes:
            idx_sql = self.format_inline_index(idx_def)
            column_parts.append(idx_sql)

        # Combine all parts
        parts.append(f"({', '.join(column_parts)})")

        # Add storage options (ClickHouse-specific format)
        if expr.storage_options:
            storage_sql = self.format_table_engine_clauses(expr.storage_options)
            if storage_sql:
                parts.append(storage_sql)

        # Add table-level comment (from dialect_options)
        if "comment" in expr.dialect_options:
            escaped_comment = self._escape_sql_string(expr.dialect_options["comment"])
            parts.append(f"COMMENT '{escaped_comment}'")

        # Add partition clause generated through PartitionClause expression.
        if expr.partition is not None:
            partition_sql, partition_params = expr.partition.to_sql()
            if partition_sql:
                parts.append(partition_sql.strip())
                all_params.extend(partition_params)

        return " ".join(parts), tuple(all_params)

    def supports_add_column_if_not_exists(self) -> bool:
        """ClickHouse supports ADD COLUMN IF NOT EXISTS."""
        return True

    def supports_drop_column_if_exists(self) -> bool:
        """ClickHouse supports DROP COLUMN IF EXISTS."""
        return True

    def supports_drop_constraint_if_exists(self) -> bool:
        return False

    def format_add_column_action(self, action) -> Tuple[str, tuple]:
        column_sql, column_params = self.format_column_definition(action.column)
        parts = []
        if getattr(action, "if_not_exists", None) is True:
            parts.append("ADD COLUMN IF NOT EXISTS")
        else:
            parts.append("ADD COLUMN")
        parts.append(column_sql)
        after = action.dialect_options.get("after")
        if after:
            parts.append(f"AFTER {self.format_identifier(after)}")
        return " ".join(parts), column_params

    def format_drop_column_action(self, action) -> Tuple[str, tuple]:
        parts = []
        if getattr(action, "if_exists", None) is True:
            parts.append("DROP COLUMN IF EXISTS")
        else:
            parts.append("DROP COLUMN")
        parts.append(self.format_identifier(action.column_name))
        return " ".join(parts), ()

    def format_drop_table_constraint_action(self, action) -> Tuple[str, tuple]:
        if getattr(action, "if_exists", None) is True:
            raise UnsupportedFeatureError(
                self.name, "DROP CONSTRAINT IF EXISTS",
                suggestion="ClickHouse does not support DROP CONSTRAINT."
            )
        raise UnsupportedFeatureError(
            self.name, "DROP CONSTRAINT",
            suggestion="ClickHouse does not support table constraints."
        )

    def format_alter_column_action(self, action) -> Tuple[str, tuple]:
        """Format ALTER TABLE ... ALTER COLUMN {SET DEFAULT | DROP DEFAULT}.

        ClickHouse 8.0 syntax is ``ALTER TABLE t ALTER [COLUMN] col {SET DEFAULT
        literal | DROP DEFAULT}``. Unlike the generic SQL-standard renderer,
        ClickHouse requires a literal for SET DEFAULT (no parenthesised
        expressions / parameters), so we inline the value.
        """
        operation = getattr(action.operation, "value", None) or str(action.operation)
        col_name = self.format_identifier(action.column_name)

        if operation == "DROP DEFAULT":
            return f"ALTER COLUMN {col_name} DROP DEFAULT", ()

        if operation == "SET DEFAULT":
            new_value = getattr(action, "new_value", None)
            if isinstance(new_value, str):
                escaped = self._escape_sql_string(new_value)
                return f"ALTER COLUMN {col_name} SET DEFAULT '{escaped}'", ()
            if isinstance(new_value, bool):
                return f"ALTER COLUMN {col_name} SET DEFAULT {1 if new_value else 0}", ()
            if new_value is None:
                raise ValueError("SET DEFAULT requires a default value")
            if isinstance(new_value, (int, float)):
                return f"ALTER COLUMN {col_name} SET DEFAULT {new_value}", ()
            if hasattr(new_value, "to_sql"):
                value_sql, value_params = new_value.to_sql()
                return f"ALTER COLUMN {col_name} SET DEFAULT {value_sql}", tuple(value_params)
            return f"ALTER COLUMN {col_name} SET DEFAULT {new_value}", ()

        # Fall through to the SQL-standard rendering for other operations.
        return super().format_alter_column_action(action)

    def format_create_table_like(self, expr: "CreateTableExpression") -> Tuple[str, tuple]:
        """Format CREATE TABLE ... LIKE statement for ClickHouse.

        Args:
            expr: CreateTableExpression instance with like_table in dialect_options

        Returns:
            Tuple of (SQL string, parameters tuple)
        """
        like_table = expr.dialect_options.get("like_table")

        parts = ["CREATE TABLE"]
        if expr.temporary:
            parts.append("TEMPORARY")
        if expr.if_not_exists:
            parts.append("IF NOT EXISTS")
        parts.append(self.format_identifier(expr.table_name))

        if isinstance(like_table, tuple):
            schema, table = like_table
            like_table_str = f"{self.format_identifier(schema)}.{self.format_identifier(table)}"
        else:
            like_table_str = self.format_identifier(like_table)

        parts.append(f"LIKE {like_table_str}")
        return ' '.join(parts), ()

    def _format_table_constraint_clickhouse(
        self,
        t_const: "TableConstraint",
        TableConstraintType
    ) -> Tuple[str, List[Any]]:
        """Format a table-level constraint.

        ClickHouse supports only PRIMARY KEY among table-level constraints;
        UNIQUE and FOREIGN KEY constraints are not supported.
        """
        parts = []
        params: List[Any] = []

        if t_const.constraint_type == TableConstraintType.PRIMARY_KEY:
            if t_const.columns:
                cols_str = ', '.join(self.format_identifier(c) for c in t_const.columns)
                parts.append(f"PRIMARY KEY ({cols_str})")
        elif t_const.constraint_type == TableConstraintType.UNIQUE:
            raise UnsupportedFeatureError(
                self.name, "UNIQUE table constraint",
                suggestion="ClickHouse does not support UNIQUE constraints."
            )
        elif t_const.constraint_type == TableConstraintType.FOREIGN_KEY:
            raise UnsupportedFeatureError(
                self.name, "FOREIGN KEY constraint",
                suggestion="ClickHouse does not support FOREIGN KEY constraints."
            )

        return ' '.join(parts), params

    def _format_inline_index_clickhouse(self, idx_def: "IndexDefinition") -> str:
        """Format an inline index definition (ClickHouse-specific)."""
        parts = []

        if idx_def.unique:
            raise UnsupportedFeatureError(
                self.name, "UNIQUE index",
                suggestion="ClickHouse cannot enforce unique indexes."
            )

        parts.append("INDEX")
        parts.append(self.format_identifier(idx_def.name))

        cols_str = ', '.join(self.format_identifier(c) for c in idx_def.columns)
        parts.append(f"({cols_str})")

        # ClickHouse USING syntax for index type
        if idx_def.type:
            parts.append(f"USING {idx_def.type}")

        return ' '.join(parts)

    def _format_storage_options_clickhouse(self, storage_options: Dict[str, Any]) -> str:
        """
        Format storage options for ClickHouse.

        Args:
            storage_options: Dict with keys like 'ENGINE', 'ORDER BY', 'PARTITION BY'

        Returns:
            Formatted storage options string (e.g., "ENGINE = MergeTree() ORDER BY id")
        """
        parts = []
        for key, value in storage_options.items():
            if isinstance(value, str):
                parts.append(f"{key}={value}")
            else:
                parts.append(f"{key}={value}")
        return ' '.join(parts)
    # endregion

    # region Trigger Support (ClickHouse does not support triggers)
    def supports_trigger(self) -> bool:
        """ClickHouse does not support triggers."""
        return False

    def supports_create_trigger(self) -> bool:
        return False

    def supports_drop_trigger(self) -> bool:
        return False

    def supports_instead_of_trigger(self) -> bool:
        return False

    def supports_statement_trigger(self) -> bool:
        return False

    def supports_trigger_referencing(self) -> bool:
        return False

    def supports_trigger_when(self) -> bool:
        return False

    def supports_trigger_if_not_exists(self) -> bool:
        return False

    def format_create_trigger_statement(
        self,
        expr: "CreateTriggerExpression",
    ):
        """Format CREATE TRIGGER statement (ClickHouse syntax).

        ClickHouse differences from SQL:1999:
        - Does not support INSTEAD OF triggers
        - Does not support FOR EACH STATEMENT
        - Does not support WHEN condition
        - Does not support REFERENCING clause
        - Uses trigger body directly instead of function call
        """
        if not self.supports_trigger():
            raise UnsupportedFeatureError(self.name, "triggers")

        if expr.timing.value == "INSTEAD OF":
            raise UnsupportedFeatureError(
                self.name,
                "INSTEAD OF triggers (ClickHouse does not support this feature)"
            )

        if expr.level and expr.level.value == "FOR EACH STATEMENT":
            raise UnsupportedFeatureError(
                self.name,
                "FOR EACH STATEMENT triggers (ClickHouse only supports FOR EACH ROW)"
            )

        if expr.condition:
            raise UnsupportedFeatureError(
                self.name,
                "WHEN condition in triggers (ClickHouse does not support this feature)"
            )

        if expr.referencing:
            raise UnsupportedFeatureError(
                self.name,
                "REFERENCING clause in triggers (ClickHouse does not support this feature)"
            )

        if len(expr.events) > 1:
            raise UnsupportedFeatureError(
                self.name,
                "multiple trigger events (ClickHouse only supports single event)"
            )

        if expr.update_columns:
            raise UnsupportedFeatureError(
                self.name,
                "UPDATE OF column_list (ClickHouse does not support this syntax)"
            )

        parts = ["CREATE TRIGGER"]

        if expr.if_not_exists and self.supports_trigger_if_not_exists():
            parts.append("IF NOT EXISTS")

        parts.append(self.format_identifier(expr.trigger_name))

        parts.append(expr.timing.value)

        if expr.events:
            parts.append(expr.events[0].value)

        parts.append("ON")
        parts.append(self.format_identifier(expr.table_name))

        parts.append("FOR EACH ROW")

        if expr.function_name:
            parts.append("CALL")
            parts.append(self.format_identifier(expr.function_name))

        return " ".join(parts), ()

    def format_drop_trigger_statement(
        self,
        expr: "DropTriggerExpression",
    ):
        """Format DROP TRIGGER statement (ClickHouse syntax)."""
        if not self.supports_trigger():
            raise UnsupportedFeatureError(self.name, "triggers")

        parts = ["DROP TRIGGER"]

        if expr.if_exists:
            parts.append("IF EXISTS")

        parts.append(self.format_identifier(expr.trigger_name))

        return " ".join(parts), ()
    # endregion
    
    # region FULLTEXT Index & Search Support (ClickHouse does not support standard FULLTEXT)
    def supports_fulltext_index(self) -> bool:
        """ClickHouse does not support standard FULLTEXT indexes (uses skip indexes instead)."""
        return False

    def supports_fulltext_parser(self) -> bool:
        return False

    def supports_fulltext_boolean_mode(self) -> bool:
        return False

    def supports_fulltext_query_expansion(self) -> bool:
        return False

    def format_fulltext_match(
        self, columns: List[str], search_term: str, mode: Optional[str] = None
    ) -> Tuple[str, Tuple]:
        """Format MATCH ... AGAINST expression for ClickHouse full-text search.

        Args:
            columns: Columns to search
            search_term: Search term or query
            mode: Search mode ('BOOLEAN', 'QUERY EXPANSION', 'WITH QUERY EXPANSION')

        Returns:
            Tuple of (SQL string, parameters tuple)
        """
        if not self.supports_fulltext_index():
            from rhosocial.activerecord.backend.dialect.exceptions import UnsupportedFeatureError
            raise UnsupportedFeatureError(self.name, "FULLTEXT search")

        cols_str = ", ".join(self.format_identifier(c) for c in columns)
        ph = self.get_parameter_placeholder()
        if mode:
            mode_upper = mode.upper()
            if mode_upper == "BOOLEAN":
                return f"MATCH({cols_str}) AGAINST({ph} IN BOOLEAN MODE)", (search_term,)
            if mode_upper in ("QUERY EXPANSION", "WITH QUERY EXPANSION"):
                return f"MATCH({cols_str}) AGAINST({ph} WITH QUERY EXPANSION)", (search_term,)
        return f"MATCH({cols_str}) AGAINST({ph} IN NATURAL LANGUAGE MODE)", (search_term,)

    def format_create_fulltext_index_statement(self, expr) -> Tuple[str, tuple]:
        """Format CREATE FULLTEXT INDEX expression for ClickHouse.

        Args:
            expr: CreateFulltextIndexExpression object with index_name, table_name,
                  columns, if_not_exists, and parser attributes.

        Returns:
            Tuple of (SQL string, parameters tuple)
        """
        if not self.supports_fulltext_index():
            from rhosocial.activerecord.backend.dialect.exceptions import UnsupportedFeatureError
            raise UnsupportedFeatureError(self.name, "FULLTEXT INDEX")

        parts = ["CREATE FULLTEXT INDEX"]
        if expr.if_not_exists:
            parts.append("IF NOT EXISTS")
        parts.append(self.format_identifier(expr.index_name))
        parts.append("ON")
        parts.append(self.format_identifier(expr.table_name))
        cols_str = ", ".join(self.format_identifier(c) for c in expr.columns)
        parts.append(f"({cols_str})")
        if expr.parser:
            parts.append(f"WITH PARSER {self.format_identifier(expr.parser)}")
        return " ".join(parts), ()

    def format_drop_fulltext_index_statement(self, expr) -> Tuple[str, tuple]:
        """Format DROP FULLTEXT INDEX expression for ClickHouse.

        ClickHouse uses DROP INDEX ... ON syntax for dropping FULLTEXT indexes.

        Args:
            expr: DropFulltextIndexExpression object with index_name, table_name,
                  and if_exists attributes.

        Returns:
            Tuple of (SQL string, parameters tuple)
        """
        if not self.supports_fulltext_index():
            from rhosocial.activerecord.backend.dialect.exceptions import UnsupportedFeatureError
            raise UnsupportedFeatureError(self.name, "FULLTEXT INDEX")

        parts = ["DROP INDEX"]
        if expr.if_exists:
            parts.append("IF EXISTS")
        parts.append(self.format_identifier(expr.index_name))
        parts.append("ON")
        parts.append(self.format_identifier(expr.table_name))
        return " ".join(parts), ()

    # endregion

    # region ClickHouse Index Features
    def supports_invisible_index(self) -> bool:
        """Whether INVISIBLE indexes are supported."""
        return False  # ClickHouse does not support INVISIBLE indexes

    def supports_descending_index(self) -> bool:
        """Whether descending indexes are supported."""
        return False  # ClickHouse does not support DESCENDING index keyword

    def supports_functional_index(self) -> bool:
        """Whether functional (expression) indexes are supported.

        ClickHouse skip indexes can be based on expressions.
        """
        return True

    def supports_check_constraint(self) -> bool:
        """Whether CHECK constraints are enforced."""
        return False  # ClickHouse does not support CHECK constraints

    # ConstraintSupport protocol implementation
    def supports_constraint_enforced(self) -> bool:
        """Whether ENFORCED/NOT ENFORCED constraint control is supported."""
        return False

    def supports_fk_match(self) -> bool:
        """Whether MATCH {SIMPLE|PARTIAL|FULL} is supported."""
        return False

    def supports_deferrable_constraint(self) -> bool:
        """Whether DEFERRABLE constraints are supported."""
        return False

    def supports_generated_column(self) -> bool:
        """Whether generated (computed) columns are supported."""
        return False  # ClickHouse does not support generated columns

    def supports_default_column_value_expression(self) -> bool:
        """Whether DEFAULT column values can use expressions."""
        return True  # ClickHouse supports expressions in DEFAULT values

    # endregion

    # region Transaction Control

    # ClickHouse function version support: function_name -> (min_version, max_version)
    # min_version: minimum supported version (inclusive), None = all versions
    # max_version: maximum supported version (inclusive), None = no upper limit
    #
    # Core (generic) SQL functions are supported on all ClickHouse versions.
    # ClickHouse-specific function wrappers (JSON_*, ST_*, etc.) are NOT provided
    # by this backend; use ClickHouse's native functions directly.
    _CLICKHOUSE_FUNCTION_VERSIONS = {
        # Core math functions: All ClickHouse versions
        "round_": (None, None),
        "pow": (None, None),
        "power": (None, None),
        "sqrt": (None, None),
        "mod": (None, None),
        "ceil": (None, None),
        "floor": (None, None),
        "trunc": (None, None),
        "max_": (None, None),
        "min_": (None, None),
        "avg": (None, None),
    }

    def supports_functions(self) -> Dict[str, bool]:
        """Return supported SQL functions as function_name -> bool mapping.

        Reports the core SQL function set. ClickHouse-specific function
        wrappers are not provided by this backend (use ClickHouse's native
        functions, e.g. ``JSONExtract*``, directly).

        Returns:
            Dict mapping function names to True (supported) or False.
        """
        from rhosocial.activerecord.backend.expression.functions import (
            __all__ as core_functions,
        )

        expression_constructors = {
            "xmlagg",
            "xmlattributes",
            "xmlcomment",
            "xmlconcat",
            "xmlelement",
            "xmlexists",
            "xmlforest",
            "xmlparse",
            "xmlpi",
            "xmlquery",
            "xmlroot",
            "xmlserialize",
            "xmltable",
        }
        result = {}
        for func_name in core_functions:
            if func_name not in expression_constructors:
                result[func_name] = self._is_clickhouse_function_supported(func_name)
        return result

        return result

    def _is_clickhouse_function_supported(self, func_name: str) -> bool:
        """Check if a ClickHouse-specific function is supported based on version.

        Args:
            func_name: Name of the ClickHouse function

        Returns:
            True if supported, False otherwise
        """
        version_range = self._CLICKHOUSE_FUNCTION_VERSIONS.get(func_name)
        if version_range is None:
            return True

        min_version, max_version = version_range

        if min_version is not None and self.version < min_version:
            return False

        if max_version is not None and self.version > max_version:
            return False

        return True

    def supports_transaction_mode(self) -> bool:
        """ClickHouse does not support transactions."""
        return False

    def supports_isolation_level_in_begin(self) -> bool:
        return False

    def supports_read_only_transaction(self) -> bool:
        return False

    def supports_deferrable_transaction(self) -> bool:
        return False

    def supports_savepoint(self) -> bool:
        return False

    def format_set_transaction(self, expr: "SetTransactionExpression") -> Tuple[str, tuple]:
        """ClickHouse does not support transactions."""
        raise UnsupportedFeatureError(
            self.name, "transactions",
            "ClickHouse does not support SET TRANSACTION."
        )

    def format_begin_transaction(self, expr: "BeginTransactionExpression") -> Tuple[str, tuple]:
        """ClickHouse does not support transactions."""
        raise UnsupportedFeatureError(
            self.name, "transactions",
            "ClickHouse does not support START TRANSACTION."
        )

    # endregion

    # region ClickHouse-specific DML Operations

    def supports_insert_ignore(self) -> bool:
        """Whether INSERT IGNORE is supported."""
        return False  # ClickHouse does not support INSERT IGNORE

    def supports_replace_into(self) -> bool:
        """Whether REPLACE INTO is supported."""
        return False  # ClickHouse does not support REPLACE INTO

    def format_insert_statement(self, expr: "InsertExpression") -> Tuple[str, tuple]:
        """Format a ClickHouse INSERT statement.

        ClickHouse does not support INSERT IGNORE / REPLACE INTO / ON CONFLICT;
        those dialect options raise UnsupportedFeatureError. INSERT ... RETURNING
        is supported.
        """
        if self.strict_validation:
            expr.validate(strict=True)

        if expr.dialect_options.get("replace", False):
            raise UnsupportedFeatureError(
                self.name, "REPLACE INTO",
                suggestion="ClickHouse does not support REPLACE INTO."
            )
        if expr.dialect_options.get("ignore", False):
            raise UnsupportedFeatureError(
                self.name, "INSERT IGNORE",
                suggestion="ClickHouse does not support INSERT IGNORE."
            )
        if expr.on_conflict:
            raise UnsupportedFeatureError(
                self.name, "ON CONFLICT / ON DUPLICATE KEY",
                suggestion="ClickHouse does not support upsert conflict clauses."
            )

        all_params: List[Any] = []
        table_sql, table_params = expr.into.to_sql()
        all_params.extend(table_params)

        parts = ["INSERT INTO", table_sql]

        if expr.columns:
            columns_sql = "(" + ", ".join([self.format_identifier(c) for c in expr.columns]) + ")"
            parts.append(columns_sql)

        # Format source (VALUES, SELECT, or DEFAULT VALUES)
        from rhosocial.activerecord.backend.expression.statements import (
            DefaultValuesSource,
            SelectSource,
            ValuesSource,
        )

        if isinstance(expr.source, DefaultValuesSource):
            parts.append("DEFAULT VALUES")
        elif isinstance(expr.source, ValuesSource):
            all_rows_sql = []
            for row in expr.source.values_list:
                row_sql, row_params = [], []
                for val in row:
                    s, p = val.to_sql()
                    row_sql.append(s)
                    row_params.extend(p)
                all_rows_sql.append(f"({', '.join(row_sql)})")
                all_params.extend(row_params)
            parts.append("VALUES " + ", ".join(all_rows_sql))
        elif isinstance(expr.source, SelectSource):
            s_sql, s_params = expr.source.select_query.to_sql()
            parts.append(s_sql)
            all_params.extend(s_params)

        sql = " ".join(parts)

        if expr.returning:
            returning_sql, returning_params = self.format_returning_clause(expr.returning)
            sql += f" {returning_sql}"
            all_params.extend(returning_params)

        return sql, tuple(all_params)

    def supports_json_table(self) -> bool:
        """Whether SQL-standard JSON_TABLE is supported.

        ClickHouse has a JSON family of functions but no SQL-standard JSON_TABLE.
        """
        return False

    def format_json_table_expression(self, expr) -> Tuple[str, tuple]:
        """JSON_TABLE is not supported by ClickHouse."""
        raise UnsupportedFeatureError(
            self.name,
            "JSON_TABLE",
            suggestion="Use JSONExtract/JSONExtractKeys with arrayJoin or subqueries instead.",
        )

    # endregion

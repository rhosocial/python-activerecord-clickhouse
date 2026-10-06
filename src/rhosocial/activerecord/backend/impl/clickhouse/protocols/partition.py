# src/rhosocial/activerecord/backend/impl/clickhouse/protocols/partition.py
"""ClickHouse table partitioning protocol.

Split out of the former single-module ``clickhouse/protocols.py``; one
concern per module so the protocol surface stays legible.
"""

from typing import Any, Protocol, runtime_checkable, Tuple, TYPE_CHECKING

from rhosocial.activerecord.backend.dialect.protocols import PartitionSupport


if TYPE_CHECKING:  # pragma: no cover
    from rhosocial.activerecord.backend.impl.clickhouse.expression.partition import (
        ClickHouseAddPartitionExpression,
        ClickHouseAnalyzePartitionExpression,
        ClickHouseCheckPartitionExpression,
        ClickHouseCoalescePartitionExpression,
        ClickHouseDropPartitionExpression,
        ClickHouseExchangePartitionExpression,
        ClickHouseGetPartitionsExpression,
        ClickHouseOptimizePartitionExpression,
        ClickHousePartitionByHash,
        ClickHousePartitionByKey,
        ClickHousePartitionByList,
        ClickHousePartitionByListColumns,
        ClickHousePartitionByRange,
        ClickHousePartitionByRangeColumns,
        ClickHousePartitionDefinition,
        ClickHousePartitionMaxValue,
        ClickHousePartitionValue,
        ClickHouseRebuildPartitionExpression,
        ClickHouseRemovePartitioningExpression,
        ClickHouseReorganizePartitionExpression,
        ClickHouseRepairPartitionExpression,
        ClickHouseSubpartitionClause,
        ClickHouseSubpartitionDefinition,
        ClickHouseTruncatePartitionExpression,
    )


@runtime_checkable
class ClickHousePartitionSupport(PartitionSupport, Protocol):
    """ClickHouse table partitioning protocol.

    ClickHouse extends the generic PartitionSupport contract with ClickHouse-specific
    partitioning strategies and ALTER TABLE partition maintenance statements.
    Executable maintenance statements are represented by ClickHouse-specific
    expressions and formatted by the methods declared here.
    """

    def supports_range_columns_partitioning(self) -> bool:
        """Whether RANGE COLUMNS partitioning is supported."""
        ...

    def supports_list_columns_partitioning(self) -> bool:
        """Whether LIST COLUMNS partitioning is supported."""
        ...

    def supports_key_table_partitioning(self) -> bool:
        """Whether KEY partitioning is supported."""
        ...

    def supports_linear_hash_partitioning(self) -> bool:
        """Whether LINEAR HASH partitioning is supported."""
        ...

    def supports_linear_key_partitioning(self) -> bool:
        """Whether LINEAR KEY partitioning is supported."""
        ...

    def supports_partition_definition_options(self) -> bool:
        """Whether partition definitions support extra ClickHouse options."""
        ...

    def supports_partition_value_maxvalue(self) -> bool:
        """Whether MAXVALUE partition boundary token is supported."""
        ...

    def supports_add_partition(self) -> bool:
        """Whether ADD PARTITION is supported."""
        ...

    def supports_drop_partition(self) -> bool:
        """Whether DROP PARTITION is supported."""
        ...

    def supports_truncate_partition(self) -> bool:
        """Whether TRUNCATE PARTITION is supported."""
        ...

    def supports_reorganize_partition(self) -> bool:
        """Whether REORGANIZE PARTITION is supported."""
        ...

    def supports_attach_partition(self) -> bool:
        """Whether ATTACH PARTITION is supported."""
        ...

    def supports_detach_partition(self) -> bool:
        """Whether DETACH PARTITION is supported."""
        ...

    def supports_remove_partitioning(self) -> bool:
        """Whether ALTER TABLE ... REMOVE PARTITIONING is supported."""
        ...

    def supports_coalesce_partition(self) -> bool:
        """Whether ALTER TABLE ... COALESCE PARTITION is supported."""
        ...

    def supports_exchange_partition(self) -> bool:
        """Whether ALTER TABLE ... EXCHANGE PARTITION is supported."""
        ...

    def supports_analyze_partition(self) -> bool:
        """Whether ALTER TABLE ... ANALYZE PARTITION is supported."""
        ...

    def supports_check_partition(self) -> bool:
        """Whether ALTER TABLE ... CHECK PARTITION is supported."""
        ...

    def supports_optimize_partition(self) -> bool:
        """Whether ALTER TABLE ... OPTIMIZE PARTITION is supported."""
        ...

    def supports_rebuild_partition(self) -> bool:
        """Whether ALTER TABLE ... REBUILD PARTITION is supported."""
        ...

    def supports_repair_partition(self) -> bool:
        """Whether ALTER TABLE ... REPAIR PARTITION is supported."""
        ...

    def format_partition_definition(self, definition: "ClickHousePartitionDefinition") -> Tuple[str, tuple]:
        """Format a ClickHouse PARTITION definition."""
        ...

    def format_partition_definition_options(self, options: dict) -> Tuple[str, tuple]:
        """Format ClickHouse PARTITION definition options."""
        ...

    def format_get_partitions_expression(self, expr: "ClickHouseGetPartitionsExpression") -> Tuple[str, tuple]:
        """Format a ``SELECT ... FROM information_schema.PARTITIONS`` query.

        Args:
            expr: ClickHouseGetPartitionsExpression with the target table name.

        Returns:
            Tuple of (SQL string, parameters tuple).
        """
        ...

    def format_partition_value(
        self,
        expr: "ClickHousePartitionValue | ClickHousePartitionMaxValue",
    ) -> Tuple[str, tuple]:
        """Format a ClickHouse partition boundary value."""
        ...

    def format_subpartition_by(self, expr: "ClickHouseSubpartitionClause") -> Tuple[str, tuple]:
        """Format ``SUBPARTITION BY {HASH|KEY}(...) SUBPARTITIONS N``.

        Args:
            expr: ClickHouseSubpartitionClause with strategy, optional expression,
                  optional count, and optional explicit definitions.

        Returns:
            Tuple of (SQL string, parameters tuple).

        Raises:
            UnsupportedFeatureError: if subpartitioning is not supported.
        """
        ...

    def format_subpartition_definition(self, definition: "ClickHouseSubpartitionDefinition") -> Tuple[str, tuple]:
        """Format a single ``SUBPARTITION name ...`` clause.

        Args:
            definition: ClickHouseSubpartitionDefinition with name and typed
                        partition options.

        Returns:
            Tuple of (SQL string, parameters tuple).

        Raises:
            ValueError: if the definition name is empty.
        """
        ...

    def format_partition_by_range(self, expr: "ClickHousePartitionByRange") -> Tuple[str, tuple]:
        """Format PARTITION BY RANGE."""
        ...

    def format_partition_by_range_columns(self, expr: "ClickHousePartitionByRangeColumns") -> Tuple[str, tuple]:
        """Format PARTITION BY RANGE COLUMNS."""
        ...

    def format_partition_by_list(self, expr: "ClickHousePartitionByList") -> Tuple[str, tuple]:
        """Format PARTITION BY LIST."""
        ...

    def format_partition_by_list_columns(self, expr: "ClickHousePartitionByListColumns") -> Tuple[str, tuple]:
        """Format PARTITION BY LIST COLUMNS."""
        ...

    def format_partition_by_hash(self, expr: "ClickHousePartitionByHash") -> Tuple[str, tuple]:
        """Format PARTITION BY HASH or LINEAR HASH."""
        ...

    def format_partition_by_key(self, expr: "ClickHousePartitionByKey") -> Tuple[str, tuple]:
        """Format PARTITION BY KEY or LINEAR KEY."""
        ...

    def format_add_partition_statement(self, expr: "ClickHouseAddPartitionExpression") -> Tuple[str, tuple]:
        """Format ALTER TABLE ... ADD PARTITION."""
        ...

    def format_drop_partition_statement(self, expr: "ClickHouseDropPartitionExpression") -> Tuple[str, tuple]:
        """Format ALTER TABLE ... DROP PARTITION."""
        ...

    def format_truncate_partition_statement(self, expr: "ClickHouseTruncatePartitionExpression") -> Tuple[str, tuple]:
        """Format ALTER TABLE ... TRUNCATE PARTITION."""
        ...

    def format_reorganize_partition_statement(
        self,
        expr: "ClickHouseReorganizePartitionExpression",
    ) -> Tuple[str, tuple]:
        """Format ALTER TABLE ... REORGANIZE PARTITION."""
        ...

    def format_exchange_partition_statement(
        self,
        expr: "ClickHouseExchangePartitionExpression",
    ) -> Tuple[str, tuple]:
        """Format ALTER TABLE ... EXCHANGE PARTITION."""
        ...

    def format_remove_partitioning_statement(
        self,
        expr: "ClickHouseRemovePartitioningExpression",
    ) -> Tuple[str, tuple]:
        """Format ALTER TABLE ... REMOVE PARTITIONING."""
        ...

    def format_coalesce_partition_statement(
        self,
        expr: "ClickHouseCoalescePartitionExpression",
    ) -> Tuple[str, tuple]:
        """Format ALTER TABLE ... COALESCE PARTITION."""
        ...

    def format_analyze_partition_statement(
        self,
        expr: "ClickHouseAnalyzePartitionExpression",
    ) -> Tuple[str, tuple]:
        """Format ALTER TABLE ... ANALYZE PARTITION."""
        ...

    def format_check_partition_statement(
        self,
        expr: "ClickHouseCheckPartitionExpression",
    ) -> Tuple[str, tuple]:
        """Format ALTER TABLE ... CHECK PARTITION."""
        ...

    def format_optimize_partition_statement(
        self,
        expr: "ClickHouseOptimizePartitionExpression",
    ) -> Tuple[str, tuple]:
        """Format ALTER TABLE ... OPTIMIZE PARTITION."""
        ...

    def format_rebuild_partition_statement(
        self,
        expr: "ClickHouseRebuildPartitionExpression",
    ) -> Tuple[str, tuple]:
        """Format ALTER TABLE ... REBUILD PARTITION."""
        ...

    def format_repair_partition_statement(
        self,
        expr: "ClickHouseRepairPartitionExpression",
    ) -> Tuple[str, tuple]:
        """Format ALTER TABLE ... REPAIR PARTITION."""
        ...

    def format_partition_name_list(self, expr) -> Tuple[str, tuple]:
        """Format a list of partition names: `p0`, `p1`, ..."""
        ...

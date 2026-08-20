# src/rhosocial/activerecord/backend/impl/clickhouse/mixins/partition.py
from typing import Sequence, Tuple, Union, TYPE_CHECKING

from rhosocial.activerecord.backend.dialect.exceptions import UnsupportedFeatureError

if TYPE_CHECKING:  # pragma: no cover
    from rhosocial.activerecord.backend.expression.statements import PartitionClause
    from rhosocial.activerecord.backend.impl.clickhouse.expression.partition import (
        ClickHouseAddPartitionExpression,
        ClickHouseDropPartitionExpression,
        ClickHouseGetPartitionsExpression,
        ClickHousePartitionByHash,
        ClickHousePartitionByKey,
        ClickHousePartitionByList,
        ClickHousePartitionByListColumns,
        ClickHousePartitionByRange,
        ClickHousePartitionByRangeColumns,
        ClickHousePartitionDefinition,
        ClickHousePartitionMaxValue,
        ClickHousePartitionValue,
        ClickHouseExchangePartitionExpression,
        ClickHouseReorganizePartitionExpression,
        ClickHouseTruncatePartitionExpression,
        ClickHouseRemovePartitioningExpression,
        ClickHouseCoalescePartitionExpression,
        ClickHouseAnalyzePartitionExpression,
        ClickHouseCheckPartitionExpression,
        ClickHouseOptimizePartitionExpression,
        ClickHouseRebuildPartitionExpression,
        ClickHouseRepairPartitionExpression,
        ClickHouseSubpartitionClause,
        ClickHouseSubpartitionDefinition,
    )


class ClickHousePartitionMixin:
    """ClickHouse table partitioning implementation.

    WARNING: ClickHouse does not support MySQL declarative partitioning
    (``PARTITION BY RANGE/LIST/HASH/KEY`` with explicit partition definitions,
    subpartitioning, and ``ALTER TABLE ... PARTITION`` maintenance statements).
    ClickHouse partitioning is expressed as a ``PARTITION BY`` expression in
    ``CREATE TABLE``, handled by ``ClickHouseTableEngineMixin``. All MySQL
    declarative partition SQL generation methods in this class raise
    ``UnsupportedFeatureError``; the corresponding ``supports_*`` switches
    return ``False``.
    """

    def supports_table_partitioning(self) -> bool:
        """ClickHouse supports ``PARTITION BY`` expression in CREATE TABLE."""
        return True

    def supports_partitioned_table_creation(self) -> bool:
        """ClickHouse supports ``PARTITION BY`` in partitioned table creation."""
        return True

    def supports_range_table_partitioning(self) -> bool:
        return False

    def supports_list_table_partitioning(self) -> bool:
        return False

    def supports_hash_table_partitioning(self) -> bool:
        return False

    def supports_key_table_partitioning(self) -> bool:
        return False

    def supports_subpartitioning(self) -> bool:
        """ClickHouse has no subpartitioning."""
        return False

    def supports_range_columns_partitioning(self) -> bool:
        return False

    def supports_list_columns_partitioning(self) -> bool:
        return False

    def supports_linear_hash_partitioning(self) -> bool:
        return False

    def supports_linear_key_partitioning(self) -> bool:
        return False

    def supports_add_partition(self) -> bool:
        return False

    def supports_drop_partition(self) -> bool:
        return False

    def supports_truncate_partition(self) -> bool:
        return False

    def supports_reorganize_partition(self) -> bool:
        return False

    def supports_attach_partition(self) -> bool:
        return False

    def supports_detach_partition(self) -> bool:
        return False

    def supports_partition_metadata_introspection(self) -> bool:
        """ClickHouse partition introspection uses ``system.parts``, not
        MySQL ``information_schema.PARTITIONS``."""
        return False

    def supports_partition_definition_options(self) -> bool:
        return False

    def supports_partition_value_maxvalue(self) -> bool:
        return False

    def supports_remove_partitioning(self) -> bool:
        return False

    def supports_coalesce_partition(self) -> bool:
        return False

    def supports_exchange_partition(self) -> bool:
        return False

    def supports_analyze_partition(self) -> bool:
        return False

    def supports_check_partition(self) -> bool:
        return False

    def supports_optimize_partition(self) -> bool:
        return False

    def supports_rebuild_partition(self) -> bool:
        return False

    def supports_repair_partition(self) -> bool:
        return False

    def _unsupported(self, feature: str) -> None:
        """Raise UnsupportedFeatureError for MySQL declarative partitioning.

        ClickHouse partitioning is a ``PARTITION BY`` expression in
        ``CREATE TABLE`` (see ``ClickHouseTableEngineMixin``), not MySQL
        declarative partitioning.
        """
        raise UnsupportedFeatureError(
            self.name,
            feature,
            suggestion="ClickHouse uses PARTITION BY expression in CREATE TABLE, not MySQL declarative partitioning.",
        )

    def format_partition_clause(self, expr: "PartitionClause") -> Tuple[str, tuple]:
        """Format ClickHouse PARTITION BY clause from a PartitionClause expression.

        MySQL declarative partitioning is not supported by ClickHouse.
        """
        self._unsupported(f"{expr.method} declarative partitioning")

    def format_partition_by_range(self, expr: "ClickHousePartitionByRange") -> Tuple[str, tuple]:
        """MySQL ``PARTITION BY RANGE`` is not supported by ClickHouse."""
        self._unsupported("RANGE declarative partitioning")

    def format_partition_by_range_columns(self, expr: "ClickHousePartitionByRangeColumns") -> Tuple[str, tuple]:
        """MySQL ``PARTITION BY RANGE COLUMNS`` is not supported by ClickHouse."""
        self._unsupported("RANGE COLUMNS declarative partitioning")

    def format_partition_by_list(self, expr: "ClickHousePartitionByList") -> Tuple[str, tuple]:
        """MySQL ``PARTITION BY LIST`` is not supported by ClickHouse."""
        self._unsupported("LIST declarative partitioning")

    def format_partition_by_list_columns(self, expr: "ClickHousePartitionByListColumns") -> Tuple[str, tuple]:
        """MySQL ``PARTITION BY LIST COLUMNS`` is not supported by ClickHouse."""
        self._unsupported("LIST COLUMNS declarative partitioning")

    def format_partition_by_hash(self, expr: "ClickHousePartitionByHash") -> Tuple[str, tuple]:
        """MySQL ``PARTITION BY HASH`` is not supported by ClickHouse."""
        self._unsupported("HASH declarative partitioning")

    def format_partition_by_key(self, expr: "ClickHousePartitionByKey") -> Tuple[str, tuple]:
        """MySQL ``PARTITION BY KEY`` is not supported by ClickHouse."""
        self._unsupported("KEY declarative partitioning")

    def format_partition_definition(self, definition: "ClickHousePartitionDefinition") -> Tuple[str, tuple]:
        """MySQL partition definitions are not supported by ClickHouse."""
        self._unsupported("partition definitions")

    def format_partition_definition_options(self, options: dict) -> Tuple[str, tuple]:
        """MySQL partition definition options are not supported by ClickHouse."""
        self._unsupported("partition definition options")

    def format_get_partitions_expression(self, expr: "ClickHouseGetPartitionsExpression") -> Tuple[str, tuple]:
        """MySQL ``SELECT ... FROM information_schema.PARTITIONS`` is not supported.

        ClickHouse partition introspection uses the ``system.parts`` table.

        Args:
            expr: ClickHouseGetPartitionsExpression with the target table name.

        Raises:
            UnsupportedFeatureError: always.
        """
        self._unsupported("information_schema.PARTITIONS introspection")

    def format_partition_value(
        self,
        expr: Union["ClickHousePartitionValue", "ClickHousePartitionMaxValue"],
    ) -> Tuple[str, tuple]:
        """MySQL partition boundary values are not supported by ClickHouse."""
        self._unsupported("partition boundary VALUES")

    def format_subpartition_by(self, expr: "ClickHouseSubpartitionClause") -> Tuple[str, tuple]:
        """MySQL ``SUBPARTITION BY`` is not supported by ClickHouse."""
        self._unsupported("subpartitioning")

    def format_subpartition_definition(self, definition: "ClickHouseSubpartitionDefinition") -> Tuple[str, tuple]:
        """MySQL subpartition definitions are not supported by ClickHouse."""
        self._unsupported("subpartition definitions")

    def format_add_partition_statement(self, expr: "ClickHouseAddPartitionExpression") -> Tuple[str, tuple]:
        """MySQL ``ALTER TABLE ... ADD PARTITION`` is not supported by ClickHouse."""
        self._unsupported("ADD PARTITION")

    def format_drop_partition_statement(self, expr: "ClickHouseDropPartitionExpression") -> Tuple[str, tuple]:
        """MySQL declarative ``ALTER TABLE ... DROP PARTITION`` is not supported.

        ClickHouse removes partitions by partition-id via
        ``ALTER TABLE ... DROP PARTITION``.
        """
        self._unsupported("declarative DROP PARTITION")

    def format_truncate_partition_statement(self, expr: "ClickHouseTruncatePartitionExpression") -> Tuple[str, tuple]:
        """MySQL ``ALTER TABLE ... TRUNCATE PARTITION`` is not supported by ClickHouse."""
        self._unsupported("TRUNCATE PARTITION")

    def format_reorganize_partition_statement(
        self,
        expr: "ClickHouseReorganizePartitionExpression",
    ) -> Tuple[str, tuple]:
        """MySQL ``ALTER TABLE ... REORGANIZE PARTITION`` is not supported by ClickHouse."""
        self._unsupported("REORGANIZE PARTITION")

    def format_exchange_partition_statement(
        self,
        expr: "ClickHouseExchangePartitionExpression",
    ) -> Tuple[str, tuple]:
        """MySQL ``ALTER TABLE ... EXCHANGE PARTITION`` is not supported by ClickHouse."""
        self._unsupported("EXCHANGE PARTITION")

    def format_partition_name_list(self, partitions: Sequence[str]) -> str:
        """MySQL partition-name lists are not supported by ClickHouse."""
        self._unsupported("partition name list")

    def format_remove_partitioning_statement(
        self,
        expr: "ClickHouseRemovePartitioningExpression",
    ) -> Tuple[str, tuple]:
        """MySQL ``ALTER TABLE ... REMOVE PARTITIONING`` is not supported by ClickHouse."""
        self._unsupported("REMOVE PARTITIONING")

    def format_coalesce_partition_statement(
        self,
        expr: "ClickHouseCoalescePartitionExpression",
    ) -> Tuple[str, tuple]:
        """MySQL ``ALTER TABLE ... COALESCE PARTITION`` is not supported by ClickHouse."""
        self._unsupported("COALESCE PARTITION")

    def format_analyze_partition_statement(
        self,
        expr: "ClickHouseAnalyzePartitionExpression",
    ) -> Tuple[str, tuple]:
        """MySQL ``ALTER TABLE ... ANALYZE PARTITION`` is not supported by ClickHouse."""
        self._unsupported("ANALYZE PARTITION")

    def format_check_partition_statement(
        self,
        expr: "ClickHouseCheckPartitionExpression",
    ) -> Tuple[str, tuple]:
        """MySQL ``ALTER TABLE ... CHECK PARTITION`` is not supported by ClickHouse."""
        self._unsupported("CHECK PARTITION")

    def format_optimize_partition_statement(
        self,
        expr: "ClickHouseOptimizePartitionExpression",
    ) -> Tuple[str, tuple]:
        """MySQL ``ALTER TABLE ... OPTIMIZE PARTITION`` is not supported by ClickHouse."""
        self._unsupported("OPTIMIZE PARTITION")

    def format_rebuild_partition_statement(
        self,
        expr: "ClickHouseRebuildPartitionExpression",
    ) -> Tuple[str, tuple]:
        """MySQL ``ALTER TABLE ... REBUILD PARTITION`` is not supported by ClickHouse."""
        self._unsupported("REBUILD PARTITION")

    def format_repair_partition_statement(
        self,
        expr: "ClickHouseRepairPartitionExpression",
    ) -> Tuple[str, tuple]:
        """MySQL ``ALTER TABLE ... REPAIR PARTITION`` is not supported by ClickHouse."""
        self._unsupported("REPAIR PARTITION")

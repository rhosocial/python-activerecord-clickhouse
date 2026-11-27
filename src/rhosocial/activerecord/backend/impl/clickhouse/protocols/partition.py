# src/rhosocial/activerecord/backend/impl/clickhouse/protocols/partition.py
"""ClickHouse table partitioning protocol.

Split out of the former single-module ``clickhouse/protocols.py``; one
concern per module so the protocol surface stays legible.
"""

from typing import TYPE_CHECKING, Protocol, Tuple, runtime_checkable

from rhosocial.activerecord.backend.dialect.protocols import PartitionSupport

if TYPE_CHECKING:  # pragma: no cover
    from rhosocial.activerecord.backend.impl.clickhouse.expression.partition import (
        ClickHouseAttachPartitionStatement,
        ClickHouseClearInPartitionStatement,
        ClickHouseDetachPartitionStatement,
        ClickHouseDropPartitionStatement,
        ClickHouseFreezePartitionStatement,
        ClickHouseMovePartitionStatement,
        ClickHouseOptimizePartitionStatement,
        ClickHouseReplacePartitionStatement,
        ClickHouseUnfreezePartitionStatement,
    )


__all__ = ["ClickHousePartitionSupport"]


@runtime_checkable
class ClickHousePartitionSupport(PartitionSupport, Protocol):
    """ClickHouse table partitioning protocol.

    Feature Source: ClickHouse native — partitioning is a property of the
    ``MergeTree`` family, not a ``PARTITION ... VALUES`` statement

    ClickHouse declares partitioning as an arbitrary expression in
    ``CREATE TABLE``::

        ENGINE = MergeTree PARTITION BY toYYYYMM(VisitDate) ORDER BY Hour

    so there is no strategy to select, no ``VALUES LESS THAN`` / ``VALUES IN`` /
    ``MAXVALUE`` boundary, and no subpartitioning. That clause is written from
    the table's ``storage_options`` mapping by
    ``ClickHouseTableEngineMixin.format_table_engine_clauses``, not by a
    partition formatter; the generic ``PartitionSupport`` members
    (``format_partition_clause`` / ``_refuse_partition_definition``) refuse
    rather than invent a boundary syntax.

    Official Documentation:
    - Custom Partitioning Key (the ``PARTITION BY`` clause, and ``system.parts``):
      https://clickhouse.com/docs/engines/table-engines/mergetree-family/custom-partitioning-key
    - ALTER TABLE ... PARTITION — the complete inventory of partition
      operations, reproduced as ``ALTER_PARTITION_INVENTORY`` in
      ``mixins/partition.py``:
      https://clickhouse.com/docs/sql-reference/statements/alter/partition

    That inventory is also the evidence for the refusals. ClickHouse has no
    ``ADD PARTITION`` (a partition materialises when a row lands in it), no
    ``TRUNCATE PARTITION`` (the substitute is a light-weight mutation,
    ``ALTER TABLE ... DELETE IN PARTITION ... WHERE ...``), and no
    ``REORGANIZE`` / ``EXCHANGE`` / ``REMOVE PARTITIONING`` / ``COALESCE
    PARTITION`` / ``ANALYZE|CHECK|OPTIMIZE|REBUILD|REPAIR PARTITION`` /
    ``SUBPARTITION BY``. Checked directly on the 26.7.3.19 scenario server:
    ``ALTER TABLE t TRUNCATE PARTITION p`` answers with an expectation list
    enumerating every ``ALTER TABLE`` clause it accepts, and none of those
    names is among them; ``ALTER TABLE t ADD PARTITION (...)`` answers
    ``Expected one of: COLUMN, INDEX, STATISTICS, PROJECTION, CONSTRAINT``;
    ``ALTER TABLE t SUBPARTITION BY HASH(id)`` gets the same list.

    Version Requirements:
    - **None.** The three clauses below are MergeTree-family DDL and answer on
      every ClickHouse release this backend targets; no version gate is
      claimed, because none can be evidenced.
    """

    def _refuse_partition_definition(self, expr) -> Tuple[str, tuple]:
        """Refuse an inline ``PARTITION ... VALUES ...`` definition.

        Core's generic ``PartitionSupport`` names
        ``format_partition_definition_expression`` for this node; ClickHouse's
        mixin still carries the older ``_refuse_partition_definition`` refusal,
        so declare it here to keep the protocol and its mixin in step.
        """
        ...

    def supports_drop_partition(self) -> bool:
        """Whether ``ALTER TABLE ... DROP PARTITION ID`` is supported — it is."""
        ...

    def supports_detach_partition(self) -> bool:
        """Whether ``ALTER TABLE ... DETACH PARTITION ID`` is supported — it is."""
        ...

    def supports_attach_partition(self) -> bool:
        """Whether ``ALTER TABLE ... ATTACH PARTITION ID`` is supported — it is."""
        ...

    def supports_replace_partition(self) -> bool:
        """Whether ``ALTER TABLE ... REPLACE PARTITION ... FROM`` is supported — it is."""
        ...

    def supports_move_partition(self) -> bool:
        """Whether ``ALTER TABLE ... MOVE PARTITION ... TO`` is supported — it is."""
        ...

    def supports_freeze_partition(self) -> bool:
        """Whether ``ALTER TABLE ... FREEZE ...`` is supported — it is."""
        ...

    def supports_unfreeze_partition(self) -> bool:
        """Whether ``ALTER TABLE ... UNFREEZE ... WITH NAME`` is supported — it is."""
        ...

    def supports_clear_in_partition(self) -> bool:
        """Whether ``ALTER TABLE ... CLEAR COLUMN|INDEX|PROJECTION`` is supported — it is."""
        ...

    def supports_optimize_partition_final(self) -> bool:
        """Whether ``OPTIMIZE TABLE ... [PARTITION ...] [FINAL]`` is supported — it is."""
        ...

    def supports_add_partition(self) -> bool:
        """Whether ``ADD PARTITION`` exists — it does not; a partition materialises."""
        ...

    def supports_truncate_partition(self) -> bool:
        """Whether ``TRUNCATE PARTITION`` exists — it does not; see the class note."""
        ...

    def supports_split_partition(self) -> bool:
        """Whether ``SPLIT PARTITION`` exists — it does not."""
        ...

    def supports_merge_partition(self) -> bool:
        """Whether ``MERGE PARTITION`` exists — it does not."""
        ...

    def supports_exchange_partition(self) -> bool:
        """Whether a partition can be swapped with a standalone table — it cannot."""
        ...

    def supports_reorganize_partition(self) -> bool:
        """Whether MySQL's ``REORGANIZE PARTITION`` exists here — it does not."""
        ...

    def supports_coalesce_partition(self) -> bool:
        """Whether ``COALESCE PARTITION`` exists — it does not."""
        ...

    def supports_analyze_partition(self) -> bool:
        """Whether ``ANALYZE PARTITION`` exists — it does not."""
        ...

    def supports_check_partition(self) -> bool:
        """Whether ``CHECK PARTITION`` exists — it does not."""
        ...

    def supports_optimize_partition(self) -> bool:
        """Whether MySQL's ``OPTIMIZE PARTITION`` exists here — it does not."""
        ...

    def supports_rebuild_partition(self) -> bool:
        """Whether ``REBUILD PARTITION`` exists — it does not."""
        ...

    def supports_repair_partition(self) -> bool:
        """Whether ``REPAIR PARTITION`` exists — it does not."""
        ...

    def supports_remove_partitioning(self) -> bool:
        """Whether ``REMOVE PARTITIONING`` exists — it does not."""
        ...

    def format_drop_partition_statement(
        self, expr: "ClickHouseDropPartitionStatement"
    ) -> Tuple[str, tuple]:
        """Format ``ALTER TABLE ... DROP PARTITION ID '<partition_id>'``.

        Args:
            expr: expression carrying the table and the ``system.parts``
                partition id.

        Returns:
            Tuple of (SQL string, empty params tuple).
        """
        ...

    def format_detach_partition_statement(
        self, expr: "ClickHouseDetachPartitionStatement"
    ) -> Tuple[str, tuple]:
        """Format ``ALTER TABLE ... DETACH PARTITION ID '<partition_id>'``.

        Args:
            expr: expression carrying the table and the ``system.parts``
                partition id.

        Returns:
            Tuple of (SQL string, empty params tuple).
        """
        ...

    def format_attach_partition_statement(
        self, expr: "ClickHouseAttachPartitionStatement"
    ) -> Tuple[str, tuple]:
        """Format ``ALTER TABLE ... ATTACH PARTITION ID '<partition_id>'``.

        Args:
            expr: expression carrying the table and the ``system.parts``
                partition id.

        Returns:
            Tuple of (SQL string, empty params tuple).
        """
        ...

    def format_replace_partition_statement(
        self, expr: "ClickHouseReplacePartitionStatement"
    ) -> Tuple[str, tuple]:
        """Format ``ALTER TABLE ... REPLACE PARTITION ID '<id>' FROM <table>``."""
        ...

    def format_move_partition_statement(
        self, expr: "ClickHouseMovePartitionStatement"
    ) -> Tuple[str, tuple]:
        """Format ``ALTER TABLE ... MOVE PARTITION ID '<id>' TO <target>``."""
        ...

    def format_freeze_partition_statement(
        self, expr: "ClickHouseFreezePartitionStatement"
    ) -> Tuple[str, tuple]:
        """Format ``ALTER TABLE ... FREEZE [PARTITION ID '<id>'] [WITH NAME '<name>']``."""
        ...

    def format_unfreeze_partition_statement(
        self, expr: "ClickHouseUnfreezePartitionStatement"
    ) -> Tuple[str, tuple]:
        """Format ``ALTER TABLE ... UNFREEZE [PARTITION ID '<id>'] WITH NAME '<name>'``."""
        ...

    def format_clear_in_partition_statement(
        self, expr: "ClickHouseClearInPartitionStatement"
    ) -> Tuple[str, tuple]:
        """Format ``ALTER TABLE ... CLEAR COLUMN|INDEX|PROJECTION ... IN PARTITION``."""
        ...

    def format_optimize_partition_final_statement(
        self, expr: "ClickHouseOptimizePartitionStatement"
    ) -> Tuple[str, tuple]:
        """Format ``OPTIMIZE TABLE ... [PARTITION ID '<id>'] [FINAL]``."""
        ...

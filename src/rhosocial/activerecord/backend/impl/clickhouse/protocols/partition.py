# src/rhosocial/activerecord/backend/impl/clickhouse/protocols/partition.py
"""ClickHouse table partitioning protocol.

Split out of the former single-module ``clickhouse/protocols.py``; one
concern per module so the protocol surface stays legible.
"""

from typing import Protocol, runtime_checkable, Tuple, TYPE_CHECKING

from rhosocial.activerecord.backend.dialect.protocols import PartitionSupport


if TYPE_CHECKING:  # pragma: no cover
    from rhosocial.activerecord.backend.impl.clickhouse.expression.partition import (
        ClickHouseAttachPartitionExpression,
        ClickHouseDetachPartitionExpression,
        ClickHouseDropPartitionExpression,
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
    (``format_partition_clause`` / ``format_partition_definition``) refuse
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

    def supports_drop_partition(self) -> bool:
        """Whether ``ALTER TABLE ... DROP PARTITION ID`` is supported — it is."""
        ...

    def supports_detach_partition(self) -> bool:
        """Whether ``ALTER TABLE ... DETACH PARTITION ID`` is supported — it is."""
        ...

    def supports_attach_partition(self) -> bool:
        """Whether ``ALTER TABLE ... ATTACH PARTITION ID`` is supported — it is."""
        ...

    def format_drop_partition_statement(
        self, expr: "ClickHouseDropPartitionExpression"
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
        self, expr: "ClickHouseDetachPartitionExpression"
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
        self, expr: "ClickHouseAttachPartitionExpression"
    ) -> Tuple[str, tuple]:
        """Format ``ALTER TABLE ... ATTACH PARTITION ID '<partition_id>'``.

        Args:
            expr: expression carrying the table and the ``system.parts``
                partition id.

        Returns:
            Tuple of (SQL string, empty params tuple).
        """
        ...

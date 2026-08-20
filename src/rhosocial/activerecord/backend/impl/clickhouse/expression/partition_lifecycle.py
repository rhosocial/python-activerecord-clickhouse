# src/rhosocial/activerecord/backend/impl/clickhouse/expression/partition_lifecycle.py
"""ClickHouse partition lifecycle management helpers.

This module provides named expression helpers that compose the low-level
DDL expressions from :mod:`partition` into common partition management
operations: add, drop, coalesce, reorganize, and add subpartition.

All methods return ``BaseExpression`` subclasses ready for ``to_sql()``
or for use in a statement execution pipeline.
"""

from typing import List, Optional, Sequence, TYPE_CHECKING, Union

from rhosocial.activerecord.backend.expression.bases import BaseExpression, SQLQueryAndParams

if TYPE_CHECKING:  # pragma: no cover
    from rhosocial.activerecord.backend.impl.clickhouse.expression.partition import (
        ClickHouseAddPartitionExpression,
        ClickHouseDropPartitionExpression,
        ClickHouseCoalescePartitionExpression,
        ClickHouseReorganizePartitionExpression,
        ClickHousePartitionDefinition,
        ClickHouseSubpartitionDefinition,
    )


def _import_partition_exprs():
    """Lazy import of partition expressions to avoid circular dependency."""
    from rhosocial.activerecord.backend.impl.clickhouse.expression.partition import (
        ClickHouseAddPartitionExpression,
        ClickHouseCoalescePartitionExpression,
        ClickHouseDropPartitionExpression,
        ClickHousePartitionDefinition,
        ClickHouseReorganizePartitionExpression,
    )
    return (
        ClickHouseAddPartitionExpression,
        ClickHouseCoalescePartitionExpression,
        ClickHouseDropPartitionExpression,
        ClickHousePartitionDefinition,
        ClickHouseReorganizePartitionExpression,
    )


def _import_subpartition():
    """Lazy import of subpartition definitions."""
    from rhosocial.activerecord.backend.impl.clickhouse.expression.partition import (
        ClickHouseSubpartitionDefinition,
    )
    return ClickHouseSubpartitionDefinition


class ClickHouseAddPartitionHelper(BaseExpression):
    """Helper that adds multiple partitions with generated names.

    .. code-block:: python

        expr = ClickHouseAddPartitionHelper(
            dialect, table="orders",
            partition_values=[2000, 2001, 2002],
            name_template="p{value}",
        )

    Args:
        dialect: ClickHouse dialect instance.
        table: Target table name.
        partition_values: Values for ``VALUES LESS THAN`` of each new partition.
        name_template: Format string for partition names (default ``"p{value}"``).
    """

    def __init__(
        self,
        dialect: "ClickHouseDialect",
        table: str,
        partition_values: Sequence[Union[int, str]],
        name_template: str = "p{value}",
    ):
        super().__init__(dialect)
        self.table = table
        if not partition_values:
            raise ValueError("partition_values must not be empty")
        self.partition_values = list(partition_values)
        self.name_template = name_template

    def to_sql(self) -> SQLQueryAndParams:
        _add, _, _, _def, _ = _import_partition_exprs()
        partitions = []
        for value in self.partition_values:
            name = self.name_template.format(value=value)
            from rhosocial.activerecord.backend.impl.clickhouse.expression.partition import (
                ClickHousePartitionValue,
            )
            partitions.append(
                _def(
                    name=name,
                    less_than=[ClickHousePartitionValue(self.dialect, value)],
                )
            )
        expr = _add(self.dialect, self.table, partitions)
        return expr.to_sql()


class ClickHouseCoalescePartitionHelper(BaseExpression):
    """Helper that coalesces partitions with validation.

    Args:
        dialect: ClickHouse dialect instance.
        table: Target table name.
        target_count: Desired number of partitions after coalescing.
        current_count: Current number of partitions (for validation).
    """

    def __init__(
        self,
        dialect: "ClickHouseDialect",
        table: str,
        target_count: int,
        current_count: int,
    ):
        super().__init__(dialect)
        self.table = table
        if target_count <= 0:
            raise ValueError("target_count must be positive")
        self.target_count = target_count
        self.current_count = current_count

    def to_sql(self) -> SQLQueryAndParams:
        _, _coalesce, _, _, _ = _import_partition_exprs()
        if self.target_count >= self.current_count:
            raise ValueError(
                f"target_count ({self.target_count}) must be less than "
                f"current_count ({self.current_count})"
            )
        count = self.current_count - self.target_count
        expr = _coalesce(self.dialect, self.table, count)
        return expr.to_sql()


class ClickHouseDropOldestPartitionHelper(BaseExpression):
    """Helper that drops the oldest partition from a list of partition names.

    Sorts partitions by name and drops the first one (lexicographically oldest).

    Args:
        dialect: ClickHouse dialect instance.
        table: Target table name.
        partition_names: List of existing partition names.
    """

    def __init__(
        self,
        dialect: "ClickHouseDialect",
        table: str,
        partition_names: Sequence[str],
    ):
        super().__init__(dialect)
        self.table = table
        if not partition_names:
            raise ValueError("partition_names must not be empty")
        self.partition_names = list(partition_names)

    def to_sql(self) -> SQLQueryAndParams:
        _, _, _drop, _, _ = _import_partition_exprs()
        sorted_names = sorted(self.partition_names)
        expr = _drop(self.dialect, self.table, [sorted_names[0]])
        return expr.to_sql()


class ClickHouseReorganizePartitionHelper(BaseExpression):
    """Helper that reorganizes a partition into multiple new partitions.

    Args:
        dialect: ClickHouse dialect instance.
        table: Target table name.
        partition: Existing partition name to reorganize.
        into: Definitions for the new partitions.
    """

    def __init__(
        self,
        dialect: "ClickHouseDialect",
        table: str,
        partition: str,
        into: List["ClickHousePartitionDefinition"],
    ):
        super().__init__(dialect)
        self.table = table
        self.partition = partition
        self.into = into

    def to_sql(self) -> SQLQueryAndParams:
        _, _, _, _, _reorg = _import_partition_exprs()
        expr = _reorg(
            self.dialect, self.table, self.partition, self.into
        )
        return expr.to_sql()


class ClickHouseAddSubpartitionHelper(BaseExpression):
    """Helper that adds a partition with explicit subpartition definitions.

    Useful when a table already has a ``SUBPARTITION BY`` clause and you
    need to add a new partition together with its subpartitions.

    Args:
        dialect: ClickHouse dialect instance.
        table: Target table name.
        partition_name: Name for the new partition.
        less_than: ``VALUES LESS THAN`` bound(s) for the partition.
        subpartition_names: Names for the subpartitions.
        in_values: Optional ``VALUES IN`` values for LIST-based partitioning.
    """

    def __init__(
        self,
        dialect: "ClickHouseDialect",
        table: str,
        partition_name: str,
        less_than: Optional[Sequence] = None,
        subpartition_names: Optional[Sequence[str]] = None,
        in_values: Optional[Sequence] = None,
    ):
        super().__init__(dialect)
        self.table = table
        self.partition_name = partition_name
        self.less_than = list(less_than) if less_than else None
        self.in_values = list(in_values) if in_values else None
        self.subpartition_names = list(subpartition_names) if subpartition_names else None

    def to_sql(self) -> SQLQueryAndParams:
        _add, _, _, _def, _ = _import_partition_exprs()
        _sub_def = _import_subpartition()

        sub_defs = None
        if self.subpartition_names:
            sub_defs = [
                _sub_def(name=sn)
                for sn in self.subpartition_names
            ]

        from rhosocial.activerecord.backend.impl.clickhouse.expression.partition import (
            ClickHousePartitionValue,
        )

        kwargs = {"name": self.partition_name, "subpartition_definitions": sub_defs}
        if self.less_than is not None:
            kwargs["less_than"] = [
                ClickHousePartitionValue(self.dialect, v) if not isinstance(v, BaseExpression) else v
                for v in self.less_than
            ]
        if self.in_values is not None:
            kwargs["in_values"] = [
                ClickHousePartitionValue(self.dialect, v) if not isinstance(v, BaseExpression) else v
                for v in self.in_values
            ]

        definition = _def(**kwargs)
        expr = _add(self.dialect, self.table, [definition])
        return expr.to_sql()

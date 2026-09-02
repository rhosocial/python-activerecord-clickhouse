# src/rhosocial/activerecord/backend/impl/clickhouse/expression/partition.py
"""
ClickHouse partition DDL expressions.

WARNING: This module contains MySQL declarative partitioning expression classes
that are dead code for ClickHouse. ClickHouse uses ``PARTITION BY`` expression
in ``CREATE TABLE`` (handled by ``ClickHouseTableEngineMixin``), not MySQL
declarative partitioning (RANGE/LIST/HASH/KEY). All ``to_sql()`` methods raise
``UnsupportedFeatureError``.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from enum import Enum
from math import isfinite
from typing import Any, Dict, List, Optional, Sequence, TYPE_CHECKING, Union

from rhosocial.activerecord.backend.dialect.exceptions import UnsupportedFeatureError
from rhosocial.activerecord.backend.expression.bases import BaseExpression, SQLQueryAndParams
from rhosocial.activerecord.backend.expression.core import TableExpression
from rhosocial.activerecord.backend.expression.statements import PartitionClause


class ClickHousePartitionStrategy(Enum):
    """MySQL declarative partitioning strategies (not supported by ClickHouse).

    ClickHouse does not support these strategies; partition keys are expressed
    via the ``PARTITION BY`` expression in ``CREATE TABLE``. Retained for
    interface compatibility; SQL generation raises ``UnsupportedFeatureError``.
    """

    RANGE = "RANGE"
    RANGE_COLUMNS = "RANGE COLUMNS"
    LIST = "LIST"
    LIST_COLUMNS = "LIST COLUMNS"
    HASH = "HASH"
    LINEAR_HASH = "LINEAR HASH"
    KEY = "KEY"
    LINEAR_KEY = "LINEAR KEY"


class ClickHouseSubpartitionStrategy(Enum):
    """MySQL subpartitioning strategies.

    ClickHouse does not support subpartitioning. Retained for interface
    compatibility; SQL generation raises ``UnsupportedFeatureError``.
    """

    HASH = "HASH"
    KEY = "KEY"
    LINEAR_HASH = "LINEAR HASH"
    LINEAR_KEY = "LINEAR KEY"


@dataclass
class ClickHouseSubpartitionDefinition:
    """A single named subpartition within a partition definition.

    Used when individual subpartitions need explicit names or distinct
    storage options. When omitted, ClickHouse applies the template from the
    ``SUBPARTITION BY`` clause automatically.

    Raises:
        ValueError: if name is empty or whitespace-only.
    """

    name: str
    dialect_options: Optional[Dict[str, Any]] = None


class ClickHouseSubpartitionClause(BaseExpression):
    """MySQL ``SUBPARTITION BY {HASH|KEY}(...) SUBPARTITIONS N`` clause.

    This is MySQL declarative partitioning syntax; ClickHouse does not support
    it. Retained for interface compatibility; ``to_sql()`` raises
    ``UnsupportedFeatureError``.

    Raises:
        TypeError: if strategy is not a ClickHouseSubpartitionStrategy.
        ValueError: if count is provided but is not a positive integer.
    """

    def __init__(
        self,
        dialect: "ClickHouseDialect",
        strategy: ClickHouseSubpartitionStrategy,
        *,
        expression: Optional[BaseExpression] = None,
        count: Optional[int] = None,
        definitions: Optional[Sequence[ClickHouseSubpartitionDefinition]] = None,
    ):
        super().__init__(dialect)
        if not isinstance(strategy, ClickHouseSubpartitionStrategy):
            raise TypeError(
                "strategy must be a ClickHouseSubpartitionStrategy value, "
                f"got {type(strategy).__name__}"
            )
        if count is not None and (not isinstance(count, int) or count <= 0):
            raise ValueError("count must be a positive integer when provided")
        self.strategy = strategy
        self.expression = expression
        self.count = count
        self.definitions = list(definitions) if definitions else None

    def to_sql(self) -> SQLQueryAndParams:
        """Raise UnsupportedFeatureError: ClickHouse has no SUBPARTITION BY."""
        raise UnsupportedFeatureError(
            self.dialect.name,
            "SUBPARTITION BY",
            suggestion="ClickHouse uses PARTITION BY expression in CREATE TABLE, not MySQL declarative partitioning.",
        )


if TYPE_CHECKING:  # pragma: no cover
    from ..dialect import ClickHouseDialect


class ClickHousePartitionMaxValue(BaseExpression):
    """MySQL MAXVALUE partition boundary token (not supported by ClickHouse).

    Retained for interface compatibility; ``to_sql()`` raises
    ``UnsupportedFeatureError``.
    """

    def __init__(self, dialect: "ClickHouseDialect"):
        super().__init__(dialect)

    def to_sql(self) -> SQLQueryAndParams:
        """Raise UnsupportedFeatureError: ClickHouse has no MAXVALUE token."""
        raise UnsupportedFeatureError(
            self.dialect.name,
            "MAXVALUE partition boundary",
            suggestion="ClickHouse uses PARTITION BY expression in CREATE TABLE, not MySQL declarative partitioning.",
        )


class ClickHousePartitionValue(BaseExpression):
    """Literal value used in MySQL partition boundary definitions.

    MySQL declarative partitioning is not supported by ClickHouse. Retained
    for interface compatibility; ``to_sql()`` raises ``UnsupportedFeatureError``.
    """

    def __init__(self, dialect: "ClickHouseDialect", value: Any):
        super().__init__(dialect)
        if isinstance(value, float) and not isfinite(value):
            raise ValueError("partition value float must be finite")
        if not isinstance(value, (str, int, float, Decimal, type(None))):
            from datetime import date, datetime

            if not isinstance(value, (date, datetime)):
                raise TypeError(
                    "partition value must be str, int, float, Decimal, "
                    f"date, datetime, or None, got {type(value).__name__}"
                )
        self.value = value

    def to_sql(self) -> SQLQueryAndParams:
        """Raise UnsupportedFeatureError: ClickHouse has no partition VALUES."""
        raise UnsupportedFeatureError(
            self.dialect.name,
            "partition VALUES boundary",
            suggestion="ClickHouse uses PARTITION BY expression in CREATE TABLE, not MySQL declarative partitioning.",
        )


@dataclass
class ClickHousePartitionDefinition:
    """A MySQL ``PARTITION ... VALUES ...`` definition.

    MySQL declarative partitioning is not supported by ClickHouse. Retained
    for interface compatibility only; partition boundaries are expressed via
    the ``PARTITION BY`` expression in ``CREATE TABLE``.

    Raises:
        ValueError: if both ``less_than`` and ``in_values`` are provided,
                    or if neither is provided.
        TypeError: if ``dialect_options`` is not a dict when provided.
    """

    name: str
    less_than: Optional[Sequence[BaseExpression]] = None
    in_values: Optional[Sequence[Union[BaseExpression, Sequence[BaseExpression]]]] = None
    subpartition_definitions: Optional[Sequence["ClickHouseSubpartitionDefinition"]] = None
    dialect_options: Optional[dict] = None

    def __post_init__(self) -> None:
        if self.less_than is not None and self.in_values is not None:
            raise ValueError("less_than and in_values are mutually exclusive")
        if self.less_than is None and self.in_values is None:
            raise ValueError("partition definition requires less_than or in_values")
        if self.dialect_options is not None and not isinstance(self.dialect_options, dict):
            raise TypeError(
                "dialect_options must be dict or None, "
                f"got {type(self.dialect_options).__name__}"
            )


class ClickHousePartitionClause(PartitionClause):
    """Base ClickHouse partition clause with ClickHouse-specific strategy enum.

    MySQL declarative partitioning (RANGE/LIST/HASH/KEY) is not supported by
    ClickHouse; partitioning is expressed via ``PARTITION BY`` in ``CREATE
    TABLE``. ``to_sql()`` raises ``UnsupportedFeatureError``.
    """

    strategy_type = ClickHousePartitionStrategy

    def to_sql(self) -> SQLQueryAndParams:
        """Raise UnsupportedFeatureError: ClickHouse has no declarative partitioning."""
        raise UnsupportedFeatureError(
            self.dialect.name,
            f"{self.method} declarative partitioning",
            suggestion="ClickHouse uses PARTITION BY expression in CREATE TABLE, not MySQL declarative partitioning.",
        )


class ClickHousePartitionByRange(ClickHousePartitionClause):
    """MySQL ``PARTITION BY RANGE`` expression (not supported by ClickHouse).

    Raises:
        TypeError: if subpartition_by is not a ClickHouseSubpartitionClause.
    """

    def __init__(
        self,
        dialect: "ClickHouseDialect",
        keys: Sequence[BaseExpression],
        *,
        partitions: Optional[Sequence[ClickHousePartitionDefinition]] = None,
        subpartition_by: Optional[ClickHouseSubpartitionClause] = None,
    ):
        super().__init__(dialect, ClickHousePartitionStrategy.RANGE, keys)
        if subpartition_by is not None and not isinstance(subpartition_by, ClickHouseSubpartitionClause):
            raise TypeError("subpartition_by must be a ClickHouseSubpartitionClause")
        self.partitions = list(partitions or [])
        self.subpartition_by = subpartition_by


class ClickHousePartitionByRangeColumns(ClickHousePartitionClause):
    """MySQL ``PARTITION BY RANGE COLUMNS`` expression (not supported by ClickHouse).

    Raises:
        TypeError: if subpartition_by is not a ClickHouseSubpartitionClause.
    """

    def __init__(
        self,
        dialect: "ClickHouseDialect",
        keys: Sequence[BaseExpression],
        *,
        partitions: Optional[Sequence[ClickHousePartitionDefinition]] = None,
        subpartition_by: Optional[ClickHouseSubpartitionClause] = None,
    ):
        super().__init__(dialect, ClickHousePartitionStrategy.RANGE_COLUMNS, keys)
        if subpartition_by is not None and not isinstance(subpartition_by, ClickHouseSubpartitionClause):
            raise TypeError("subpartition_by must be a ClickHouseSubpartitionClause")
        self.partitions = list(partitions or [])
        self.subpartition_by = subpartition_by


class ClickHousePartitionByList(ClickHousePartitionClause):
    """MySQL ``PARTITION BY LIST`` expression (not supported by ClickHouse).

    Raises:
        TypeError: if subpartition_by is not a ClickHouseSubpartitionClause.
    """

    def __init__(
        self,
        dialect: "ClickHouseDialect",
        keys: Sequence[BaseExpression],
        *,
        partitions: Optional[Sequence[ClickHousePartitionDefinition]] = None,
        subpartition_by: Optional[ClickHouseSubpartitionClause] = None,
    ):
        super().__init__(dialect, ClickHousePartitionStrategy.LIST, keys)
        if subpartition_by is not None and not isinstance(subpartition_by, ClickHouseSubpartitionClause):
            raise TypeError("subpartition_by must be a ClickHouseSubpartitionClause")
        self.partitions = list(partitions or [])
        self.subpartition_by = subpartition_by


class ClickHousePartitionByListColumns(ClickHousePartitionClause):
    """MySQL ``PARTITION BY LIST COLUMNS`` expression (not supported by ClickHouse).

    Raises:
        TypeError: if subpartition_by is not a ClickHouseSubpartitionClause.
    """

    def __init__(
        self,
        dialect: "ClickHouseDialect",
        keys: Sequence[BaseExpression],
        *,
        partitions: Optional[Sequence[ClickHousePartitionDefinition]] = None,
        subpartition_by: Optional[ClickHouseSubpartitionClause] = None,
    ):
        super().__init__(dialect, ClickHousePartitionStrategy.LIST_COLUMNS, keys)
        if subpartition_by is not None and not isinstance(subpartition_by, ClickHouseSubpartitionClause):
            raise TypeError("subpartition_by must be a ClickHouseSubpartitionClause")
        self.partitions = list(partitions or [])
        self.subpartition_by = subpartition_by


class ClickHousePartitionByHash(ClickHousePartitionClause):
    """MySQL ``PARTITION BY HASH`` expression (not supported by ClickHouse)."""

    def __init__(
        self,
        dialect: "ClickHouseDialect",
        keys: Sequence[BaseExpression],
        *,
        partitions_count: Optional[int] = None,
        linear: bool = False,
    ):
        method = ClickHousePartitionStrategy.LINEAR_HASH if linear else ClickHousePartitionStrategy.HASH
        super().__init__(dialect, method, keys)
        self.partitions_count = partitions_count
        self.linear = linear


class ClickHousePartitionByKey(ClickHousePartitionClause):
    """MySQL ``PARTITION BY KEY`` expression (not supported by ClickHouse).

    ClickHouse uses ``PARTITION BY`` expression in ``CREATE TABLE``, not
    MySQL declarative KEY partitioning. Retained for interface compatibility;
    ``to_sql()`` raises ``UnsupportedFeatureError``.
    """

    def __init__(
        self,
        dialect: "ClickHouseDialect",
        keys: Optional[Sequence[BaseExpression]] = None,
        *,
        partitions_count: Optional[int] = None,
        linear: bool = False,
    ):
        method = ClickHousePartitionStrategy.LINEAR_KEY if linear else ClickHousePartitionStrategy.KEY
        if keys:
            super().__init__(dialect, method, keys)
        else:
            BaseExpression.__init__(self, dialect)
            self.method = method.value
            self.keys = list(keys) if keys else []
        self.partitions_count = partitions_count
        self.linear = linear


class ClickHouseAddPartitionExpression(BaseExpression):
    """MySQL ``ALTER TABLE ... ADD PARTITION`` expression.

    MySQL declarative partition maintenance is not supported by ClickHouse;
    retained for interface compatibility. ``to_sql()`` raises
    ``UnsupportedFeatureError``.
    """

    def __init__(
        self,
        dialect: "ClickHouseDialect",
        table: str,
        partitions: List[ClickHousePartitionDefinition],
    ):
        super().__init__(dialect)
        self.table = TableExpression(dialect, table)
        self.partitions = partitions

    def to_sql(self) -> SQLQueryAndParams:
        """Raise UnsupportedFeatureError: ClickHouse has no ADD PARTITION."""
        raise UnsupportedFeatureError(
            self.dialect.name, "ADD PARTITION",
            suggestion="ClickHouse uses PARTITION BY expression in CREATE TABLE, not MySQL declarative partitioning.",
        )


class ClickHouseDropPartitionExpression(BaseExpression):
    """MySQL ``ALTER TABLE ... DROP PARTITION`` expression.

    ClickHouse removes partitions via ``ALTER TABLE ... DROP PARTITION`` with
    partition-id syntax, not MySQL declarative partition names. Retained for
    interface compatibility; ``to_sql()`` raises ``UnsupportedFeatureError``.
    """

    def __init__(self, dialect: "ClickHouseDialect", table: str, partitions: Sequence[str]):
        super().__init__(dialect)
        self.table = TableExpression(dialect, table)
        self.partitions = list(partitions)

    def to_sql(self) -> SQLQueryAndParams:
        """Raise UnsupportedFeatureError: MySQL declarative DROP PARTITION."""
        raise UnsupportedFeatureError(
            self.dialect.name, "DROP PARTITION",
            suggestion="ClickHouse uses PARTITION BY expression in CREATE TABLE, not MySQL declarative partitioning.",
        )


class ClickHouseTruncatePartitionExpression(BaseExpression):
    """MySQL ``ALTER TABLE ... TRUNCATE PARTITION`` expression.

    Retained for interface compatibility; ``to_sql()`` raises
    ``UnsupportedFeatureError``.
    """

    def __init__(self, dialect: "ClickHouseDialect", table: str, partitions: Sequence[str]):
        super().__init__(dialect)
        self.table = TableExpression(dialect, table)
        self.partitions = list(partitions)

    def to_sql(self) -> SQLQueryAndParams:
        """Raise UnsupportedFeatureError: MySQL declarative TRUNCATE PARTITION."""
        raise UnsupportedFeatureError(
            self.dialect.name, "TRUNCATE PARTITION",
            suggestion="ClickHouse uses PARTITION BY expression in CREATE TABLE, not MySQL declarative partitioning.",
        )


class ClickHouseReorganizePartitionExpression(BaseExpression):
    """MySQL ``ALTER TABLE ... REORGANIZE PARTITION`` expression.

    Retained for interface compatibility; ``to_sql()`` raises
    ``UnsupportedFeatureError``.
    """

    def __init__(
        self,
        dialect: "ClickHouseDialect",
        table: str,
        partition: str,
        into: List[ClickHousePartitionDefinition],
    ):
        super().__init__(dialect)
        self.table = TableExpression(dialect, table)
        self.partition = partition
        self.into = into

    def to_sql(self) -> SQLQueryAndParams:
        """Raise UnsupportedFeatureError: MySQL declarative REORGANIZE PARTITION."""
        raise UnsupportedFeatureError(
            self.dialect.name, "REORGANIZE PARTITION",
            suggestion="ClickHouse uses PARTITION BY expression in CREATE TABLE, not MySQL declarative partitioning.",
        )


class ClickHouseExchangePartitionExpression(BaseExpression):
    """MySQL ``ALTER TABLE ... EXCHANGE PARTITION`` expression.

    Retained for interface compatibility; ``to_sql()`` raises
    ``UnsupportedFeatureError``.
    """

    def __init__(
        self,
        dialect: "ClickHouseDialect",
        table: str,
        partition: str,
        exchange_table: str,
        *,
        with_validation: bool = True,
    ):
        super().__init__(dialect)
        self.table = TableExpression(dialect, table)
        self.partition = partition
        self.exchange_table = TableExpression(dialect, exchange_table)
        self.with_validation = with_validation

    def to_sql(self) -> SQLQueryAndParams:
        """Raise UnsupportedFeatureError: MySQL declarative EXCHANGE PARTITION."""
        raise UnsupportedFeatureError(
            self.dialect.name, "EXCHANGE PARTITION",
            suggestion="ClickHouse uses PARTITION BY expression in CREATE TABLE, not MySQL declarative partitioning.",
        )


class ClickHouseRemovePartitioningExpression(BaseExpression):
    """MySQL ``ALTER TABLE ... REMOVE PARTITIONING`` expression.

    Retained for interface compatibility; ``to_sql()`` raises
    ``UnsupportedFeatureError``.
    """

    def __init__(self, dialect: "ClickHouseDialect", table: str):
        super().__init__(dialect)
        self.table = TableExpression(dialect, table)

    def to_sql(self) -> SQLQueryAndParams:
        """Raise UnsupportedFeatureError: MySQL declarative REMOVE PARTITIONING."""
        raise UnsupportedFeatureError(
            self.dialect.name, "REMOVE PARTITIONING",
            suggestion="ClickHouse uses PARTITION BY expression in CREATE TABLE, not MySQL declarative partitioning.",
        )


class ClickHouseCoalescePartitionExpression(BaseExpression):
    """MySQL ``ALTER TABLE ... COALESCE PARTITION`` expression.

    Retained for interface compatibility; ``to_sql()`` raises
    ``UnsupportedFeatureError``.
    """

    def __init__(self, dialect: "ClickHouseDialect", table: str, count: int):
        super().__init__(dialect)
        if not isinstance(count, int) or count <= 0:
            raise ValueError("count must be a positive integer")
        self.table = TableExpression(dialect, table)
        self.count = count

    def to_sql(self) -> SQLQueryAndParams:
        """Raise UnsupportedFeatureError: MySQL declarative COALESCE PARTITION."""
        raise UnsupportedFeatureError(
            self.dialect.name, "COALESCE PARTITION",
            suggestion="ClickHouse uses PARTITION BY expression in CREATE TABLE, not MySQL declarative partitioning.",
        )


class ClickHouseAnalyzePartitionExpression(BaseExpression):
    """MySQL ``ALTER TABLE ... ANALYZE PARTITION`` expression.

    Retained for interface compatibility; ``to_sql()`` raises
    ``UnsupportedFeatureError``.
    """

    def __init__(self, dialect: "ClickHouseDialect", table: str, partitions: Sequence[str]):
        super().__init__(dialect)
        self.table = TableExpression(dialect, table)
        self.partitions = list(partitions)

    def to_sql(self) -> SQLQueryAndParams:
        """Raise UnsupportedFeatureError: MySQL declarative ANALYZE PARTITION."""
        raise UnsupportedFeatureError(
            self.dialect.name, "ANALYZE PARTITION",
            suggestion="ClickHouse uses PARTITION BY expression in CREATE TABLE, not MySQL declarative partitioning.",
        )


class ClickHouseCheckPartitionExpression(BaseExpression):
    """MySQL ``ALTER TABLE ... CHECK PARTITION`` expression.

    Retained for interface compatibility; ``to_sql()`` raises
    ``UnsupportedFeatureError``.
    """

    def __init__(self, dialect: "ClickHouseDialect", table: str, partitions: Sequence[str]):
        super().__init__(dialect)
        self.table = TableExpression(dialect, table)
        self.partitions = list(partitions)

    def to_sql(self) -> SQLQueryAndParams:
        """Raise UnsupportedFeatureError: MySQL declarative CHECK PARTITION."""
        raise UnsupportedFeatureError(
            self.dialect.name, "CHECK PARTITION",
            suggestion="ClickHouse uses PARTITION BY expression in CREATE TABLE, not MySQL declarative partitioning.",
        )


class ClickHouseOptimizePartitionExpression(BaseExpression):
    """MySQL ``ALTER TABLE ... OPTIMIZE PARTITION`` expression.

    Retained for interface compatibility; ``to_sql()`` raises
    ``UnsupportedFeatureError``.
    """

    def __init__(self, dialect: "ClickHouseDialect", table: str, partitions: Sequence[str]):
        super().__init__(dialect)
        self.table = TableExpression(dialect, table)
        self.partitions = list(partitions)

    def to_sql(self) -> SQLQueryAndParams:
        """Raise UnsupportedFeatureError: MySQL declarative OPTIMIZE PARTITION."""
        raise UnsupportedFeatureError(
            self.dialect.name, "OPTIMIZE PARTITION",
            suggestion="ClickHouse uses PARTITION BY expression in CREATE TABLE, not MySQL declarative partitioning.",
        )


class ClickHouseRebuildPartitionExpression(BaseExpression):
    """MySQL ``ALTER TABLE ... REBUILD PARTITION`` expression.

    Retained for interface compatibility; ``to_sql()`` raises
    ``UnsupportedFeatureError``.
    """

    def __init__(self, dialect: "ClickHouseDialect", table: str, partitions: Sequence[str]):
        super().__init__(dialect)
        self.table = TableExpression(dialect, table)
        self.partitions = list(partitions)

    def to_sql(self) -> SQLQueryAndParams:
        """Raise UnsupportedFeatureError: MySQL declarative REBUILD PARTITION."""
        raise UnsupportedFeatureError(
            self.dialect.name, "REBUILD PARTITION",
            suggestion="ClickHouse uses PARTITION BY expression in CREATE TABLE, not MySQL declarative partitioning.",
        )


class ClickHouseRepairPartitionExpression(BaseExpression):
    """MySQL ``ALTER TABLE ... REPAIR PARTITION`` expression.

    Retained for interface compatibility; ``to_sql()`` raises
    ``UnsupportedFeatureError``.
    """

    def __init__(self, dialect: "ClickHouseDialect", table: str, partitions: Sequence[str]):
        super().__init__(dialect)
        self.table = TableExpression(dialect, table)
        self.partitions = list(partitions)

    def to_sql(self) -> SQLQueryAndParams:
        """Raise UnsupportedFeatureError: MySQL declarative REPAIR PARTITION."""
        raise UnsupportedFeatureError(
            self.dialect.name, "REPAIR PARTITION",
            suggestion="ClickHouse uses PARTITION BY expression in CREATE TABLE, not MySQL declarative partitioning.",
        )


class ClickHouseGetPartitionsExpression(BaseExpression):
    """MySQL ``information_schema.PARTITIONS`` query expression.

    This is MySQL declarative partition introspection, not supported by
    ClickHouse. ClickHouse partition introspection uses the ``system.parts``
    table. Retained for interface compatibility; ``to_sql()`` raises
    ``UnsupportedFeatureError``.

    Raises:
        ValueError: if table is empty.
    """

    def __init__(self, dialect: "ClickHouseDialect", table: str):
        super().__init__(dialect)
        if not table or not table.strip():
            raise ValueError("table must not be empty")
        self.table = table

    def to_sql(self) -> SQLQueryAndParams:
        """Raise UnsupportedFeatureError: use ``system.parts`` for introspection."""
        raise UnsupportedFeatureError(
            self.dialect.name, "information_schema.PARTITIONS introspection",
            suggestion="ClickHouse partition introspection uses the system.parts "
            "table, not MySQL information_schema.PARTITIONS.",
        )

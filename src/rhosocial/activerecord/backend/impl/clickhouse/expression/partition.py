# src/rhosocial/activerecord/backend/impl/clickhouse/expression/partition.py
"""ClickHouse partition DDL expressions."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from enum import Enum
from math import isfinite
from typing import Any, Dict, List, Optional, Sequence, TYPE_CHECKING, Union

from rhosocial.activerecord.backend.expression.bases import BaseExpression, SQLQueryAndParams
from rhosocial.activerecord.backend.expression.core import TableExpression
from rhosocial.activerecord.backend.expression.statements import PartitionClause


class ClickHousePartitionStrategy(Enum):
    """ClickHouse table partitioning strategies supported by ClickHousePartitionMixin."""

    RANGE = "RANGE"
    RANGE_COLUMNS = "RANGE COLUMNS"
    LIST = "LIST"
    LIST_COLUMNS = "LIST COLUMNS"
    HASH = "HASH"
    LINEAR_HASH = "LINEAR HASH"
    KEY = "KEY"
    LINEAR_KEY = "LINEAR KEY"


class ClickHouseSubpartitionStrategy(Enum):
    """ClickHouse subpartitioning strategies.

    ClickHouse restricts subpartitioning to HASH and KEY (and their LINEAR
    variants) only. RANGE and LIST cannot be used for subpartitioning.
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
    """ClickHouse ``SUBPARTITION BY {HASH|KEY}(...) SUBPARTITIONS N`` clause.

    This clause appears after ``PARTITION BY ...`` and before the list
    of partition definitions in a ``CREATE TABLE`` statement.

    When ``definitions`` is provided, those explicit subpartition names
    override the template for each parent partition.

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
        """Delegate SQL generation to the dialect."""
        return self.dialect.format_subpartition_by(self)


if TYPE_CHECKING:  # pragma: no cover
    from ..dialect import ClickHouseDialect


class ClickHousePartitionMaxValue(BaseExpression):
    """ClickHouse MAXVALUE partition boundary token."""

    def __init__(self, dialect: "ClickHouseDialect"):
        super().__init__(dialect)

    def to_sql(self) -> SQLQueryAndParams:
        return self.dialect.format_partition_value(self)


class ClickHousePartitionValue(BaseExpression):
    """Literal value used in ClickHouse partition boundary definitions."""

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
        return self.dialect.format_partition_value(self)


@dataclass
class ClickHousePartitionDefinition:
    """A ClickHouse ``PARTITION ... VALUES ...`` definition.

    For single-column LIST COLUMNS, ``in_values`` accepts a flat sequence
    of ``BaseExpression`` (e.g. ``[val('a'), val('b')]`` → ``VALUES IN ('a', 'b')``).

    For multi-column LIST COLUMNS, ``in_values`` accepts a sequence where
    each element is itself a sequence of ``BaseExpression`` values, representing
    a row tuple (e.g. ``[(val('a'), val('x')), (val('b'), val('y'))]`` →
    ``VALUES IN (('a', 'x'), ('b', 'y'))``).

    When subpartitioning is used, ``subpartition_definitions`` optionally
    overrides the template from the ``SUBPARTITION BY`` clause for this
    specific partition.

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
    """Base ClickHouse partition clause with ClickHouse-specific strategy enum."""

    strategy_type = ClickHousePartitionStrategy


class ClickHousePartitionByRange(ClickHousePartitionClause):
    """ClickHouse PARTITION BY RANGE expression.

    When ``subpartition_by`` is provided, the generated DDL includes a
    ``SUBPARTITION BY`` clause. Each partition definition may also carry
    optional ``subpartition_definitions``.

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
    """ClickHouse PARTITION BY RANGE COLUMNS expression.

    Supports optional subpartitioning via ``subpartition_by``.

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
    """ClickHouse PARTITION BY LIST expression.

    Supports optional subpartitioning via ``subpartition_by``.

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
    """ClickHouse PARTITION BY LIST COLUMNS expression.

    Supports optional subpartitioning via ``subpartition_by``.

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
    """ClickHouse PARTITION BY HASH expression."""

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
    """ClickHouse PARTITION BY KEY expression.

    ClickHouse allows empty ``KEY()`` to use all primary key columns as the
    partition key. When ``keys`` is empty or ``None``, this expression
    bypasses the base class key validation (which requires at least one
    key expression) and produces ``PARTITION BY KEY()``.
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
    """Expression for ``ALTER TABLE ... ADD PARTITION``."""

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
        return self.dialect.format_add_partition_statement(self)


class ClickHouseDropPartitionExpression(BaseExpression):
    """Expression for ``ALTER TABLE ... DROP PARTITION``."""

    def __init__(self, dialect: "ClickHouseDialect", table: str, partitions: Sequence[str]):
        super().__init__(dialect)
        self.table = TableExpression(dialect, table)
        self.partitions = list(partitions)

    def to_sql(self) -> SQLQueryAndParams:
        return self.dialect.format_drop_partition_statement(self)


class ClickHouseTruncatePartitionExpression(BaseExpression):
    """Expression for ``ALTER TABLE ... TRUNCATE PARTITION``."""

    def __init__(self, dialect: "ClickHouseDialect", table: str, partitions: Sequence[str]):
        super().__init__(dialect)
        self.table = TableExpression(dialect, table)
        self.partitions = list(partitions)

    def to_sql(self) -> SQLQueryAndParams:
        return self.dialect.format_truncate_partition_statement(self)


class ClickHouseReorganizePartitionExpression(BaseExpression):
    """Expression for ``ALTER TABLE ... REORGANIZE PARTITION``."""

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
        return self.dialect.format_reorganize_partition_statement(self)


class ClickHouseExchangePartitionExpression(BaseExpression):
    """Expression for ``ALTER TABLE ... EXCHANGE PARTITION``."""

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
        return self.dialect.format_exchange_partition_statement(self)


class ClickHouseRemovePartitioningExpression(BaseExpression):
    """Expression for ``ALTER TABLE ... REMOVE PARTITIONING``."""

    def __init__(self, dialect: "ClickHouseDialect", table: str):
        super().__init__(dialect)
        self.table = TableExpression(dialect, table)

    def to_sql(self) -> SQLQueryAndParams:
        return self.dialect.format_remove_partitioning_statement(self)


class ClickHouseCoalescePartitionExpression(BaseExpression):
    """Expression for ``ALTER TABLE ... COALESCE PARTITION``."""

    def __init__(self, dialect: "ClickHouseDialect", table: str, count: int):
        super().__init__(dialect)
        if not isinstance(count, int) or count <= 0:
            raise ValueError("count must be a positive integer")
        self.table = TableExpression(dialect, table)
        self.count = count

    def to_sql(self) -> SQLQueryAndParams:
        return self.dialect.format_coalesce_partition_statement(self)


class ClickHouseAnalyzePartitionExpression(BaseExpression):
    """Expression for ``ALTER TABLE ... ANALYZE PARTITION``."""

    def __init__(self, dialect: "ClickHouseDialect", table: str, partitions: Sequence[str]):
        super().__init__(dialect)
        self.table = TableExpression(dialect, table)
        self.partitions = list(partitions)

    def to_sql(self) -> SQLQueryAndParams:
        return self.dialect.format_analyze_partition_statement(self)


class ClickHouseCheckPartitionExpression(BaseExpression):
    """Expression for ``ALTER TABLE ... CHECK PARTITION``."""

    def __init__(self, dialect: "ClickHouseDialect", table: str, partitions: Sequence[str]):
        super().__init__(dialect)
        self.table = TableExpression(dialect, table)
        self.partitions = list(partitions)

    def to_sql(self) -> SQLQueryAndParams:
        return self.dialect.format_check_partition_statement(self)


class ClickHouseOptimizePartitionExpression(BaseExpression):
    """Expression for ``ALTER TABLE ... OPTIMIZE PARTITION``."""

    def __init__(self, dialect: "ClickHouseDialect", table: str, partitions: Sequence[str]):
        super().__init__(dialect)
        self.table = TableExpression(dialect, table)
        self.partitions = list(partitions)

    def to_sql(self) -> SQLQueryAndParams:
        return self.dialect.format_optimize_partition_statement(self)


class ClickHouseRebuildPartitionExpression(BaseExpression):
    """Expression for ``ALTER TABLE ... REBUILD PARTITION``."""

    def __init__(self, dialect: "ClickHouseDialect", table: str, partitions: Sequence[str]):
        super().__init__(dialect)
        self.table = TableExpression(dialect, table)
        self.partitions = list(partitions)

    def to_sql(self) -> SQLQueryAndParams:
        return self.dialect.format_rebuild_partition_statement(self)


class ClickHouseRepairPartitionExpression(BaseExpression):
    """Expression for ``ALTER TABLE ... REPAIR PARTITION``."""

    def __init__(self, dialect: "ClickHouseDialect", table: str, partitions: Sequence[str]):
        super().__init__(dialect)
        self.table = TableExpression(dialect, table)
        self.partitions = list(partitions)

    def to_sql(self) -> SQLQueryAndParams:
        return self.dialect.format_repair_partition_statement(self)


class ClickHouseGetPartitionsExpression(BaseExpression):
    """Expression that queries ``information_schema.PARTITIONS`` for a table.

    Generates a SELECT statement retrieving partition name, method,
    expression, description, and storage statistics for the given table.
    Delegates SQL generation to the dialect's ``format_get_partitions_expression``.

    Raises:
        ValueError: if table_name is empty.
    """

    def __init__(self, dialect: "ClickHouseDialect", table_name: str):
        super().__init__(dialect)
        if not table_name or not table_name.strip():
            raise ValueError("table_name must not be empty")
        self.table_name = table_name

    def to_sql(self) -> SQLQueryAndParams:
        return self.dialect.format_get_partitions_expression(self)

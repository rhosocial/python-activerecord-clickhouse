# src/rhosocial/activerecord/backend/impl/clickhouse/introspection/types.py
"""ClickHouse-specific introspection results.

The core introspection types describe what every backend can be asked about —
tables, columns, indexes. ClickHouse exposes two further facts that those
shapes cannot carry: how a MergeTree table's data is divided into partitions on
disk, and the storage definition a table was created with. Both are read here
as frozen dataclasses, one row per answer.

Naming, stated once and not translated anywhere below:

    ClickHouse has **no schema layer**. Its top-level namespace is called a
    *database* (``system.databases``, ``system.tables.database``), and an object
    is qualified by that database alone. The core introspection API calls that
    slot ``schema`` because most backends have both; when the core hands this
    backend a ``schema``, the value is a ClickHouse database name. The methods
    in :mod:`.introspector` therefore name the parameter ``database`` — that is
    what it is — and do not turn it into anything else.

So ``ClickHousePartitionInfo.database`` and ``ClickHouseTableEngineInfo.database``
hold a ClickHouse database name, the same string the server reports in
``system.parts.database`` / ``system.tables.database``.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Optional

__all__ = [
    "ClickHousePartitionInfo",
    "ClickHouseTableEngineInfo",
]


@dataclass(frozen=True)
class ClickHousePartitionInfo:
    """One partition of a table, aggregated from its active parts.

    Built from ``system.parts`` grouped by ``partition_id``. Only *active* parts
    are read, because inactive parts are those a merge has already replaced and
    are waiting for removal: counting them would report the same rows twice.

    Args:
        partition_id: ``system.parts.partition_id`` — the identity ClickHouse
            itself uses (``DROP PARTITION ID '...'``), and the grouping key.
            A table declared without ``PARTITION BY`` has the single id
            ``'all'``.
        table_name: The table the partition belongs to.
        database: The ClickHouse database the table lives in.
        engine: The table engine, as ``system.parts.engine`` reports it.
        partition: ``system.parts.partition`` — the readable partition value
            the key produced (e.g. ``'202601'`` for ``toYYYYMM(date)``,
            ``'tuple()'`` for a table with no partition key). Kept beside the
            id because the id is a hash-like token for many key expressions.
        row_count: Sum of ``rows`` over the partition's active parts.
        bytes_on_disk: Sum of ``bytes_on_disk`` over the active parts.
        active_part_count: Number of active parts the partition consists of.
            A partition with more than one active part is normal: parts merge
            in the background.
        min_modification_time: Earliest ``modification_time`` among the active
            parts, or ``None`` when the server reports none.
        max_modification_time: Latest ``modification_time`` among them.
    """

    partition_id: str
    table_name: str
    database: str
    engine: str
    partition: Optional[str] = None
    row_count: int = 0
    bytes_on_disk: int = 0
    active_part_count: int = 0
    min_modification_time: Optional[datetime] = None
    max_modification_time: Optional[datetime] = None


@dataclass(frozen=True)
class ClickHouseTableEngineInfo:
    """The storage definition of one table, from ``system.tables``.

    Every field is the column of the same name on ``system.tables``. The key
    expressions are the ones the table was declared with; ClickHouse reports
    ``''`` (not ``None``) for a key the table does not have, so the empty string
    is passed through unchanged rather than being turned into a missing value
    the server never said.

    Args:
        table_name: ``system.tables.name``.
        database: The ClickHouse database the table lives in.
        engine: ``engine`` — the short engine name (``MergeTree``,
            ``ReplicatedMergeTree``, ``View``, ...).
        sorting_key: ``sorting_key`` — the ``ORDER BY`` expression.
        primary_key: ``primary_key`` — the primary key expression.
        partition_key: ``partition_key`` — the ``PARTITION BY`` expression.
        sampling_key: ``sampling_key`` — the ``SAMPLE BY`` expression.
        total_rows: ``total_rows`` as the server reports it; ``None`` when the
            server has no estimate (the column is ``Nullable(UInt64)`` and is
            empty for engines that do not track rows).
        total_bytes: ``total_bytes``, same treatment.
        comment: ``comment`` — ``''`` when the table has none.
    """

    table_name: str
    database: str
    engine: str
    sorting_key: Optional[str] = None
    primary_key: Optional[str] = None
    partition_key: Optional[str] = None
    sampling_key: Optional[str] = None
    total_rows: Optional[int] = None
    total_bytes: Optional[int] = None
    comment: Optional[str] = None

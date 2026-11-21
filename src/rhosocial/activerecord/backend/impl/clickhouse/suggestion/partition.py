# src/rhosocial/activerecord/backend/impl/clickhouse/suggestion/partition.py
"""ClickHouse's backend suggestions for the eight partition-lifecycle points.

ClickHouse has no declarative partition *strategy* and no subpartitioning. A
partition is declared inline on ``CREATE TABLE`` as a ``PARTITION BY <expr>``
storage clause, and it appears the first time a row lands in it -- so there is
nothing to ``ADD``. What it does have is maintenance by server-assigned
partition id (``system.parts.partition_id``): ``DROP`` / ``DETACH`` / ``ATTACH
PARTITION ID '<id>'``. It has no ``REORGANIZE`` / ``COALESCE`` / ``REMOVE
PARTITIONING`` verb, so splitting, merging and in-place alteration are
genuinely unavailable.

This mixin answers the "how" question at each lifecycle point with a real
expression chain, an explicit ``False`` (no mechanism), or ``None`` (no action):
never with SQL text. ``plan`` is opaque to the core protocol, so a small,
documented set of fields is read from either a mapping or an object with
attributes:

* ``expressions`` (alias ``keys``) -- build: a ``BaseExpression`` (or a sequence
  of them) forming the ``PARTITION BY`` clause;
* ``table`` -- table name (``str``) or a ready ``Table`` object;
* ``partition_id`` (alias ``partition``) -- drop: the id to drop;
* ``partition_ids`` -- retention: an explicit, ordered list of ids to drop.

ClickHouse is a pseudo-async backend (clickhouse-connect is sync-only), so only
these synchronous suggestions are meaningful; there is no async counterpart.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING, Any, Optional, Tuple

from rhosocial.activerecord.backend.suggestion import (
    PartitionAddSuggestion,
    PartitionBuildSuggestion,
    PartitionDropSuggestion,
    PartitionMergeSuggestion,
    PartitionRetentionSuggestion,
    PartitionSplitSuggestion,
    PartitionTableAlterSuggestion,
    PartitionTableDropSuggestion,
)
from ....expression import DropTableStatement
from ....expression.bases import BaseExpression
from ....expression.objects import Table
from ..expression import (
    ClickHouseDropPartitionStatement,
    ClickHouseStorageOptionKind,
    ClickHouseTableStorageOption,
)

if TYPE_CHECKING:  # pragma: no cover
    from ....expression.statements import PartitionStrategy

__all__ = ["ClickHousePartitionSuggestionMixin"]


def _get(plan: Any, name: str, default: Any = None) -> Any:
    """Read one field from a mapping-shaped or attribute-shaped plan."""
    if plan is None:
        return default
    if isinstance(plan, Mapping):
        return plan.get(name, default)
    return getattr(plan, name, default)


class ClickHousePartitionSuggestionMixin:
    """Suggest ClickHouse's real DDL action chains at each partition lifecycle point."""

    # -- shared helpers --------------------------------------------------

    def _suggestion_table(self, plan: Any) -> Optional[Table]:
        """Build a ``Table`` from ``plan.table`` when it names one."""
        target = _get(plan, "table")
        if isinstance(target, Table):
            return target
        if isinstance(target, str) and target.strip():
            return Table(self, target)
        return None

    def _suggestion_table_name(self, plan: Any) -> Optional[str]:
        """Return a plain table name for the ``PARTITION ID`` statements."""
        target = _get(plan, "table")
        if isinstance(target, Table):
            name = getattr(target, "name", None)
            return name if isinstance(name, str) and name.strip() else None
        if isinstance(target, str) and target.strip():
            return target
        return None

    def _suggestion_expressions(self, plan: Any) -> Optional[Tuple[BaseExpression, ...]]:
        """Return the build's ``PARTITION BY`` expression nodes, if valid."""
        raw = _get(plan, "expressions")
        if raw is None:
            raw = _get(plan, "keys")
        if isinstance(raw, BaseExpression):
            return (raw,)
        if (
            isinstance(raw, (list, tuple))
            and raw
            and all(isinstance(item, BaseExpression) for item in raw)
        ):
            return tuple(raw)
        return None

    # -- 1. build --------------------------------------------------------

    def suggest_partition_build(
        self, strategy: "PartitionStrategy", plan: object
    ) -> PartitionBuildSuggestion:
        """Suggest the inline ``PARTITION BY <expr>`` storage clause for CREATE TABLE."""
        expressions = self._suggestion_expressions(plan)
        if not expressions:
            return PartitionBuildSuggestion(False)
        clause = ClickHouseTableStorageOption(
            self,
            ClickHouseStorageOptionKind.PARTITION_BY,
            value=expressions,
        )
        return PartitionBuildSuggestion((clause,))

    # -- 2. table_drop ---------------------------------------------------

    def suggest_partition_table_drop(
        self, strategy: "PartitionStrategy", plan: object
    ) -> PartitionTableDropSuggestion:
        """Suggest dropping the whole table (ClickHouse has no REMOVE PARTITIONING)."""
        table = self._suggestion_table(plan)
        if table is None:
            return PartitionTableDropSuggestion(False)
        return PartitionTableDropSuggestion((DropTableStatement(self, table),))

    # -- 3. table_alter --------------------------------------------------

    def suggest_partition_table_alter(
        self, strategy: "PartitionStrategy", plan: object
    ) -> PartitionTableAlterSuggestion:
        """There is no single ALTER verb to add/remove/reorganise partitioning."""
        return PartitionTableAlterSuggestion(False)

    # -- 4. add ----------------------------------------------------------

    def suggest_partition_add(
        self, strategy: "PartitionStrategy", plan: object
    ) -> PartitionAddSuggestion:
        """A partition appears with its first row; there is no ADD PARTITION."""
        return PartitionAddSuggestion(None)

    # -- 5. drop ---------------------------------------------------------

    def suggest_partition_drop(
        self, strategy: "PartitionStrategy", plan: object
    ) -> PartitionDropSuggestion:
        """Suggest ``ALTER TABLE ... DROP PARTITION ID '<id>'``."""
        table = self._suggestion_table_name(plan)
        partition_id = _get(plan, "partition_id")
        if partition_id is None:
            partition_id = _get(plan, "partition")
        if not table or not isinstance(partition_id, str) or not partition_id.strip():
            return PartitionDropSuggestion(False)
        return PartitionDropSuggestion(
            (ClickHouseDropPartitionStatement(self, table, partition_id),)
        )

    # -- 6. split --------------------------------------------------------

    def suggest_partition_split(
        self, strategy: "PartitionStrategy", plan: object
    ) -> PartitionSplitSuggestion:
        """ClickHouse has no REORGANIZE PARTITION, so a partition cannot be split."""
        return PartitionSplitSuggestion(False)

    # -- 7. merge --------------------------------------------------------

    def suggest_partition_merge(
        self, strategy: "PartitionStrategy", plan: object
    ) -> PartitionMergeSuggestion:
        """ClickHouse has no COALESCE / MERGE PARTITION, so partitions cannot be merged."""
        return PartitionMergeSuggestion(False)

    # -- 8. retention ----------------------------------------------------

    def suggest_partition_retention(
        self, strategy: "PartitionStrategy", plan: object
    ) -> PartitionRetentionSuggestion:
        """Retire an explicit set of partition ids, one ``DROP PARTITION ID`` each.

        ClickHouse has no cutoff-based retention semantics and the suggestion
        layer never reads live state, so with no explicit id list there is no
        action to suggest (``None``). An id list without a table is answered
        ``False``; a malformed list is declined rather than turned into SQL text.
        """
        ids = _get(plan, "partition_ids")
        if ids is None:
            return PartitionRetentionSuggestion(None)
        table = self._suggestion_table_name(plan)
        if not table:
            return PartitionRetentionSuggestion(False)
        if isinstance(ids, str):
            ids = [ids]
        if not isinstance(ids, (list, tuple)) or not ids:
            return PartitionRetentionSuggestion(False)
        if not all(isinstance(pid, str) and pid.strip() for pid in ids):
            return PartitionRetentionSuggestion(False)
        drops = tuple(ClickHouseDropPartitionStatement(self, table, pid) for pid in ids)
        return PartitionRetentionSuggestion(drops)

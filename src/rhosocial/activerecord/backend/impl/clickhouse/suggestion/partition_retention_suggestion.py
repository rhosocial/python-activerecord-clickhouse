# src/rhosocial/activerecord/backend/impl/clickhouse/suggestion/partition_retention_suggestion.py
"""ClickHouse's partition retention suggestion.

Retire an explicit set of partition ids, one ``DROP PARTITION ID`` each.

ClickHouse has no cutoff-based retention semantics and the suggestion layer
never reads live state, so with no explicit id list there is no action to
suggest (``None``). An id list without a table is answered ``False``; a
malformed list is declined rather than turned into SQL text.
"""

from typing import TYPE_CHECKING

from ....suggestion import PartitionRetentionSuggestion
from ..expression import ClickHouseDropPartitionStatement
from ._common import ClickHousePartitionSuggestionBase, _get

if TYPE_CHECKING:  # pragma: no cover
    from ....expression.statements import PartitionStrategy

__all__ = ["ClickHousePartitionRetentionSuggestionMixin"]


class ClickHousePartitionRetentionSuggestionMixin(ClickHousePartitionSuggestionBase):
    """Retire an explicit set of partition ids, one ``DROP PARTITION ID`` each."""

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

# src/rhosocial/activerecord/backend/impl/clickhouse/suggestion/partition_merge_suggestion.py
"""ClickHouse's partition merge suggestion.

ClickHouse has no ``COALESCE`` / ``MERGE PARTITION`` verb, so partitions cannot be
merged. The mechanism is declined unconditionally (``False``).
"""

from typing import TYPE_CHECKING

from ....suggestion import PartitionMergeSuggestion
from ._common import ClickHousePartitionSuggestionBase

if TYPE_CHECKING:  # pragma: no cover
    from ....expression.statements import PartitionByClause

__all__ = ["ClickHousePartitionMergeSuggestionMixin"]


class ClickHousePartitionMergeSuggestionMixin(ClickHousePartitionSuggestionBase):
    """Answer that ClickHouse cannot merge partitions."""

    def suggest_partition_merge(
        self, strategy: "PartitionByClause", plan: object
    ) -> PartitionMergeSuggestion:
        """ClickHouse has no COALESCE / MERGE PARTITION, so partitions cannot be merged."""
        return PartitionMergeSuggestion(False)

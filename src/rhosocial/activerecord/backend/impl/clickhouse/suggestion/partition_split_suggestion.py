# src/rhosocial/activerecord/backend/impl/clickhouse/suggestion/partition_split_suggestion.py
"""ClickHouse's partition split suggestion.

ClickHouse has no ``REORGANIZE PARTITION`` verb, so a partition cannot be split.
The mechanism is declined unconditionally (``False``).
"""

from typing import TYPE_CHECKING

from ....suggestion import PartitionSplitSuggestion
from ._common import ClickHousePartitionSuggestionBase

if TYPE_CHECKING:  # pragma: no cover
    from ....expression.statements import PartitionByClause

__all__ = ["ClickHousePartitionSplitSuggestionMixin"]


class ClickHousePartitionSplitSuggestionMixin(ClickHousePartitionSuggestionBase):
    """Answer that ClickHouse cannot split a partition."""

    def suggest_partition_split(
        self, strategy: "PartitionByClause", plan: object
    ) -> PartitionSplitSuggestion:
        """ClickHouse has no REORGANIZE PARTITION, so a partition cannot be split."""
        return PartitionSplitSuggestion(False)

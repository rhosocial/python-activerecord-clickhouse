# src/rhosocial/activerecord/backend/impl/clickhouse/suggestion/partition_table_alter_suggestion.py
"""ClickHouse's partition table-alter suggestion.

There is no single ``ALTER`` verb to add, remove or reorganise a partition
declaration in ClickHouse, so the mechanism is declined unconditionally
(``False``).
"""

from typing import TYPE_CHECKING

from ....suggestion import PartitionTableAlterSuggestion
from ._common import ClickHousePartitionSuggestionBase

if TYPE_CHECKING:  # pragma: no cover
    from ....expression.statements import PartitionByClause

__all__ = ["ClickHousePartitionTableAlterSuggestionMixin"]


class ClickHousePartitionTableAlterSuggestionMixin(ClickHousePartitionSuggestionBase):
    """Answer that no ALTER verb can add/remove/reorganise partitioning."""

    def suggest_partition_table_alter(
        self, strategy: "PartitionByClause", plan: object
    ) -> PartitionTableAlterSuggestion:
        """There is no single ALTER verb to add/remove/reorganise partitioning."""
        return PartitionTableAlterSuggestion(False)

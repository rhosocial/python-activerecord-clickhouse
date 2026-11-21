# src/rhosocial/activerecord/backend/impl/clickhouse/suggestion/partition_add_suggestion.py
"""ClickHouse's partition add suggestion.

A partition comes into existence with its first row; there is no ``ADD
PARTITION`` verb. This lifecycle point is a genuine no-op, so the answer is
``None`` (no action) unconditionally.
"""

from typing import TYPE_CHECKING

from ....suggestion import PartitionAddSuggestion
from ._common import ClickHousePartitionSuggestionBase

if TYPE_CHECKING:  # pragma: no cover
    from ....expression.statements import PartitionByClause

__all__ = ["ClickHousePartitionAddSuggestionMixin"]


class ClickHousePartitionAddSuggestionMixin(ClickHousePartitionSuggestionBase):
    """Answer that a partition appears with its first row (no ADD verb)."""

    def suggest_partition_add(
        self, strategy: "PartitionByClause", plan: object
    ) -> PartitionAddSuggestion:
        """A partition appears with its first row; there is no ADD PARTITION."""
        return PartitionAddSuggestion(None)

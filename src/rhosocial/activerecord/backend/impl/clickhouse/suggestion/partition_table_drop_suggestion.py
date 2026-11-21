# src/rhosocial/activerecord/backend/impl/clickhouse/suggestion/partition_table_drop_suggestion.py
"""ClickHouse's partition table-drop suggestion.

ClickHouse has no ``REMOVE PARTITIONING`` verb, so the only way to do away with a
partition declaration is to drop the whole table. When the plan names a table
the answer is a real ``DropTableStatement``; otherwise it is declined
(``False``).
"""

from typing import TYPE_CHECKING

from ....expression import DropTableStatement
from ....suggestion import PartitionTableDropSuggestion
from ._common import ClickHousePartitionSuggestionBase

if TYPE_CHECKING:  # pragma: no cover
    from ....expression.statements import PartitionStrategy

__all__ = ["ClickHousePartitionTableDropSuggestionMixin"]


class ClickHousePartitionTableDropSuggestionMixin(ClickHousePartitionSuggestionBase):
    """Suggest dropping the whole table (ClickHouse has no REMOVE PARTITIONING)."""

    def suggest_partition_table_drop(
        self, strategy: "PartitionStrategy", plan: object
    ) -> PartitionTableDropSuggestion:
        """Suggest dropping the whole table (ClickHouse has no REMOVE PARTITIONING)."""
        table = self._suggestion_table(plan)
        if table is None:
            return PartitionTableDropSuggestion(False)
        return PartitionTableDropSuggestion((DropTableStatement(self, table),))

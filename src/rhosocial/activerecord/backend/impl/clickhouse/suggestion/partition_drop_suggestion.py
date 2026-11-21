# src/rhosocial/activerecord/backend/impl/clickhouse/suggestion/partition_drop_suggestion.py
"""ClickHouse's partition drop suggestion.

ClickHouse drops a partition by its server-assigned id via ``ALTER TABLE ...
DROP PARTITION ID '<id>'``. When the plan names a table and carries a partition
id the answer is a real ``ClickHouseDropPartitionStatement``; otherwise it is
declined (``False``). Never SQL text.
"""

from typing import TYPE_CHECKING

from ....suggestion import PartitionDropSuggestion
from ..expression import ClickHouseDropPartitionStatement
from ._common import ClickHousePartitionSuggestionBase, _get

if TYPE_CHECKING:  # pragma: no cover
    from ....expression.statements import PartitionByClause

__all__ = ["ClickHousePartitionDropSuggestionMixin"]


class ClickHousePartitionDropSuggestionMixin(ClickHousePartitionSuggestionBase):
    """Suggest ``ALTER TABLE ... DROP PARTITION ID '<id>'``."""

    def suggest_partition_drop(
        self, strategy: "PartitionByClause", plan: object
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

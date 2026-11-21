# src/rhosocial/activerecord/backend/impl/clickhouse/suggestion/partition_build_suggestion.py
"""ClickHouse's partition build suggestion.

A partition is declared inline on ``CREATE TABLE`` as a ``PARTITION BY <expr>``
storage clause. When the plan carries real ``BaseExpression`` nodes the answer
is a ``ClickHouseTableStorageOption``; otherwise the mechanism is declined
(``False``). Never SQL text.
"""

from typing import TYPE_CHECKING

from ....suggestion import PartitionBuildSuggestion
from ..expression import ClickHouseStorageOptionKind, ClickHouseTableStorageOption
from ._common import ClickHousePartitionSuggestionBase

if TYPE_CHECKING:  # pragma: no cover
    from ....expression.statements import PartitionStrategy

__all__ = ["ClickHousePartitionBuildSuggestionMixin"]


class ClickHousePartitionBuildSuggestionMixin(ClickHousePartitionSuggestionBase):
    """Suggest the inline ``PARTITION BY <expr>`` storage clause for CREATE TABLE."""

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

# src/rhosocial/activerecord/backend/impl/clickhouse/suggestion/__init__.py
"""ClickHouse's concrete backend-suggestion implementations.

Suggestion values are core ``rhosocial.activerecord.backend.suggestion`` data
classes; this package holds only the backend's "how" answers expressed as real
expression chains (never SQL text). Kept separate from ``impl.clickhouse.mixins``
so the suggestion layer is importable without pulling in the SQL mixin bundle.

There is one module per partition-lifecycle point, mirroring the SQLite
suggestion package, plus one module for each of the four migration change
points (column reorder, table constraint change, table index change and
partition scheme change). Shared plan-reading helpers and their common base
live in ``_common.py``.
"""

from ._common import ClickHousePartitionSuggestionBase
from .column_reorder_suggestion import ClickHouseColumnReorderSuggestionMixin
from .partition_scheme_change_suggestion import ClickHousePartitionSchemeChangeSuggestionMixin
from .table_constraint_change_suggestion import ClickHouseTableConstraintChangeSuggestionMixin
from .table_index_change_suggestion import ClickHouseTableIndexChangeSuggestionMixin
from .generated_value_suggestion import ClickHouseGeneratedValueSuggestionMixin
from .general_suggestions import (
    ClickHouseCreateTableLayoutSuggestionMixin,
    ClickHouseStringConcatenationSuggestionMixin,
)
from .partition_add_suggestion import ClickHousePartitionAddSuggestionMixin
from .partition_build_suggestion import ClickHousePartitionBuildSuggestionMixin
from .partition_drop_suggestion import ClickHousePartitionDropSuggestionMixin
from .partition_merge_suggestion import ClickHousePartitionMergeSuggestionMixin
from .partition_retention_suggestion import ClickHousePartitionRetentionSuggestionMixin
from .partition_split_suggestion import ClickHousePartitionSplitSuggestionMixin
from .partition_table_alter_suggestion import ClickHousePartitionTableAlterSuggestionMixin
from .partition_table_drop_suggestion import ClickHousePartitionTableDropSuggestionMixin

__all__ = [
    "ClickHousePartitionSuggestionBase",
    "ClickHouseColumnReorderSuggestionMixin",
    "ClickHousePartitionSchemeChangeSuggestionMixin",
    "ClickHouseTableConstraintChangeSuggestionMixin",
    "ClickHouseTableIndexChangeSuggestionMixin",
    "ClickHouseGeneratedValueSuggestionMixin",
    "ClickHouseCreateTableLayoutSuggestionMixin",
    "ClickHouseStringConcatenationSuggestionMixin",
    "ClickHousePartitionAddSuggestionMixin",
    "ClickHousePartitionBuildSuggestionMixin",
    "ClickHousePartitionDropSuggestionMixin",
    "ClickHousePartitionMergeSuggestionMixin",
    "ClickHousePartitionRetentionSuggestionMixin",
    "ClickHousePartitionSplitSuggestionMixin",
    "ClickHousePartitionTableAlterSuggestionMixin",
    "ClickHousePartitionTableDropSuggestionMixin",
]

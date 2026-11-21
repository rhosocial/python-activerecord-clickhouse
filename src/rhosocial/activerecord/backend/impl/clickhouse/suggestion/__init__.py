# src/rhosocial/activerecord/backend/impl/clickhouse/suggestion/__init__.py
"""ClickHouse's concrete backend-suggestion implementations.

Suggestion values are core ``rhosocial.activerecord.backend.suggestion`` data
classes; this package holds only the backend's "how" answers expressed as real
expression chains (never SQL text). Kept separate from ``impl.clickhouse.mixins``
so the suggestion layer is importable without pulling in the SQL mixin bundle.
"""

from .partition import ClickHousePartitionSuggestionMixin

__all__ = ["ClickHousePartitionSuggestionMixin"]

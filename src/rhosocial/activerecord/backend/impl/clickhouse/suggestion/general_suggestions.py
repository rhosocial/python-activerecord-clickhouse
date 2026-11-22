# src/rhosocial/activerecord/backend/impl/clickhouse/suggestion/general_suggestions.py
"""ClickHouse's general suggestion answers."""
from rhosocial.activerecord.backend.suggestion.definitions import (
    ConcatenationFunctionSuggestion,
)
from rhosocial.activerecord.backend.suggestion.protocols import (
    StringConcatenationSuggestionSupport,
)


class ClickHouseStringConcatenationSuggestionMixin(StringConcatenationSuggestionSupport):
    """ClickHouse spells string concatenation with the ``concat`` function."""

    def suggest_concatenation_function(self) -> ConcatenationFunctionSuggestion:
        return ConcatenationFunctionSuggestion(function="concat")


__all__ = ["ClickHouseStringConcatenationSuggestionMixin"]

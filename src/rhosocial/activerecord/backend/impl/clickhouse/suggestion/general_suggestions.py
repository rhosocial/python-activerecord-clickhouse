# src/rhosocial/activerecord/backend/impl/clickhouse/suggestion/general_suggestions.py
"""ClickHouse's general suggestion answers."""
from rhosocial.activerecord.backend.suggestion.definitions import (
    ConcatenationFunctionSuggestion,
    CreateTableLayoutSuggestion,
)
from rhosocial.activerecord.backend.suggestion.protocols import (
    CreateTableLayoutSuggestionSupport,
    StringConcatenationSuggestionSupport,
)


class ClickHouseCreateTableLayoutSuggestionMixin(CreateTableLayoutSuggestionSupport):
    """ClickHouse inlines indexes and the table comment in one CREATE TABLE."""

    def suggest_create_table_layout(self) -> CreateTableLayoutSuggestion:
        # The composed dialect supplies both capability probes through its
        # table mixin. Read them instead of hard-coding the answer so the layout
        # stays honest if either switch ever changes.
        inline_index = bool(self.supports_inline_index())  # type: ignore[attr-defined]
        inline_comment = bool(self.supports_table_comment())  # type: ignore[attr-defined]
        strategy = "single" if inline_index and inline_comment else "split"
        return CreateTableLayoutSuggestion(
            strategy=strategy,
            inline_index=inline_index,
            inline_comment=inline_comment,
            state="actions",
        )


class ClickHouseStringConcatenationSuggestionMixin(StringConcatenationSuggestionSupport):
    """ClickHouse spells string concatenation with the ``concat`` function."""

    def suggest_concatenation_function(self) -> ConcatenationFunctionSuggestion:
        return ConcatenationFunctionSuggestion(function="concat")


__all__ = [
    "ClickHouseCreateTableLayoutSuggestionMixin",
    "ClickHouseStringConcatenationSuggestionMixin",
]

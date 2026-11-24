# src/rhosocial/activerecord/backend/impl/clickhouse/suggestion/generated_value_suggestion.py
"""ClickHouse's generated-value suggestion.

ClickHouse has no server-side identity or auto-increment clause for a column.
Its integer primary keys are snowflake ids produced by the client before the
INSERT, so the generated-value mechanism lives in the column's storage type
(an ``Int64`` column holding a client-generated id), not in a DDL clause.

This mixin is a plain class on purpose: inheriting the runtime-checkable
``GeneratedValueSuggestionSupport`` Protocol would insert ``Protocol.__init__``
into the dialect's MRO and swallow constructor arguments under strict
validation. Structural presence of ``suggest_generated_value`` is all the
consumer checks.
"""

from typing import TYPE_CHECKING

from ....suggestion import GeneratedValueSuggestion

if TYPE_CHECKING:  # pragma: no cover
    from ....expression.types import DataType

__all__ = ["ClickHouseGeneratedValueSuggestionMixin"]


class ClickHouseGeneratedValueSuggestionMixin:
    """Report the generated-value mechanism as embedded in the storage type."""

    def suggest_generated_value(self, default_type: "DataType") -> GeneratedValueSuggestion:
        """Answer with the plain integer column that carries a snowflake id.

        ``embedded-in-type`` is the actionable answer that keeps the column
        plain: no clause is appended and the declared storage type is kept.
        ``no-action`` would be the other structurally possible "no DDL change"
        answer, but the core deriver reads it as "this is not a generated
        column" and refuses an explicit ``IdentityAttribute``. Reporting the
        mechanism as embedded in the type lets both inferred and explicitly
        declared integer keys render as the plain column ClickHouse accepts.
        """
        return GeneratedValueSuggestion(
            state="embedded-in-type",
            storage_type=default_type,
        )

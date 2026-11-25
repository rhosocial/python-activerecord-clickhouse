# src/rhosocial/activerecord/backend/impl/clickhouse/suggestion/table_index_change_suggestion.py
"""ClickHouse's answer for the table-index-change decision point.

This is a deliberate ``False`` for a real change, and the reason is *not* that
ClickHouse lacks ``ALTER TABLE ... ADD INDEX`` / ``DROP INDEX``. The engine has
data-skipping indexes and the official reference documents both commands;
``ClickHouseIndexMixin.supports_index_if_not_exists()`` and
``supports_index_if_exists()`` are ``True`` on that evidence, and the live
execute test at ``feature/backend/execute/query/test_query_features.py`` runs
``ALTER TABLE ... ADD INDEX idx val TYPE minmax GRANULARITY 1`` and
``DROP INDEX idx`` against 26.7.3.19.

What is missing is an *expression node* for that spelling. The backend's only
index node is ``ClickHouseIndexDefinition``, rendered inline in CREATE TABLE by
``format_index_definition`` with the mandatory ``TYPE ... GRANULARITY ...``.
The core ``AddIndexAction`` / ``DropIndexAction`` render MySQL's
``ADD INDEX name (columns)`` form and are gated by
``supports_alter_table_index_actions()``, which this dialect answers ``False``
precisely because that form is not ClickHouse's. The frozen point also carries
no columns, index type or granularity to rebuild a skip-index definition from.

Returning a chain would therefore require inventing an expression class or SQL
text. The honest answer is ``False`` (unaddressable by this backend's node
set), while an unchanged index set needs no action (``None``).
"""

from ....suggestion.definitions import TableIndexChangeSuggestion

__all__ = ["ClickHouseTableIndexChangeSuggestionMixin"]


class ClickHouseTableIndexChangeSuggestionMixin:
    """Decline index changes: no node renders ClickHouse's ALTER INDEX spelling.

    Plain class, not a protocol subclass: see the other backend suggestion
    mixins. Inheriting the protocol would put ``Protocol.__init__`` ahead of
    ``SQLDialectBase`` in the dialect's MRO; structural presence is enough.
    """

    def suggest_table_index_change(
        self, point: TableIndexChangeSuggestion
    ) -> TableIndexChangeSuggestion:
        """Return ``None`` when nothing changed, otherwise ``False``."""
        old = (
            tuple(point.old_indexes)
            if isinstance(point.old_indexes, (list, tuple))
            else point.old_indexes
        )
        new = (
            tuple(point.new_indexes)
            if isinstance(point.new_indexes, (list, tuple))
            else point.new_indexes
        )
        if old == new:
            return TableIndexChangeSuggestion(operations=None)
        return TableIndexChangeSuggestion(operations=False)

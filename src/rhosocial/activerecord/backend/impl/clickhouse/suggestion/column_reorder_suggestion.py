# src/rhosocial/activerecord/backend/impl/clickhouse/suggestion/column_reorder_suggestion.py
"""ClickHouse's answer for the column-reorder migration decision point.

The point carries only column names (``old_order`` / ``new_order`` /
``reordered_columns``), never column definitions. ClickHouse can position a
*new* column with ``ADD COLUMN ... [AFTER <name> | FIRST]``
(:class:`~..expression.alter_column.ClickHouseAddColumnAction`, measured on
26.7.3.19), but it has no action that repositions an *existing* column from its
name alone. Its full-type ``MODIFY COLUMN name type ... AFTER ...`` production
is a different clause from the portable type-change action this backend
renders, and ``ClickHouseModifyColumnMixin.format_modify_column_action``
refuses ``first`` / ``after_column`` rather than guess at that spelling.

There is therefore no expression node this backend can return for the point,
and the honest tri-state answer is ``False`` (explicitly unaddressable), not
``None`` (no action needed). Never SQL text, never an invented node.
"""

from ....suggestion.definitions import ColumnReorderSuggestion

__all__ = ["ClickHouseColumnReorderSuggestionMixin"]


class ClickHouseColumnReorderSuggestionMixin:
    """Decline column reordering: no node positions an existing column by name.

    A plain class on purpose, like the other backend suggestion mixins:
    inheriting the runtime-checkable protocol would insert ``Protocol.__init__``
    into the dialect's MRO and swallow constructor arguments. Structural
    presence of ``suggest_column_reorder`` is all the consumer checks.
    """

    def suggest_column_reorder(
        self, point: ColumnReorderSuggestion
    ) -> ColumnReorderSuggestion:
        """Return ``False`` -- the point has no ClickHouse-addressable action."""
        return ColumnReorderSuggestion(operations=False)

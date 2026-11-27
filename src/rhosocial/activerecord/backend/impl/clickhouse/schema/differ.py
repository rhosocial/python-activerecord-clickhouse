# src/rhosocial/activerecord/backend/impl/clickhouse/schema/differ.py
"""ClickHouse schema differ — column order is significant.

ClickHouse has no AUTO_INCREMENT, FOREIGN KEY, UNIQUE or collation objects, so
the core differ's branches for those never fire here. That is a property of the
engine, not a missing comparison: a declaration carrying one of those concepts
has already been refused by the dialect before a plan reaches this class. What
this class adds is the one comparison the engine makes special -- the ordinal,
because ``ALTER TABLE`` has no in-place reorder.
"""

from rhosocial.activerecord.backend.schema.differ import SchemaDiffer


class ClickHouseSchemaDiffer(SchemaDiffer):
    """ClickHouse schema differ.

    Column order is part of the schema: ``ALTER TABLE`` has no reorder form, so
    a declaration that places a column in a different position describes a
    different table. ``_columns_equivalent`` therefore compares
    ``ordinal_position`` on top of the core comparison. The core branches for
    AUTO_INCREMENT / FOREIGN KEY / UNIQUE / collation never fire, because the
    engine has none of those objects.
    """

    def _columns_equivalent(self, old_col, new_col) -> bool:
        if not super()._columns_equivalent(old_col, new_col):
            return False
        return old_col.ordinal_position == new_col.ordinal_position

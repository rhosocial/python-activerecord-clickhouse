# src/rhosocial/activerecord/backend/impl/clickhouse/schema/differ.py
"""ClickHouse schema differ — column order is significant.

.. warning::
    Schema differ copied from MySQL template. ClickHouse has no
    AUTO_INCREMENT / FOREIGN KEY / UNIQUE / charset collation concepts;
    those comparisons are no-ops.
"""

from rhosocial.activerecord.backend.schema.differ import SchemaDiffer


class ClickHouseSchemaDiffer(SchemaDiffer):
    """ClickHouse schema differ.

    ClickHouse column order matters: adding a column in the middle shifts
    all subsequent columns. ``_columns_equivalent`` additionally checks
    ``ordinal_position`` to detect re-orderings.

    .. warning::
        Schema differ copied from MySQL template. ClickHouse has no
        AUTO_INCREMENT / FOREIGN KEY / UNIQUE / charset collation concepts;
        those comparisons are no-ops.
    """

    def _columns_equivalent(self, old_col, new_col) -> bool:
        if not super()._columns_equivalent(old_col, new_col):
            return False
        return old_col.ordinal_position == new_col.ordinal_position

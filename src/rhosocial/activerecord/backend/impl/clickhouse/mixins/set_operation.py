# src/rhosocial/activerecord/backend/impl/clickhouse/mixins/set_operation.py
from typing import Tuple, TYPE_CHECKING

if TYPE_CHECKING:  # pragma: no cover
    from rhosocial.activerecord.backend.expression import bases

#: The node's operation words mapped to the spelling ClickHouse needs. Every
#: entry carries the explicit ALL/DISTINCT modifier the grammar demands --
#: see the method docstring for why none of them can drop it.
_OP_SPELLINGS = {
    "union": "UNION DISTINCT",
    "union_all": "UNION ALL",
    "intersect": "INTERSECT DISTINCT",
    "except": "EXCEPT DISTINCT",
}


class ClickHouseSetOperationMixin:
    """ClickHouse set operation support (UNION, INTERSECT, EXCEPT)."""

    def supports_union(self) -> bool:
        """UNION is supported."""
        return True

    def supports_union_all(self) -> bool:
        """UNION ALL is supported."""
        return True

    def supports_intersect(self) -> bool:
        """INTERSECT is supported."""
        return True

    def supports_except(self) -> bool:
        """EXCEPT is supported."""
        return True

    def format_set_operation(self, expr: "bases.BaseExpression") -> Tuple[str, tuple]:
        """Format a set operation with an explicit ALL/DISTINCT modifier.

        The node carries the operation as a **word** (``union`` /
        ``union_all`` / ``intersect`` / ``except``); this method maps each
        word to the spelling this backend writes. Every spelling carries an
        explicit ``ALL`` or ``DISTINCT``, because ClickHouse's grammar has no
        bare form: it rejects a bare ``UNION`` when ``union_default_mode`` is
        empty (the default) -- measured 26.7.3.19: ``Code: 558. Expected ALL
        or DISTINCT in SelectWithUnion query`` -- and a bare SQL-standard
        ``UNION`` means ``UNION DISTINCT``. So ``union`` and ``union_all``
        are told apart by the modifier rather than by the keyword, and
        ``intersect`` / ``except`` take the same required ``DISTINCT`` default.

        The former ``all_`` / ``distinct`` flag pair is gone with the trailing
        clauses that no longer live on the node: ordering, row limiting and
        locking of a compound query are statement-level clauses, not part of
        this node, so this formatter renders the two operands and the
        operator word and nothing else.

        Args:
            expr: The node exposing ``op``, ``left`` and ``right``.

        Returns:
            Tuple of (SQL string, parameters tuple), carrying the operands'
            parameters in order.
        """
        spelling = _OP_SPELLINGS[expr.op]
        left_sql, left_params = expr.left.to_sql()
        right_sql, right_params = expr.right.to_sql()
        return (
            f"{left_sql} {spelling} {right_sql}",
            tuple(left_params) + tuple(right_params),
        )
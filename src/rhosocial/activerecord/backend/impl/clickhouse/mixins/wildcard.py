# src/rhosocial/activerecord/backend/impl/clickhouse/mixins/wildcard.py
"""ClickHouse's wildcard formatters: the two asterisk positions.

Core split the asterisk by grammar position (spec 4.10) and gave each position
its own formatter: ``format_all_columns_wildcard`` for the select list and
RETURNING, ``format_row_count_wildcard`` for ``COUNT``'s argument. A dialect
overrides the one whose *spelling* differs, and ClickHouse's row-count position
does:

* ``COUNT(*)`` -- the bare asterisk, which core already spells, so nothing here
  changes it;
* ``COUNT(DISTINCT *)`` -- the distinct combinations of every column's value
  rather than the rows. Only ClickHouse accepts it of the eleven backends
  measured (:file:`wildcard-survey.md`, row B8), so it is the backend's own
  node (:class:`~...expression.wildcard.ClickHouseRowCountDistinctWildcard`)
  and this override is what spells it.

The select-list position is core's verbatim -- ClickHouse writes ``*`` and
``rel.*`` exactly as the shared formatter does -- so ``format_all_columns_wildcard``
is not overridden here.

**Evidence level: measured.** On the scenario server named by
``tests/config/clickhouse_scenarios.yaml`` (``clickhouse_http``: ClickHouse
26.7.3.19 official build, HTTP on ``127.0.0.1:18682``, database
``test_db``)::

    INSERT INTO probe_distinct_star VALUES (1, 1), (1, 1), (1, 2), (2, 2)
    SELECT count() FROM probe_distinct_star            -- 4
    SELECT count(DISTINCT *) FROM probe_distinct_star   -- 3, answered as
                                                        --   countDistinct(a, b)

so the extension is accepted and counts the distinct combinations of every
column's value, exactly the different count this node exists to spell. The
rendering contract is verified by test.
"""

from typing import Tuple, TYPE_CHECKING

if TYPE_CHECKING:  # pragma: no cover
    from rhosocial.activerecord.backend.expression.bases import BaseExpression


class ClickHouseWildcardMixin:
    """Render ClickHouse's row-count wildcard, and delegate everything else.

    The check is a class test, never a missing-attribute probe: core's
    ``RowCountWildcard`` is the bare asterisk and has no distinctness field to
    look for, and asking for one anyway is the reflection the project's rule 9.8
    forbids. Anything that is not the ClickHouse node is core's bare ``*``, so
    ``super()`` answers it -- which keeps core's plain ``COUNT(*)`` path
    byte-identical.
    """

    def format_row_count_wildcard(
        self, expr: "BaseExpression"
    ) -> Tuple[str, tuple]:
        """Render ``COUNT``'s argument: the bare ``*``, or ``DISTINCT *``.

        Core's node renders ``*``; the ClickHouse node adds the ``DISTINCT``,
        which is what makes it a different count rather than a modifier on the
        same one.

        Args:
            expr: The wildcard being rendered.

        Returns:
            A ``(sql, params)`` tuple; ``params`` is empty.
        """
        from rhosocial.activerecord.backend.impl.clickhouse.expression.wildcard import (
            ClickHouseRowCountDistinctWildcard,
        )

        if not isinstance(expr, ClickHouseRowCountDistinctWildcard):
            return super().format_row_count_wildcard(expr)
        return "DISTINCT *", ()

    def format_count_function(self, expr: "BaseExpression") -> Tuple[str, tuple]:
        """Render ``COUNT`` over the row-count position: ``(*)`` or ``(DISTINCT *)``.

        Core's shared aggregate helper answers every ``RowCountWildcard``
        with the bare asterisk -- which would silently drop this backend's
        distinct node's spelling and return a count of the wrong thing.
        ``DISTINCT`` is not a modifier the aggregate carries: core refuses
        ``count(dialect, "*", is_distinct=True)`` at construction (the
        row-count wildcard counts rows, which have no duplicates), so the
        extension reaches the statement as a different *operand* -- this
        backend's own node -- and the classed entry point is where that
        operand is consulted.

        Args:
            expr: The :class:`CountFunction` whose operand may be the
                ClickHouse distinct row-count wildcard.

        Returns:
            A ``(sql, params)`` tuple; ``params`` is empty.
        """
        from rhosocial.activerecord.backend.impl.clickhouse.expression.wildcard import (
            ClickHouseRowCountDistinctWildcard,
        )

        if isinstance(expr.operand, ClickHouseRowCountDistinctWildcard):
            sql = "COUNT(DISTINCT *)"
            if expr.alias:
                sql = f"{sql} AS {self.format_identifier(expr.alias)}"
            return sql, ()
        return super().format_count_function(expr)


__all__ = ["ClickHouseWildcardMixin"]

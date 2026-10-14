# src/rhosocial/activerecord/backend/impl/clickhouse/expression/wildcard.py
"""ClickHouse's own row-count wildcard: ``COUNT(DISTINCT *)``.

Core splits the one asterisk into two by grammar position (spec 4.10): the
select-list ``*`` expands columns and belongs to ``AllColumnsWildcard``, while
``COUNT(*)``'s asterisk counts rows and belongs to ``RowCountWildcard``. Core
draws the line at the bare asterisk -- ``RowCountWildcard`` accepts no relation,
because standard ``COUNT(*)`` never qualifies it.

ClickHouse adds one spelling the specification leaves to the backends that have
it: ``COUNT(DISTINCT *)``, which counts the distinct combinations of every
column's value rather than the rows (:file:`wildcard-survey.md` row B8; only
ClickHouse accepts it of the eleven measured backends). It is not a flag on
core's node -- the same asterisk answers a different question -- so it is a
derived node here, and the catalog names it
``ClickHouseRowCountDistinctWildcard``.

**Reachability, and the core short-circuit it runs into.**  Core's shared
``format_function_call`` answers *any* ``RowCountWildcard`` argument with the
bare asterisk before consulting a formatter, and takes the ``DISTINCT`` from the
call's own ``is_distinct`` flag rather than from the argument. So the full
statement is reached through that flag --

    count(dialect, "*", is_distinct=True)  ->  COUNT(DISTINCT *)

-- and this node's own ``to_sql()`` renders the argument text, ``DISTINCT *``.
The node names the capability; it does not carry the aggregate around it. The
same core short-circuit is recorded against the PostgreSQL and Snowflake
row-count wildcards, and changing it means changing core's shared formatter,
which this branch does not do.
"""

from typing import TYPE_CHECKING

from rhosocial.activerecord.backend.expression.core import RowCountWildcard

if TYPE_CHECKING:  # pragma: no cover
    from rhosocial.activerecord.backend.dialect import SQLDialectBase


class ClickHouseRowCountDistinctWildcard(RowCountWildcard):
    """``COUNT(DISTINCT *)`` -- the distinct combinations, not the rows.

    Core's ``RowCountWildcard`` renders the bare ``*`` and is left alone; this
    node adds the ``DISTINCT`` that only ClickHouse spells in this position.

    It takes no relation, exactly as core's does: ClickHouse writes the
    argument as ``DISTINCT *`` and has no qualified form here, so there is no
    relation slot to fill and none is added.
    """

    def __init__(self, dialect: "SQLDialectBase"):
        super().__init__(dialect)


__all__ = ["ClickHouseRowCountDistinctWildcard"]

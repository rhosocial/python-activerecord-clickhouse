# src/rhosocial/activerecord/backend/impl/clickhouse/expression/statements/index.py
"""ClickHouse standalone ``ALTER TABLE ... ADD/DROP INDEX`` statements.

These are separate nodes from the inline :class:`ClickHouseIndexDefinition`:
the ADD form spells its body as ``<name> <expression> TYPE <type>
[GRANULARITY n]``, with the leading ``INDEX`` keyword and parenthesised column
list belonging only to the inline CREATE TABLE production.

Official reference (ADD INDEX / DROP INDEX grammar, and where IF NOT EXISTS /
IF EXISTS are allowed):
https://clickhouse.com/docs/sql-reference/statements/alter/skipping-index
"""

from __future__ import annotations

from typing import Any, Optional

from rhosocial.activerecord.backend.expression.bases.bases import BaseExpression


__all__ = [
    "ClickHouseAddIndexStatement",
    "ClickHouseDropIndexStatement",
]


class ClickHouseAddIndexStatement(BaseExpression):
    """``ALTER TABLE <table> ADD INDEX [IF NOT EXISTS] <name> <expr> TYPE <type> [GRANULARITY n]``.

    ClickHouse's standalone skip-index ADD is an ``ALTER TABLE`` action, not
    MySQL's ``ADD INDEX name (columns)``. The official grammar is::

        ALTER TABLE [db.]table_name [ON CLUSTER cluster]
            ADD INDEX [IF NOT EXISTS] name expression TYPE type
            [GRANULARITY value] [FIRST|AFTER name]

    ``IF NOT EXISTS`` belongs after ``ADD INDEX``; ``IF EXISTS`` does not occur
    in this production. ``ALTER TABLE`` itself has no ``IF EXISTS`` qualifier on
    the reference page either (the generic ALTER syntax is ``ALTER [TEMPORARY]
    TABLE [db].name [ON CLUSTER cluster]``), so neither misplaced qualifier is
    accepted here.

    The constructor is a plain parameter collector: it validates nothing and
    stores exactly what the caller passed, including a ``None`` dialect. The
    dialect formatter owns every spelling decision and refusal. ``expression``
    is an expression node (a ``Column`` for a bare column, a function call for
    ``toDate(ts)``, ...), rendered through its own ``to_sql()``; it is not SQL
    text supplied by this class.
    """

    def __init__(
        self,
        dialect: Any,
        table: str,
        name: str,
        expression: Any,
        type: Optional[str] = None,
        granularity: Optional[int] = None,
        *,
        schema: Optional[str] = None,
        if_not_exists: bool = False,
        if_exists: bool = False,
        if_table_exists: bool = False,
    ):
        super().__init__(dialect)
        self.table = table
        self.name = name
        self.expression = expression
        self.type = type
        self.granularity = granularity
        self.schema = schema
        self.if_not_exists = if_not_exists
        self.if_exists = if_exists
        self.if_table_exists = if_table_exists

    @property
    def format_method(self) -> str:
        """The dialect formatting method that renders this statement."""
        return "format_clickhouse_add_index_statement"


class ClickHouseDropIndexStatement(BaseExpression):
    """``ALTER TABLE <table> DROP INDEX [IF EXISTS] <name>``.

    The official grammar is::

        ALTER TABLE [db.]table_name [ON CLUSTER cluster]
            DROP INDEX [IF EXISTS] name

    ``IF EXISTS`` belongs after ``DROP INDEX``; ``IF NOT EXISTS`` does not. As
    with ADD, the reference gives ``ALTER TABLE`` no ``IF EXISTS`` qualifier.
    Removing the description also deletes the index files, but leaves table
    data alone — this is a metadata mutation, not a data-moving operation.

    The constructor collects parameters without validation, so the artifact
    carries every qualifier the caller supplied; the dialect formatter decides
    which of them have a ClickHouse spelling.
    """

    def __init__(
        self,
        dialect: Any,
        table: str,
        name: str,
        *,
        schema: Optional[str] = None,
        if_exists: bool = False,
        if_not_exists: bool = False,
        if_table_exists: bool = False,
    ):
        super().__init__(dialect)
        self.table = table
        self.name = name
        self.schema = schema
        self.if_exists = if_exists
        self.if_not_exists = if_not_exists
        self.if_table_exists = if_table_exists

    @property
    def format_method(self) -> str:
        """The dialect formatting method that renders this statement."""
        return "format_clickhouse_drop_index_statement"

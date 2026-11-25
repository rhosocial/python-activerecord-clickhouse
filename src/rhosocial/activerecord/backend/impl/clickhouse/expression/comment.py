# src/rhosocial/activerecord/backend/impl/clickhouse/expression/comment.py
"""ClickHouse-proprietary ``ALTER TABLE`` comment statements.

ClickHouse spells a table comment change with a verb of its own, and a column
comment change with the ``COMMENT`` modifier of ``MODIFY COLUMN``. Neither has a
portable core node: core only carries the inline ``COMMENT 'text'`` clauses on
``CREATE TABLE`` / column definitions and the SQL-standard ``COMMENT ON``
statement, which ClickHouse does not parse. These two nodes are therefore owned
by this backend and are never exported from core.

Official references:

* ``ALTER TABLE [db].name [ON CLUSTER cluster] MODIFY COMMENT 'Comment'`` --
  https://clickhouse.com/docs/reference/statements/alter/comment . Available
  since 23.9; ``''`` removes the comment.
* ``MODIFY COLUMN [IF EXISTS] name [type] [COMMENT 'comment for column'] ...``
  -- https://clickhouse.com/docs/reference/statements/alter/column . These
  nodes carry only the column name and comment: adding a type, codec, TTL or
  position would be a different operation and belongs on a different node.

The constructors are parameter collectors. They accept a ``None`` dialect and
validate nothing; the dialect formatters own every spelling decision, probe
check and refusal.
"""

from __future__ import annotations

from typing import Any, Optional

from rhosocial.activerecord.backend.expression.bases import BaseExpression

__all__ = [
    "ClickHouseModifyTableCommentStatement",
    "ClickHouseModifyColumnCommentStatement",
]


class ClickHouseModifyTableCommentStatement(BaseExpression):
    """``ALTER TABLE <table> MODIFY COMMENT '<text>'`` (ClickHouse 23.9+).

    The official grammar is::

        ALTER TABLE [db].name [ON CLUSTER cluster] MODIFY COMMENT 'Comment'

    An empty comment is meaningful: the reference uses ``MODIFY COMMENT ''`` to
    remove a table comment. No ``IF EXISTS`` belongs after ``ALTER TABLE``; the
    formatter refuses it by name if a caller supplies one.
    """

    def __init__(
        self,
        dialect: Any,
        table: str,
        comment: str,
        *,
        schema: Optional[str] = None,
        if_table_exists: bool = False,
    ):
        super().__init__(dialect)
        self.table = table
        self.comment = comment
        self.schema = schema
        self.if_table_exists = if_table_exists

    @property
    def format_method(self) -> str:
        """The dialect formatting method that renders this statement."""
        return "format_clickhouse_modify_table_comment_statement"


class ClickHouseModifyColumnCommentStatement(BaseExpression):
    """``ALTER TABLE <table> MODIFY COLUMN [IF EXISTS] <c> COMMENT '<text>'``.

    The official ``MODIFY COLUMN`` production is::

        MODIFY COLUMN [IF EXISTS] name
            [type] [default_expr] [COMMENT 'comment for column'] [codec] ...

    Only the comment modifier is modelled here. ``IF EXISTS`` belongs after
    ``MODIFY COLUMN``; ``ALTER TABLE`` itself has no ``IF EXISTS`` in the
    reference. An empty comment clears the column's comment (the separate
    ``MODIFY COLUMN ... REMOVE COMMENT`` form is not this statement).
    """

    def __init__(
        self,
        dialect: Any,
        table: str,
        column: str,
        comment: str,
        *,
        schema: Optional[str] = None,
        if_exists: bool = False,
        if_table_exists: bool = False,
    ):
        super().__init__(dialect)
        self.table = table
        self.column = column
        self.comment = comment
        self.schema = schema
        self.if_exists = if_exists
        self.if_table_exists = if_table_exists

    @property
    def format_method(self) -> str:
        """The dialect formatting method that renders this statement."""
        return "format_clickhouse_modify_column_comment_statement"

# src/rhosocial/activerecord/backend/impl/clickhouse/mixins/ddl_comment.py
"""ClickHouse ``ALTER TABLE ... MODIFY COMMENT`` support and formatters.

ClickHouse has no ``COMMENT ON`` statement. A table comment changes through
``ALTER TABLE <table> MODIFY COMMENT '<text>'`` (23.9+, an empty string removes
it), and a column comment through the ``COMMENT`` modifier of ``MODIFY COLUMN``.
Both nodes live in this backend's expression package because core models only
the inline ``COMMENT`` clauses and the SQL-standard ``COMMENT ON`` spelling this
server does not parse.

Official references:

* https://clickhouse.com/docs/reference/statements/alter/comment
* https://clickhouse.com/docs/reference/statements/alter/column
"""

from typing import Optional, Tuple

from ..expression.comment import (
    ClickHouseModifyColumnCommentStatement,
    ClickHouseModifyTableCommentStatement,
)

#: ``ALTER TABLE ... MODIFY COMMENT`` arrived in ClickHouse 23.9.
_MODIFY_COMMENT_SINCE = (23, 9, 0)


class ClickHouseCommentMixin:
    """Capability probe and the two comment formatters."""

    def supports_modify_comment(self) -> bool:
        """True from ClickHouse 23.9, where ``ALTER TABLE ... MODIFY COMMENT`` arrived.

        Measured reference: the ``alter/comment`` page marks the statement as
        available since 23.9. Below that floor the spelling does not exist, and
        the formatters refuse it by name rather than emitting a statement the
        server rejects.
        """
        return self.version_at_least(_MODIFY_COMMENT_SINCE)  # type: ignore[attr-defined]

    def _comment_table_sql(self, table: str, schema: Optional[str]) -> str:
        """Render a table name with the database in ClickHouse's catalog slot."""
        from rhosocial.activerecord.backend.expression.objects import Table

        table_sql, _params = self.format_table_object(
            Table(self, table, catalog_name=schema)
        )
        return table_sql

    def format_clickhouse_modify_table_comment_statement(
        self, expr: "ClickHouseModifyTableCommentStatement"
    ) -> Tuple[str, tuple]:
        """Render ``ALTER TABLE <t> MODIFY COMMENT '<text>'``.

        ``IF EXISTS`` is not part of this production, so requesting it is
        refused by name; an empty comment is legal and removes the comment.

        Raises:
            TypeError: if the comment is not a string, or if the table name is
                missing/blank (a caller error; a blank name cannot be rendered).
            UnsupportedFeatureError: below 23.9, or with the table-level
                ``IF EXISTS`` qualifier this production does not carry.
        """
        from rhosocial.activerecord.backend.dialect.exceptions import (
            UnsupportedFeatureError,
        )

        if not self.supports_modify_comment():
            raise UnsupportedFeatureError(
                self.name,  # type: ignore[attr-defined]
                "ALTER TABLE MODIFY COMMENT",
                "MODIFY COMMENT requires ClickHouse 23.9 or later.",
            )
        if expr.if_table_exists:
            raise UnsupportedFeatureError(
                self.name,  # type: ignore[attr-defined]
                "ALTER TABLE IF EXISTS MODIFY COMMENT",
                "ClickHouse's ALTER TABLE header has no IF EXISTS for MODIFY COMMENT.",
            )
        if not isinstance(expr.table, str) or not expr.table.strip():
            raise TypeError("MODIFY COMMENT requires a non-empty table name")
        if not isinstance(expr.comment, str):
            raise TypeError(
                "MODIFY COMMENT requires comment to be a string, got "
                f"{type(expr.comment).__name__}"
            )
        table = self._comment_table_sql(expr.table, expr.schema)
        comment = self.format_literal(expr.comment)  # type: ignore[attr-defined]
        return f"ALTER TABLE {table} MODIFY COMMENT {comment}", ()

    def format_clickhouse_modify_column_comment_statement(
        self, expr: "ClickHouseModifyColumnCommentStatement"
    ) -> Tuple[str, tuple]:
        """Render ``ALTER TABLE <t> MODIFY COLUMN [IF EXISTS] <c> COMMENT '<text>'``.

        Only the comment modifier is modelled. ``IF EXISTS`` belongs after
        ``MODIFY COLUMN``; the table-level qualifier is refused by name.

        Raises:
            TypeError: if the comment is not a string, or if the table or
                column name is missing/blank (a caller error; a blank name
                cannot be rendered).
            UnsupportedFeatureError: below 23.9, or with the table-level
                ``IF EXISTS`` qualifier this production does not carry.
        """
        from rhosocial.activerecord.backend.dialect.exceptions import (
            UnsupportedFeatureError,
        )

        if not self.supports_modify_comment():
            raise UnsupportedFeatureError(
                self.name,  # type: ignore[attr-defined]
                "ALTER TABLE MODIFY COLUMN COMMENT",
                "MODIFY COLUMN COMMENT requires ClickHouse 23.9 or later.",
            )
        if expr.if_table_exists:
            raise UnsupportedFeatureError(
                self.name,  # type: ignore[attr-defined]
                "ALTER TABLE IF EXISTS MODIFY COLUMN COMMENT",
                "ClickHouse's ALTER TABLE header has no IF EXISTS for MODIFY COLUMN.",
            )
        if not isinstance(expr.table, str) or not expr.table.strip():
            raise TypeError("MODIFY COLUMN COMMENT requires a non-empty table name")
        if not isinstance(expr.column, str) or not expr.column.strip():
            raise TypeError("MODIFY COLUMN COMMENT requires a non-empty column name")
        if not isinstance(expr.comment, str):
            raise TypeError(
                "MODIFY COLUMN COMMENT requires comment to be a string, got "
                f"{type(expr.comment).__name__}"
            )
        table = self._comment_table_sql(expr.table, expr.schema)
        column = self.format_identifier(expr.column)  # type: ignore[attr-defined]
        exists = " IF EXISTS" if expr.if_exists else ""
        comment = self.format_literal(expr.comment)  # type: ignore[attr-defined]
        return (
            f"ALTER TABLE {table} MODIFY COLUMN{exists} {column} COMMENT {comment}",
            (),
        )

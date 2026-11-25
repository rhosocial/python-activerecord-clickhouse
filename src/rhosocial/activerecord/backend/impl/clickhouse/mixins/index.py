# src/rhosocial/activerecord/backend/impl/clickhouse/mixins/index.py
"""ClickHouse index support and rendering.

The capability switches describe the real skip-index lifecycle; the two
``format_*`` methods at the bottom render its standalone ``ALTER TABLE``
spelling. All validation and every refusal live here, not in the nodes -- the
nodes are parameter collectors so a round-trip artifact carries exactly what
the caller supplied.

Official reference (ADD INDEX / DROP INDEX grammar):
https://clickhouse.com/docs/sql-reference/statements/alter/skipping-index
"""

from typing import Any, Optional, Tuple, TYPE_CHECKING

from rhosocial.activerecord.backend.dialect.exceptions import UnsupportedFeatureError
from rhosocial.activerecord.backend.expression.bases import BaseExpression

if TYPE_CHECKING:  # pragma: no cover
    from ..expression.index import (
        ClickHouseAddIndexStatement,
        ClickHouseDropIndexStatement,
    )


#: The grammar this mixin implements, quoted in every refusal so the caller sees
#: the spelling ClickHouse actually accepts rather than a MySQL-style guess.
_ADD_INDEX_DETAIL = (
    "ClickHouse spells ADD INDEX as ``ALTER TABLE [db.]table ADD INDEX "
    "[IF NOT EXISTS] name expression TYPE type [GRANULARITY n]``. "
    "https://clickhouse.com/docs/sql-reference/statements/alter/skipping-index"
)
_DROP_INDEX_DETAIL = (
    "ClickHouse spells DROP INDEX as ``ALTER TABLE [db.]table DROP INDEX "
    "[IF EXISTS] name``. "
    "https://clickhouse.com/docs/sql-reference/statements/alter/skipping-index"
)


class ClickHouseIndexMixin:
    """ClickHouse index support."""

    def supports_create_index(self) -> bool:
        """Whether CREATE INDEX is supported."""
        return True

    def supports_drop_index(self) -> bool:
        """Whether DROP INDEX is supported."""
        return True

    def supports_drop_index_on_table(self) -> bool:
        """ClickHouse drops indexes by name (no ON <table> suffix)."""
        return False

    def supports_unique_index(self) -> bool:
        """Whether UNIQUE indexes are supported."""
        return False  # ClickHouse cannot enforce uniqueness on indexes

    def supports_index_if_not_exists(self) -> bool:
        """True: ``ALTER TABLE ... ADD INDEX [IF NOT EXISTS] name ...``.

        Official reference (ALTER TABLE ... INDEX, ADD INDEX):
        https://clickhouse.com/docs/sql-reference/statements/alter/skipping-index
        """
        return True

    def supports_index_if_exists(self) -> bool:
        """True: ``ALTER TABLE ... DROP INDEX [IF EXISTS] name``.

        Official reference (ALTER TABLE ... INDEX, DROP INDEX):
        https://clickhouse.com/docs/sql-reference/statements/alter/skipping-index
        """
        return True

    def supports_invisible_index(self) -> bool:
        """Whether INVISIBLE indexes are supported."""
        return False

    def supports_descending_index(self) -> bool:
        """Whether descending indexes are supported."""
        return False

    def supports_functional_index(self) -> bool:
        """Whether functional (expression) indexes are supported.

        ClickHouse skip indexes can be based on expressions.
        """
        return True

    def supports_index_type(self) -> bool:
        """Whether index type specification is supported.

        ClickHouse skip indexes carry a type, but the keyword is ``TYPE``, not
        MySQL's ``USING``: ``INDEX i (s) TYPE minmax GRANULARITY 1`` is accepted
        on 26.7.3.19, while ``INDEX i (s) USING minmax`` is a ``SYNTAX_ERROR``
        ("failed at position 54 (USING)").
        """
        return True

    # ------------------------------------------------------------------
    # Formatters — the standalone ALTER TABLE ... INDEX statements
    # ------------------------------------------------------------------

    def format_clickhouse_add_index_statement(
        self, expr: "ClickHouseAddIndexStatement"
    ) -> Tuple[str, tuple]:
        """Render ``ALTER TABLE ... ADD INDEX [IF NOT EXISTS] ... TYPE ...``.

        The body is built from the node's expression node, type and granularity.
        The inline ``ClickHouseIndexDefinition`` is deliberately not reused: it
        renders ``INDEX name (cols)`` for ``CREATE TABLE`` and carries a column
        list rather than an arbitrary expression, so borrowing it would import
        an inline-CREATE-only assumption into ``ALTER TABLE``.

        Raises:
            TypeError: if ``expr`` is not a ``ClickHouseAddIndexStatement``.
            UnsupportedFeatureError: for a misplaced qualifier, a missing
                table/name/type/expression, an expression that would bind a
                parameter in a DDL position, or an invalid granularity.
        """
        from ..expression.index import ClickHouseAddIndexStatement

        if not isinstance(expr, ClickHouseAddIndexStatement):
            raise TypeError(
                "format_clickhouse_add_index_statement expects a "
                "ClickHouseAddIndexStatement, "
                f"got {type(expr).__name__}"
            )

        # The reference gives ALTER TABLE no IF EXISTS, and puts IF NOT EXISTS
        # (not IF EXISTS) after ADD INDEX. Refuse both misplacements by name
        # instead of silently dropping a qualifier the caller asked for.
        if expr.if_table_exists:
            raise UnsupportedFeatureError(
                self.name, "ALTER TABLE IF EXISTS", _ADD_INDEX_DETAIL
            )
        if expr.if_exists:
            raise UnsupportedFeatureError(
                self.name, "ADD INDEX IF EXISTS", _ADD_INDEX_DETAIL
            )
        if not self.supports_create_index():  # type: ignore[attr-defined]
            raise UnsupportedFeatureError(
                self.name, "ALTER TABLE ADD INDEX", _ADD_INDEX_DETAIL
            )
        if expr.if_not_exists and not self.supports_index_if_not_exists():  # type: ignore[attr-defined]
            raise UnsupportedFeatureError(
                self.name, "ADD INDEX IF NOT EXISTS", _ADD_INDEX_DETAIL
            )
        if not self.supports_index_type():  # type: ignore[attr-defined]
            raise UnsupportedFeatureError(
                self.name, "ADD INDEX TYPE", _ADD_INDEX_DETAIL
            )

        self._require_index_name(expr.table, "ADD INDEX", _ADD_INDEX_DETAIL)
        self._require_index_name(expr.name, "ADD INDEX", _ADD_INDEX_DETAIL)

        expression = expr.expression
        if not isinstance(expression, BaseExpression):
            raise UnsupportedFeatureError(
                self.name,
                "ADD INDEX <expression>",
                _ADD_INDEX_DETAIL
                + " The expression must be an expression node, not SQL text.",
            )
        expression_sql, expression_params = expression.to_sql()
        if expression_params:
            # An ALTER clause is DDL: there is no bind-parameter slot in it.
            raise UnsupportedFeatureError(
                self.name,
                "ADD INDEX <expression> with bind parameters",
                _ADD_INDEX_DETAIL,
            )

        index_type = expr.type
        if not isinstance(index_type, str) or not index_type.strip():
            raise UnsupportedFeatureError(
                self.name, "ADD INDEX TYPE", _ADD_INDEX_DETAIL
            )
        if any(mark in index_type for mark in (";", "--", "/*", "*/", "\n", "\r")):
            raise UnsupportedFeatureError(
                self.name, "ADD INDEX TYPE", _ADD_INDEX_DETAIL
            )

        granularity = expr.granularity
        if granularity is not None and (
            not isinstance(granularity, int)
            or isinstance(granularity, bool)
            or granularity < 1
        ):
            raise UnsupportedFeatureError(
                self.name, "ADD INDEX GRANULARITY", _ADD_INDEX_DETAIL
            )

        parts = [
            "ALTER TABLE",
            self._index_table_sql(expr.table, expr.schema),
            "ADD INDEX",
        ]
        if expr.if_not_exists:
            parts.append("IF NOT EXISTS")
        parts.extend(
            [
                self.format_identifier(expr.name),
                expression_sql,
                "TYPE",
                index_type,
            ]
        )
        if granularity is not None:
            parts.extend(["GRANULARITY", str(granularity)])
        return " ".join(parts), ()

    def format_clickhouse_drop_index_statement(
        self, expr: "ClickHouseDropIndexStatement"
    ) -> Tuple[str, tuple]:
        """Render ``ALTER TABLE ... DROP INDEX [IF EXISTS] <name>``.

        Raises:
            TypeError: if ``expr`` is not a ``ClickHouseDropIndexStatement``.
            UnsupportedFeatureError: for a misplaced qualifier or a missing
                table or index name.
        """
        from ..expression.index import ClickHouseDropIndexStatement

        if not isinstance(expr, ClickHouseDropIndexStatement):
            raise TypeError(
                "format_clickhouse_drop_index_statement expects a "
                "ClickHouseDropIndexStatement, "
                f"got {type(expr).__name__}"
            )

        if expr.if_table_exists:
            raise UnsupportedFeatureError(
                self.name, "ALTER TABLE IF EXISTS", _DROP_INDEX_DETAIL
            )
        if expr.if_not_exists:
            raise UnsupportedFeatureError(
                self.name, "DROP INDEX IF NOT EXISTS", _DROP_INDEX_DETAIL
            )
        if not self.supports_drop_index():  # type: ignore[attr-defined]
            raise UnsupportedFeatureError(
                self.name, "ALTER TABLE DROP INDEX", _DROP_INDEX_DETAIL
            )
        if expr.if_exists and not self.supports_index_if_exists():  # type: ignore[attr-defined]
            raise UnsupportedFeatureError(
                self.name, "DROP INDEX IF EXISTS", _DROP_INDEX_DETAIL
            )

        self._require_index_name(expr.table, "DROP INDEX", _DROP_INDEX_DETAIL)
        self._require_index_name(expr.name, "DROP INDEX", _DROP_INDEX_DETAIL)

        parts = [
            "ALTER TABLE",
            self._index_table_sql(expr.table, expr.schema),
            "DROP INDEX",
        ]
        if expr.if_exists:
            parts.append("IF EXISTS")
        parts.append(self.format_identifier(expr.name))
        return " ".join(parts), ()

    # ------------------------------------------------------------------
    # Helpers (not private *renderers*: the shared-formatter guard requires one
    # private renderer per public format_* entry point)
    # ------------------------------------------------------------------

    def _index_table_sql(self, table: str, schema: Optional[str]) -> str:
        """Render the table with the database in ClickHouse's catalog slot."""
        from rhosocial.activerecord.backend.expression.objects import Table

        table_sql, _params = self.format_table_object(
            Table(self, table, catalog_name=schema)
        )
        return table_sql

    def _require_index_name(self, value: Any, feature: str, detail: str) -> None:
        """Require a non-empty string: a DDL action must be aimable by name."""
        if not isinstance(value, str) or not value.strip():
            raise UnsupportedFeatureError(self.name, feature, detail)

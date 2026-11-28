# src/rhosocial/activerecord/backend/impl/clickhouse/mixins/column.py
"""ClickHouse ALTER TABLE column-modification formatting.

ClickHouse's ``ALTER TABLE ... COLUMN`` grammar
(https://clickhouse.com/docs/sql-reference/statements/alter/column) offers:

* ``MODIFY COLUMN [IF EXISTS] name [type] ...`` to change a column's type,
  default expression, codec or TTL. The column name is kept as-is.
* ``RENAME COLUMN [IF EXISTS] name TO new_name`` to rename a column.

There is no ``CHANGE COLUMN`` in ClickHouse: a rename and a type change cannot
be combined in one action the way MySQL's ``CHANGE COLUMN`` does. ``FIRST`` /
``AFTER`` positioning belongs to ``ADD COLUMN`` (and to a separate, full-type
branch of ``MODIFY COLUMN``), not to the portable type-change action this
mixin renders. Rather than emit a clause whose meaning depends on that
distinction, refuse those modifiers here.
"""

from typing import Tuple, TYPE_CHECKING

from rhosocial.activerecord.backend.dialect.exceptions import UnsupportedFeatureError

if TYPE_CHECKING:
    from rhosocial.activerecord.backend.expression.statements import (
        ChangeColumnAction as ChangeColumn,
        ModifyColumnAction as ModifyColumn,
    )


class ClickHouseModifyColumnMixin:
    """ClickHouse MODIFY COLUMN support, with an honest refusal for CHANGE COLUMN."""

    def supports_modify_column(self) -> bool:
        """ClickHouse changes a column's type in place with MODIFY COLUMN."""
        return True

    def supports_change_column(self) -> bool:
        """ClickHouse has no CHANGE COLUMN.

        A rename is a separate ``RENAME COLUMN old TO new`` action and cannot
        be combined with a type change in a single clause.
        """
        return False

    def format_modify_column_action(self, expr: "ModifyColumn") -> Tuple[str, tuple]:
        """Render a type change as ``MODIFY COLUMN <name> <type>``.

        The column definition already carries the quoted name, so the rendered
        form is exactly the ClickHouse ``MODIFY COLUMN name type`` spelling.

        Raises:
            UnsupportedFeatureError: ``first`` or ``after_column`` is set. The
                portable type-change action has no ClickHouse equivalent for a
                positional clause; emitting one would be guessing at grammar.
        """
        if expr.first or expr.after_column:
            raise UnsupportedFeatureError(
                self.name,
                "ALTER TABLE MODIFY COLUMN FIRST/AFTER",
                "ClickHouse column positioning is not part of the portable MODIFY COLUMN "
                "action; use ADD COLUMN ... AFTER/FIRST when positioning a new column.",
            )
        col_sql, col_params = self.format_column_definition(expr.column)
        return f"MODIFY COLUMN {col_sql}", col_params

    def format_change_column_action(self, expr: "ChangeColumn") -> Tuple[str, tuple]:
        """Refuse MySQL's CHANGE COLUMN: ClickHouse has no such clause.

        Raises:
            UnsupportedFeatureError: Always. Use ``RENAME COLUMN old TO new``
                for the rename plus a separate ``MODIFY COLUMN`` for the type.
        """
        raise UnsupportedFeatureError(
            self.name,
            "ALTER TABLE CHANGE COLUMN",
            "ClickHouse has no CHANGE COLUMN; use RENAME COLUMN old TO new and, "
            "if the type changes too, a separate MODIFY COLUMN action.",
        )

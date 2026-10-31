# tests/rhosocial/activerecord_clickhouse_test/feature/backend/expression/test_add_column_action.py
"""``ADD COLUMN ... AFTER <name>`` — the one clause on ClickHouse's ADD COLUMN.

Core's ``AddColumnAction`` declares ``column`` and ``if_not_exists`` and stops
there: no other backend has a positional clause, so there is no core slot for
one to arrive through. ``ClickHouseAddColumnAction`` adds ClickHouse's ``AFTER``
as its own parameter, and this module is what proves the parameter reaches the
SQL -- it was declared, stored, serialised, and read by nobody, which is why the
example that passes ``after="name"`` and reports the new column shifted into
position never shifted it.

Construction -> render only, no connection (§12); the end-to-end half belongs
to the ddl area.

The name is an identifier, not a value, so it is quoted the way every other
identifier this dialect writes is quoted -- including when the name is a
reserved word, which is the case a bare ``f"{sql} AFTER {after}"`` would turn
into a server-side syntax error.
"""

import pytest

from rhosocial.activerecord.backend.expression.objects import Table
from rhosocial.activerecord.backend.expression.statements import (
    AlterTableStatement,
    ColumnDefinition,
)
from rhosocial.activerecord.backend.expression.statements.ddl_alter import (
    AddColumnAction,
)
from rhosocial.activerecord.backend.impl.clickhouse.dialect import ClickHouseDialect
from rhosocial.activerecord.backend.impl.clickhouse.expression import (
    ClickHouseAddColumnAction,
)
from rhosocial.activerecord.backend.impl.clickhouse.expression.types import (
    ClickHouseUInt32Type,
)


@pytest.fixture
def dialect():
    return ClickHouseDialect()


def _alter(dialect, action):
    return AlterTableStatement(dialect, Table(dialect, "users"), [action]).to_sql()


def _action(dialect, cls, **kwargs):
    return cls(
        dialect,
        ColumnDefinition(dialect, "age", ClickHouseUInt32Type(dialect)),
        **kwargs,
    )


class TestAfterClause:
    """``after`` is a position the caller asked for, so it must be in the SQL."""

    def test_no_position_renders_exactly_what_the_core_entry_renders(self, dialect):
        assert _alter(dialect, _action(dialect, ClickHouseAddColumnAction)) == (
            "ALTER TABLE `users` ADD COLUMN `age` UInt32",
            (),
        )

    def test_the_core_action_is_untouched_by_the_derived_one(self, dialect):
        """Two kinds, two entries: the core node keeps its own spelling."""
        assert _alter(dialect, _action(dialect, AddColumnAction)) == (
            "ALTER TABLE `users` ADD COLUMN `age` UInt32",
            (),
        )

    def test_after_names_the_position(self, dialect):
        assert _alter(
            dialect, _action(dialect, ClickHouseAddColumnAction, after="name")
        ) == ("ALTER TABLE `users` ADD COLUMN `age` UInt32 AFTER `name`", ())

    def test_after_composes_with_if_not_exists(self, dialect):
        """Both modifiers are the caller's, so both must reach the same line."""
        assert _alter(
            dialect,
            _action(
                dialect, ClickHouseAddColumnAction, if_not_exists=True, after="name"
            ),
        ) == (
            "ALTER TABLE `users` ADD COLUMN IF NOT EXISTS `age` UInt32 AFTER `name`",
            (),
        )

    def test_after_quotes_a_reserved_word(self, dialect):
        """Unquoted, this is the server's syntax error rather than our error."""
        assert _alter(
            dialect, _action(dialect, ClickHouseAddColumnAction, after="select")
        ) == ("ALTER TABLE `users` ADD COLUMN `age` UInt32 AFTER `select`", ())
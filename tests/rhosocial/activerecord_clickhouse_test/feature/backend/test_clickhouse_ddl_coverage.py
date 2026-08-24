# tests/rhosocial/activerecord_clickhouse_test/feature/backend/test_ddl_coverage.py
"""
ClickHouse DDL / statement coverage gap-completion tests.

Covers the supported SQL statements:

- RENAME TABLE (atomic multi-table rename)
- TRUNCATE TABLE (option guards)
- ALTER TABLE ... ALTER COLUMN {SET DEFAULT | DROP DEFAULT}

MySQL-only statement families (whole-table ``ANALYZE``/``CHECK``/``CHECKSUM``/
``REPAIR`` maintenance, stored ``PROCEDURE``/``FUNCTION``/``CALL``, ``TABLE``/
``VALUES`` constructors, ``LOAD XML``, and the ``FLUSH``/``RESET``/``KILL``/
``GRANT`` admin set) are intentionally **not** tested here: ClickHouse does
not support them and the corresponding dialect mixins fail fast with
``UnsupportedFeatureError``.
"""

import pytest

from rhosocial.activerecord.backend.expression.statements.ddl_alter import (
    AlterColumn,
    AlterTableExpression,
    ColumnAlterOperation,
)
from rhosocial.activerecord.backend.expression.statements.ddl_truncate import TruncateExpression
from rhosocial.activerecord.backend.dialect.exceptions import UnsupportedFeatureError
from rhosocial.activerecord.backend.impl.clickhouse import expression as clickhouse_expr
from rhosocial.activerecord.backend.impl.clickhouse.dialect import ClickHouseDialect


@pytest.fixture(scope="module")
def dialect():
    return ClickHouseDialect()


class TestRenameTable:
    """Test ClickHouse RENAME TABLE statement."""

    def test_single_rename(self, dialect):
        expr = clickhouse_expr.ClickHouseRenameTableExpression(dialect, [("old_name", "new_name")])
        sql, params = expr.to_sql()
        assert sql == "RENAME TABLE `old_name` TO `new_name`"
        assert params == ()

    def test_multi_rename(self, dialect):
        expr = clickhouse_expr.ClickHouseRenameTableExpression(dialect, [("a", "b"), ("c", "d")])
        sql, params = expr.to_sql()
        assert sql == "RENAME TABLE `a` TO `b`, `c` TO `d`"

    def test_empty_raises(self, dialect):
        expr = clickhouse_expr.ClickHouseRenameTableExpression(dialect, [])
        with pytest.raises(ValueError, match="at least one"):
            expr.to_sql()

    def test_supports_flags(self, dialect):
        assert dialect.supports_rename_table() is True
        assert dialect.supports_multi_table_rename() is True


class TestTruncateTable:
    """Test ClickHouse TRUNCATE TABLE statement."""

    def test_basic(self, dialect):
        sql, params = TruncateExpression(dialect, table_name="users").to_sql()
        assert sql == "TRUNCATE TABLE `users`"
        assert params == ()

    def test_supports_flags(self, dialect):
        assert dialect.supports_truncate() is True
        assert dialect.supports_truncate_table_keyword() is True
        assert dialect.supports_truncate_restart_identity() is False
        assert dialect.supports_truncate_cascade() is False

    def test_restart_identity_unsupported(self, dialect):
        with pytest.raises(UnsupportedFeatureError):
            TruncateExpression(dialect, table_name="users", restart_identity=True).to_sql()

    def test_cascade_unsupported(self, dialect):
        with pytest.raises(UnsupportedFeatureError):
            TruncateExpression(dialect, table_name="users", cascade=True).to_sql()


class TestAlterColumnDefault:
    """Test ALTER TABLE ... ALTER COLUMN {SET DEFAULT | DROP DEFAULT}."""

    def test_set_default_string(self, dialect):
        action = AlterColumn(dialect, "col", ColumnAlterOperation.SET_DEFAULT, new_value="ABC")
        sql, params = AlterTableExpression(dialect, "t", [action]).to_sql()
        assert "ALTER COLUMN `col` SET DEFAULT 'ABC'" in sql
        assert params == ()

    def test_set_default_integer(self, dialect):
        action = AlterColumn(dialect, "num", ColumnAlterOperation.SET_DEFAULT, new_value=5)
        sql, _ = AlterTableExpression(dialect, "t", [action]).to_sql()
        assert "ALTER COLUMN `num` SET DEFAULT 5" in sql

    def test_drop_default(self, dialect):
        action = AlterColumn(dialect, "col", ColumnAlterOperation.DROP_DEFAULT)
        sql, params = AlterTableExpression(dialect, "t", [action]).to_sql()
        assert "ALTER COLUMN `col` DROP DEFAULT" in sql
        assert params == ()

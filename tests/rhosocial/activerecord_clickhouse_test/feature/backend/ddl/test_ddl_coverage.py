# tests/rhosocial/activerecord_clickhouse_test/feature/backend/ddl/test_ddl_coverage.py
"""
ClickHouse DDL / statement coverage gap-completion tests.

Covers the supported SQL statements:

- RENAME TABLE (atomic multi-table rename)
- TRUNCATE TABLE (option guards)
- ALTER TABLE ... ALTER COLUMN (a default change, in ClickHouse's own spelling)

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
from rhosocial.activerecord.backend.expression.objects import Table
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
        sql, params = TruncateExpression(dialect, table=Table(dialect, "users")).to_sql()
        assert sql == "TRUNCATE TABLE `users`"
        assert params == ()

    def test_supports_flags(self, dialect):
        assert dialect.supports_truncate() is True
        assert dialect.supports_truncate_table_keyword() is True
        assert dialect.supports_truncate_restart_identity() is False
        assert dialect.supports_truncate_cascade() is False

    def test_restart_identity_unsupported(self, dialect):
        with pytest.raises(UnsupportedFeatureError):
            TruncateExpression(dialect, table=Table(dialect, "users"), restart_identity=True).to_sql()

    def test_cascade_unsupported(self, dialect):
        with pytest.raises(UnsupportedFeatureError):
            TruncateExpression(dialect, table=Table(dialect, "users"), cascade=True).to_sql()


class TestAlterColumnDefault:
    """``SET DEFAULT`` / ``DROP DEFAULT`` render as ClickHouse's own spellings.

    ``ALTER COLUMN c SET DEFAULT v`` is a ``SYNTAX_ERROR`` on 26.7.3.19 — the
    server's expected-token list after ``ALTER COLUMN c`` contains ``DEFAULT``
    and not ``SET`` — and ``ALTER COLUMN c DROP DEFAULT`` is a ``SYNTAX_ERROR``
    too, because removing a column property is
    ``MODIFY COLUMN c REMOVE <property>``. See
    ``https://clickhouse.com/docs/reference/statements/alter/column``.
    """

    def test_set_default_string(self, dialect):
        action = AlterColumn(dialect, "col", ColumnAlterOperation.SET_DEFAULT, new_value="ABC")
        sql, params = AlterTableExpression(dialect, Table(dialect, "t"), [action]).to_sql()
        assert "ALTER COLUMN `col` DEFAULT 'ABC'" in sql
        assert params == ()

    def test_set_default_integer(self, dialect):
        action = AlterColumn(dialect, "num", ColumnAlterOperation.SET_DEFAULT, new_value=5)
        sql, _ = AlterTableExpression(dialect, Table(dialect, "t"), [action]).to_sql()
        assert "ALTER COLUMN `num` DEFAULT 5" in sql

    def test_drop_default_uses_modify_remove(self, dialect):
        action = AlterColumn(dialect, "col", ColumnAlterOperation.DROP_DEFAULT)
        sql, params = AlterTableExpression(dialect, Table(dialect, "t"), [action]).to_sql()
        assert "MODIFY COLUMN `col` REMOVE DEFAULT" in sql
        assert params == ()

    def test_no_set_or_drop_default_keyword_is_rendered(self, dialect):
        """The two spellings the server rejects must not appear in the output."""
        set_sql, _ = AlterTableExpression(
            dialect, Table(dialect, "t"), [AlterColumn(dialect, "col", ColumnAlterOperation.SET_DEFAULT, new_value=1)]
        ).to_sql()
        drop_sql, _ = AlterTableExpression(
            dialect, Table(dialect, "t"), [AlterColumn(dialect, "col", ColumnAlterOperation.DROP_DEFAULT)]
        ).to_sql()
        assert "SET DEFAULT" not in set_sql
        assert "DROP DEFAULT" not in drop_sql

    def test_both_renderings_execute_on_the_server(self, clickhouse_backend_single):
        """The rendered SQL is what the server accepts, and it changes the metadata.

        Before this was corrected the dialect emitted ``ALTER COLUMN c SET
        DEFAULT 5`` and ``ALTER COLUMN c DROP DEFAULT``, both of which 26.7.3.19
        rejects with ``Code: 62 ... Expected one of: token sequence, Dot, token,
        REMOVE, MODIFY SETTING, RESET SETTING, ADD ENUM VALUES, NULL, NOT,
        DEFAULT, MATERIALIZED, EPHEMERAL, ALIAS, AUTO_INCREMENT, TTL, PRIMARY
        KEY, COMMENT, CODEC, TYPE. (SYNTAX_ERROR)``.
        """
        backend = clickhouse_backend_single
        backend.execute("DROP TABLE IF EXISTS ar_alter_default")
        backend.execute("CREATE TABLE ar_alter_default (id UInt32) ENGINE = MergeTree ORDER BY id")
        try:
            d = backend.dialect
            backend.execute(*AlterTableExpression(
                d, Table(d, "ar_alter_default"),
                [AlterColumn(d, "id", ColumnAlterOperation.SET_DEFAULT, new_value=7)],
            ).to_sql())
            create = backend.execute("SHOW CREATE TABLE ar_alter_default").data[0]["statement"]
            assert "DEFAULT 7" in create

            backend.execute(*AlterTableExpression(
                d, Table(d, "ar_alter_default"),
                [AlterColumn(d, "id", ColumnAlterOperation.DROP_DEFAULT)],
            ).to_sql())
            create = backend.execute("SHOW CREATE TABLE ar_alter_default").data[0]["statement"]
            assert "DEFAULT" not in create
        finally:
            backend.execute("DROP TABLE IF EXISTS ar_alter_default")

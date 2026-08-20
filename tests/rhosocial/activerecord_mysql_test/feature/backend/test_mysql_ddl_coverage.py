# tests/rhosocial/activerecord_clickhouse_test/feature/backend/test_ddl_coverage.py
"""
ClickHouse DDL / statement coverage gap-completion tests.

Covers the missing SQL statements identified in the coverage-gap analysis:

- RENAME TABLE (atomic multi-table rename)
- TRUNCATE TABLE (option guards)
- ALTER TABLE ... ALTER COLUMN {SET DEFAULT | DROP DEFAULT}
- ANALYZE / CHECK / CHECKSUM / OPTIMIZE / REPAIR TABLE (whole-table)
- CREATE/DROP PROCEDURE, CREATE/DROP FUNCTION (stored), CALL
- TABLE statement and VALUES table value constructor
- LOAD XML
- Administrative utility commands (FLUSH, RESET, KILL, INSTALL, GRANT, ...)
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


class TestTableMaintenance:
    """Test ClickHouse whole-table maintenance statements."""

    def test_analyze_table(self, dialect):
        expr = clickhouse_expr.ClickHouseAnalyzeTableExpression(dialect, ["t1", "t2"])
        sql, params = expr.to_sql()
        assert sql == "ANALYZE TABLE `t1`, `t2`"
        assert params == ()

    def test_check_table(self, dialect):
        expr = clickhouse_expr.ClickHouseCheckTableExpression(
            dialect, ["t1"], options=[clickhouse_expr.CheckTableOption.QUICK]
        )
        sql, _ = expr.to_sql()
        assert sql == "CHECK TABLE `t1` QUICK"

    def test_checksum_table(self, dialect):
        expr = clickhouse_expr.ClickHouseChecksumTableExpression(dialect, [("db", "t")])
        sql, _ = expr.to_sql()
        assert sql == "CHECKSUM TABLE `db`.`t`"

    def test_optimize_table(self, dialect):
        expr = clickhouse_expr.ClickHouseOptimizeTableExpression(dialect, ["t1"])
        sql, _ = expr.to_sql()
        assert sql == "OPTIMIZE TABLE `t1`"

    def test_repair_table(self, dialect):
        expr = clickhouse_expr.ClickHouseRepairTableExpression(
            dialect, ["t1"], options=[clickhouse_expr.RepairTableOption.USE_FRM]
        )
        sql, _ = expr.to_sql()
        assert sql == "REPAIR TABLE `t1` USE_FRM"

    def test_no_write_to_binlog(self, dialect):
        expr = clickhouse_expr.ClickHouseAnalyzeTableExpression(
            dialect, ["t1"], no_write_to_binlog=clickhouse_expr.NoWriteToBinlogOption.LOCAL
        )
        sql, _ = expr.to_sql()
        assert sql == "ANALYZE TABLE LOCAL `t1`"

    def test_support_flags(self, dialect):
        for method in (
            dialect.supports_analyze_table,
            dialect.supports_check_table,
            dialect.supports_checksum_table,
            dialect.supports_optimize_table,
            dialect.supports_repair_table,
        ):
            assert method() is True


class TestStoredRoutines:
    """Test ClickHouse stored procedure / function / CALL statements."""

    def test_create_procedure(self, dialect):
        expr = clickhouse_expr.ClickHouseCreateProcedureExpression(
            dialect, "sp", params=[("IN", "x", "INT")], body="BEGIN END"
        )
        sql, _ = expr.to_sql()
        assert sql == "CREATE PROCEDURE `sp` (IN `x` INT) BEGIN END"

    def test_drop_procedure(self, dialect):
        expr = clickhouse_expr.ClickHouseDropProcedureExpression(dialect, "sp", if_exists=True)
        sql, _ = expr.to_sql()
        assert sql == "DROP PROCEDURE IF EXISTS `sp`"

    def test_create_function(self, dialect):
        expr = clickhouse_expr.ClickHouseCreateFunctionExpression(
            dialect, "fn", returns="INT", deterministic=True, body="RETURN 1"
        )
        sql, _ = expr.to_sql()
        assert sql == "CREATE FUNCTION `fn` () RETURNS INT DETERMINISTIC RETURN 1"

    def test_drop_function(self, dialect):
        expr = clickhouse_expr.ClickHouseDropFunctionExpression(dialect, "fn")
        sql, _ = expr.to_sql()
        assert sql == "DROP FUNCTION `fn`"

    def test_call(self, dialect):
        expr = clickhouse_expr.ClickHouseCallExpression(dialect, "sp", [1, "a"])
        sql, params = expr.to_sql()
        assert sql == "CALL `sp` (%s, %s)"
        assert params == (1, "a")

    def test_supports_flags(self, dialect):
        assert dialect.supports_procedure() is True
        assert dialect.supports_stored_function() is True
        assert dialect.supports_call() is True


class TestTableStatement:
    """Test ClickHouse TABLE statement and VALUES constructor."""

    def test_table_statement(self, dialect):
        expr = clickhouse_expr.ClickHouseTableExpression(dialect, "users")
        sql, params = expr.to_sql()
        assert sql == "TABLE `users`"
        assert params == ()

    def test_table_statement_with_limit(self, dialect):
        expr = clickhouse_expr.ClickHouseTableExpression(dialect, "users", limit=10)
        sql, _ = expr.to_sql()
        assert sql == "TABLE `users` LIMIT 10"

    def test_values_constructor(self, dialect):
        expr = clickhouse_expr.ClickHouseValuesExpression(dialect, [[1, "x"], [2, "y"]])
        sql, params = expr.to_sql()
        assert sql == "VALUES (%s, %s), (%s, %s)"
        assert params == (1, "x", 2, "y")


class TestLoadXML:
    """Test ClickHouse LOAD XML statement."""

    def test_basic(self, dialect):
        expr = clickhouse_expr.ClickHouseLoadXMLEXpression(dialect, "/tmp/data.xml", "t")
        sql, _ = expr.to_sql()
        assert sql == "LOAD XML INFILE '/tmp/data.xml' INTO TABLE `t`"

    def test_local(self, dialect):
        expr = clickhouse_expr.ClickHouseLoadXMLEXpression(dialect, "/tmp/data.xml", "t", local=True)
        sql, _ = expr.to_sql()
        assert sql == "LOAD XML LOCAL INFILE '/tmp/data.xml' INTO TABLE `t`"


class TestAdminCommands:
    """Test ClickHouse administrative utility commands."""

    def test_flush(self, dialect):
        expr = clickhouse_expr.ClickHouseFlushExpression(dialect, [clickhouse_expr.FlushOption.PRIVILEGES])
        sql, _ = expr.to_sql()
        assert sql == "FLUSH PRIVILEGES"

    def test_reset(self, dialect):
        expr = clickhouse_expr.ClickHouseResetExpression(dialect, clickhouse_expr.ResetOption.MASTER)
        sql, _ = expr.to_sql()
        assert sql == "RESET MASTER"

    def test_kill(self, dialect):
        expr = clickhouse_expr.ClickHouseKillExpression(dialect, 42)
        sql, _ = expr.to_sql()
        assert sql == "KILL CONNECTION 42"

    def test_install_plugin(self, dialect):
        expr = clickhouse_expr.ClickHouseInstallPluginExpression(dialect, "p", "libp.so")
        sql, _ = expr.to_sql()
        assert sql == "INSTALL PLUGIN `p` SONAME 'libp.so'"

    def test_grant(self, dialect):
        expr = clickhouse_expr.ClickHouseGrantExpression(
            dialect,
            [clickhouse_expr.GrantPrivilege("SELECT")],
            [clickhouse_expr.AccountSpec("u", "localhost")],
            on_object="db.*",
        )
        sql, _ = expr.to_sql()
        assert sql == "GRANT SELECT ON db.* TO 'u'@'localhost'"

    def test_supports_flags(self, dialect):
        for method in (
            dialect.supports_flush,
            dialect.supports_reset,
            dialect.supports_kill,
            dialect.supports_install_plugin,
            dialect.supports_grant,
        ):
            assert method() is True
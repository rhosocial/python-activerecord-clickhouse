# tests/rhosocial/activerecord_clickhouse_test/feature/backend/test_admin_statement_coverage.py
"""
Extended branch-coverage for ClickHouse administrative / maintenance / routine
statements added by the DDL coverage-gap completion.

Complements ``test_clickhouse_ddl_coverage.py`` by exercising the option-rich
branches (NO_WRITE_TO_BINLOG, index lists, component/plugin lists, CLONE
both directions, HANDLER READ variants, DO with sub-expressions, account
lists, GRANT/REVOKE with columns and GRANT OPTION) plus every
``validate()`` rejection path.
"""

import pytest

from rhosocial.activerecord.backend.dialect.exceptions import UnsupportedFeatureError
from rhosocial.activerecord.backend.impl.clickhouse import expression as clickhouse_expr
from rhosocial.activerecord.backend.impl.clickhouse.dialect import ClickHouseDialect
from rhosocial.activerecord.backend.impl.clickhouse.expression.maintenance import (
    ClickHouseTableMaintenanceExpression,
)


@pytest.fixture(scope="module")
def dialect():
    return ClickHouseDialect()


class _InspectableExpr:
    """Minimal stand-in for a core expression exposing to_sql()."""

    def __init__(self, sql="1 + 1", params=()):
        self._sql = sql
        self._params = params

    def to_sql(self):
        return self._sql, self._params


class TestFlushBranches:
    def test_no_write_to_binlog_multi_options(self, dialect):
        expr = clickhouse_expr.ClickHouseFlushExpression(
            dialect,
            [clickhouse_expr.FlushOption.PRIVILEGES, clickhouse_expr.FlushOption.LOGS],
            no_write_to_binlog=True,
        )
        sql, _ = expr.to_sql()
        assert sql == "FLUSH NO_WRITE_TO_BINLOG PRIVILEGES, LOGS"

    def test_empty_raises(self, dialect):
        expr = clickhouse_expr.ClickHouseFlushExpression(dialect, [])
        with pytest.raises(ValueError, match="at least one option"):
            expr.to_sql()

    def test_non_strict_skips_validation(self, dialect):
        dialect.strict_validation = False
        try:
            sql, _ = clickhouse_expr.ClickHouseFlushExpression(dialect, []).to_sql()
            assert sql == "FLUSH "
        finally:
            dialect.strict_validation = True


class TestCacheIndex:
    def test_cache_index_without_indexes(self, dialect):
        expr = clickhouse_expr.ClickHouseCacheIndexExpression(
            dialect, [{"table": "t1"}, {"table": ("db", "t2")}], "shared"
        )
        sql, _ = expr.to_sql()
        assert sql == "CACHE INDEX `t1`, `db`.`t2` IN `shared`"

    def test_cache_index_with_indexes(self, dialect):
        expr = clickhouse_expr.ClickHouseCacheIndexExpression(
            dialect, [{"table": "t1", "indexes": ["i1", "i2"]}], "shared"
        )
        sql, _ = expr.to_sql()
        assert sql == "CACHE INDEX `t1` INDEX (`i1`, `i2`) IN `shared`"

    def test_load_index_into_cache(self, dialect):
        expr = clickhouse_expr.ClickHouseLoadIndexIntoCacheExpression(
            dialect, [{"table": "t1", "indexes": ["i1"]}]
        )
        sql, _ = expr.to_sql()
        assert sql == "LOAD INDEX INTO CACHE `t1` INDEX (`i1`)"


class TestComponentPlugin:
    def test_install_component_multi(self, dialect):
        expr = clickhouse_expr.ClickHouseInstallComponentExpression(dialect, ["comp1", "comp2"])
        sql, _ = expr.to_sql()
        assert sql == "INSTALL COMPONENT 'comp1', 'comp2'"

    def test_uninstall_component_multi(self, dialect):
        expr = clickhouse_expr.ClickHouseUninstallComponentExpression(dialect, ["comp1", "comp2"])
        sql, _ = expr.to_sql()
        assert sql == "UNINSTALL COMPONENT 'comp1', 'comp2'"

    def test_uninstall_plugin(self, dialect):
        expr = clickhouse_expr.ClickHouseUninstallPluginExpression(dialect, "p")
        sql, _ = expr.to_sql()
        assert sql == "UNINSTALL PLUGIN `p`"


class TestClone:
    def test_clone_instance_from(self, dialect):
        expr = clickhouse_expr.ClickHouseCloneExpression(
            dialect,
            from_user="root",
            from_host="donor.example.com",
            from_port=3308,
            password="secret",
        )
        sql, _ = expr.to_sql()
        assert sql == (
            "CLONE INSTANCE FROM 'root'@'donor.example.com' PORT = 3308 "
            "PASSWORD = 'secret'"
        )

    def test_clone_instance_default_port(self, dialect):
        expr = clickhouse_expr.ClickHouseCloneExpression(dialect, from_user="u", from_host="h")
        sql, _ = expr.to_sql()
        assert sql == "CLONE INSTANCE FROM 'u'@'h' PORT = 3306"

    def test_clone_local(self, dialect):
        expr = clickhouse_expr.ClickHouseCloneExpression(
            dialect, from_data_directory="/from", to_data_directory="/to"
        )
        sql, _ = expr.to_sql()
        assert sql == "CLONE LOCAL DATA DIRECTORY '/from' TO DATA DIRECTORY = '/to'"

    def test_clone_local_no_dest(self, dialect):
        expr = clickhouse_expr.ClickHouseCloneExpression(dialect, from_data_directory="/from")
        sql, _ = expr.to_sql()
        assert sql == "CLONE LOCAL DATA DIRECTORY '/from'"


class TestInstanceCommands:
    def test_restart(self, dialect):
        sql, _ = clickhouse_expr.ClickHouseRestartExpression(dialect).to_sql()
        assert sql == "RESTART"

    def test_binlog(self, dialect):
        sql, _ = clickhouse_expr.ClickHouseBinlogExpression(dialect, "ZWNvZGVk").to_sql()
        assert sql == "BINLOG 'ZWNvZGVk'"


class TestHandler:
    def test_open_no_alias(self, dialect):
        expr = clickhouse_expr.ClickHouseHandlerOpenExpression(dialect, "t")
        sql, _ = expr.to_sql()
        assert sql == "HANDLER `t` OPEN"

    def test_open_alias(self, dialect):
        expr = clickhouse_expr.ClickHouseHandlerOpenExpression(dialect, "t", alias="a")
        sql, _ = expr.to_sql()
        assert sql == "HANDLER `t` OPEN AS `a`"

    def test_read_first_no_extras(self, dialect):
        expr = clickhouse_expr.ClickHouseHandlerReadExpression(
            dialect, "t", clickhouse_expr.HandlerReadMode.FIRST
        )
        sql, params = expr.to_sql()
        assert sql == "HANDLER `t` READ FIRST"
        assert params == ()

    def test_read_index_key_value(self, dialect):
        expr = clickhouse_expr.ClickHouseHandlerReadExpression(
            dialect,
            "t",
            clickhouse_expr.HandlerReadMode.NEXT,
            index="i1",
            key_value=5,
        )
        sql, params = expr.to_sql()
        assert sql == "HANDLER `t` READ `i1` NEXT (%s)"
        assert params == (5,)

    def test_read_where_limit_expr_key(self, dialect):
        where = _InspectableExpr("x > %s", (2,))
        key = _InspectableExpr("3 + 4", ())
        expr = clickhouse_expr.ClickHouseHandlerReadExpression(
            dialect,
            ("db", "t"),
            clickhouse_expr.HandlerReadMode.LAST,
            key_value=key,
            where=where,
            limit=10,
        )
        sql, params = expr.to_sql()
        assert sql == "HANDLER `db`.`t` READ LAST (3 + 4) WHERE x > %s LIMIT 10"
        assert params == (2,)

    def test_close(self, dialect):
        expr = clickhouse_expr.ClickHouseHandlerCloseExpression(dialect, ("db", "t"))
        sql, _ = expr.to_sql()
        assert sql == "HANDLER `db`.`t` CLOSE"


class TestDo:
    def test_plain_values(self, dialect):
        expr = clickhouse_expr.ClickHouseDoExpression(dialect, [1, "x"])
        sql, params = expr.to_sql()
        assert sql == "DO %s, %s"
        assert params == (1, "x")

    def test_expression_values(self, dialect):
        expr = clickhouse_expr.ClickHouseDoExpression(dialect, [_InspectableExpr("1 + 1", ())])
        sql, params = expr.to_sql()
        assert sql == "DO 1 + 1"
        assert params == ()


class TestKillShutdownHelp:
    def test_kill_query(self, dialect):
        sql, _ = clickhouse_expr.ClickHouseKillExpression(
            dialect, 42, clickhouse_expr.KillTarget.QUERY
        ).to_sql()
        assert sql == "KILL QUERY 42"

    def test_shutdown(self, dialect):
        sql, _ = clickhouse_expr.ClickHouseShutdownExpression(dialect).to_sql()
        assert sql == "SHUTDOWN"

    def test_help(self, dialect):
        sql, _ = clickhouse_expr.ClickHouseHelpExpression(dialect, "CREATE TABLE").to_sql()
        assert sql == "HELP 'CREATE TABLE'"


class TestAccountManagement:
    def test_create_user(self, dialect):
        expr = clickhouse_expr.ClickHouseCreateUserExpression(
            dialect,
            [clickhouse_expr.AccountSpec("alice"), clickhouse_expr.AccountSpec("bob", "%.example.com")],
            if_not_exists=True,
            identified_by="pwd",
        )
        sql, _ = expr.to_sql()
        assert sql == (
            "CREATE USER IF NOT EXISTS 'alice'@'%', 'bob'@'%.example.com' "
            "IDENTIFIED BY 'pwd'"
        )

    def test_create_user_no_options(self, dialect):
        expr = clickhouse_expr.ClickHouseCreateUserExpression(dialect, [clickhouse_expr.AccountSpec("u", "h")])
        sql, _ = expr.to_sql()
        assert sql == "CREATE USER 'u'@'h'"

    def test_drop_user(self, dialect):
        expr = clickhouse_expr.ClickHouseDropUserExpression(
            dialect, [clickhouse_expr.AccountSpec("u", "h")], if_exists=True
        )
        sql, _ = expr.to_sql()
        assert sql == "DROP USER IF EXISTS 'u'@'h'"


class TestGrantRevoke:
    def test_grant_with_columns_and_option(self, dialect):
        expr = clickhouse_expr.ClickHouseGrantExpression(
            dialect,
            [
                clickhouse_expr.GrantPrivilege("SELECT", ["c1", "c2"]),
                clickhouse_expr.GrantPrivilege("UPDATE"),
            ],
            [clickhouse_expr.AccountSpec("u", "h")],
            on_object="db.t",
            with_grant_option=True,
        )
        sql, _ = expr.to_sql()
        assert sql == (
            "GRANT SELECT (`c1`, `c2`), UPDATE ON db.t TO 'u'@'h' WITH GRANT OPTION"
        )

    def test_grant_default_object(self, dialect):
        expr = clickhouse_expr.ClickHouseGrantExpression(
            dialect, [clickhouse_expr.GrantPrivilege("ALL PRIVILEGES")], [clickhouse_expr.AccountSpec("u")]
        )
        sql, _ = expr.to_sql()
        assert sql == "GRANT ALL PRIVILEGES ON *.* TO 'u'@'%'"

    def test_revoke_with_columns(self, dialect):
        expr = clickhouse_expr.ClickHouseRevokeExpression(
            dialect,
            [clickhouse_expr.GrantPrivilege("SELECT", ["c1"])],
            [clickhouse_expr.AccountSpec("u", "h")],
            on_object="db.t",
        )
        sql, _ = expr.to_sql()
        assert sql == "REVOKE SELECT (`c1`) ON db.t FROM 'u'@'h'"

    def test_revoke_default_object(self, dialect):
        expr = clickhouse_expr.ClickHouseRevokeExpression(
            dialect, [clickhouse_expr.GrantPrivilege("SELECT")], [clickhouse_expr.AccountSpec("u")]
        )
        sql, _ = expr.to_sql()
        assert sql == "REVOKE SELECT ON *.* FROM 'u'@'%'"


class TestLoadXMLBranches:
    def test_full_options(self, dialect):
        expr = clickhouse_expr.ClickHouseLoadXMLEXpression(
            dialect,
            "/tmp/f.xml",
            "t",
            priority=clickhouse_expr.LoadXMLPriority.LOW_PRIORITY,
            conflict_mode=clickhouse_expr.LoadXMLConflictMode.REPLACE,
            character_set="utf8mb4",
            rows_identified_by="row",
            ignore_count=2,
            ignore_unit="ROWS",
        )
        sql, _ = expr.to_sql()
        assert sql == (
            "LOAD XML LOW_PRIORITY INFILE '/tmp/f.xml' REPLACE INTO TABLE `t` "
            "CHARACTER SET utf8mb4 ROWS IDENTIFIED BY '<row>' IGNORE 2 ROWS"
        )

    def test_validation_type_error(self, dialect):
        expr = clickhouse_expr.ClickHouseLoadXMLEXpression(dialect, 123, "t")
        with pytest.raises(TypeError):
            expr.to_sql()

    def test_validation_priority_local_conflict(self, dialect):
        expr = clickhouse_expr.ClickHouseLoadXMLEXpression(
            dialect,
            "/tmp/f.xml",
            "t",
            local=True,
            priority=clickhouse_expr.LoadXMLPriority.CONCURRENT,
        )
        with pytest.raises(ValueError, match="cannot be combined with LOCAL"):
            expr.to_sql()

    def test_validation_negative_ignore(self, dialect):
        expr = clickhouse_expr.ClickHouseLoadXMLEXpression(dialect, "/tmp/f.xml", "t", ignore_count=-1)
        with pytest.raises(ValueError, match="non-negative"):
            expr.to_sql()

    def test_validation_bad_unit(self, dialect):
        expr = clickhouse_expr.ClickHouseLoadXMLEXpression(dialect, "/tmp/f.xml", "t", ignore_unit="COLS")
        with pytest.raises(ValueError, match="'LINES' or 'ROWS'"):
            expr.to_sql()

    def test_validation_table_not_str(self, dialect):
        expr = clickhouse_expr.ClickHouseLoadXMLEXpression(dialect, "/tmp/f.xml", 5)
        with pytest.raises(TypeError):
            expr.to_sql()


class TestAllSupportsFlags:
    """Exercise every supports_* capability flag on the admin mixin."""

    def test_admin_supports_cache_and_service(self, dialect):
        for method in (
            dialect.supports_cache_index,
            dialect.supports_load_index_into_cache,
            dialect.supports_install_component,
            dialect.supports_uninstall_component,
            dialect.supports_install_plugin,
            dialect.supports_uninstall_plugin,
            dialect.supports_clone,
            dialect.supports_restart,
            dialect.supports_binlog,
            dialect.supports_handler,
            dialect.supports_do,
            dialect.supports_shutdown,
            dialect.supports_help,
            dialect.supports_create_user,
            dialect.supports_drop_user,
            dialect.supports_revoke,
            dialect.supports_load_xml,
            dialect.supports_rename_table,
            dialect.supports_multi_table_rename,
        ):
            assert method() is True

    def test_table_statement_flags_versioned(self):
        d8 = ClickHouseDialect(version=(8, 0, 19))
        assert d8.supports_table_statement() is True
        assert d8.supports_values_table_constructor() is True
        d7 = ClickHouseDialect(version=(5, 7, 44))
        assert d7.supports_table_statement() is False
        assert d7.supports_values_table_constructor() is False


class TestNonStrictValidation:
    """strict=False short-circuits validate() in each expression."""

    def test_flush(self, dialect):
        clickhouse_expr.ClickHouseFlushExpression(dialect, []).validate(strict=False)

    def test_load_xml(self, dialect):
        clickhouse_expr.ClickHouseLoadXMLEXpression(dialect, 123, 456).validate(strict=False)

    def test_maintenance(self, dialect):
        clickhouse_expr.ClickHouseAnalyzeTableExpression(dialect, []).validate(strict=False)

    def test_rename(self, dialect):
        clickhouse_expr.ClickHouseRenameTableExpression(dialect, []).validate(strict=False)

    def test_routine(self, dialect):
        clickhouse_expr.ClickHouseCreateProcedureExpression(dialect, 123).validate(strict=False)

    def test_call(self, dialect):
        clickhouse_expr.ClickHouseCallExpression(dialect, 123).validate(strict=False)

    def test_table_statement(self, dialect):
        clickhouse_expr.ClickHouseTableExpression(dialect, 5).validate(strict=False)

    def test_values(self, dialect):
        clickhouse_expr.ClickHouseValuesExpression(dialect, []).validate(strict=False)


class TestRoutineBranches:
    """Exercise stored-routine option and validation branches."""

    def test_create_procedure_without_body_and_2tx(self, dialect):
        expr = clickhouse_expr.ClickHouseCreateProcedureExpression(
            dialect, ("db", "sp"), params=[("x", "INT")]
        )
        sql, _ = expr.to_sql()
        assert sql == "CREATE PROCEDURE `db`.`sp` (`x` INT)"

    def test_create_function_all_options(self, dialect):
        expr = clickhouse_expr.ClickHouseCreateFunctionExpression(
            dialect,
            ("db", "fn"),
            returns="INT",
            params=[("OUT", "r", "INT")],
            body="RETURN 1",
            deterministic=True,
        )
        sql, _ = expr.to_sql()
        assert sql == (
            "CREATE FUNCTION `db`.`fn` (OUT `r` INT) RETURNS INT DETERMINISTIC RETURN 1"
        )

    def test_drop_function_if_exists(self, dialect):
        sql, _ = clickhouse_expr.ClickHouseDropFunctionExpression(
            dialect, "fn", if_exists=True
        ).to_sql()
        assert sql == "DROP FUNCTION IF EXISTS `fn`"

    def test_call_with_none_and_expr(self, dialect):
        expr = clickhouse_expr.ClickHouseCallExpression(
            dialect, ("db", "sp"), [None, _InspectableExpr("NOW()", ())]
        )
        sql, params = expr.to_sql()
        assert sql == "CALL `db`.`sp` (NULL, NOW())"
        assert params == ()

    def test_routine_invalid_name(self, dialect):
        for cls, kw in (
            (clickhouse_expr.ClickHouseCreateProcedureExpression, {"body": "x"}),
            (clickhouse_expr.ClickHouseCallExpression, {}),
        ):
            expr = cls(dialect, 123, **kw)
            with pytest.raises((TypeError, ValueError)):
                expr.to_sql()

    def test_routine_invalid_schema_qualified_name(self, dialect):
        expr = clickhouse_expr.ClickHouseCreateProcedureExpression(dialect, ("a", "b", "c"))
        with pytest.raises(ValueError, match="schema-qualified"):
            expr.to_sql()

    def test_call_invalid_schema_qualified_name(self, dialect):
        expr = clickhouse_expr.ClickHouseCallExpression(dialect, ("a", "b", "c"))
        with pytest.raises(ValueError, match="schema-qualified"):
            expr.to_sql()


class TestTableStatementBranches:
    def test_table_order_offset(self, dialect):
        expr = clickhouse_expr.ClickHouseTableExpression(dialect, "t", order_by=["a"], offset=5)
        sql, _ = expr.to_sql()
        assert sql == "TABLE `t` ORDER BY `a` OFFSET 5"

    def test_table_negative_limit(self, dialect):
        expr = clickhouse_expr.ClickHouseTableExpression(dialect, "t", limit=-1)
        with pytest.raises(ValueError):
            expr.to_sql()

    def test_table_negative_offset(self, dialect):
        expr = clickhouse_expr.ClickHouseTableExpression(dialect, "t", offset=-1)
        with pytest.raises(ValueError):
            expr.to_sql()

    def test_table_bad_name(self, dialect):
        expr = clickhouse_expr.ClickHouseTableExpression(dialect, 5)
        with pytest.raises(TypeError):
            expr.to_sql()

    def test_values_empty(self, dialect):
        expr = clickhouse_expr.ClickHouseValuesExpression(dialect, [])
        with pytest.raises(ValueError, match="requires at least one ROW"):
            expr.to_sql()


class TestMaintenanceBranches:
    def test_checksum_option(self, dialect):
        expr = clickhouse_expr.ClickHouseChecksumTableExpression(
            dialect, ["t1"], option=clickhouse_expr.ChecksumTableOption.QUICK
        )
        sql, _ = expr.to_sql()
        assert sql == "CHECKSUM TABLE `t1` QUICK"

    def test_analyze_no_write_local_binlog(self, dialect):
        expr = clickhouse_expr.ClickHouseAnalyzeTableExpression(
            dialect,
            ["t1"],
            no_write_to_binlog=clickhouse_expr.NoWriteToBinlogOption.NO_WRITE_TO_BINLOG,
        )
        sql, _ = expr.to_sql()
        assert sql == "ANALYZE TABLE NO_WRITE_TO_BINLOG `t1`"

    def test_empty_tables(self, dialect):
        expr = clickhouse_expr.ClickHouseAnalyzeTableExpression(dialect, [])
        with pytest.raises(ValueError, match="at least one table"):
            expr.to_sql()

    def test_bad_table(self, dialect):
        expr = clickhouse_expr.ClickHouseAnalyzeTableExpression(dialect, [("a", "b", "c")])
        with pytest.raises(ValueError):
            expr.to_sql()

    def test_bad_table_type(self, dialect):
        expr = clickhouse_expr.ClickHouseAnalyzeTableExpression(dialect, [123])
        with pytest.raises(TypeError):
            expr.to_sql()

    def test_unsupported_operation(self, dialect):
        expr = _UnsupportedMaintenanceExpr(dialect, ["t1"])
        with pytest.raises(UnsupportedFeatureError):
            expr.to_sql()


class _UnsupportedMaintenanceExpr(ClickHouseTableMaintenanceExpression):
    """Maintenance base with an unsupported operation keyword."""

    operation = "VACUUM"

    def to_sql(self):
        return self.dialect.format_table_maintenance_statement(self)


class TestRenameTableBranches:
    def test_invalid_pair(self, dialect):
        expr = clickhouse_expr.ClickHouseRenameTableExpression(dialect, [("a",)])
        with pytest.raises(ValueError):
            expr.to_sql()

    def test_non_string_names(self, dialect):
        expr = clickhouse_expr.ClickHouseRenameTableExpression(dialect, [(1, 2)])
        with pytest.raises(TypeError):
            expr.to_sql()


class TestRoutineParamBranches:
    def test_invalid_param_tuple(self, dialect):
        expr = clickhouse_expr.ClickHouseCreateProcedureExpression(
            dialect, "sp", params=[("a", "x", "INT", "EXTRA")]
        )
        with pytest.raises(ValueError, match="Invalid parameter"):
            expr.to_sql()

    def test_two_tuple_param(self, dialect):
        expr = clickhouse_expr.ClickHouseCreateProcedureExpression(
            dialect, "sp", params=[("x", "INT")]
        )
        sql, _ = expr.to_sql()
        assert sql == "CREATE PROCEDURE `sp` (`x` INT)"

    def test_plain_string_param(self, dialect):
        expr = clickhouse_expr.ClickHouseCreateProcedureExpression(
            dialect, "sp", params=["IN p INT"]
        )
        sql, _ = expr.to_sql()
        assert sql == "CREATE PROCEDURE `sp` (IN p INT)"


class TestValuesInlineExpression:
    def test_values_with_expression(self, dialect):
        expr = clickhouse_expr.ClickHouseValuesExpression(
            dialect, [[_InspectableExpr("UUID()", ())], [2]]
        )
        sql, params = expr.to_sql()
        assert sql == "VALUES (UUID()), (%s)"
        assert params == (2,)
# src/rhosocial/activerecord/backend/impl/clickhouse/mixins/admin.py
from typing import TYPE_CHECKING, Tuple

if TYPE_CHECKING:  # pragma: no cover
    from rhosocial.activerecord.backend.impl.clickhouse.expression.admin import (
        ClickHouseCacheIndexExpression,
        ClickHouseCloneExpression,
        ClickHouseCreateUserExpression,
        ClickHouseDropUserExpression,
        ClickHouseFlushExpression,
        ClickHouseGrantExpression,
        ClickHouseHelpExpression,
        ClickHouseInstallComponentExpression,
        ClickHouseInstallPluginExpression,
        ClickHouseKillExpression,
        ClickHouseLoadIndexIntoCacheExpression,
        ClickHouseResetExpression,
        ClickHouseRestartExpression,
        ClickHouseRevokeExpression,
        ClickHouseShutdownExpression,
        ClickHouseBinlogExpression,
        ClickHouseUninstallComponentExpression,
        ClickHouseUninstallPluginExpression,
        ClickHouseDoExpression,
        ClickHouseHandlerOpenExpression,
        ClickHouseHandlerReadExpression,
        ClickHouseHandlerCloseExpression,
    )


class ClickHouseAdminCommandMixin:
    """ClickHouse administrative / instance-level utility command support."""

    # --- FLUSH ---

    def supports_flush(self) -> bool:
        return True

    def format_flush_statement(self, expr: "ClickHouseFlushExpression") -> Tuple[str, tuple]:
        """Format ``FLUSH [NO_WRITE_TO_BINLOG|LOCAL] option [, option ...]``."""
        expr.validate(strict=self.strict_validation)
        parts = ["FLUSH"]
        if expr.no_write_to_binlog:
            parts.append("NO_WRITE_TO_BINLOG")
        parts.append(", ".join(option.value for option in expr.options))
        return " ".join(parts), ()

    # --- RESET ---

    def supports_reset(self) -> bool:
        return True

    def format_reset_statement(self, expr: "ClickHouseResetExpression") -> Tuple[str, tuple]:
        """Format ``RESET option``."""
        return f"RESET {expr.option.value}", ()

    # --- CACHE INDEX / LOAD INDEX INTO CACHE ---

    def supports_cache_index(self) -> bool:
        return True

    def _format_cache_entries(self, cache_entries) -> str:
        entries = []
        for entry in cache_entries:
            table = entry["table"]
            table_sql = _fmt_table(self, table)
            if entry.get("indexes"):
                idx = ", ".join(self.format_identifier(i) for i in entry["indexes"])
                table_sql += f" INDEX ({idx})"
            entries.append(table_sql)
        return ", ".join(entries)

    def format_cache_index_statement(
        self,
        expr: "ClickHouseCacheIndexExpression",
    ) -> Tuple[str, tuple]:
        """Format ``CACHE INDEX table [INDEX (...)] IN key_cache``."""
        expr.validate(strict=self.strict_validation)
        entries = self._format_cache_entries(expr.cache_entries)
        return f"CACHE INDEX {entries} IN {self.format_identifier(expr.key_cache)}", ()

    def supports_load_index_into_cache(self) -> bool:
        return True

    def format_load_index_into_cache_statement(
        self,
        expr: "ClickHouseLoadIndexIntoCacheExpression",
    ) -> Tuple[str, tuple]:
        """Format ``LOAD INDEX INTO CACHE table [INDEX (...)]``."""
        expr.validate(strict=self.strict_validation)
        entries = self._format_cache_entries(expr.cache_entries)
        return f"LOAD INDEX INTO CACHE {entries}", ()

    # --- INSTALL / UNINSTALL COMPONENT / PLUGIN ---

    def supports_install_component(self) -> bool:
        return True

    def format_install_component_statement(
        self,
        expr: "ClickHouseInstallComponentExpression",
    ) -> Tuple[str, tuple]:
        """Format ``INSTALL COMPONENT 'name' [, 'name' ...]``."""
        expr.validate(strict=self.strict_validation)
        names = ", ".join(f"'{n}'" for n in expr.names)
        return f"INSTALL COMPONENT {names}", ()

    def supports_uninstall_component(self) -> bool:
        return True

    def format_uninstall_component_statement(
        self,
        expr: "ClickHouseUninstallComponentExpression",
    ) -> Tuple[str, tuple]:
        """Format ``UNINSTALL COMPONENT 'name' [, 'name' ...]``."""
        expr.validate(strict=self.strict_validation)
        names = ", ".join(f"'{n}'" for n in expr.names)
        return f"UNINSTALL COMPONENT {names}", ()

    def supports_install_plugin(self) -> bool:
        return True

    def format_install_plugin_statement(
        self,
        expr: "ClickHouseInstallPluginExpression",
    ) -> Tuple[str, tuple]:
        """Format ``INSTALL PLUGIN name SONAME 'library.so'``."""
        expr.validate(strict=self.strict_validation)
        return f"INSTALL PLUGIN {self.format_identifier(expr.plugin_name)} SONAME '{expr.soname}'", ()

    def supports_uninstall_plugin(self) -> bool:
        return True

    def format_uninstall_plugin_statement(
        self,
        expr: "ClickHouseUninstallPluginExpression",
    ) -> Tuple[str, tuple]:
        """Format ``UNINSTALL PLUGIN name``."""
        expr.validate(strict=self.strict_validation)
        return f"UNINSTALL PLUGIN {self.format_identifier(expr.plugin_name)}", ()

    # --- CLONE / RESTART / BINLOG ---

    def supports_clone(self) -> bool:
        return True

    def format_clone_statement(self, expr: "ClickHouseCloneExpression") -> Tuple[str, tuple]:
        """Format ``CLONE INSTANCE FROM ...`` / ``CLONE LOCAL DATA DIRECTORY``."""
        parts = ["CLONE"]
        if expr.from_data_directory:
            parts.append("LOCAL DATA DIRECTORY")
            parts.append(f"'{expr.from_data_directory}'")
            if expr.to_data_directory:
                parts.append(f"TO DATA DIRECTORY = '{expr.to_data_directory}'")
            return " ".join(parts), ()
        parts.append("INSTANCE FROM")
        user_host = f"'{expr.from_user}'@'{expr.from_host}'"
        parts.append(user_host)
        port = expr.from_port or 3306
        parts.append(f"PORT = {port}")
        if expr.password:
            parts.append(f"PASSWORD = '{expr.password}'")
        return " ".join(parts), ()

    def supports_restart(self) -> bool:
        return True

    def format_restart_statement(self, expr: "ClickHouseRestartExpression") -> Tuple[str, tuple]:
        """Format the ``RESTART`` server statement."""
        return "RESTART", ()

    def supports_binlog(self) -> bool:
        return True

    def format_binlog_statement(self, expr: "ClickHouseBinlogExpression") -> Tuple[str, tuple]:
        """Format ``BINLOG 'base64_encoded_event'``."""
        return f"BINLOG '{expr.encoded}'", ()

    # --- HANDLER ---

    def supports_handler(self) -> bool:
        return True

    def format_handler_open_statement(
        self,
        expr: "ClickHouseHandlerOpenExpression",
    ) -> Tuple[str, tuple]:
        """Format ``HANDLER table OPEN [AS alias]``."""
        parts = ["HANDLER", _fmt_table(self, expr.table), "OPEN"]
        if expr.alias:
            parts.append("AS")
            parts.append(self.format_identifier(expr.alias))
        return " ".join(parts), ()

    def format_handler_read_statement(
        self,
        expr: "ClickHouseHandlerReadExpression",
    ) -> Tuple[str, tuple]:
        """Format ``HANDLER table READ ...``."""
        params = []
        parts = ["HANDLER", _fmt_table(self, expr.table), "READ"]
        if expr.index:
            parts.append(self.format_identifier(expr.index))
        parts.append(expr.mode.value)
        if expr.key_value is not None:
            if hasattr(expr.key_value, "to_sql"):
                sql, p = expr.key_value.to_sql()
                parts.append(f"({sql})")
                params.extend(p)
            else:
                parts.append("(" + self.get_parameter_placeholder() + ")")
                params.append(expr.key_value)
        if expr.where is not None:
            where_sql, where_params = expr.where.to_sql()
            parts.append(f"WHERE {where_sql}")
            params.extend(where_params)
        if expr.limit is not None:
            parts.append(f"LIMIT {int(expr.limit)}")
        return " ".join(parts), tuple(params)

    def format_handler_close_statement(
        self,
        expr: "ClickHouseHandlerCloseExpression",
    ) -> Tuple[str, tuple]:
        """Format ``HANDLER table CLOSE``."""
        return f"HANDLER {_fmt_table(self, expr.table)} CLOSE", ()

    # --- DO / KILL / SHUTDOWN / HELP ---

    def supports_do(self) -> bool:
        return True

    def format_do_statement(self, expr: "ClickHouseDoExpression") -> Tuple[str, tuple]:
        """Format ``DO expr [, expr ...]``."""
        params = []
        expr_parts = []
        for e in expr.expressions:
            if hasattr(e, "to_sql"):
                sql, p = e.to_sql()
                expr_parts.append(sql)
                params.extend(p)
            else:
                expr_parts.append(self.get_parameter_placeholder())
                params.append(e)
        return "DO " + ", ".join(expr_parts), tuple(params)

    def supports_kill(self) -> bool:
        return True

    def format_kill_statement(self, expr: "ClickHouseKillExpression") -> Tuple[str, tuple]:
        """Format ``KILL [CONNECTION | QUERY] processlist_id``."""
        parts = ["KILL"]
        if expr.target.value:
            parts.append(expr.target.value)
        parts.append(str(int(expr.processlist_id)))
        return " ".join(parts), ()

    def supports_shutdown(self) -> bool:
        return True

    def format_shutdown_statement(self, expr: "ClickHouseShutdownExpression") -> Tuple[str, tuple]:
        """Format the ``SHUTDOWN`` statement."""
        return "SHUTDOWN", ()

    def supports_help(self) -> bool:
        return True

    def format_help_statement(self, expr: "ClickHouseHelpExpression") -> Tuple[str, tuple]:
        """Format ``HELP 'topic'``."""
        return f"HELP '{expr.topic}'", ()

    # --- Account management (GRANT / REVOKE / CREATE / DROP USER) ---

    def supports_create_user(self) -> bool:
        return True

    def format_create_user_statement(
        self,
        expr: "ClickHouseCreateUserExpression",
    ) -> Tuple[str, tuple]:
        """Format ``CREATE USER [IF NOT EXISTS] acct [IDENTIFIED BY 'pwd']``."""
        parts = ["CREATE USER"]
        if expr.if_not_exists:
            parts.append("IF NOT EXISTS")
        parts.append(_format_accounts(self, expr.accounts))
        if expr.identified_by:
            parts.append(f"IDENTIFIED BY '{expr.identified_by}'")
        return " ".join(parts), ()

    def supports_drop_user(self) -> bool:
        return True

    def format_drop_user_statement(self, expr: "ClickHouseDropUserExpression") -> Tuple[str, tuple]:
        """Format ``DROP USER [IF EXISTS] acct [, acct ...]``."""
        parts = ["DROP USER"]
        if expr.if_exists:
            parts.append("IF EXISTS")
        parts.append(_format_accounts(self, expr.accounts))
        return " ".join(parts), ()

    def supports_grant(self) -> bool:
        return True

    def format_grant_statement(self, expr: "ClickHouseGrantExpression") -> Tuple[str, tuple]:
        """Format ``GRANT priv ON obj TO acct [WITH GRANT OPTION]``."""
        priv_parts = []
        for p in expr.privileges:
            if p.columns:
                cols = ", ".join(self.format_identifier(c) for c in p.columns)
                priv_parts.append(f"{p.privilege} ({cols})")
            else:
                priv_parts.append(p.privilege)
        parts = ["GRANT", ", ".join(priv_parts)]
        parts.append("ON")
        parts.append(expr.on_object or "*.*")
        parts.append("TO")
        parts.append(_format_accounts(self, expr.accounts))
        if expr.with_grant_option:
            parts.append("WITH GRANT OPTION")
        return " ".join(parts), ()

    def supports_revoke(self) -> bool:
        return True

    def format_revoke_statement(self, expr: "ClickHouseRevokeExpression") -> Tuple[str, tuple]:
        """Format ``REVOKE priv ON obj FROM acct``."""
        priv_parts = []
        for p in expr.privileges:
            if p.columns:
                cols = ", ".join(self.format_identifier(c) for c in p.columns)
                priv_parts.append(f"{p.privilege} ({cols})")
            else:
                priv_parts.append(p.privilege)
        parts = ["REVOKE", ", ".join(priv_parts)]
        parts.append("ON")
        parts.append(expr.on_object or "*.*")
        parts.append("FROM")
        parts.append(_format_accounts(self, expr.accounts))
        return " ".join(parts), ()


def _fmt_table(dialect, table):
    """Format a possibly schema-qualified table name."""
    if isinstance(table, tuple):
        schema, name = table
        return f"{dialect.format_identifier(schema)}.{dialect.format_identifier(name)}"
    return dialect.format_identifier(table)


def _format_accounts(dialect, accounts) -> str:
    """Format account specifications as ``'user'@'host'``."""
    parts = []
    for acct in accounts:
        host = acct.host if acct.host else "%"
        parts.append(f"'{acct.user}'@'{host}'")
    return ", ".join(parts)
# src/rhosocial/activerecord/backend/impl/clickhouse/protocols/admin.py
"""ClickHouse administrative / utility command protocol.

Split out of the former single-module ``clickhouse/protocols.py``; one
concern per module so the protocol surface stays legible.
"""

from typing import Protocol, runtime_checkable, Tuple, TYPE_CHECKING

if TYPE_CHECKING:  # pragma: no cover
    from rhosocial.activerecord.backend.impl.clickhouse.expression.admin import (
        ClickHouseBinlogExpression,
        ClickHouseCacheIndexExpression,
        ClickHouseCloneExpression,
        ClickHouseCreateUserExpression,
        ClickHouseDoExpression,
        ClickHouseDropUserExpression,
        ClickHouseFlushExpression,
        ClickHouseGrantExpression,
        ClickHouseHandlerCloseExpression,
        ClickHouseHandlerOpenExpression,
        ClickHouseHandlerReadExpression,
        ClickHouseHelpExpression,
        ClickHouseInstallComponentExpression,
        ClickHouseInstallPluginExpression,
        ClickHouseKillExpression,
        ClickHouseLoadIndexIntoCacheExpression,
        ClickHouseResetExpression,
        ClickHouseRestartExpression,
        ClickHouseRevokeExpression,
        ClickHouseShutdownExpression,
        ClickHouseUninstallComponentExpression,
        ClickHouseUninstallPluginExpression,
    )

@runtime_checkable
class ClickHouseAdminCommandSupport(Protocol):
    """ClickHouse administrative / utility command support protocol.

    Feature Source: ClickHouse native (instance administration)

    Covers FLUSH, RESET, CACHE INDEX, LOAD INDEX INTO CACHE, INSTALL /
    UNINSTALL COMPONENT / PLUGIN, CLONE, RESTART, BINLOG, HANDLER, DO,
    KILL, SHUTDOWN, HELP, and account management (CREATE/DROP USER, GRANT,
    REVOKE).

    Official Documentation:
    - Administrative statements: https://dev.clickhouse.com/doc/refman/8.0/en/sql-statements.html#sql-statements-administrative
    """

    def supports_flush(self) -> bool:
        ...

    def format_flush_statement(self, expr: "ClickHouseFlushExpression") -> Tuple[str, tuple]:
        ...

    def supports_reset(self) -> bool:
        ...

    def format_reset_statement(self, expr: "ClickHouseResetExpression") -> Tuple[str, tuple]:
        ...

    def supports_cache_index(self) -> bool:
        ...

    def format_cache_index_statement(self, expr: "ClickHouseCacheIndexExpression") -> Tuple[str, tuple]:
        ...

    def supports_load_index_into_cache(self) -> bool:
        ...

    def format_load_index_into_cache_statement(
        self, expr: "ClickHouseLoadIndexIntoCacheExpression"
    ) -> Tuple[str, tuple]:
        ...

    def supports_install_component(self) -> bool:
        ...

    def format_install_component_statement(self, expr: "ClickHouseInstallComponentExpression") -> Tuple[str, tuple]:
        ...

    def supports_uninstall_component(self) -> bool:
        ...

    def format_uninstall_component_statement(
        self, expr: "ClickHouseUninstallComponentExpression"
    ) -> Tuple[str, tuple]:
        ...

    def supports_install_plugin(self) -> bool:
        ...

    def format_install_plugin_statement(self, expr: "ClickHouseInstallPluginExpression") -> Tuple[str, tuple]:
        ...

    def supports_uninstall_plugin(self) -> bool:
        ...

    def format_uninstall_plugin_statement(self, expr: "ClickHouseUninstallPluginExpression") -> Tuple[str, tuple]:
        ...

    def supports_clone(self) -> bool:
        ...

    def format_clone_statement(self, expr: "ClickHouseCloneExpression") -> Tuple[str, tuple]:
        ...

    def supports_restart(self) -> bool:
        ...

    def format_restart_statement(self, expr: "ClickHouseRestartExpression") -> Tuple[str, tuple]:
        ...

    def supports_binlog(self) -> bool:
        ...

    def format_binlog_statement(self, expr: "ClickHouseBinlogExpression") -> Tuple[str, tuple]:
        ...

    def supports_handler(self) -> bool:
        ...

    def format_handler_open_statement(self, expr: "ClickHouseHandlerOpenExpression") -> Tuple[str, tuple]:
        ...

    def format_handler_read_statement(self, expr: "ClickHouseHandlerReadExpression") -> Tuple[str, tuple]:
        ...

    def format_handler_close_statement(self, expr: "ClickHouseHandlerCloseExpression") -> Tuple[str, tuple]:
        ...

    def supports_do(self) -> bool:
        ...

    def format_do_statement(self, expr: "ClickHouseDoExpression") -> Tuple[str, tuple]:
        ...

    def supports_kill(self) -> bool:
        ...

    def format_kill_statement(self, expr: "ClickHouseKillExpression") -> Tuple[str, tuple]:
        ...

    def supports_shutdown(self) -> bool:
        ...

    def format_shutdown_statement(self, expr: "ClickHouseShutdownExpression") -> Tuple[str, tuple]:
        ...

    def supports_help(self) -> bool:
        ...

    def format_help_statement(self, expr: "ClickHouseHelpExpression") -> Tuple[str, tuple]:
        ...

    def supports_create_user(self) -> bool:
        ...

    def format_create_user_statement(self, expr: "ClickHouseCreateUserExpression") -> Tuple[str, tuple]:
        ...

    def supports_drop_user(self) -> bool:
        ...

    def format_drop_user_statement(self, expr: "ClickHouseDropUserExpression") -> Tuple[str, tuple]:
        ...

    def supports_grant(self) -> bool:
        ...

    def format_grant_statement(self, expr: "ClickHouseGrantExpression") -> Tuple[str, tuple]:
        ...

    def supports_revoke(self) -> bool:
        ...

    def format_revoke_statement(self, expr: "ClickHouseRevokeExpression") -> Tuple[str, tuple]:
        ...

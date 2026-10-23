# src/rhosocial/activerecord/backend/impl/clickhouse/protocols/admin.py
"""ClickHouse administrative / utility command protocol.

Split out of the former single-module ``clickhouse/protocols.py``; one
concern per module so the protocol surface stays legible.
"""

from typing import Protocol, runtime_checkable, Tuple, TYPE_CHECKING

if TYPE_CHECKING:  # pragma: no cover
    from rhosocial.activerecord.backend.impl.clickhouse.expression.admin import (
        ClickHouseBinlogStatement,
        ClickHouseCacheIndexStatement,
        ClickHouseCloneStatement,
        ClickHouseCreateUserStatement,
        ClickHouseDoStatement,
        ClickHouseDropUserStatement,
        ClickHouseFlushStatement,
        ClickHouseGrantStatement,
        ClickHouseHandlerCloseStatement,
        ClickHouseHandlerOpenStatement,
        ClickHouseHandlerReadStatement,
        ClickHouseHelpStatement,
        ClickHouseInstallComponentStatement,
        ClickHouseInstallPluginStatement,
        ClickHouseKillStatement,
        ClickHouseLoadIndexIntoCacheStatement,
        ClickHouseResetStatement,
        ClickHouseRestartStatement,
        ClickHouseRevokeStatement,
        ClickHouseShutdownStatement,
        ClickHouseUninstallComponentStatement,
        ClickHouseUninstallPluginStatement,
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

    def format_flush_statement(self, expr: "ClickHouseFlushStatement") -> Tuple[str, tuple]:
        ...

    def supports_reset(self) -> bool:
        ...

    def format_reset_statement(self, expr: "ClickHouseResetStatement") -> Tuple[str, tuple]:
        ...

    def supports_cache_index(self) -> bool:
        ...

    def format_cache_index_statement(self, expr: "ClickHouseCacheIndexStatement") -> Tuple[str, tuple]:
        ...

    def supports_load_index_into_cache(self) -> bool:
        ...

    def format_load_index_into_cache_statement(
        self, expr: "ClickHouseLoadIndexIntoCacheStatement"
    ) -> Tuple[str, tuple]:
        ...

    def supports_install_component(self) -> bool:
        ...

    def format_install_component_statement(self, expr: "ClickHouseInstallComponentStatement") -> Tuple[str, tuple]:
        ...

    def supports_uninstall_component(self) -> bool:
        ...

    def format_uninstall_component_statement(
        self, expr: "ClickHouseUninstallComponentStatement"
    ) -> Tuple[str, tuple]:
        ...

    def supports_install_plugin(self) -> bool:
        ...

    def format_install_plugin_statement(self, expr: "ClickHouseInstallPluginStatement") -> Tuple[str, tuple]:
        ...

    def supports_uninstall_plugin(self) -> bool:
        ...

    def format_uninstall_plugin_statement(self, expr: "ClickHouseUninstallPluginStatement") -> Tuple[str, tuple]:
        ...

    def supports_clone(self) -> bool:
        ...

    def format_clone_statement(self, expr: "ClickHouseCloneStatement") -> Tuple[str, tuple]:
        ...

    def supports_restart(self) -> bool:
        ...

    def format_restart_statement(self, expr: "ClickHouseRestartStatement") -> Tuple[str, tuple]:
        ...

    def supports_binlog(self) -> bool:
        ...

    def format_binlog_statement(self, expr: "ClickHouseBinlogStatement") -> Tuple[str, tuple]:
        ...

    def supports_handler(self) -> bool:
        ...

    def format_handler_open_statement(self, expr: "ClickHouseHandlerOpenStatement") -> Tuple[str, tuple]:
        ...

    def format_handler_read_statement(self, expr: "ClickHouseHandlerReadStatement") -> Tuple[str, tuple]:
        ...

    def format_handler_close_statement(self, expr: "ClickHouseHandlerCloseStatement") -> Tuple[str, tuple]:
        ...

    def supports_do(self) -> bool:
        ...

    def format_do_statement(self, expr: "ClickHouseDoStatement") -> Tuple[str, tuple]:
        ...

    def supports_kill(self) -> bool:
        ...

    def format_kill_statement(self, expr: "ClickHouseKillStatement") -> Tuple[str, tuple]:
        ...

    def supports_shutdown(self) -> bool:
        ...

    def format_shutdown_statement(self, expr: "ClickHouseShutdownStatement") -> Tuple[str, tuple]:
        ...

    def supports_help(self) -> bool:
        ...

    def format_help_statement(self, expr: "ClickHouseHelpStatement") -> Tuple[str, tuple]:
        ...

    def supports_create_user(self) -> bool:
        ...

    def format_create_user_statement(self, expr: "ClickHouseCreateUserStatement") -> Tuple[str, tuple]:
        ...

    def supports_drop_user(self) -> bool:
        ...

    def format_drop_user_statement(self, expr: "ClickHouseDropUserStatement") -> Tuple[str, tuple]:
        ...

    def supports_grant(self) -> bool:
        ...

    def format_grant_statement(self, expr: "ClickHouseGrantStatement") -> Tuple[str, tuple]:
        ...

    def supports_revoke(self) -> bool:
        ...

    def format_revoke_statement(self, expr: "ClickHouseRevokeStatement") -> Tuple[str, tuple]:
        ...

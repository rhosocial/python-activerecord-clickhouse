# src/rhosocial/activerecord/backend/impl/clickhouse/mixins/admin.py
from typing import Any, Tuple

from rhosocial.activerecord.backend.dialect.exceptions import UnsupportedFeatureError


def _fmt_table(dialect, table):
    """Format a possibly schema-qualified table name."""
    if isinstance(table, tuple):
        schema, name = table
        return f"{dialect.format_identifier(schema)}.{dialect.format_identifier(name)}"
    return dialect.format_identifier(table)


class ClickHouseAdminCommandMixin:
    """ClickHouse does not support the MySQL instance-level administrative
    command set.

    Statements such as ``FLUSH``, ``RESET``, ``CACHE INDEX``, ``LOAD INDEX
    INTO CACHE``, ``INSTALL/UNINSTALL COMPONENT/PLUGIN``, ``CLONE``,
    ``RESTART``, ``BINLOG``, ``HANDLER``, ``DO``, ``KILL``, ``SHUTDOWN``,
    ``HELP`` and the account-management commands (``CREATE/DROP USER``,
    ``GRANT``, ``REVOKE``) are MySQL-specific. ClickHouse exposes its own
    ``SYSTEM`` command family (``SYSTEM RELOAD``, ``SYSTEM KILL``, ...) which
    are not mapped here. All methods fail fast.
    """

    def supports_flush(self) -> bool:
        return False

    def format_flush_statement(self, expr: Any) -> Tuple[str, tuple]:
        raise UnsupportedFeatureError(
            self.name, "FLUSH",
            suggestion="Use ClickHouse SYSTEM commands (e.g. SYSTEM FLUSH).",
        )

    def supports_reset(self) -> bool:
        return False

    def format_reset_statement(self, expr: Any) -> Tuple[str, tuple]:
        raise UnsupportedFeatureError(
            self.name, "RESET",
            suggestion="Use ClickHouse SYSTEM RESET.",
        )

    def supports_cache_index(self) -> bool:
        return False

    def format_cache_index_statement(self, expr: Any) -> Tuple[str, tuple]:
        raise UnsupportedFeatureError(
            self.name, "CACHE INDEX",
            suggestion="ClickHouse has no CACHE INDEX (MySQL key cache).",
        )

    def supports_load_index_into_cache(self) -> bool:
        return False

    def format_load_index_into_cache_statement(self, expr: Any) -> Tuple[str, tuple]:
        raise UnsupportedFeatureError(
            self.name, "LOAD INDEX INTO CACHE",
            suggestion="ClickHouse has no MySQL key-cache commands.",
        )

    def supports_install_component(self) -> bool:
        return False

    def format_install_component_statement(self, expr: Any) -> Tuple[str, tuple]:
        raise UnsupportedFeatureError(
            self.name, "INSTALL COMPONENT",
            suggestion="ClickHouse has no INSTALL COMPONENT.",
        )

    def supports_uninstall_component(self) -> bool:
        return False

    def format_uninstall_component_statement(self, expr: Any) -> Tuple[str, tuple]:
        raise UnsupportedFeatureError(
            self.name, "UNINSTALL COMPONENT",
            suggestion="ClickHouse has no UNINSTALL COMPONENT.",
        )

    def supports_install_plugin(self) -> bool:
        return False

    def format_install_plugin_statement(self, expr: Any) -> Tuple[str, tuple]:
        raise UnsupportedFeatureError(
            self.name, "INSTALL PLUGIN",
            suggestion="ClickHouse has no INSTALL PLUGIN SONAME.",
        )

    def supports_uninstall_plugin(self) -> bool:
        return False

    def format_uninstall_plugin_statement(self, expr: Any) -> Tuple[str, tuple]:
        raise UnsupportedFeatureError(
            self.name, "UNINSTALL PLUGIN",
            suggestion="ClickHouse has no UNINSTALL PLUGIN.",
        )

    def supports_clone(self) -> bool:
        return False

    def format_clone_statement(self, expr: Any) -> Tuple[str, tuple]:
        raise UnsupportedFeatureError(
            self.name, "CLONE",
            suggestion="ClickHouse has no CLONE INSTANCE.",
        )

    def supports_restart(self) -> bool:
        return False

    def format_restart_statement(self, expr: Any) -> Tuple[str, tuple]:
        raise UnsupportedFeatureError(
            self.name, "RESTART",
            suggestion="Use ClickHouse SYSTEM RESTART.",
        )

    def supports_binlog(self) -> bool:
        return False

    def format_binlog_statement(self, expr: Any) -> Tuple[str, tuple]:
        raise UnsupportedFeatureError(
            self.name, "BINLOG",
            suggestion="ClickHouse has no BINLOG statement.",
        )

    def supports_handler(self) -> bool:
        return False

    def format_handler_open_statement(self, expr: Any) -> Tuple[str, tuple]:
        raise UnsupportedFeatureError(
            self.name, "HANDLER",
            suggestion="ClickHouse has no HANDLER statement.",
        )

    def format_handler_read_statement(self, expr: Any) -> Tuple[str, tuple]:
        raise UnsupportedFeatureError(
            self.name, "HANDLER",
            suggestion="ClickHouse has no HANDLER statement.",
        )

    def format_handler_close_statement(self, expr: Any) -> Tuple[str, tuple]:
        raise UnsupportedFeatureError(
            self.name, "HANDLER",
            suggestion="ClickHouse has no HANDLER statement.",
        )

    def supports_do(self) -> bool:
        return False

    def format_do_statement(self, expr: Any) -> Tuple[str, tuple]:
        raise UnsupportedFeatureError(
            self.name, "DO",
            suggestion="ClickHouse has no DO statement.",
        )

    def supports_kill(self) -> bool:
        return False

    def format_kill_statement(self, expr: Any) -> Tuple[str, tuple]:
        raise UnsupportedFeatureError(
            self.name, "KILL",
            suggestion="Use ClickHouse SYSTEM KILL.",
        )

    def supports_shutdown(self) -> bool:
        return False

    def format_shutdown_statement(self, expr: Any) -> Tuple[str, tuple]:
        raise UnsupportedFeatureError(
            self.name, "SHUTDOWN",
            suggestion="Use ClickHouse SYSTEM SHUTDOWN.",
        )

    def supports_help(self) -> bool:
        return False

    def format_help_statement(self, expr: Any) -> Tuple[str, tuple]:
        raise UnsupportedFeatureError(
            self.name, "HELP",
            suggestion="ClickHouse has no HELP statement.",
        )

    def supports_create_user(self) -> bool:
        return False

    def format_create_user_statement(self, expr: Any) -> Tuple[str, tuple]:
        raise UnsupportedFeatureError(
            self.name, "CREATE USER",
            suggestion="Use ClickHouse CREATE USER (different syntax, not this MySQL mixin).",
        )

    def supports_drop_user(self) -> bool:
        return False

    def format_drop_user_statement(self, expr: Any) -> Tuple[str, tuple]:
        raise UnsupportedFeatureError(
            self.name, "DROP USER",
            suggestion="Use ClickHouse DROP USER (different syntax, not this MySQL mixin).",
        )

    def supports_grant(self) -> bool:
        return False

    def format_grant_statement(self, expr: Any) -> Tuple[str, tuple]:
        raise UnsupportedFeatureError(
            self.name, "GRANT",
            suggestion="Use ClickHouse GRANT (different syntax, not this MySQL mixin).",
        )

    def supports_revoke(self) -> bool:
        return False

    def format_revoke_statement(self, expr: Any) -> Tuple[str, tuple]:
        raise UnsupportedFeatureError(
            self.name, "REVOKE",
            suggestion="Use ClickHouse REVOKE (different syntax, not this MySQL mixin).",
        )

# src/rhosocial/activerecord/backend/impl/clickhouse/expression/admin.py
"""ClickHouse administrative utility statement expressions.

These cover instance-level, security, and maintenance commands that do not
map cleanly to the SQL standard DDL/DML layer:

- FLUSH [NO_WRITE_TO_BINLOG | LOCAL] option [, option ...]
- RESET {MASTER | REPLICA | SLAVE | PERSIST}
- CACHE INDEX table [INDEX index_list] [, ...] IN key_cache
- LOAD INDEX INTO CACHE table [INDEX ...] [, ...]
- INSTALL / UNINSTALL COMPONENT 'name'
- INSTALL / UNINSTALL PLUGIN name SONAME 'library.so'
- CLONE [INSTANCE FROM ...]
- RESTART
- BINLOG 'encoded'
- HANDLER table {OPEN | READ ... | CLOSE}
- DO expr [, expr ...]
- KILL [CONNECTION | QUERY] processlist_id
- SHUTDOWN
- HELP 'topic'
- GRANT / REVOKE / CREATE USER (account management)
"""

from enum import Enum
from typing import Any, Dict, List, Optional, Tuple, TYPE_CHECKING

from rhosocial.activerecord.backend.expression.bases import BaseExpression

if TYPE_CHECKING:  # pragma: no cover
    from rhosocial.activerecord.backend.dialect import SQLDialectBase


class FlushOption(Enum):
    """FLUSH statement options."""

    TABLES = "TABLES"
    LOGS = "LOGS"
    PRIVILEGES = "PRIVILEGES"
    BINARY_LOGS = "BINARY LOGS"
    ENGINE_LOGS = "ENGINE LOGS"
    ERROR_LOGS = "ERROR LOGS"
    GENERAL_LOGS = "GENERAL LOGS"
    HOSTS = "HOSTS"
    OPTIMIZER_COSTS = "OPTIMIZER COSTS"
    RELAY_LOGS = "RELAY LOGS"
    SLOW_LOGS = "SLOW LOGS"
    STATUS = "STATUS"
    USER_RESOURCES = "USER_RESOURCES"
    QUERY_CACHE = "QUERY CACHE"
    DES_KEY_FILE = "DES_KEY_FILE"
    MASTER = "MASTER"
    REPLICA = "REPLICA"
    SLAVE = "SLAVE"


class ResetOption(Enum):
    """RESET statement options."""

    MASTER = "MASTER"
    REPLICA = "REPLICA"
    SLAVE = "SLAVE"
    PERSIST = "PERSIST"


class KillTarget(Enum):
    """KILL target selector."""

    CONNECTION = "CONNECTION"
    QUERY = "QUERY"


class HandlerReadMode(Enum):
    """HANDLER READ modes."""

    FIRST = "FIRST"
    NEXT = "NEXT"
    PREV = "PREV"
    LAST = "LAST"


class ClickHouseFlushExpression(BaseExpression):
    """Represent ``FLUSH`` with one or more options."""

    def __init__(
        self,
        dialect: "SQLDialectBase",
        options: List[FlushOption],
        *,
        no_write_to_binlog: bool = False,
        dialect_options: Optional[Dict[str, Any]] = None,
    ):
        super().__init__(dialect)
        self.options: List[FlushOption] = list(options)
        self.no_write_to_binlog: bool = no_write_to_binlog
        self.dialect_options: Dict[str, Any] = dialect_options or {}

    def validate(self, strict: bool = True) -> None:
        if not strict:
            return
        if not self.options:
            raise ValueError("FLUSH requires at least one option")

    @property
    def format_method(self) -> str:
        return "format_flush_statement"


class ClickHouseResetExpression(BaseExpression):
    """Represent ``RESET`` with one option."""

    def __init__(
        self,
        dialect: "SQLDialectBase",
        option: ResetOption,
        *,
        dialect_options: Optional[Dict[str, Any]] = None,
    ):
        super().__init__(dialect)
        self.option: ResetOption = option
        self.dialect_options: Dict[str, Any] = dialect_options or {}

    @property
    def format_method(self) -> str:
        return "format_reset_statement"


class ClickHouseCacheIndexExpression(BaseExpression):
    """Represent ``CACHE INDEX ... IN key_cache``."""

    def __init__(
        self,
        dialect: "SQLDialectBase",
        cache_entries: List[Dict[str, Any]],
        key_cache: str,
        *,
        dialect_options: Optional[Dict[str, Any]] = None,
    ):
        super().__init__(dialect)
        # Each entry: {"table": name, "indexes": [names]} (indexes optional)
        self.cache_entries: List[Dict[str, Any]] = list(cache_entries)
        self.key_cache: str = key_cache
        self.dialect_options: Dict[str, Any] = dialect_options or {}

    @property
    def format_method(self) -> str:
        return "format_cache_index_statement"


class ClickHouseLoadIndexIntoCacheExpression(BaseExpression):
    """Represent ``LOAD INDEX INTO CACHE``."""

    def __init__(
        self,
        dialect: "SQLDialectBase",
        cache_entries: List[Dict[str, Any]],
        *,
        dialect_options: Optional[Dict[str, Any]] = None,
    ):
        super().__init__(dialect)
        self.cache_entries: List[Dict[str, Any]] = list(cache_entries)
        self.dialect_options: Dict[str, Any] = dialect_options or {}

    @property
    def format_method(self) -> str:
        return "format_load_index_into_cache_statement"


class ClickHouseInstallComponentExpression(BaseExpression):
    """Represent ``INSTALL COMPONENT 'name' [, 'name' ...]``."""

    def __init__(
        self,
        dialect: "SQLDialectBase",
        names: List[str],
        *,
        dialect_options: Optional[Dict[str, Any]] = None,
    ):
        super().__init__(dialect)
        self.names: List[str] = list(names)
        self.dialect_options: Dict[str, Any] = dialect_options or {}

    @property
    def format_method(self) -> str:
        return "format_install_component_statement"


class ClickHouseUninstallComponentExpression(BaseExpression):
    """Represent ``UNINSTALL COMPONENT 'name' [, 'name' ...]``."""

    def __init__(
        self,
        dialect: "SQLDialectBase",
        names: List[str],
        *,
        dialect_options: Optional[Dict[str, Any]] = None,
    ):
        super().__init__(dialect)
        self.names: List[str] = list(names)
        self.dialect_options: Dict[str, Any] = dialect_options or {}

    @property
    def format_method(self) -> str:
        return "format_uninstall_component_statement"


class ClickHouseInstallPluginExpression(BaseExpression):
    """Represent ``INSTALL PLUGIN name SONAME 'library.so'``."""

    def __init__(
        self,
        dialect: "SQLDialectBase",
        plugin_name: str,
        soname: str,
        *,
        dialect_options: Optional[Dict[str, Any]] = None,
    ):
        super().__init__(dialect)
        self.plugin_name: str = plugin_name
        self.soname: str = soname
        self.dialect_options: Dict[str, Any] = dialect_options or {}

    @property
    def format_method(self) -> str:
        return "format_install_plugin_statement"


class ClickHouseUninstallPluginExpression(BaseExpression):
    """Represent ``UNINSTALL PLUGIN name``."""

    def __init__(
        self,
        dialect: "SQLDialectBase",
        plugin_name: str,
        *,
        dialect_options: Optional[Dict[str, Any]] = None,
    ):
        super().__init__(dialect)
        self.plugin_name: str = plugin_name
        self.dialect_options: Dict[str, Any] = dialect_options or {}

    @property
    def format_method(self) -> str:
        return "format_uninstall_plugin_statement"


class ClickHouseCloneExpression(BaseExpression):
    """Represent ``CLONE INSTANCE FROM ...``.

    Attributes:
        from_user / from_host / from_port: Connection for the donor instance.
        password: Donor account password.
        from_data_directory: ``CLONE LOCAL DATA DIRECTORY`` source path.
        to_data_directory: Destination data directory for ``CLONE LOCAL``.
    """

    def __init__(
        self,
        dialect: "SQLDialectBase",
        *,
        from_user: Optional[str] = None,
        from_host: Optional[str] = None,
        from_port: Optional[int] = None,
        password: Optional[str] = None,
        from_data_directory: Optional[str] = None,
        to_data_directory: Optional[str] = None,
        dialect_options: Optional[Dict[str, Any]] = None,
    ):
        super().__init__(dialect)
        self.from_user = from_user
        self.from_host = from_host
        self.from_port = from_port
        self.password = password
        self.from_data_directory = from_data_directory
        self.to_data_directory = to_data_directory
        self.dialect_options: Dict[str, Any] = dialect_options or {}

    @property
    def format_method(self) -> str:
        return "format_clone_statement"


class ClickHouseRestartExpression(BaseExpression):
    """Represent the ``RESTART`` server statement."""

    def __init__(
        self,
        dialect: "SQLDialectBase",
        *,
        dialect_options: Optional[Dict[str, Any]] = None,
    ):
        super().__init__(dialect)
        self.dialect_options: Dict[str, Any] = dialect_options or {}

    @property
    def format_method(self) -> str:
        return "format_restart_statement"


class ClickHouseBinlogExpression(BaseExpression):
    """Represent ``BINLOG 'base64_encoded_event'``."""

    def __init__(
        self,
        dialect: "SQLDialectBase",
        encoded: str,
        *,
        dialect_options: Optional[Dict[str, Any]] = None,
    ):
        super().__init__(dialect)
        self.encoded: str = encoded
        self.dialect_options: Dict[str, Any] = dialect_options or {}

    @property
    def format_method(self) -> str:
        return "format_binlog_statement"


class ClickHouseHandlerOpenExpression(BaseExpression):
    """Represent ``HANDLER table OPEN [AS alias]``."""

    def __init__(
        self,
        dialect: "SQLDialectBase",
        table: Any,
        alias: Optional[str] = None,
        *,
        dialect_options: Optional[Dict[str, Any]] = None,
    ):
        super().__init__(dialect)
        self.table = table
        self.alias = alias
        self.dialect_options: Dict[str, Any] = dialect_options or {}

    @property
    def format_method(self) -> str:
        return "format_handler_open_statement"


class ClickHouseHandlerReadExpression(BaseExpression):
    """Represent ``HANDLER table READ {FIRST | NEXT}`` and variants."""

    def __init__(
        self,
        dialect: "SQLDialectBase",
        table: Any,
        mode: HandlerReadMode,
        *,
        index: Optional[str] = None,
        key_value: Optional[Any] = None,
        where: Optional[Any] = None,
        limit: Optional[int] = None,
        dialect_options: Optional[Dict[str, Any]] = None,
    ):
        super().__init__(dialect)
        self.table = table
        self.mode: HandlerReadMode = mode
        self.index = index
        self.key_value = key_value
        self.where = where
        self.limit = limit
        self.dialect_options: Dict[str, Any] = dialect_options or {}

    @property
    def format_method(self) -> str:
        return "format_handler_read_statement"


class ClickHouseHandlerCloseExpression(BaseExpression):
    """Represent ``HANDLER table CLOSE``."""

    def __init__(
        self,
        dialect: "SQLDialectBase",
        table: Any,
        *,
        dialect_options: Optional[Dict[str, Any]] = None,
    ):
        super().__init__(dialect)
        self.table = table
        self.dialect_options: Dict[str, Any] = dialect_options or {}

    @property
    def format_method(self) -> str:
        return "format_handler_close_statement"


class ClickHouseDoExpression(BaseExpression):
    """Represent ``DO expr [, expr ...]``."""

    def __init__(
        self,
        dialect: "SQLDialectBase",
        expressions: List[Any],
        *,
        dialect_options: Optional[Dict[str, Any]] = None,
    ):
        super().__init__(dialect)
        self.expressions: List[Any] = list(expressions)
        self.dialect_options: Dict[str, Any] = dialect_options or {}

    @property
    def format_method(self) -> str:
        return "format_do_statement"


class ClickHouseKillExpression(BaseExpression):
    """Represent ``KILL [CONNECTION | QUERY] processlist_id``."""

    def __init__(
        self,
        dialect: "SQLDialectBase",
        processlist_id: int,
        target: KillTarget = KillTarget.CONNECTION,
        *,
        dialect_options: Optional[Dict[str, Any]] = None,
    ):
        super().__init__(dialect)
        self.processlist_id: int = processlist_id
        self.target: KillTarget = target
        self.dialect_options: Dict[str, Any] = dialect_options or {}

    @property
    def format_method(self) -> str:
        return "format_kill_statement"


class ClickHouseShutdownExpression(BaseExpression):
    """Represent the ``SHUTDOWN`` statement."""

    def __init__(
        self,
        dialect: "SQLDialectBase",
        *,
        dialect_options: Optional[Dict[str, Any]] = None,
    ):
        super().__init__(dialect)
        self.dialect_options: Dict[str, Any] = dialect_options or {}

    @property
    def format_method(self) -> str:
        return "format_shutdown_statement"


class ClickHouseHelpExpression(BaseExpression):
    """Represent ``HELP 'topic'``."""

    def __init__(
        self,
        dialect: "SQLDialectBase",
        topic: str,
        *,
        dialect_options: Optional[Dict[str, Any]] = None,
    ):
        super().__init__(dialect)
        self.topic: str = topic
        self.dialect_options: Dict[str, Any] = dialect_options or {}

    @property
    def format_method(self) -> str:
        return "format_help_statement"


class AccountSpec:
    """Represent a ``'user'@'host'`` account specification."""

    def __init__(self, user: str, host: str = "%"):
        self.user: str = user
        self.host: str = host

    def __repr__(self) -> str:  # pragma: no cover
        return f"AccountSpec(user={self.user!r}, host={self.host!r})"


class ClickHouseCreateUserExpression(BaseExpression):
    """Represent ``CREATE USER [IF NOT EXISTS] 'user'@'host' [IDENTIFIED BY ...]``."""

    def __init__(
        self,
        dialect: "SQLDialectBase",
        accounts: List[AccountSpec],
        *,
        if_not_exists: bool = False,
        identified_by: Optional[str] = None,
        dialect_options: Optional[Dict[str, Any]] = None,
    ):
        super().__init__(dialect)
        self.accounts: List[AccountSpec] = list(accounts)
        self.if_not_exists: bool = if_not_exists
        self.identified_by: Optional[str] = identified_by
        self.dialect_options: Dict[str, Any] = dialect_options or {}

    @property
    def format_method(self) -> str:
        return "format_create_user_statement"


class ClickHouseDropUserExpression(BaseExpression):
    """Represent ``DROP USER [IF EXISTS] 'user'@'host' [, ...]``."""

    def __init__(
        self,
        dialect: "SQLDialectBase",
        accounts: List[AccountSpec],
        *,
        if_exists: bool = False,
        dialect_options: Optional[Dict[str, Any]] = None,
    ):
        super().__init__(dialect)
        self.accounts: List[AccountSpec] = list(accounts)
        self.if_exists: bool = if_exists
        self.dialect_options: Dict[str, Any] = dialect_options or {}

    @property
    def format_method(self) -> str:
        return "format_drop_user_statement"


class GrantPrivilege:
    """Represent a privilege grant for ``GRANT`` / ``REVOKE``.

    Attributes:
        privilege: Privilege name, e.g. ``SELECT``, ``ALL PRIVILEGES``.
        columns: Optional column list.
    """

    def __init__(self, privilege: str, columns: Optional[List[str]] = None):
        self.privilege: str = privilege
        self.columns: List[str] = list(columns or [])

    def __repr__(self) -> str:  # pragma: no cover
        return f"GrantPrivilege(privilege={self.privilege!r}, columns={self.columns!r})"


class ClickHouseGrantExpression(BaseExpression):
    """Represent ``GRANT priv_list ON object TO account_list``."""

    def __init__(
        self,
        dialect: "SQLDialectBase",
        privileges: List[GrantPrivilege],
        accounts: List[AccountSpec],
        *,
        on_object: Optional[str] = None,
        with_grant_option: bool = False,
        dialect_options: Optional[Dict[str, Any]] = None,
    ):
        super().__init__(dialect)
        self.privileges: List[GrantPrivilege] = list(privileges)
        self.accounts: List[AccountSpec] = list(accounts)
        self.on_object: Optional[str] = on_object  # default "*.*"
        self.with_grant_option: bool = with_grant_option
        self.dialect_options: Dict[str, Any] = dialect_options or {}

    @property
    def format_method(self) -> str:
        return "format_grant_statement"


class ClickHouseRevokeExpression(BaseExpression):
    """Represent ``REVOKE priv_list ON object FROM account_list``."""

    def __init__(
        self,
        dialect: "SQLDialectBase",
        privileges: List[GrantPrivilege],
        accounts: List[AccountSpec],
        *,
        on_object: Optional[str] = None,
        dialect_options: Optional[Dict[str, Any]] = None,
    ):
        super().__init__(dialect)
        self.privileges: List[GrantPrivilege] = list(privileges)
        self.accounts: List[AccountSpec] = list(accounts)
        self.on_object: Optional[str] = on_object
        self.dialect_options: Dict[str, Any] = dialect_options or {}

    @property
    def format_method(self) -> str:
        return "format_revoke_statement"

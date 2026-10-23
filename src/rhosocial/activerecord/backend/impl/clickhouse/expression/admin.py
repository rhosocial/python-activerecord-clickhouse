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
from typing import Any, Dict, List, Optional, TYPE_CHECKING

from rhosocial.activerecord.backend.expression.bases import BaseExpression

if TYPE_CHECKING:  # pragma: no cover
    from rhosocial.activerecord.backend.dialect import SQLDialectBase


class FlushOption(str, Enum):
    """FLUSH statement options.

    A ``str`` enum: a member *is* the word it carries, so an artifact can name
    the option without a vocabulary table, and the constructor normalises the
    serialized word back to the member. ``__str__`` is pinned to ``str.__str__``
    because ``Enum.__str__`` would otherwise win and spell members as
    ``FlushOption.TABLES`` -- on the XML channel that spelling is what travels,
    and no reader accepts it.
    """

    __str__ = str.__str__

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


class ResetOption(str, Enum):
    """RESET statement options. A ``str`` enum -- see :class:`FlushOption`."""

    __str__ = str.__str__

    MASTER = "MASTER"
    REPLICA = "REPLICA"
    SLAVE = "SLAVE"
    PERSIST = "PERSIST"


class KillTarget(str, Enum):
    """KILL target selector. A ``str`` enum -- see :class:`FlushOption`."""

    __str__ = str.__str__

    CONNECTION = "CONNECTION"
    QUERY = "QUERY"


class HandlerReadMode(str, Enum):
    """HANDLER READ modes. A ``str`` enum -- see :class:`FlushOption`."""

    __str__ = str.__str__

    FIRST = "FIRST"
    NEXT = "NEXT"
    PREV = "PREV"
    LAST = "LAST"


class ClickHouseFlushStatement(BaseExpression):
    """Represent ``FLUSH`` with one or more options."""

    def __init__(
        self,
        dialect: "SQLDialectBase",
        options: List[FlushOption],
        *,
        no_write_to_binlog: bool = False,
    ):
        super().__init__(dialect)
        # Normalise, don't just store: a member passes through, and the word an
        # artifact carries comes back as its member. A plain store would make
        # the restored instance hold a bare ``str`` where the original held the
        # enum, and the round trip would fail on the type.
        self.options: List[FlushOption] = [FlushOption(o) for o in options]
        self.no_write_to_binlog: bool = no_write_to_binlog

    def validate(self, strict: bool = True) -> None:
        if not strict:
            return
        if not self.options:
            raise ValueError("FLUSH requires at least one option")

    @property
    def format_method(self) -> str:
        return "format_flush_statement"


class ClickHouseResetStatement(BaseExpression):
    """Represent ``RESET`` with one option."""

    def __init__(
        self,
        dialect: "SQLDialectBase",
        option: ResetOption,
    ):
        super().__init__(dialect)
        self.option: ResetOption = ResetOption(option)

    @property
    def format_method(self) -> str:
        return "format_reset_statement"


class ClickHouseCacheIndexStatement(BaseExpression):
    """Represent ``CACHE INDEX ... IN key_cache``."""

    def __init__(
        self,
        dialect: "SQLDialectBase",
        cache_entries: List[Dict[str, Any]],
        key_cache: str,
    ):
        super().__init__(dialect)
        # Each entry: {"table": name, "indexes": [names]} (indexes optional)
        self.cache_entries: List[Dict[str, Any]] = list(cache_entries)
        self.key_cache: str = key_cache

    @property
    def format_method(self) -> str:
        return "format_cache_index_statement"


class ClickHouseLoadIndexIntoCacheStatement(BaseExpression):
    """Represent ``LOAD INDEX INTO CACHE``."""

    def __init__(
        self,
        dialect: "SQLDialectBase",
        cache_entries: List[Dict[str, Any]],
    ):
        super().__init__(dialect)
        self.cache_entries: List[Dict[str, Any]] = list(cache_entries)

    @property
    def format_method(self) -> str:
        return "format_load_index_into_cache_statement"


class ClickHouseInstallComponentStatement(BaseExpression):
    """Represent ``INSTALL COMPONENT 'name' [, 'name' ...]``."""

    def __init__(
        self,
        dialect: "SQLDialectBase",
        names: List[str],
    ):
        super().__init__(dialect)
        self.names: List[str] = list(names)

    @property
    def format_method(self) -> str:
        return "format_install_component_statement"


class ClickHouseUninstallComponentStatement(BaseExpression):
    """Represent ``UNINSTALL COMPONENT 'name' [, 'name' ...]``."""

    def __init__(
        self,
        dialect: "SQLDialectBase",
        names: List[str],
    ):
        super().__init__(dialect)
        self.names: List[str] = list(names)

    @property
    def format_method(self) -> str:
        return "format_uninstall_component_statement"


class ClickHouseInstallPluginStatement(BaseExpression):
    """Represent ``INSTALL PLUGIN name SONAME 'library.so'``."""

    def __init__(
        self,
        dialect: "SQLDialectBase",
        plugin_name: str,
        soname: str,
    ):
        super().__init__(dialect)
        self.plugin_name: str = plugin_name
        self.soname: str = soname

    @property
    def format_method(self) -> str:
        return "format_install_plugin_statement"


class ClickHouseUninstallPluginStatement(BaseExpression):
    """Represent ``UNINSTALL PLUGIN name``."""

    def __init__(
        self,
        dialect: "SQLDialectBase",
        plugin_name: str,
    ):
        super().__init__(dialect)
        self.plugin_name: str = plugin_name

    @property
    def format_method(self) -> str:
        return "format_uninstall_plugin_statement"


class ClickHouseCloneStatement(BaseExpression):
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
    ):
        super().__init__(dialect)
        self.from_user = from_user
        self.from_host = from_host
        self.from_port = from_port
        self.password = password
        self.from_data_directory = from_data_directory
        self.to_data_directory = to_data_directory

    @property
    def format_method(self) -> str:
        return "format_clone_statement"


class ClickHouseRestartStatement(BaseExpression):
    """Represent the ``RESTART`` server statement."""

    def __init__(
        self,
        dialect: "SQLDialectBase",
    ):
        super().__init__(dialect)

    @property
    def format_method(self) -> str:
        return "format_restart_statement"


class ClickHouseBinlogStatement(BaseExpression):
    """Represent ``BINLOG 'base64_encoded_event'``."""

    def __init__(
        self,
        dialect: "SQLDialectBase",
        encoded: str,
    ):
        super().__init__(dialect)
        self.encoded: str = encoded

    @property
    def format_method(self) -> str:
        return "format_binlog_statement"


class ClickHouseHandlerOpenStatement(BaseExpression):
    """Represent ``HANDLER table OPEN [AS alias]``."""

    def __init__(
        self,
        dialect: "SQLDialectBase",
        table: Any,
        alias: Optional[str] = None,
    ):
        super().__init__(dialect)
        self.table = table
        self.alias = alias

    @property
    def format_method(self) -> str:
        return "format_handler_open_statement"


class ClickHouseHandlerReadStatement(BaseExpression):
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
    ):
        super().__init__(dialect)
        self.table = table
        self.mode: HandlerReadMode = HandlerReadMode(mode)
        self.index = index
        self.key_value = key_value
        self.where = where
        self.limit = limit

    @property
    def format_method(self) -> str:
        return "format_handler_read_statement"


class ClickHouseHandlerCloseStatement(BaseExpression):
    """Represent ``HANDLER table CLOSE``."""

    def __init__(
        self,
        dialect: "SQLDialectBase",
        table: Any,
    ):
        super().__init__(dialect)
        self.table = table

    @property
    def format_method(self) -> str:
        return "format_handler_close_statement"


class ClickHouseDoStatement(BaseExpression):
    """Represent ``DO expr [, expr ...]``."""

    def __init__(
        self,
        dialect: "SQLDialectBase",
        expressions: List[Any],
    ):
        super().__init__(dialect)
        self.expressions: List[Any] = list(expressions)

    @property
    def format_method(self) -> str:
        return "format_do_statement"


class ClickHouseKillStatement(BaseExpression):
    """Represent ``KILL [CONNECTION | QUERY] processlist_id``."""

    def __init__(
        self,
        dialect: "SQLDialectBase",
        processlist_id: int,
        target: KillTarget = KillTarget.CONNECTION,
    ):
        super().__init__(dialect)
        self.processlist_id: int = processlist_id
        self.target: KillTarget = KillTarget(target)

    @property
    def format_method(self) -> str:
        return "format_kill_statement"


class ClickHouseShutdownStatement(BaseExpression):
    """Represent the ``SHUTDOWN`` statement."""

    def __init__(
        self,
        dialect: "SQLDialectBase",
    ):
        super().__init__(dialect)

    @property
    def format_method(self) -> str:
        return "format_shutdown_statement"


class ClickHouseHelpStatement(BaseExpression):
    """Represent ``HELP 'topic'``."""

    def __init__(
        self,
        dialect: "SQLDialectBase",
        topic: str,
    ):
        super().__init__(dialect)
        self.topic: str = topic

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


class ClickHouseCreateUserStatement(BaseExpression):
    """Represent ``CREATE USER [IF NOT EXISTS] 'user'@'host' [IDENTIFIED BY ...]``."""

    def __init__(
        self,
        dialect: "SQLDialectBase",
        accounts: List[AccountSpec],
        *,
        if_not_exists: bool = False,
        identified_by: Optional[str] = None,
    ):
        super().__init__(dialect)
        self.accounts: List[AccountSpec] = list(accounts)
        self.if_not_exists: bool = if_not_exists
        self.identified_by: Optional[str] = identified_by

    @property
    def format_method(self) -> str:
        return "format_create_user_statement"


class ClickHouseDropUserStatement(BaseExpression):
    """Represent ``DROP USER [IF EXISTS] 'user'@'host' [, ...]``."""

    def __init__(
        self,
        dialect: "SQLDialectBase",
        accounts: List[AccountSpec],
        *,
        if_exists: bool = False,
    ):
        super().__init__(dialect)
        self.accounts: List[AccountSpec] = list(accounts)
        self.if_exists: bool = if_exists

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


class ClickHouseGrantStatement(BaseExpression):
    """Represent ``GRANT priv_list ON object TO account_list``."""

    def __init__(
        self,
        dialect: "SQLDialectBase",
        privileges: List[GrantPrivilege],
        accounts: List[AccountSpec],
        *,
        on_object: Optional[str] = None,
        with_grant_option: bool = False,
    ):
        super().__init__(dialect)
        self.privileges: List[GrantPrivilege] = list(privileges)
        self.accounts: List[AccountSpec] = list(accounts)
        self.on_object: Optional[str] = on_object  # default "*.*"
        self.with_grant_option: bool = with_grant_option

    @property
    def format_method(self) -> str:
        return "format_grant_statement"


class ClickHouseRevokeStatement(BaseExpression):
    """Represent ``REVOKE priv_list ON object FROM account_list``."""

    def __init__(
        self,
        dialect: "SQLDialectBase",
        privileges: List[GrantPrivilege],
        accounts: List[AccountSpec],
        *,
        on_object: Optional[str] = None,
    ):
        super().__init__(dialect)
        self.privileges: List[GrantPrivilege] = list(privileges)
        self.accounts: List[AccountSpec] = list(accounts)
        self.on_object: Optional[str] = on_object

    @property
    def format_method(self) -> str:
        return "format_revoke_statement"

# src/rhosocial/activerecord/backend/impl/clickhouse/expression/show.py
"""
ClickHouse SHOW command expression classes.

This module defines expression classes for ClickHouse SHOW commands.
Each expression class collects parameters and delegates SQL generation
to the dialect's format_show_* methods.

Expression classes inherit from BaseExpression and implement to_sql(),
following the expression-dialect pattern used throughout the codebase.

Key design:
- **Every parameter is a constructor parameter.** A node is complete the moment
  it is built, so ``get_params()`` reads the declared fields and nothing has to
  be filled in afterwards. The ``schema()`` / ``full()`` / ``like()`` /
  ``for_user()`` setters this module used to carry made "the node" a thing that
  was only sometimes finished, and an artifact built from one could not say
  which state it had captured (expression-dialect §16.1).
- Expressions hold a dialect reference
- to_sql() delegates to dialect.format_show_* methods
- Dialect handles actual SQL generation

Nine of these are ClickHouse statements, and their output column names differ
from MySQL's: ``SHOW CREATE TABLE`` / ``SHOW CREATE VIEW`` answer a single
``statement`` column; ``SHOW TABLES`` names it ``name``, adding ``engine``
under ``FULL``; ``SHOW DATABASES`` names it ``name``; ``SHOW COLUMNS`` reports
``field`` / ``type`` / ``null`` / ``key`` / ``default`` / ``extra``; ``SHOW
INDEX`` reports ``pk_col`` where MySQL says ``Column_name``; ``SHOW
PROCESSLIST`` and ``SHOW ENGINES`` are ``system.processes`` and
``system.table_engines`` verbatim; and ``SHOW GRANTS`` returns one column named
after the statement text plus the requested output format. The rest of the
MySQL ``SHOW`` set is ClickHouse's to not have, and each of those expressions
carries a NOTE saying so — their dialect formatter raises
``UnsupportedFeatureError`` naming the ClickHouse replacement, so no expression
here renders SQL the server would reject.
"""

from typing import Optional, TYPE_CHECKING

from rhosocial.activerecord.backend.expression.bases import BaseExpression, SQLQueryAndParams

if TYPE_CHECKING:
    from ..dialect import ClickHouseDialect


class ShowExpression(BaseExpression):
    """Base class for ClickHouse SHOW command expressions.

    All ClickHouse SHOW expressions inherit from this class. ``schema`` is the
    ClickHouse database the statement is qualified by, and it is declared here
    because every subclass that can carry one declares it in its own
    ``__init__`` too: ``get_params()`` reads the *class's own* signature, so a
    qualifier declared on the base alone would be invisible to the artifact and
    silently dropped from the rendered statement.
    """

    def __init__(self, dialect: "ClickHouseDialect", *, schema: Optional[str] = None):
        super().__init__(dialect)
        self.schema: Optional[str] = schema

    def to_sql(self) -> SQLQueryAndParams:
        """Generate SQL. Subclasses must implement this method."""
        raise NotImplementedError("Subclasses must implement to_sql() method")


class ShowCreateTableExpression(ShowExpression):
    """Expression for SHOW CREATE TABLE command."""

    def __init__(
        self,
        dialect: "ClickHouseDialect",
        table: str,
        *,
        schema: Optional[str] = None,
    ):
        super().__init__(dialect, schema=schema)
        self.table: str = table

    def to_sql(self) -> SQLQueryAndParams:
        return self._dialect.format_show_create_table(self)


class ShowCreateViewExpression(ShowExpression):
    """Expression for SHOW CREATE VIEW command."""

    def __init__(
        self,
        dialect: "ClickHouseDialect",
        view_name: str,
        *,
        schema: Optional[str] = None,
    ):
        super().__init__(dialect, schema=schema)
        self.view_name: str = view_name

    def to_sql(self) -> SQLQueryAndParams:
        return self._dialect.format_show_create_view(self)


class ShowColumnsExpression(ShowExpression):
    """Expression for SHOW [FULL] COLUMNS command.

    ClickHouse has this statement; the table is mandatory (bare ``SHOW COLUMNS``
    is a ``SYNTAX_ERROR``) and the database, when given, is part of the table
    reference (``SHOW COLUMNS FROM db.t``), never a second ``FROM``.
    """

    def __init__(
        self,
        dialect: "ClickHouseDialect",
        table: str,
        *,
        full: bool = False,
        like_pattern: Optional[str] = None,
        schema: Optional[str] = None,
    ):
        super().__init__(dialect, schema=schema)
        self.table: str = table
        self.full: bool = full
        self.like_pattern: Optional[str] = like_pattern

    def to_sql(self) -> SQLQueryAndParams:
        return self._dialect.format_show_columns(self)


class ShowIndexExpression(ShowExpression):
    """Expression for SHOW INDEX command.

    ClickHouse has this statement "mostly for compatibility with MySQL". As with
    ``SHOW COLUMNS``, the database is part of the table reference.
    """

    def __init__(
        self,
        dialect: "ClickHouseDialect",
        table: str,
        *,
        schema: Optional[str] = None,
    ):
        super().__init__(dialect, schema=schema)
        self.table: str = table

    def to_sql(self) -> SQLQueryAndParams:
        return self._dialect.format_show_index(self)


class ShowTablesExpression(ShowExpression):
    """Expression for SHOW [FULL] TABLES command."""

    def __init__(
        self,
        dialect: "ClickHouseDialect",
        *,
        full: bool = False,
        like_pattern: Optional[str] = None,
        schema: Optional[str] = None,
    ):
        super().__init__(dialect, schema=schema)
        self.full: bool = full
        self.like_pattern: Optional[str] = like_pattern

    def to_sql(self) -> SQLQueryAndParams:
        return self._dialect.format_show_tables(self)


class ShowDatabasesExpression(ShowExpression):
    """Expression for SHOW DATABASES command."""

    def __init__(
        self,
        dialect: "ClickHouseDialect",
        *,
        like_pattern: Optional[str] = None,
    ):
        super().__init__(dialect)
        self.like_pattern: Optional[str] = like_pattern

    def to_sql(self) -> SQLQueryAndParams:
        return self._dialect.format_show_databases(self)


class ShowTableStatusExpression(ShowExpression):
    """Expression for SHOW TABLE STATUS command.

    NOTE: MySQL-only command, not supported by ClickHouse.
    """

    def __init__(
        self,
        dialect: "ClickHouseDialect",
        *,
        like_pattern: Optional[str] = None,
        schema: Optional[str] = None,
    ):
        super().__init__(dialect, schema=schema)
        self.like_pattern: Optional[str] = like_pattern

    def to_sql(self) -> SQLQueryAndParams:
        return self._dialect.format_show_table_status(self)


class ShowTriggersExpression(ShowExpression):
    """Expression for SHOW TRIGGERS command.

    NOTE: MySQL-only command, not supported by ClickHouse.
    """

    def __init__(
        self,
        dialect: "ClickHouseDialect",
        *,
        table: Optional[str] = None,
        schema: Optional[str] = None,
    ):
        super().__init__(dialect, schema=schema)
        self.table: Optional[str] = table

    def to_sql(self) -> SQLQueryAndParams:
        return self._dialect.format_show_triggers(self)


class ShowCreateTriggerExpression(ShowExpression):
    """Expression for SHOW CREATE TRIGGER command.

    NOTE: MySQL-only command, not supported by ClickHouse.
    """

    def __init__(
        self,
        dialect: "ClickHouseDialect",
        trigger: str,
        *,
        schema: Optional[str] = None,
    ):
        super().__init__(dialect, schema=schema)
        self.trigger: str = trigger

    def to_sql(self) -> SQLQueryAndParams:
        return self._dialect.format_show_create_trigger(self)


class ShowVariablesExpression(ShowExpression):
    """Expression for SHOW VARIABLES command.

    NOTE: MySQL-only command, not supported by ClickHouse.
    """

    def __init__(
        self,
        dialect: "ClickHouseDialect",
        *,
        session: bool = True,
        like_pattern: Optional[str] = None,
        schema: Optional[str] = None,
    ):
        super().__init__(dialect, schema=schema)
        self.session: bool = session
        self.like_pattern: Optional[str] = like_pattern

    def to_sql(self) -> SQLQueryAndParams:
        return self._dialect.format_show_variables(self)


class ShowStatusExpression(ShowExpression):
    """Expression for SHOW STATUS command.

    NOTE: MySQL-only command, not supported by ClickHouse.
    """

    def __init__(
        self,
        dialect: "ClickHouseDialect",
        *,
        session: bool = True,
        like_pattern: Optional[str] = None,
        schema: Optional[str] = None,
    ):
        super().__init__(dialect, schema=schema)
        self.session: bool = session
        self.like_pattern: Optional[str] = like_pattern

    def to_sql(self) -> SQLQueryAndParams:
        return self._dialect.format_show_status(self)


class ShowProcessListExpression(ShowExpression):
    """Expression for SHOW PROCESSLIST command.

    ClickHouse has this statement; it is ``SELECT * FROM system.processes``.
    ``full`` is accepted and never rendered — the statement has no ``FULL``
    variant.
    """

    def __init__(
        self,
        dialect: "ClickHouseDialect",
        *,
        full: bool = False,
        schema: Optional[str] = None,
    ):
        super().__init__(dialect, schema=schema)
        self.full: bool = full

    def to_sql(self) -> SQLQueryAndParams:
        return self._dialect.format_show_processlist(self)


class ShowWarningsExpression(ShowExpression):
    """Expression for SHOW WARNINGS command.

    NOTE: MySQL-only command, not supported by ClickHouse.
    """

    def __init__(
        self,
        dialect: "ClickHouseDialect",
        *,
        limit: Optional[int] = None,
    ):
        super().__init__(dialect)
        self.limit: Optional[int] = limit

    def to_sql(self) -> SQLQueryAndParams:
        return self._dialect.format_show_warnings(self)


class ShowErrorsExpression(ShowExpression):
    """Expression for SHOW ERRORS command.

    NOTE: MySQL-only command, not supported by ClickHouse.
    """

    def __init__(
        self,
        dialect: "ClickHouseDialect",
        *,
        limit: Optional[int] = None,
    ):
        super().__init__(dialect)
        self.limit: Optional[int] = limit

    def to_sql(self) -> SQLQueryAndParams:
        return self._dialect.format_show_errors(self)


class ShowEnginesExpression(ShowExpression):
    """Expression for SHOW ENGINES command.

    ClickHouse has this statement; it is ``SELECT * FROM system.table_engines``.
    """

    def to_sql(self) -> SQLQueryAndParams:
        return self._dialect.format_show_engines(self)


class ShowCharsetExpression(ShowExpression):
    """Expression for SHOW CHARACTER SET command.

    NOTE: MySQL-only command, not supported by ClickHouse.
    """

    def __init__(
        self,
        dialect: "ClickHouseDialect",
        *,
        like_pattern: Optional[str] = None,
    ):
        super().__init__(dialect)
        self.like_pattern: Optional[str] = like_pattern

    def to_sql(self) -> SQLQueryAndParams:
        return self._dialect.format_show_charset(self)


class ShowCollationExpression(ShowExpression):
    """Expression for SHOW COLLATION command.

    NOTE: MySQL-only command, not supported by ClickHouse.
    """

    def __init__(
        self,
        dialect: "ClickHouseDialect",
        *,
        like_pattern: Optional[str] = None,
    ):
        super().__init__(dialect)
        self.like_pattern: Optional[str] = like_pattern

    def to_sql(self) -> SQLQueryAndParams:
        return self._dialect.format_show_collation(self)


class ShowGrantsExpression(ShowExpression):
    """Expression for SHOW GRANTS command.

    ClickHouse has this statement. Its ``FOR`` clause takes access-entity names
    only — there is no ``user@host`` form — so ``host`` is recorded and not
    rendered. It stays a parameter because the callers that drive SHOW from a
    MySQL-shaped interface pass it; the dialect formatter is where the fact that
    ClickHouse cannot spell it is stated.
    """

    def __init__(
        self,
        dialect: "ClickHouseDialect",
        *,
        user: Optional[str] = None,
        host: Optional[str] = None,
    ):
        super().__init__(dialect)
        self.user: Optional[str] = user
        self.host: Optional[str] = host

    def to_sql(self) -> SQLQueryAndParams:
        return self._dialect.format_show_grants(self)


class ShowPluginsExpression(ShowExpression):
    """Expression for SHOW PLUGINS command.

    NOTE: MySQL-only command, not supported by ClickHouse.
    """

    def to_sql(self) -> SQLQueryAndParams:
        return self._dialect.format_show_plugins(self)

# src/rhosocial/activerecord/backend/impl/clickhouse/mixins/ddl_database.py
"""ClickHouse database DDL mixin."""
from __future__ import annotations

from enum import Enum
from typing import Tuple, TYPE_CHECKING

from rhosocial.activerecord.backend.dialect.exceptions import UnsupportedFeatureError
from rhosocial.activerecord.backend.expression.objects import Database

if TYPE_CHECKING:
    from rhosocial.activerecord.backend.expression.statements.ddl_database import (
        AlterDatabaseStatement,
        CreateDatabaseStatement,
        DropDatabaseStatement,
    )


class ClickHouseDatabaseMixin:
    """ClickHouse database DDL support.

    ClickHouse supports CREATE/DROP/ALTER DATABASE with ENGINE,
    ON CLUSTER, COMMENT, and SYNC options.
    """

    def supports_database(self) -> bool:
        return True

    def supports_create_database(self) -> bool:
        return True

    def supports_drop_database(self) -> bool:
        return True

    def supports_alter_database(self) -> bool:
        """ClickHouse supports ALTER DATABASE (MODIFY COMMENT only)."""
        return True

    def supports_database_if_not_exists(self) -> bool:
        return True

    def supports_database_if_exists(self) -> bool:
        return True

    def supports_database_comment(self) -> bool:
        """ClickHouse supports COMMENT for databases."""
        return True

    def format_create_database_statement(
        self, expr: CreateDatabaseStatement
    ) -> Tuple[str, tuple]:
        """Format ``CREATE DATABASE``.

        Raises:
            TypeError: ``expr.database`` is not a Database. A Table or a View
                would otherwise render its own name as the created database's.
        """
        if not isinstance(expr.database, Database):
            raise TypeError(
                f"CreateDatabaseStatement.database must be a Database, "
                f"got {type(expr.database).__name__}"
            )
        parts = ["CREATE DATABASE"]
        if expr.if_not_exists:
            parts.append("IF NOT EXISTS")
        parts.append(expr.database.to_sql()[0])
        if expr.comment:
            escaped_comment = expr.comment.replace("'", "''")
            parts.append(f"COMMENT '{escaped_comment}'")
        # ``ENGINE`` / ``ON CLUSTER`` are ClickHouse clauses and live on this
        # backend's own node; the generic CreateDatabaseStatement carries
        # neither, and which one arrived is a type question asked with
        # isinstance rather than probed field by field.
        from ..expression.database import ClickHouseCreateDatabaseExpression

        if isinstance(expr, ClickHouseCreateDatabaseExpression):
            if expr.engine:
                parts.append(f"ENGINE = {expr.engine}")
            if expr.on_cluster:
                parts.append(f"ON CLUSTER {self.format_identifier(expr.on_cluster)}")
        return " ".join(parts), ()

    def format_drop_database_statement(
        self, expr: DropDatabaseStatement
    ) -> Tuple[str, tuple]:
        """Format ``DROP DATABASE``.

        Raises:
            TypeError: ``expr.database`` is not a Database. Anything else would
                have its own name rendered as the dropped database's.
        """
        if not isinstance(expr.database, Database):
            raise TypeError(
                f"DropDatabaseStatement.database must be a Database, "
                f"got {type(expr.database).__name__}"
            )
        parts = ["DROP DATABASE"]
        if expr.if_exists:
            parts.append("IF EXISTS")
        parts.append(expr.database.to_sql()[0])
        # ``SYNC`` is a ClickHouse clause and lives on this backend's own
        # node; the generic DropDatabaseStatement does not carry it.
        from ..expression.database import ClickHouseDropDatabaseExpression

        if isinstance(expr, ClickHouseDropDatabaseExpression) and expr.sync:
            parts.append("SYNC")
        return " ".join(parts), ()

    def format_alter_database_statement(
        self, expr: AlterDatabaseStatement
    ) -> Tuple[str, tuple]:
        """Format ``ALTER DATABASE``.

        ClickHouse's ALTER DATABASE takes a list of ALTER commands, and
        ``MODIFY SETTING`` / ``MODIFY COMMENT`` are the two this branch
        spells -- see :meth:`supports_alter_database`.  It has no
        ``RENAME TO``: the server's own answer to that spelling is a syntax
        error ("Expected one of: ON, a list of ALTER commands, ALTER command,
        MODIFY SETTING, MODIFY COMMENT"), and a database is renamed with
        ``RENAME DATABASE <old> TO <new>``, which is a different statement.
        So the action is refused by name rather than emitted in a form the
        server rejects.

        Raises:
            TypeError: ``expr.database`` is not a Database. Anything else would
                have its own name rendered as the altered database's.
            UnsupportedFeatureError: An action ClickHouse's ALTER DATABASE has
                no form for.
        """
        if not isinstance(expr.database, Database):
            raise TypeError(
                f"AlterDatabaseStatement.database must be a Database, "
                f"got {type(expr.database).__name__}"
            )
        from rhosocial.activerecord.backend.expression.statements.ddl_database import (
            AlterDatabaseAction,
        )
        # ``MODIFY COMMENT`` was read off this branch by name and core's
        # AlterDatabaseAction has no such member, so every ALTER DATABASE
        # raised AttributeError before reaching any of this; an action
        # ClickHouse has no form for is reported rather than silently
        # dropped.  ``action`` accepts the enum or its raw spelling; which one
        # it is is a type question, so it is asked with isinstance rather than
        # probed field by field.
        action = expr.action.value if isinstance(expr.action, Enum) else expr.action
        if expr.action == AlterDatabaseAction.RENAME_TO:
            raise UnsupportedFeatureError(
                self.name,
                "ALTER DATABASE ... RENAME TO",
                suggestion=(
                    "ClickHouse has no ALTER DATABASE ... RENAME TO; rename the "
                    "database with RENAME DATABASE <old> TO <new>."
                ),
            )
        raise UnsupportedFeatureError(
            self.name,
            f"ALTER DATABASE {action}",
            suggestion=(
                "ClickHouse's ALTER DATABASE takes MODIFY SETTING / MODIFY "
                "COMMENT."
            ),
        )


__all__ = ['ClickHouseDatabaseMixin']

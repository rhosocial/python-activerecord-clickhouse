# src/rhosocial/activerecord/backend/impl/clickhouse/mixins/ddl_database.py
"""ClickHouse database DDL mixin."""
from __future__ import annotations

from typing import Tuple, TYPE_CHECKING

from rhosocial.activerecord.backend.dialect.exceptions import UnsupportedFeatureError
from rhosocial.activerecord.backend.expression.objects import Database

if TYPE_CHECKING:
    from rhosocial.activerecord.backend.expression.statements.ddl_database import (
        AlterDatabaseExpression,
        CreateDatabaseExpression,
        DropDatabaseExpression,
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
        self, expr: CreateDatabaseExpression
    ) -> Tuple[str, tuple]:
        """Format ``CREATE DATABASE``.

        Raises:
            TypeError: ``expr.database`` is not a Database. A Table or a View
                would otherwise render its own name as the created database's.
        """
        if not isinstance(expr.database, Database):
            raise TypeError(
                f"CreateDatabaseExpression.database must be a Database, "
                f"got {type(expr.database).__name__}"
            )
        parts = ["CREATE DATABASE"]
        if expr.if_not_exists:
            parts.append("IF NOT EXISTS")
        parts.append(expr.database.to_sql()[0])
        if expr.comment:
            escaped_comment = expr.comment.replace("'", "''")
            parts.append(f"COMMENT '{escaped_comment}'")
        engine = getattr(expr, "engine", None)
        if engine:
            parts.append(f"ENGINE = {engine}")
        on_cluster = getattr(expr, "on_cluster", None)
        if on_cluster:
            parts.append(f"ON CLUSTER {self.format_identifier(on_cluster)}")
        return " ".join(parts), ()

    def format_drop_database_statement(
        self, expr: DropDatabaseExpression
    ) -> Tuple[str, tuple]:
        """Format ``DROP DATABASE``.

        Raises:
            TypeError: ``expr.database`` is not a Database. Anything else would
                have its own name rendered as the dropped database's.
        """
        if not isinstance(expr.database, Database):
            raise TypeError(
                f"DropDatabaseExpression.database must be a Database, "
                f"got {type(expr.database).__name__}"
            )
        parts = ["DROP DATABASE"]
        if expr.if_exists:
            parts.append("IF EXISTS")
        parts.append(expr.database.to_sql()[0])
        sync = getattr(expr, "sync", False)
        if sync:
            parts.append("SYNC")
        return " ".join(parts), ()

    def format_alter_database_statement(
        self, expr: AlterDatabaseExpression
    ) -> Tuple[str, tuple]:
        """Format ``ALTER DATABASE``.

        Raises:
            TypeError: ``expr.database`` is not a Database. Anything else would
                have its own name rendered as the altered database's.
            UnsupportedFeatureError: An action ClickHouse's ALTER DATABASE has
                no form for.
        """
        if not isinstance(expr.database, Database):
            raise TypeError(
                f"AlterDatabaseExpression.database must be a Database, "
                f"got {type(expr.database).__name__}"
            )
        from rhosocial.activerecord.backend.expression.statements.ddl_database import (
            AlterDatabaseAction,
        )
        parts = ["ALTER DATABASE"]
        parts.append(expr.database.to_sql()[0])
        # ``RENAME TO`` is the one action core's enum names and ClickHouse spells
        # the same way. ``MODIFY COMMENT`` was read off this branch by name and
        # core's AlterDatabaseAction has no such member, so every ALTER DATABASE
        # raised AttributeError before reaching any of this; an action ClickHouse
        # has no form for is reported rather than silently dropped.
        if expr.action == AlterDatabaseAction.RENAME_TO:
            target = expr.target
            if not target:
                raise UnsupportedFeatureError(
                    self.name, "ALTER DATABASE ... RENAME TO",
                    suggestion="RENAME TO requires the new database name.",
                )
            parts.append(f"RENAME TO {self.format_identifier(str(target))}")
        else:
            raise UnsupportedFeatureError(
                self.name,
                f"ALTER DATABASE {getattr(expr.action, 'value', expr.action)}",
                suggestion="ClickHouse supports ALTER DATABASE ... RENAME TO.",
            )
        return " ".join(parts), ()


__all__ = ['ClickHouseDatabaseMixin']

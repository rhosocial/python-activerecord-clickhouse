# src/rhosocial/activerecord/backend/impl/clickhouse/mixins/ddl_database.py
"""ClickHouse database DDL mixin."""
from __future__ import annotations

from typing import Tuple, TYPE_CHECKING

from rhosocial.activerecord.backend.dialect.exceptions import UnsupportedFeatureError

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
        parts = ["CREATE DATABASE"]
        if expr.if_not_exists:
            parts.append("IF NOT EXISTS")
        parts.append(self.format_identifier(expr.database_name))
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
        parts = ["DROP DATABASE"]
        if expr.if_exists:
            parts.append("IF EXISTS")
        parts.append(self.format_identifier(expr.database_name))
        sync = getattr(expr, "sync", False)
        if sync:
            parts.append("SYNC")
        return " ".join(parts), ()

    def format_alter_database_statement(
        self, expr: AlterDatabaseExpression
    ) -> Tuple[str, tuple]:
        from rhosocial.activerecord.backend.expression.statements.ddl_database import AlterDatabaseAction
        parts = ["ALTER DATABASE"]
        parts.append(self.format_identifier(expr.database_name))
        if expr.action == AlterDatabaseAction.MODIFY_COMMENT:
            comment = expr.target or ""
            escaped_comment = comment.replace("'", "''")
            parts.append(f"MODIFY COMMENT '{escaped_comment}'")
        return " ".join(parts), ()


__all__ = ['ClickHouseDatabaseMixin']

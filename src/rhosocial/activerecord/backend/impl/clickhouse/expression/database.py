# src/rhosocial/activerecord/backend/impl/clickhouse/expression/database.py
"""ClickHouse-specific CREATE / DROP DATABASE expressions."""

from typing import TYPE_CHECKING, Optional

from rhosocial.activerecord.backend.expression.statements.ddl_database import (
    CreateDatabaseExpression,
    DropDatabaseExpression,
)

if TYPE_CHECKING:  # pragma: no cover
    from rhosocial.activerecord.backend.dialect import SQLDialectBase


class ClickHouseCreateDatabaseExpression(CreateDatabaseExpression):
    """A ClickHouse CREATE DATABASE statement extending the generic one.

    Adds the ClickHouse-only ``ENGINE = <expr>`` and ``ON CLUSTER <name>``
    clauses, which have no generic equivalent.
    """

    def __init__(
        self,
        dialect: "SQLDialectBase",
        database_name: str,
        if_not_exists: bool = False,
        owner: Optional[str] = None,
        encoding: Optional[str] = None,
        collation: Optional[str] = None,
        tablespace: Optional[str] = None,
        template: Optional[str] = None,
        connection_limit: Optional[int] = None,
        comment: Optional[str] = None,
        or_replace: bool = False,
        *,
        engine: Optional[str] = None,
        on_cluster: Optional[str] = None,
    ):
        super().__init__(
            dialect,
            database_name=database_name,
            if_not_exists=if_not_exists,
            owner=owner,
            encoding=encoding,
            collation=collation,
            tablespace=tablespace,
            template=template,
            connection_limit=connection_limit,
            comment=comment,
            or_replace=or_replace,
        )
        self.engine = engine
        self.on_cluster = on_cluster


class ClickHouseDropDatabaseExpression(DropDatabaseExpression):
    """A ClickHouse DROP DATABASE statement extending the generic one.

    Adds the ClickHouse-only ``SYNC`` modifier, which has no generic
    equivalent.
    """

    def __init__(
        self,
        dialect: "SQLDialectBase",
        database_name: str,
        if_exists: bool = False,
        force: bool = False,
        *,
        sync: bool = False,
    ):
        super().__init__(
            dialect,
            database_name=database_name,
            if_exists=if_exists,
            force=force,
        )
        self.sync = sync


__all__ = [
    "ClickHouseCreateDatabaseExpression",
    "ClickHouseDropDatabaseExpression",
]

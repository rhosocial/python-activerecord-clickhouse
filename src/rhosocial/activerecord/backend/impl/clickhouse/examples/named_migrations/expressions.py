# src/rhosocial/activerecord/backend/impl/clickhouse/examples/named_migrations/expressions.py
"""
DDL named expression functions for ClickHouse migration examples.

Each function receives a *dialect* and returns a DDL expression object.
These are the building blocks used by NamedMigration up()/down() methods.

"""

from rhosocial.activerecord.backend.expression.statements.ddl_table import (
    CreateTableExpression,
    ColumnDefinition,
    ColumnConstraint,
    ColumnConstraintType,
    DropTableExpression,
)
from rhosocial.activerecord.backend.impl.clickhouse.expression.types import (
    ClickHouseUInt32Type,
    ClickHouseStringType,
)


def create_users_table(dialect):
    """CREATE TABLE users (id UInt32 PRIMARY KEY, name String, email String)."""
    return CreateTableExpression(
        dialect,
        table="users",
        columns=[
            ColumnDefinition(
                dialect,
                "id",
                ClickHouseUInt32Type(dialect),
                constraints=[
                    ColumnConstraint(
                        ColumnConstraintType.PRIMARY_KEY,
                    ),
                ],
            ),
            ColumnDefinition(dialect, "name", ClickHouseStringType(dialect)),
            ColumnDefinition(dialect, "email", ClickHouseStringType(dialect)),
        ],
    )


def drop_users_table(dialect):
    """DROP TABLE IF EXISTS users."""
    return DropTableExpression(dialect, table="users", if_exists=True)


def create_posts_table(dialect):
    """CREATE TABLE posts (id UInt32 PRIMARY KEY, title String, user_id UInt32)."""
    return CreateTableExpression(
        dialect,
        table="posts",
        columns=[
            ColumnDefinition(
                dialect,
                "id",
                ClickHouseUInt32Type(dialect),
                constraints=[
                    ColumnConstraint(
                        ColumnConstraintType.PRIMARY_KEY,
                    ),
                ],
            ),
            ColumnDefinition(dialect, "title", ClickHouseStringType(dialect)),
            ColumnDefinition(dialect, "user_id", ClickHouseUInt32Type(dialect)),
        ],
    )


def drop_posts_table(dialect):
    """DROP TABLE IF EXISTS posts."""
    return DropTableExpression(dialect, table="posts", if_exists=True)


def create_custom_table(dialect, table: str = "custom_table"):
    """CREATE TABLE <table> (id UInt32 PRIMARY KEY, value String).

    This expression accepts an extra ``table`` parameter, allowing
    the migration to control the target table name at runtime.
    """
    return CreateTableExpression(
        dialect,
        table=table,
        columns=[
            ColumnDefinition(
                dialect,
                "id",
                ClickHouseUInt32Type(dialect),
                constraints=[
                    ColumnConstraint(
                        ColumnConstraintType.PRIMARY_KEY,
                    ),
                ],
            ),
            ColumnDefinition(dialect, "value", ClickHouseStringType(dialect)),
        ],
    )


def drop_custom_table(dialect, table: str = "custom_table"):
    """DROP TABLE IF EXISTS <table>."""
    return DropTableExpression(dialect, table=table, if_exists=True)
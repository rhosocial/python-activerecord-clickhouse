# src/rhosocial/activerecord/backend/impl/clickhouse/examples/named_migrations/expressions.py
"""
DDL named expression functions for ClickHouse migration examples.

Each function receives a *dialect* and returns a DDL expression object.
These are the building blocks used by NamedMigration up()/down() methods.

.. warning::

    Example from MySQL template. Contains MySQL-specific syntax
    (AUTO_INCREMENT, ON DUPLICATE KEY, transactions, etc.) not supported by
    ClickHouse. For illustration only; adjust for ClickHouse before use.
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
                "id",
                ClickHouseUInt32Type(),
                constraints=[
                    ColumnConstraint(
                        ColumnConstraintType.PRIMARY_KEY,
                    ),
                ],
            ),
            ColumnDefinition("name", ClickHouseStringType()),
            ColumnDefinition("email", ClickHouseStringType()),
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
                "id",
                ClickHouseUInt32Type(),
                constraints=[
                    ColumnConstraint(
                        ColumnConstraintType.PRIMARY_KEY,
                    ),
                ],
            ),
            ColumnDefinition("title", ClickHouseStringType()),
            ColumnDefinition("user_id", ClickHouseUInt32Type()),
        ],
    )


def drop_posts_table(dialect):
    """DROP TABLE IF EXISTS posts."""
    return DropTableExpression(dialect, table="posts", if_exists=True)


def create_custom_table(dialect, table_name: str = "custom_table"):
    """CREATE TABLE <table_name> (id UInt32 PRIMARY KEY, value String).

    This expression accepts an extra ``table_name`` parameter, allowing
    the migration to control the target table name at runtime.
    """
    return CreateTableExpression(
        dialect,
        table=table_name,
        columns=[
            ColumnDefinition(
                "id",
                ClickHouseUInt32Type(),
                constraints=[
                    ColumnConstraint(
                        ColumnConstraintType.PRIMARY_KEY,
                    ),
                ],
            ),
            ColumnDefinition("value", ClickHouseStringType()),
        ],
    )


def drop_custom_table(dialect, table_name: str = "custom_table"):
    """DROP TABLE IF EXISTS <table_name>."""
    return DropTableExpression(dialect, table=table_name, if_exists=True)
"""
DDL Test Script for ClickHouse Backend
Tests CreateTableExpression, DropTableExpression, AlterTableExpression, etc.
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../src'))

from typing import ClassVar
from rhosocial.activerecord.model import ActiveRecord
from rhosocial.activerecord.base import FieldProxy
from rhosocial.activerecord.backend.impl.clickhouse import ClickHouseBackend
from rhosocial.activerecord.backend.expression import (
    ColumnDefinition,
    CreateTableExpression,
    DropTableExpression,
    AlterTableExpression,
    AddColumn,
    DropColumn,
)
from rhosocial.activerecord.backend.expression.statements import (
    ColumnConstraint,
    ColumnConstraintType,
)


class User(ActiveRecord):
    """User Model for DDL test"""
    name: str
    email: str

    c: ClassVar[FieldProxy] = FieldProxy()

    @classmethod
    def table_name(cls) -> str:
        return "ddl_test_users"


def main():
    # Configure with ClickHouse backend
    from rhosocial.activerecord.backend.impl.clickhouse import ClickHouseConnectionConfig

    config = ClickHouseConnectionConfig(
        host=os.environ.get("CLICKHOUSE_HOST", "localhost"),
        port=int(os.environ.get("CLICKHOUSE_PORT", "3306")),
        database=os.environ.get("CLICKHOUSE_DATABASE", "test_db"),
        username=os.environ.get("CLICKHOUSE_USER", "root"),
        password=os.environ.get("CLICKHOUSE_PASSWORD", ""),
        charset="utf8mb4",
        autocommit=True,
        ssl_verify_cert=False,
    )
    User.configure(config, ClickHouseBackend)

    dialect = User.__backend__.dialect
    backend = User.__backend__
    introspector = backend.introspector

    print(f"Connected to ClickHouse: {dialect.get_server_version()}")
    print()

    # ============================================================
    # Test 1: Create Table
    # ============================================================
    print("=== Test 1: Create Table ===")
    columns = [
        ColumnDefinition(
            "id",
            "INTEGER",
            constraints=[ColumnConstraint(ColumnConstraintType.PRIMARY_KEY)]
        ),
        ColumnDefinition(
            "name",
            "VARCHAR(100)",
            constraints=[ColumnConstraint(ColumnConstraintType.NOT_NULL)]
        ),
        ColumnDefinition(
            "email",
            "VARCHAR(255)",
            constraints=[ColumnConstraint(ColumnConstraintType.NOT_NULL)]
        ),
    ]

    create = CreateTableExpression(
        dialect=dialect,
        table_name="ddl_test_users",
        columns=columns,
    )

    sql, params = create.to_sql()
    print(f"SQL: {sql}")
    print()

    sql_str, params_str = create.to_sql()
    backend.execute(sql_str, params_str)

    # Introspection
    tables = introspector.list_tables()
    print(f"Tables after create: {[t.name for t in tables]}")
    print()

    # ============================================================
    # Test 2: Create Table with IF NOT EXISTS
    # ============================================================
    print("=== Test 2: Create Table with IF NOT EXISTS ===")
    create2 = CreateTableExpression(
        dialect=dialect,
        table_name="ddl_test_users",
        columns=columns,
        if_not_exists=True,
    )

    sql, params = create2.to_sql()
    print(f"SQL: {sql}")
    print()

    sql_str, params_str = create2.to_sql()
    backend.execute(sql_str, params_str)
    print("Created with IF NOT EXISTS successfully")
    print()

    # ============================================================
    # Test 3: Alter Table - Add Column
    # ============================================================
    print("=== Test 3: Alter Table - Add Column ===")
    alter = AlterTableExpression(
        dialect,
        table_name="ddl_test_users",
        actions=[
            AddColumn(ColumnDefinition("phone", "VARCHAR(20)"))
        ]
    )

    sql, params = alter.to_sql()
    print(f"SQL: {sql}")
    print()

    sql_str, params_str = alter.to_sql()
    backend.execute(sql_str, params_str)

    # Verify column added
    table_info = introspector.get_table_info("ddl_test_users")
    if table_info and table_info.columns:
        print(f"Columns: {[c.name for c in table_info.columns]}")
    print()

    # ============================================================
    # Test 4: Alter Table - Drop Column
    # ============================================================
    print("=== Test 4: Alter Table - Drop Column ===")
    # First add a column to drop
    alter_add = AlterTableExpression(
        dialect,
        table_name="ddl_test_users",
        actions=[AddColumn(ColumnDefinition("temp_field", "TEXT"))]
    )
    sql_str, params_str = alter_add.to_sql()
    backend.execute(sql_str, params_str)

    alter_drop = AlterTableExpression(
        dialect,
        table_name="ddl_test_users",
        actions=[DropColumn("temp_field")]
    )

    sql, params = alter_drop.to_sql()
    print(f"SQL: {sql}")
    print()

    sql_str, params_str = alter_drop.to_sql()
    backend.execute(sql_str, params_str)

    table_info = introspector.get_table_info("ddl_test_users")
    if table_info and table_info.columns:
        print(f"Columns after drop: {[c.name for c in table_info.columns]}")
    print()

    # ============================================================
    # Test 5: Drop Table
    # ============================================================
    print("=== Test 5: Drop Table ===")
    drop = DropTableExpression(
        dialect,
        table_name="ddl_test_users",
        if_exists=True,
    )

    sql, params = drop.to_sql()
    print(f"SQL: {sql}")
    print()

    sql_str, params_str = drop.to_sql()
    backend.execute(sql_str, params_str)

    tables = introspector.list_tables()
    print(f"Tables after drop: {[t.name for t in tables]}")
    print()

    print("=== All ClickHouse DDL tests completed! ===")


if __name__ == "__main__":
    main()
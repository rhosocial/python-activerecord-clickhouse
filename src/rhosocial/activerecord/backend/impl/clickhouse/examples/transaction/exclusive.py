"""
ClickHouse isolation level awareness demonstration.

This example demonstrates:
1. ClickHouse does NOT support transaction isolation levels
2. All operations happen in auto-commit mode
3. The transaction_manager will raise UnsupportedFeatureError

For transaction isolation, use a database engine that supports ACID
transactions (e.g., PostgreSQL, MySQL with InnoDB).
"""

import os
from rhosocial.activerecord.backend.impl.clickhouse import ClickHouseBackend
from rhosocial.activerecord.backend.impl.clickhouse.config import ClickHouseConnectionConfig
from rhosocial.activerecord.backend.expression import (
    CreateTableExpression,
    DropTableExpression,
    InsertExpression,
    ValuesSource,
    QueryExpression,
    TableExpression,
)
from rhosocial.activerecord.backend.expression.core import Literal, Column
from rhosocial.activerecord.backend.expression.statements.dql import OrderByClause
from rhosocial.activerecord.backend.expression.statements import (
    ColumnDefinition,
    ColumnConstraint,
    ColumnConstraintType,
)
from rhosocial.activerecord.backend.options import ExecutionOptions
from rhosocial.activerecord.backend.schema import StatementType

config = ClickHouseConnectionConfig(
    host=os.getenv("CLICKHOUSE_HOST", "localhost"),
    port=int(os.getenv("CLICKHOUSE_PORT", 3306)),
    database=os.getenv("CLICKHOUSE_DATABASE", "test"),
    username=os.getenv("CLICKHOUSE_USER", "root"),
    password=os.getenv("CLICKHOUSE_PASSWORD", ""),
)
backend = ClickHouseBackend(connection_config=config)
backend.connect()
dialect = backend.dialect

dql_options = ExecutionOptions(stmt_type=StatementType.DQL)

drop_table = DropTableExpression(dialect=dialect, table_name="accounts", if_exists=True)
sql, params = drop_table.to_sql()
backend.execute(sql, params)

create_table = CreateTableExpression(
    dialect=dialect,
    table_name="accounts",
    columns=[
        ColumnDefinition(
            "id",
            "UInt32",
            constraints=[
                ColumnConstraint(ColumnConstraintType.PRIMARY_KEY),
                ColumnConstraint(ColumnConstraintType.NOT_NULL),
            ],
        ),
        ColumnDefinition(
            "name",
            "String",
            constraints=[
                ColumnConstraint(ColumnConstraintType.NOT_NULL),
            ],
        ),
        ColumnDefinition(
            "balance",
            "Decimal(10, 2)",
            constraints=[
                ColumnConstraint(ColumnConstraintType.DEFAULT, default_value=Literal(dialect, 0)),
            ],
        ),
    ],
    if_not_exists=True,
)
sql, params = create_table.to_sql()
backend.execute(sql, params)

insert_expr = InsertExpression(
    dialect=dialect,
    into="accounts",
    columns=["name", "balance"],
    source=ValuesSource(
        dialect,
        [
            [Literal(dialect, "Alice"), Literal(dialect, 1000)],
            [Literal(dialect, "Bob"), Literal(dialect, 500)],
        ],
    ),
)
sql, params = insert_expr.to_sql()
backend.execute(sql, params)

# ============================================================
# SECTION: Business Logic (the pattern to learn)
# ============================================================

print("ClickHouse does not support transaction isolation levels.")
print("All operations are auto-committed immediately.\n")

# Simple query - works in auto-commit mode
query = QueryExpression(
    dialect=dialect,
    select=[Column(dialect, "name"), Column(dialect, "balance")],
    from_=TableExpression(dialect, "accounts"),
    order_by=OrderByClause(dialect, [Column(dialect, "id")]),
)
sql, params = query.to_sql()
result = backend.execute(sql, params, options=dql_options)
print(f"Accounts: {result.data}")

# ============================================================
# SECTION: Isolation level attempt (will raise)
# ============================================================
print("\nAttempting transaction with isolation level...")
try:
    from rhosocial.activerecord.backend.transaction import IsolationLevel
    with backend.transaction_manager.transaction(isolation_level=IsolationLevel.REPEATABLE_READ):
        pass
    print("  (unexpected: succeeded)")
except Exception as e:
    print(f"  UnsupportedFeatureError: {e}")

# ============================================================
# SECTION: Teardown (necessary for execution, reference only)
# ============================================================
drop_table = DropTableExpression(dialect=dialect, table_name="accounts", if_exists=True)
sql, params = drop_table.to_sql()
backend.execute(sql, params)
backend.disconnect()

# ============================================================
# SECTION: Summary
# ============================================================
# Key points:
# 1. ClickHouse does NOT support transaction isolation levels
# 2. All operations are auto-committed immediately
# 3. backend.transaction_manager.transaction() raises UnsupportedFeatureError
# 4. For isolation levels, use a transactional database backend
"""
Transaction Isolation Levels - ClickHouse.

This example demonstrates:
1. READ COMMITTED isolation level
2. REPEATABLE READ isolation level (ClickHouse default)
3. SERIALIZABLE isolation level
4. How to set isolation level on a transaction
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
    UpdateExpression,
)
from rhosocial.activerecord.backend.expression.core import Literal, Column
from rhosocial.activerecord.backend.expression.statements.dql import OrderByClause
from rhosocial.activerecord.backend.expression.predicates import ComparisonPredicate
from rhosocial.activerecord.backend.expression.statements import (
    ColumnDefinition,
    ColumnConstraint,
    ColumnConstraintType,
)
from rhosocial.activerecord.backend.options import ExecutionOptions
from rhosocial.activerecord.backend.schema import StatementType
from rhosocial.activerecord.backend.transaction import IsolationLevel

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
dml_options = ExecutionOptions(stmt_type=StatementType.DML)

drop_table = DropTableExpression(dialect=dialect, table_name="accounts", if_exists=True)
sql, params = drop_table.to_sql()
backend.execute(sql, params)

create_table = CreateTableExpression(
    dialect=dialect,
    table_name="accounts",
    columns=[
        ColumnDefinition(
            "id",
            "INT",
            constraints=[
                ColumnConstraint(ColumnConstraintType.PRIMARY_KEY),
                ColumnConstraint(ColumnConstraintType.NOT_NULL, is_auto_increment=True),
            ],
        ),
        ColumnDefinition(
            "name",
            "VARCHAR(100)",
            constraints=[
                ColumnConstraint(ColumnConstraintType.NOT_NULL),
            ],
        ),
        ColumnDefinition(
            "balance",
            "DECIMAL(10,2)",
            constraints=[
                ColumnConstraint(ColumnConstraintType.DEFAULT, default_value=0),
            ],
        ),
    ],
    if_not_exists=True,
    dialect_options={"engine": "InnoDB"},
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

# 1. READ COMMITTED isolation level
# Prevents dirty reads: only committed data is visible.
# Non-repeatable reads and phantom reads can still occur.
print("--- READ COMMITTED ---")
with backend.transaction_manager.transaction(isolation_level=IsolationLevel.READ_COMMITTED):
    # Read Alice's balance
    query = QueryExpression(
        dialect=dialect,
        select=[Column(dialect, "name"), Column(dialect, "balance")],
        from_=TableExpression(dialect, "accounts"),
        where=ComparisonPredicate(dialect, "=", Column(dialect, "name"), Literal(dialect, "Alice")),
    )
    sql, params = query.to_sql()
    result = backend.execute(sql, params, options=dql_options)
    print(f"READ COMMITTED - Alice's balance: {result.data[0]['balance']}")

    # Update within the transaction
    update_expr = UpdateExpression(
        dialect=dialect,
        table="accounts",
        assignments={"balance": Literal(dialect, 1100)},
        where=ComparisonPredicate(dialect, "=", Column(dialect, "name"), Literal(dialect, "Alice")),
    )
    sql, params = update_expr.to_sql()
    backend.execute(sql, params, options=dml_options)

# After commit, the change is visible to all subsequent transactions
query = QueryExpression(
    dialect=dialect,
    select=[Column(dialect, "name"), Column(dialect, "balance")],
    from_=TableExpression(dialect, "accounts"),
    where=ComparisonPredicate(dialect, "=", Column(dialect, "name"), Literal(dialect, "Alice")),
)
sql, params = query.to_sql()
result = backend.execute(sql, params, options=dql_options)
print(f"After commit - Alice's balance: {result.data[0]['balance']}")

# 2. REPEATABLE READ isolation level (ClickHouse default)
# Prevents dirty reads and non-repeatable reads.
# Phantom reads are also prevented in ClickHouse due to next-key locking.
print("\n--- REPEATABLE READ (ClickHouse default) ---")
with backend.transaction_manager.transaction(isolation_level=IsolationLevel.REPEATABLE_READ):
    # First read
    query = QueryExpression(
        dialect=dialect,
        select=[Column(dialect, "name"), Column(dialect, "balance")],
        from_=TableExpression(dialect, "accounts"),
        where=ComparisonPredicate(dialect, "=", Column(dialect, "name"), Literal(dialect, "Alice")),
    )
    sql, params = query.to_sql()
    result = backend.execute(sql, params, options=dql_options)
    first_read = result.data[0]["balance"]

    # Second read in the same transaction returns the same result
    # even if another transaction committed changes in between
    sql, params = query.to_sql()
    result = backend.execute(sql, params, options=dql_options)
    second_read = result.data[0]["balance"]

    print(f"First read: {first_read}, Second read: {second_read}")
    print(f"Consistent reads: {first_read == second_read}")

# 3. SERIALIZABLE isolation level
# The strictest level: prevents dirty reads, non-repeatable reads,
# and phantom reads. Transactions appear to execute sequentially.
print("\n--- SERIALIZABLE ---")
with backend.transaction_manager.transaction(isolation_level=IsolationLevel.SERIALIZABLE):
    # Read all accounts
    query = QueryExpression(
        dialect=dialect,
        select=[Column(dialect, "name"), Column(dialect, "balance")],
        from_=TableExpression(dialect, "accounts"),
        order_by=OrderByClause(dialect, [Column(dialect, "id")]),
    )
    sql, params = query.to_sql()
    result = backend.execute(sql, params, options=dql_options)
    print(f"SERIALIZABLE - All accounts: {result.data}")

    # Update Bob's balance
    update_expr = UpdateExpression(
        dialect=dialect,
        table="accounts",
        assignments={"balance": Literal(dialect, 600)},
        where=ComparisonPredicate(dialect, "=", Column(dialect, "name"), Literal(dialect, "Bob")),
    )
    sql, params = update_expr.to_sql()
    backend.execute(sql, params, options=dml_options)

# 4. Setting isolation level per transaction
# The isolation_level parameter on transaction() sets the level
# for that specific transaction only, without affecting the
# default level of subsequent transactions.
print("\n--- Per-transaction isolation level ---")

# Transaction 1: SERIALIZABLE
with backend.transaction_manager.transaction(isolation_level=IsolationLevel.SERIALIZABLE):
    update_expr = UpdateExpression(
        dialect=dialect,
        table="accounts",
        assignments={"balance": Literal(dialect, 1200)},
        where=ComparisonPredicate(dialect, "=", Column(dialect, "name"), Literal(dialect, "Alice")),
    )
    sql, params = update_expr.to_sql()
    backend.execute(sql, params, options=dml_options)

# Transaction 2: defaults to REPEATABLE READ (ClickHouse default)
with backend.transaction():
    query = QueryExpression(
        dialect=dialect,
        select=[Column(dialect, "name"), Column(dialect, "balance")],
        from_=TableExpression(dialect, "accounts"),
        order_by=OrderByClause(dialect, [Column(dialect, "id")]),
    )
    sql, params = query.to_sql()
    result = backend.execute(sql, params, options=dql_options)
    print(f"Default isolation - All accounts: {result.data}")

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
# 1. Use isolation_level parameter in backend.transaction_manager.transaction() to set isolation
# 2. READ COMMITTED: prevents dirty reads, allows non-repeatable reads
# 3. REPEATABLE READ: ClickHouse default, prevents dirty and non-repeatable reads
# 4. SERIALIZABLE: strictest level, all transactions appear sequential
# 5. ClickHouse uses next-key locking in REPEATABLE READ to prevent phantom reads
# 6. Requires InnoDB engine for transaction isolation support

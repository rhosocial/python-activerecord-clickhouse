"""
ClickHouse transaction awareness demonstration.

This example demonstrates:
1. ClickHouse does NOT support ACID transactions (BEGIN/COMMIT/ROLLBACK)
2. INSERT and SELECT operations work as expected
3. The backend.transaction() context manager will raise UnsupportedFeatureError

For transactional workloads, use a database engine that supports transactions
(e.g., PostgreSQL, MySQL with InnoDB).
"""

# ============================================================
# SECTION: Setup (necessary for execution, reference only)
# ============================================================
import os
from rhosocial.activerecord.backend.impl.clickhouse import ClickHouseBackend
from rhosocial.activerecord.backend.impl.clickhouse.config import ClickHouseConnectionConfig

config = ClickHouseConnectionConfig(
    host=os.getenv("CLICKHOUSE_HOST", "localhost"),
    port=int(os.getenv("CLICKHOUSE_PORT", 8123)),
    database=os.getenv("CLICKHOUSE_DATABASE", "test"),
    username=os.getenv("CLICKHOUSE_USER", "root"),
    password=os.getenv("CLICKHOUSE_PASSWORD", ""),
)
backend = ClickHouseBackend(connection_config=config)
backend.connect()
dialect = backend.dialect

from rhosocial.activerecord.backend.expression import (  # noqa: E402
    CreateTableExpression,
    DropTableExpression,
    InsertExpression,
    ValuesSource,
    QueryExpression,
    TableExpression,
)
from rhosocial.activerecord.backend.expression.core import Literal, Column  # noqa: E402
from rhosocial.activerecord.backend.expression.statements import (  # noqa: E402
    ColumnDefinition,
    ColumnConstraint,
    ColumnConstraintType,
)
from rhosocial.activerecord.backend.options import ExecutionOptions  # noqa: E402
from rhosocial.activerecord.backend.schema import StatementType  # noqa: E402

# Drop table first for clean setup
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
            [Literal(dialect, "Alice"), Literal(dialect, 100)],
        ],
    ),
)
sql, params = insert_expr.to_sql()
backend.execute(sql, params)

dql_options = ExecutionOptions(stmt_type=StatementType.DQL)

# ============================================================
# SECTION: Plain INSERT/SELECT (no transaction)
# ============================================================
# ClickHouse does not support BEGIN/COMMIT/ROLLBACK.
# The backend.transaction() context manager will raise
# UnsupportedFeatureError if called.

print("ClickHouse does not support ACID transactions.")
print("Use plain INSERT/SELECT statements instead.")

# Insert another row
insert_expr2 = InsertExpression(
    dialect=dialect,
    into="accounts",
    columns=["name", "balance"],
    source=ValuesSource(
        dialect,
        [
            [Literal(dialect, "Bob"), Literal(dialect, 50)],
        ],
    ),
)
sql, params = insert_expr2.to_sql()
backend.execute(sql, params)

# Verify
query = QueryExpression(
    dialect=dialect,
    select=[Column(dialect, "name"), Column(dialect, "balance")],
    from_=TableExpression(dialect, "accounts"),
)
sql, params = query.to_sql()
result = backend.execute(sql, params, options=dql_options)
if result.data:
    print(f"Accounts: {result.data}")

# ============================================================
# SECTION: Transaction attempt (will raise)
# ============================================================
print("\nAttempting transaction context manager...")
try:
    with backend.transaction():
        pass
    print("  (unexpected: transaction succeeded)")
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
# 1. ClickHouse does NOT support ACID transactions
# 2. backend.transaction() raises UnsupportedFeatureError
# 3. Use plain INSERT/SELECT/UPDATE/DELETE without transactional wrappers
# 4. For transactional workloads, use a different database backend
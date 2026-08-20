"""
Basic transaction control using transaction manager.

This example demonstrates:
1. How to use the transaction context manager
2. How to handle transaction rollback on error
3. How to use savepoints for nested transactions
"""

# ============================================================
# SECTION: Setup (necessary for execution, reference only)
# ============================================================
import os
from rhosocial.activerecord.backend.impl.clickhouse import ClickHouseBackend
from rhosocial.activerecord.backend.impl.clickhouse.config import ClickHouseConnectionConfig

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

from rhosocial.activerecord.backend.expression import (  # noqa: E402
    CreateTableExpression,
    DropTableExpression,
    InsertExpression,
    ValuesSource,
    UpdateExpression,
    QueryExpression,
    TableExpression,
)
from rhosocial.activerecord.backend.expression.core import Literal, Column  # noqa: E402
from rhosocial.activerecord.backend.expression.predicates import ComparisonPredicate  # noqa: E402
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
dml_options = ExecutionOptions(stmt_type=StatementType.DML)

# ============================================================
# SECTION: Transaction Context Manager
# ============================================================
# The transaction() method returns a context manager
# that automatically handles COMMIT/ROLLBACK

# Simple transaction - auto commits on success
with backend.transaction():
    update_expr = UpdateExpression(
        dialect=dialect,
        table="accounts",
        assignments={"balance": Literal(dialect, 50)},
        where=ComparisonPredicate(dialect, "=", Column(dialect, "name"), Literal(dialect, "Alice")),
    )
    sql, params = update_expr.to_sql()
    backend.execute(sql, params, options=dml_options)

# Verify
query = QueryExpression(
    dialect=dialect,
    select=[Column(dialect, "balance")],
    from_=TableExpression(dialect, "accounts"),
    where=ComparisonPredicate(dialect, "=", Column(dialect, "name"), Literal(dialect, "Alice")),
)
sql, params = query.to_sql()
result = backend.execute(sql, params, options=dql_options)
if result.data:
    print(f"Balance after transaction: {result.data[0]['balance']}")

# ============================================================
# SECTION: Transaction with Rollback
# ============================================================
# If an exception is raised, the transaction is rolled back

try:
    with backend.transaction():
        update_expr = UpdateExpression(
            dialect=dialect,
            table="accounts",
            assignments={"balance": Literal(dialect, -100)},
            where=ComparisonPredicate(dialect, "=", Column(dialect, "name"), Literal(dialect, "Alice")),
        )
        sql, params = update_expr.to_sql()
        backend.execute(sql, params, options=dml_options)
        raise RuntimeError("Simulated error to trigger rollback")
except Exception as e:
    print(f"Transaction rolled back: {e}")

# ============================================================
# SECTION: Savepoints (Nested Transactions)
# ============================================================
# ClickHouse supports savepoints for nested transactions

with backend.transaction():
    update_expr = UpdateExpression(
        dialect=dialect,
        table="accounts",
        assignments={"balance": Literal(dialect, 40)},
        where=ComparisonPredicate(dialect, "=", Column(dialect, "name"), Literal(dialect, "Alice")),
    )
    sql, params = update_expr.to_sql()
    backend.execute(sql, params, options=dml_options)
    backend.transaction_manager.savepoint("sp1")

    try:
        update_expr2 = UpdateExpression(
            dialect=dialect,
            table="accounts",
            assignments={"balance": Literal(dialect, 20)},
            where=ComparisonPredicate(dialect, "=", Column(dialect, "name"), Literal(dialect, "Alice")),
        )
        sql, params = update_expr2.to_sql()
        backend.execute(sql, params, options=dml_options)
    except Exception:
        backend.transaction_manager.rollback_to("sp1")

# ============================================================
# SECTION: Teardown (necessary for execution, reference only)
# ============================================================
backend.disconnect()

# ============================================================
# SECTION: Summary
# ============================================================
# Key points:
# 1. Use backend.transaction() as a context manager
# 2. Exceptions automatically trigger rollback
# 3. Use savepoints for partial rollback
# 4. ClickHouse requires InnoDB engine for transactions

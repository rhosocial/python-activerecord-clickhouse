"""
DELETE using DeleteExpression - ClickHouse.

This example demonstrates:
1. Delete single row using DeleteExpression
2. Delete with WHERE condition
3. Delete all rows
"""

# ============================================================
# SECTION: Setup (necessary for execution, reference only)
# ============================================================
import os
from rhosocial.activerecord.backend.impl.clickhouse import ClickHouseBackend
from rhosocial.activerecord.backend.impl.clickhouse.config import ClickHouseConnectionConfig
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

from rhosocial.activerecord.backend.expression import (  # noqa: E402
    CreateTableExpression,
    InsertExpression,
    ValuesSource,
    DropTableExpression,
)
from rhosocial.activerecord.backend.expression.core import Literal, Column  # noqa: E402
from rhosocial.activerecord.backend.expression.statements import (  # noqa: E402
    ColumnDefinition,
    ColumnConstraint,
    ColumnConstraintType,
)

# Drop dependent tables first for clean setup
drop_orders = DropTableExpression(dialect=dialect, table_name="orders", if_exists=True)
sql, params = drop_orders.to_sql()
backend.execute(sql, params)

drop_table = DropTableExpression(dialect=dialect, table_name="users", if_exists=True)
sql, params = drop_table.to_sql()
backend.execute(sql, params)

create_table = CreateTableExpression(
    dialect=dialect,
    table_name="users",
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
    ],
    if_not_exists=True,
)
sql, params = create_table.to_sql()
print(f"Create table SQL: {sql}")
backend.execute(sql, params)

insert = InsertExpression(
    dialect=dialect,
    into="users",
    columns=["name"],
    source=ValuesSource(
        dialect,
        [
            [Literal(dialect, "Alice")],
            [Literal(dialect, "Bob")],
            [Literal(dialect, "Charlie")],
        ],
    ),
)
sql, params = insert.to_sql()
print(f"Insert SQL: {sql}")
backend.execute(sql, params)

# ============================================================
# SECTION: Delete Single Row
# ============================================================
from rhosocial.activerecord.backend.expression import DeleteExpression  # noqa: E402
from rhosocial.activerecord.backend.expression.predicates import ComparisonPredicate  # noqa: E402

delete_expr = DeleteExpression(
    dialect=dialect,
    table="users",
    where=ComparisonPredicate(dialect, "=", Column(dialect, "name"), Literal(dialect, "Alice")),
)
sql, params = delete_expr.to_sql()
print(f"Delete SQL: {sql}")
print(f"Params: {params}")

options = ExecutionOptions(stmt_type=StatementType.DML)
result = backend.execute(sql, params, options=options)
print(f"Deleted rows: {result.affected_rows}")

# ============================================================
# SECTION: Delete with Condition
# ============================================================
delete_expr = DeleteExpression(
    dialect=dialect,
    table="users",
    where=ComparisonPredicate(dialect, "=", Column(dialect, "name"), Literal(dialect, "Bob")),
)
sql, params = delete_expr.to_sql()
print(f"Delete SQL: {sql}")
result = backend.execute(sql, params, options=options)
print(f"Deleted rows: {result.affected_rows}")

# ============================================================
# SECTION: Delete All Rows
# ============================================================
delete_expr = DeleteExpression(dialect=dialect, table="users")
sql, params = delete_expr.to_sql()
print(f"Delete all SQL: {sql}")
result = backend.execute(sql, params, options=options)
print(f"Deleted rows: {result.affected_rows}")

# ============================================================
# SECTION: Teardown (necessary for execution, reference only)
# ============================================================
drop_orders = DropTableExpression(dialect=dialect, table_name="orders", if_exists=True)
sql, params = drop_orders.to_sql()
backend.execute(sql, params)

drop_expr = DropTableExpression(dialect=dialect, table_name="users", if_exists=True)
sql, params = drop_expr.to_sql()
backend.execute(sql, params)
backend.disconnect()

# ============================================================
# SECTION: Summary
# ============================================================
# Key points:
# 1. Use DeleteExpression to build DELETE query
# 2. Use ComparisonPredicate for WHERE conditions
# 3. Omit where parameter to delete all rows
# 4. affected_rows shows number of deleted rows

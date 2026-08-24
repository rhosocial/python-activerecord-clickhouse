"""
UPDATE using UpdateExpression - ClickHouse.

This example demonstrates:
1. Update single row
2. Update with WHERE condition
3. Update multiple rows

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
    InsertExpression,
    ValuesSource,
    DropTableExpression,
    UpdateExpression,
)
from rhosocial.activerecord.backend.expression.core import Literal, Column  # noqa: E402
from rhosocial.activerecord.backend.expression.predicates import ComparisonPredicate  # noqa: E402
from rhosocial.activerecord.backend.expression.operators import BinaryArithmeticExpression  # noqa: E402
from rhosocial.activerecord.backend.expression.statements import (  # noqa: E402
    ColumnDefinition,
    ColumnConstraint,
    ColumnConstraintType,
)

# Drop table first for clean setup
drop_table = DropTableExpression(dialect=dialect, table_name="users", if_exists=True)
sql, params = drop_table.to_sql()
backend.execute(sql, params)

create_table = CreateTableExpression(
    dialect=dialect,
    table_name="users",
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
        ColumnDefinition("age", "UInt32"),
    ],
    if_not_exists=True,
)
sql, params = create_table.to_sql()
print(f"Create table SQL: {sql}")
backend.execute(sql, params)

insert = InsertExpression(
    dialect=dialect,
    into="users",
    columns=["name", "age"],
    source=ValuesSource(
        dialect,
        [
            [Literal(dialect, "Alice"), Literal(dialect, 25)],
            [Literal(dialect, "Bob"), Literal(dialect, 30)],
        ],
    ),
)
sql, params = insert.to_sql()
print(f"Insert SQL: {sql}")
backend.execute(sql, params)

# ============================================================
# SECTION: Update Single Row
# ============================================================
update_expr = UpdateExpression(
    dialect=dialect,
    table="users",
    assignments={"age": Literal(dialect, 26)},
    where=ComparisonPredicate(dialect, "=", Column(dialect, "name"), Literal(dialect, "Alice")),
)
sql, params = update_expr.to_sql()
print(f"Update SQL: {sql}")
print(f"Params: {params}")

options = ExecutionOptions(stmt_type=StatementType.DML)
result = backend.execute(sql, params, options=options)
print(f"Updated rows: {result.affected_rows}")

# ============================================================
# SECTION: Update with Expression
# ============================================================
update_expr = UpdateExpression(
    dialect=dialect,
    table="users",
    assignments={
        "age": BinaryArithmeticExpression(dialect, "+", Column(dialect, "age"), Literal(dialect, 1)),
    },
    where=ComparisonPredicate(dialect, "=", Column(dialect, "name"), Literal(dialect, "Alice")),
)
sql, params = update_expr.to_sql()
print(f"Update with expression SQL: {sql}")
result = backend.execute(sql, params, options=options)
print(f"Updated rows: {result.affected_rows}")

# ============================================================
# SECTION: Update All Rows
# ============================================================
update_expr = UpdateExpression(
    dialect=dialect,
    table="users",
    assignments={"age": Literal(dialect, 99)},
)
sql, params = update_expr.to_sql()
print(f"Update all SQL: {sql}")
result = backend.execute(sql, params, options=options)
print(f"Updated rows: {result.affected_rows}")

# ============================================================
# SECTION: Teardown (necessary for execution, reference only)
# ============================================================
drop_expr = DropTableExpression(dialect=dialect, table_name="users", if_exists=True)
sql, params = drop_expr.to_sql()
backend.execute(sql, params)
backend.disconnect()

# ============================================================
# SECTION: Summary
# ============================================================
# Key points:
# 1. Use UpdateExpression with assignments dict for SET clause
# 2. Use BinaryArithmeticExpression for expressions like age + 1
# 3. Omit where parameter to update all rows
# 4. affected_rows shows number of updated rows

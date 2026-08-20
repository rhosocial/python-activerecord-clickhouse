"""
DROP TABLE using DropTableExpression - ClickHouse.

This example demonstrates:
1. DROP TABLE
2. DROP TABLE IF EXISTS

.. warning::

    Example from MySQL template. Contains MySQL-specific syntax
    (AUTO_INCREMENT, ON DUPLICATE KEY, transactions, etc.) not supported by
    ClickHouse. For illustration only; adjust for ClickHouse before use.
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
)
from rhosocial.activerecord.backend.expression.statements import (  # noqa: E402
    ColumnDefinition,
    ColumnConstraint,
    ColumnConstraintType,
)

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
            "UInt32",
            constraints=[
                ColumnConstraint(ColumnConstraintType.PRIMARY_KEY),
            ],
        ),
    ],
    if_not_exists=True,
)
sql, params = create_table.to_sql()
print(f"Create table SQL: {sql}")
backend.execute(sql, params)

# ============================================================
# SECTION: DROP TABLE
# ============================================================
drop_expr = DropTableExpression(
    dialect=dialect,
    table_name="users",
)
sql, params = drop_expr.to_sql()
print(f"DROP TABLE SQL: {sql}")
print(f"Params: {params}")
backend.execute(sql, params)

# ============================================================
# SECTION: DROP TABLE IF EXISTS
# ============================================================
drop_expr_if_exists = DropTableExpression(
    dialect=dialect,
    table_name="users",
    if_exists=True,
)
sql, params = drop_expr_if_exists.to_sql()
print(f"DROP TABLE IF EXISTS SQL: {sql}")
backend.execute(sql, params)

# ============================================================
# SECTION: Teardown
# ============================================================
backend.disconnect()

# ============================================================
# SECTION: Summary
# ============================================================
# Key points:
# 1. Use DropTableExpression to drop tables
# 2. if_exists=True prevents error if table doesn't exist
# 3. CASCADE and RESTRICT options available

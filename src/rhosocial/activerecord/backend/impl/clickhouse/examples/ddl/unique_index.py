"""
CREATE UNIQUE INDEX - ClickHouse.

This example demonstrates:
1. CREATE UNIQUE INDEX
2. CREATE INDEX with multiple columns

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

from rhosocial.activerecord.backend.expression import CreateTableExpression, DropTableExpression  # noqa: E402
from rhosocial.activerecord.backend.expression.statements import (  # noqa: E402
    ColumnDefinition,
    ColumnConstraint,
    ColumnConstraintType,
)

# Drop dependent tables first for clean setup
drop_orders = DropTableExpression(dialect=dialect, table="orders", if_exists=True)
sql, params = drop_orders.to_sql()
backend.execute(sql, params)

drop_table = DropTableExpression(dialect=dialect, table="users", if_exists=True)
sql, params = drop_table.to_sql()
backend.execute(sql, params)

create_table = CreateTableExpression(
    dialect=dialect,
    table="users",
    columns=[
        ColumnDefinition(
            "id",
            "UInt32",
            constraints=[
                ColumnConstraint(ColumnConstraintType.PRIMARY_KEY),
            ],
        ),
        ColumnDefinition("email", "String"),
        ColumnDefinition("name", "String"),
    ],
    if_not_exists=True,
)
sql, params = create_table.to_sql()
print(f"Create table SQL: {sql}")
backend.execute(sql, params)

# ============================================================
# SECTION: CREATE UNIQUE INDEX
# ============================================================
from rhosocial.activerecord.backend.expression import CreateIndexExpression, DropIndexExpression  # noqa: E402

# Drop index first if exists (ClickHouse does not support IF NOT EXISTS in CREATE INDEX)
try:
    drop_idx = DropIndexExpression(dialect=dialect, index="idx_users_email_unique")
    sql, params = drop_idx.to_sql()
    backend.execute(sql, params)
except Exception:
    pass

unique_idx = CreateIndexExpression(
    dialect=dialect,
    index="idx_users_email_unique",
    table="users",
    columns=["email"],
    unique=True,
)
sql, params = unique_idx.to_sql()
print(f"CREATE UNIQUE INDEX SQL: {sql}")
print(f"Params: {params}")
backend.execute(sql, params)

# ============================================================
# SECTION: CREATE INDEX with multiple columns
# ============================================================
# Drop composite index first if exists
try:
    drop_idx2 = DropIndexExpression(dialect=dialect, index="idx_users_name_email")
    sql, params = drop_idx2.to_sql()
    backend.execute(sql, params)
except Exception:
    pass

composite_idx = CreateIndexExpression(
    dialect=dialect,
    index="idx_users_name_email",
    table="users",
    columns=["name", "email"],
)
sql, params = composite_idx.to_sql()
print(f"CREATE INDEX multi-col SQL: {sql}")
backend.execute(sql, params)

# ============================================================
# SECTION: Teardown
# ============================================================
drop_orders = DropTableExpression(dialect=dialect, table="orders", if_exists=True)
sql, params = drop_orders.to_sql()
backend.execute(sql, params)

drop_table = DropTableExpression(dialect=dialect, table="users", if_exists=True)
sql, params = drop_table.to_sql()
backend.execute(sql, params)
backend.disconnect()

# ============================================================
# SECTION: Summary
# ============================================================
# Key points:
# 1. Use CreateIndexExpression with unique=True
# 2. Use columns=[col1, col2] for composite index
# 3. Use DropIndexExpression to drop

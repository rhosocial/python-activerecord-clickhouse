"""
Create a table with primary key, auto-increment, and ClickHouse-specific options.

This example demonstrates:
1. CREATE TABLE with various column types and constraints
2. ClickHouse UInt32 primary key
3. ClickHouse-specific ENGINE options
4. Inline index definitions
5. Default values and NOT NULL constraints

"""

# ============================================================
# SECTION: Setup (necessary for execution, reference only)
# ============================================================
import os
from rhosocial.activerecord.backend.impl.clickhouse import ClickHouseBackend
from rhosocial.activerecord.backend.impl.clickhouse.config import ClickHouseConnectionConfig
from rhosocial.activerecord.backend.expression import (
    DropTableExpression,
    CreateTableExpression,
)
from rhosocial.activerecord.backend.expression.functions.datetime import current_timestamp
from rhosocial.activerecord.backend.expression.statements import (
    ColumnDefinition,
    ColumnConstraint,
    ColumnConstraintType,
)
from rhosocial.activerecord.backend.expression.statements.ddl_table import (
    IndexDefinition,
)

config = ClickHouseConnectionConfig(
    host=os.getenv("CLICKHOUSE_HOST", "localhost"),
    port=int(os.getenv("CLICKHOUSE_PORT", "8123")),
    database=os.getenv("CLICKHOUSE_DATABASE", "test"),
    username=os.getenv("CLICKHOUSE_USER", "root"),
    password=os.getenv("CLICKHOUSE_PASSWORD", ""),
)
backend = ClickHouseBackend(connection_config=config)
backend.connect()
dialect = backend.dialect

# Drop if exists for clean setup
drop = DropTableExpression(dialect=dialect, table_name="products", if_exists=True)
sql, params = drop.to_sql()
backend.execute(sql, params)

# ============================================================
# SECTION: Business Logic (the pattern to learn)
# ============================================================

columns = [
    ColumnDefinition(
        name="id",
        data_type="UInt32",
        constraints=[
            ColumnConstraint(ColumnConstraintType.PRIMARY_KEY),
            ColumnConstraint(ColumnConstraintType.NOT_NULL),
        ],
    ),
    ColumnDefinition(
        name="name",
        data_type="String",
        constraints=[
            ColumnConstraint(ColumnConstraintType.NOT_NULL),
        ],
    ),
    ColumnDefinition(
        name="price",
        data_type="Decimal(10, 2)",
        constraints=[
            ColumnConstraint(ColumnConstraintType.NOT_NULL),
        ],
    ),
    ColumnDefinition(
        name="category",
        data_type="String",
    ),
    ColumnDefinition(
        name="is_active",
        data_type="UInt8",
        constraints=[
            ColumnConstraint(ColumnConstraintType.DEFAULT, default_value=1),
        ],
    ),
    ColumnDefinition(
        name="created_at",
        data_type="DateTime",
        constraints=[
            ColumnConstraint(ColumnConstraintType.DEFAULT, default_value=current_timestamp(dialect)),
        ],
    ),
]

indexes = [
    IndexDefinition(
        name="idx_products_category",
        columns=["category"],
    ),
]

# Create table with ClickHouse-specific ENGINE option
create_expr = CreateTableExpression(
    dialect=dialect,
    table_name="products",
    columns=columns,
    indexes=indexes,
    if_not_exists=True,
    dialect_options={
        "engine": "MergeTree()",
    },
)

sql, params = create_expr.to_sql()
print(f"SQL: {sql}")
print(f"Params: {params}")

# ============================================================
# SECTION: Execution (run the expression)
# ============================================================
result = backend.execute(sql, params)
print("Table created: products")

# Verify table structure using introspector
columns_info = backend.introspector.list_columns("products")
print("Columns in 'products':")
for col in columns_info:
    print(f"  {col}")

# ============================================================
# SECTION: Teardown (necessary for execution, reference only)
# ============================================================
drop_table = DropTableExpression(dialect=dialect, table_name="products", if_exists=True)
sql, params = drop_table.to_sql()
backend.execute(sql, params)
backend.disconnect()

# ============================================================
# SECTION: Summary
# ============================================================
# Key points:
# 1. Use ColumnDefinition with ClickHouse column types (UInt32, String, etc.)
# 2. ClickHouse dialect_options supports the 'engine' key (e.g. MergeTree())
# 3. IndexDefinition creates inline indexes within CREATE TABLE
# 4. Use current_timestamp(dialect) for SQL niladic functions (no parentheses)
# 5. Use introspector.get_columns() to verify table structure

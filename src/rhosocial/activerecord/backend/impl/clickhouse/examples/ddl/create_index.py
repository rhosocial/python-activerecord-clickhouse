"""
Create an index on an existing table.

"""

# ============================================================
# SECTION: Setup (necessary for execution, reference only)
# ============================================================
import os
from rhosocial.activerecord.backend.impl.clickhouse import ClickHouseBackend
from rhosocial.activerecord.backend.impl.clickhouse.config import ClickHouseConnectionConfig
from rhosocial.activerecord.backend.expression import CreateTableExpression, DropTableExpression
from rhosocial.activerecord.backend.expression.statements import (
    ColumnDefinition,
    ColumnConstraint,
    ColumnConstraintType,
)

config = ClickHouseConnectionConfig(
    host=os.getenv("CLICKHOUSE_HOST", "localhost"),
    port=int(os.getenv("CLICKHOUSE_PORT", "3306")),
    database=os.getenv("CLICKHOUSE_DATABASE", "test"),
    username=os.getenv("CLICKHOUSE_USER", "root"),
    password=os.getenv("CLICKHOUSE_PASSWORD", ""),
)
backend = ClickHouseBackend(connection_config=config)
backend.connect()
dialect = backend.dialect

# Drop table first for clean setup
drop = DropTableExpression(dialect=dialect, table_name="products", if_exists=True)
sql, params = drop.to_sql()
backend.execute(sql, params)

create_table = CreateTableExpression(
    dialect=dialect,
    table_name="products",
    columns=[
        ColumnDefinition(
            "id",
            "UInt32",
            constraints=[
                ColumnConstraint(ColumnConstraintType.PRIMARY_KEY),
                ColumnConstraint(ColumnConstraintType.NOT_NULL),
            ],
        ),
        ColumnDefinition("name", "String"),
        ColumnDefinition("category", "String"),
        ColumnDefinition("price", "Decimal(10, 2)"),
    ],
    if_not_exists=True,
)
sql, params = create_table.to_sql()
backend.execute(sql, params)

# ============================================================
# SECTION: Business Logic (the pattern to learn)
# ============================================================
from rhosocial.activerecord.backend.expression import CreateIndexExpression, DropIndexExpression  # noqa: E402

# Drop index first if exists (ClickHouse does not support IF NOT EXISTS in CREATE INDEX)
try:
    drop_idx = DropIndexExpression(dialect=dialect, index_name="idx_category_price")
    sql, params = drop_idx.to_sql()
    backend.execute(sql, params)
except Exception:
    pass

create_idx = CreateIndexExpression(
    dialect=dialect,
    index_name="idx_category_price",
    table_name="products",
    columns=["category", "price"],
)

sql, params = create_idx.to_sql()
print(f"SQL: {sql}")
print(f"Params: {params}")

# ============================================================
# SECTION: Execution (run the expression)
# ============================================================
backend.execute(sql, params)
print("Index created successfully")

# Verify using introspector
indexes = backend.introspector.list_indexes("products")
target_index = [idx for idx in indexes if "idx_category_price" in str(idx)]
print(f"Index info: {target_index}")

# ============================================================
# SECTION: Teardown (necessary for execution, reference only)
# ============================================================
backend.disconnect()

"""
Window functions using ORDER BY and LIMIT BY - ClickHouse.

ClickHouse does not support window functions in MySQL 5.7 style.
Instead, use ClickHouse-native features:
- ORDER BY with LIMIT BY for per-group top-N queries
- ClickHouse window functions (8.0+ support)

For ClickHouse 8.0+, see: query/window.py
"""

# ============================================================
# SECTION: Setup (necessary for execution, reference only)
# ============================================================
import os
from rhosocial.activerecord.backend.impl.clickhouse import ClickHouseBackend
from rhosocial.activerecord.backend.impl.clickhouse.config import ClickHouseConnectionConfig

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

from rhosocial.activerecord.backend.expression import (  # noqa: E402
    CreateTableExpression,
    InsertExpression,
    ValuesSource,
    DropTableExpression,
)
from rhosocial.activerecord.backend.expression.core import Literal  # noqa: E402
from rhosocial.activerecord.backend.expression.statements import (  # noqa: E402
    ColumnDefinition,
    ColumnConstraint,
    ColumnConstraintType,
)

drop_table = DropTableExpression(dialect=dialect, table_name="sales_data", if_exists=True)
sql, params = drop_table.to_sql()
backend.execute(sql, params)

create_table = CreateTableExpression(
    dialect=dialect,
    table_name="sales_data",
    columns=[
        ColumnDefinition(
            "id",
            "UInt32",
            constraints=[
                ColumnConstraint(ColumnConstraintType.PRIMARY_KEY),
                ColumnConstraint(ColumnConstraintType.NOT_NULL),
            ],
        ),
        ColumnDefinition("salesperson", "String"),
        ColumnDefinition("region", "String"),
        ColumnDefinition("amount", "Decimal(10, 2)"),
    ],
    if_not_exists=True,
)
sql, params = create_table.to_sql()
backend.execute(sql, params)

insert = InsertExpression(
    dialect=dialect,
    into="sales_data",
    columns=["salesperson", "region", "amount"],
    source=ValuesSource(
        dialect,
        [
            [Literal(dialect, "Alice"), Literal(dialect, "North"), Literal(dialect, 1000)],
            [Literal(dialect, "Alice"), Literal(dialect, "North"), Literal(dialect, 1500)],
            [Literal(dialect, "Bob"), Literal(dialect, "North"), Literal(dialect, 1200)],
            [Literal(dialect, "Bob"), Literal(dialect, "South"), Literal(dialect, 1800)],
            [Literal(dialect, "Charlie"), Literal(dialect, "South"), Literal(dialect, 2000)],
        ],
    ),
)
sql, params = insert.to_sql()
backend.execute(sql, params)

# ============================================================
# SECTION: Business Logic (the pattern to learn)
# ============================================================
# ClickHouse does not support MySQL user variables for window emulation.
# Use ORDER BY with LIMIT BY for per-group aggregation instead.

# Example: Get top sales by region using ORDER BY + LIMIT BY
sql = """
SELECT
    salesperson,
    region,
    amount
FROM sales_data
ORDER BY region, amount DESC
LIMIT 2 BY region
"""
params = ()

# ============================================================
# SECTION: Execution (run the expression)
# ============================================================
result = backend.execute(sql, params)
print(f"Rows returned: {len(result.data) if result.data else 0}")
for row in result.data or []:
    print(f"  {row}")

backend.disconnect()
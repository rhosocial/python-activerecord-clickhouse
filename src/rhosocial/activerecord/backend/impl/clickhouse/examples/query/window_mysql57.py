"""
Window functions using user variables - ClickHouse 5.7 and earlier fallback.

Note: This example provides window function alternatives for ClickHouse 5.6/5.7
which do not support built-in window functions introduced in ClickHouse 8.0.

Supported versions: ClickHouse 5.6, 5.7
Unsupported versions: ClickHouse 8.0+

For ClickHouse 8.0+, see: query/window.py

This example uses user variables to emulate:
- ROW_NUMBER() OVER (PARTITION BY region ORDER BY amount DESC)
- SUM(amount) OVER (PARTITION BY region)
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
    charset="utf8mb4",
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
            "INT",
            constraints=[
                ColumnConstraint(ColumnConstraintType.PRIMARY_KEY),
                ColumnConstraint(ColumnConstraintType.NOT_NULL, is_auto_increment=True),
            ],
        ),
        ColumnDefinition("salesperson", "VARCHAR(100)"),
        ColumnDefinition("region", "VARCHAR(50)"),
        ColumnDefinition("amount", "DECIMAL(10,2)"),
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
# Using user variables to emulate window functions in ClickHouse 5.6/5.7
# Row number with partition by region and order by amount DESC
sql = """
SELECT
    salesperson,
    region,
    amount,
    @row_num := IF(@current_region = region,
        @row_num + 1,
        1) AS row_num,
    @current_region := region
FROM sales_data,
    (SELECT @row_num := 0, @current_region := '') AS vars
ORDER BY region, amount DESC
"""
params = ()

# ============================================================
# SECTION: Execution (run the expression)
# ============================================================
result = backend.execute(sql, params)
print(f"Rows returned: {len(result.data) if result.data else 0}")
for row in result.data or []:
    print(f" {row}")

backend.disconnect()

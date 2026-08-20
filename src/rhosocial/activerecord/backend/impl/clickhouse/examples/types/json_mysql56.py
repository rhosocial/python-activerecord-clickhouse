"""
ClickHouse JSON operations using TEXT storage.

Note: ClickHouse 5.6 does not support JSON data type.
Use TEXT column and parse with string functions.

Supported versions: ClickHouse 5.6
Unsupported versions: ClickHouse 5.7+ (use json_basic.py instead)

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
    DropTableExpression,
    InsertExpression,
    ValuesSource,
)
from rhosocial.activerecord.backend.expression.core import Literal  # noqa: E402
from rhosocial.activerecord.backend.expression.statements import (  # noqa: E402
    ColumnDefinition,
    ColumnConstraint,
    ColumnConstraintType,
)

drop_table = DropTableExpression(dialect=dialect, table_name="documents", if_exists=True)
sql, params = drop_table.to_sql()
backend.execute(sql, params)

from rhosocial.activerecord.backend.expression import CreateTableExpression  # noqa: E402

create_table = CreateTableExpression(
    dialect=dialect,
    table_name="documents",
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
            "data",
            "String",
            constraints=[
                ColumnConstraint(ColumnConstraintType.NOT_NULL),
            ],
        ),
    ],
)
sql, params = create_table.to_sql()
backend.execute(sql, params)

insert_expr = InsertExpression(
    dialect=dialect,
    into="documents",
    columns=["data"],
    source=ValuesSource(
        dialect,
        [
            [Literal(dialect, '{"name": "Alice", "age": 30}')],
            [Literal(dialect, '{"name": "Bob", "age": 25}')],
        ],
    ),
)
sql, params = insert_expr.to_sql()
backend.execute(sql, params)

# ============================================================
# SECTION: Business Logic (the pattern to learn)
# ============================================================
# ClickHouse 5.6: Use TEXT column directly
# JSON parsing with string functions is error-prone, so we just show the raw data
sql = "SELECT id, data FROM documents"
params = ()

print(f"SQL: {sql}")
print(f"Params: {params}")

# ============================================================
# SECTION: Execution (run the expression)
# ============================================================
result = backend.execute(sql, params)
print(f"Rows returned: {len(result.data) if result.data else 0}")
for row in result.data or []:
    print(f" {row}")

backend.disconnect()

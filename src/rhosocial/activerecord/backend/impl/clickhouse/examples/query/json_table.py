"""
ClickHouse JSON_TABLE - Convert JSON data to relational format (ClickHouse 8.0+).

Demonstrates using ClickHouseJSONTableExpression with QueryExpression to build
a SELECT query that flattens JSON array data into relational rows.

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
    username=os.getenv("CLICKHOUSE_USERNAME", "root"),
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

drop_table = DropTableExpression(dialect=dialect, table_name="orders", if_exists=True)
sql, params = drop_table.to_sql()
backend.execute(sql, params)

create_table = CreateTableExpression(
    dialect=dialect,
    table_name="orders",
    columns=[
        ColumnDefinition(
            "id",
            "UInt32",
            constraints=[
                ColumnConstraint(ColumnConstraintType.PRIMARY_KEY),
                ColumnConstraint(ColumnConstraintType.NOT_NULL),
            ],
        ),
        ColumnDefinition("order_data", "JSON"),
    ],
    if_not_exists=True,
)
sql, params = create_table.to_sql()
backend.execute(sql, params)

insert = InsertExpression(
    dialect=dialect,
    into="orders",
    columns=["order_data"],
    source=ValuesSource(
        dialect,
        [
            [
                Literal(
                    dialect,
                    '{"customer": "Alice", "items": '
                    '[{"product": "Widget", "qty": 5, "price": 10.00}, '
                    '{"product": "Gadget", "qty": 3, "price": 15.00}]}',
                )
            ],
            [Literal(dialect, '{"customer": "Bob", "items": [{"product": "Widget", "qty": 2, "price": 10.00}]}')],
        ],
    ),
)
sql, params = insert.to_sql()
backend.execute(sql, params)

# ============================================================
# SECTION: Business Logic (the pattern to learn)
# ============================================================
from rhosocial.activerecord.backend.expression import (  # noqa: E402
    QueryExpression,
    TableExpression,
    Column,
)
from rhosocial.activerecord.backend.impl.clickhouse.expression.json_table import (  # noqa: E402
    ClickHouseJSONTableExpression,
    JSONTableColumn,
)

json_table = ClickHouseJSONTableExpression(
    dialect=dialect,
    json_doc="o.order_data",
    path="$.items[*]",
    columns=[
        JSONTableColumn(name="product", type="String", path="$.product"),
        JSONTableColumn(name="qty", type="UInt32", path="$.qty"),
        JSONTableColumn(name="price", type="Decimal(10, 2)", path="$.price"),
    ],
    alias="items",
)

json_table_sql, json_table_params = json_table.to_sql()
print(f"JSON_TABLE SQL: {json_table_sql}")

# Build the query using QueryExpression with a comma-separated FROM clause
# (equivalent to an implicit CROSS JOIN).
# Note: ClickHouseJSONTableExpression is not yet in the FromSourceType validation whitelist,
# so we temporarily disable strict validation when generating SQL.
query = QueryExpression(
    dialect=dialect,
    select=[
        Column(dialect, "id", table="o"),
        Column(dialect, "product", table="items"),
        Column(dialect, "qty", table="items"),
        Column(dialect, "price", table="items"),
    ],
    from_=[
        TableExpression(dialect, "orders", alias="o"),
        json_table,
    ],
)

# Temporarily disable strict validation to allow ClickHouseJSONTableExpression in FROM
original_strict = dialect.strict_validation
dialect.strict_validation = False
sql, params = query.to_sql()
dialect.strict_validation = original_strict
print(f"Query SQL: {sql}")

# ============================================================
# SECTION: Execution (run the expression)
# ============================================================
result = backend.execute(sql, params)
print(f"Rows returned: {len(result.data) if result.data else 0}")
for row in result.data or []:
    print(f" {row}")

# ============================================================
# SECTION: Teardown (necessary for execution, reference only)
# ============================================================
backend.disconnect()

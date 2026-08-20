"""
ClickHouse JSON functions - JSON_EXTRACT, JSON_UNQUOTE.

Supported versions: ClickHouse 5.7+
Unsupported versions: ClickHouse 5.6 (use json_clickhouse56.py instead)

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

drop_table = DropTableExpression(dialect=dialect, table_name="documents", if_exists=True)
sql, params = drop_table.to_sql()
backend.execute(sql, params)

# Create table with JSON column (ClickHouse 5.7+)
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
        ColumnDefinition("data", "JSON"),
    ],
    if_not_exists=True,
)
sql, params = create_table.to_sql()
backend.execute(sql, params)

insert = InsertExpression(
    dialect=dialect,
    into="documents",
    columns=["data"],
    source=ValuesSource(
        dialect,
        [
            [Literal(dialect, '{"name": "Alice", "age": 30, "tags": ["a", "b"]}')],
            [Literal(dialect, '{"name": "Bob", "age": 25, "tags": ["c"]}')],
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
from rhosocial.activerecord.backend.impl.clickhouse.functions.json import json_extract, json_unquote  # noqa: E402

query = QueryExpression(
    dialect=dialect,
    select=[
        Column(dialect, "id"),
        json_unquote(dialect, json_extract(dialect, Column(dialect, "data"), "$.name")).as_("name"),
        json_extract(dialect, Column(dialect, "data"), "$.age").as_("age"),
    ],
    from_=TableExpression(dialect, "documents"),
)

sql, params = query.to_sql()
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

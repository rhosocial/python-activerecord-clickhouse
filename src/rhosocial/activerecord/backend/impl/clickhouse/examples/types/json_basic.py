"""
ClickHouse JSON functions - JSONExtract, JSONExtractString.

Supported versions: ClickHouse supports JSON functions via the JSONExtract family.
ClickHouse has native JSON column type support (since recent versions).

This example demonstrates:
1. Creating a table with JSON column
2. Using JSONExtract to extract typed values
3. Using JSONExtractString to extract string values
"""

# ============================================================
# SECTION: Setup (necessary for execution, reference only)
# ============================================================
import os
from rhosocial.activerecord.backend.impl.clickhouse import ClickHouseBackend
from rhosocial.activerecord.backend.impl.clickhouse.config import ClickHouseConnectionConfig

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

from rhosocial.activerecord.backend.expression import (  # noqa: E402
    CreateTableExpression,
    InsertExpression,
    ValuesSource,
    DropTableExpression,
    QueryExpression,
    TableExpression,
    Column,
)
from rhosocial.activerecord.backend.expression.core import Literal, FunctionCall  # noqa: E402
from rhosocial.activerecord.backend.expression.statements import (  # noqa: E402
    ColumnDefinition,
    ColumnConstraint,
    ColumnConstraintType,
)
from rhosocial.activerecord.backend.options import ExecutionOptions  # noqa: E402
from rhosocial.activerecord.backend.schema import StatementType  # noqa: E402

dql_options = ExecutionOptions(stmt_type=StatementType.DQL)

drop_table = DropTableExpression(dialect=dialect, table="documents", if_exists=True)
sql, params = drop_table.to_sql()
backend.execute(sql, params)

# Create table with JSON column
create_table = CreateTableExpression(
    dialect=dialect,
    table="documents",
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

# Use JSONExtract functions (ClickHouse) instead of JSON_EXTRACT (MySQL)
query = QueryExpression(
    dialect=dialect,
    select=[
        Column(dialect, "id"),
        FunctionCall(
            dialect, "JSONExtractString", Column(dialect, "data"),
            Literal(dialect, "$.name"),
        ).as_("name"),
        FunctionCall(
            dialect, "JSONExtract", Column(dialect, "data"),
            Literal(dialect, "$.age"), Literal(dialect, "UInt32"),
        ).as_("age"),
    ],
    from_=TableExpression(dialect, "documents"),
)

sql, params = query.to_sql()
print(f"SQL: {sql}")
print(f"Params: {params}")

# ============================================================
# SECTION: Execution (run the expression)
# ============================================================
result = backend.execute(sql, params, options=dql_options)
print(f"Rows returned: {len(result.data) if result.data else 0}")
for row in result.data or []:
    print(f"  {row}")

backend.disconnect()
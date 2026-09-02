"""
DISTINCT using SelectModifier - ClickHouse.

This example demonstrates:
1. SELECT DISTINCT
2. SELECT DISTINCT with multiple columns

"""

# ============================================================
# SECTION: Setup (necessary for execution, reference only)
# ============================================================
import os
from rhosocial.activerecord.backend.impl.clickhouse import ClickHouseBackend
from rhosocial.activerecord.backend.impl.clickhouse.config import ClickHouseConnectionConfig
from rhosocial.activerecord.backend.options import ExecutionOptions
from rhosocial.activerecord.backend.schema import StatementType

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

from rhosocial.activerecord.backend.expression import (  # noqa: E402
    CreateTableExpression,
    InsertExpression,
    ValuesSource,
    DropTableExpression,
)
from rhosocial.activerecord.backend.expression.core import Literal, Column  # noqa: E402
from rhosocial.activerecord.backend.expression.statements import (  # noqa: E402
    ColumnDefinition,
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
        ColumnDefinition("id", "UInt32"),
        ColumnDefinition("name", "String"),
    ],
    if_not_exists=True,
)
sql, params = create_table.to_sql()
print(f"Create table SQL: {sql}")
backend.execute(sql, params)

insert = InsertExpression(
    dialect=dialect,
    into="users",
    columns=["id", "name"],
    source=ValuesSource(
        dialect,
        [
            [Literal(dialect, 1), Literal(dialect, "Alice")],
            [Literal(dialect, 2), Literal(dialect, "Bob")],
            [Literal(dialect, 3), Literal(dialect, "Alice")],
        ],
    ),
)
sql, params = insert.to_sql()
print(f"Insert SQL: {sql}")
backend.execute(sql, params)

# ============================================================
# SECTION: SELECT DISTINCT
# ============================================================
from rhosocial.activerecord.backend.expression import (  # noqa: E402
    QueryExpression,
    TableExpression,
    SelectModifier,
)

query = QueryExpression(
    dialect=dialect,
    select=[Column(dialect, "name")],
    from_=TableExpression(dialect, "users"),
    select_modifier=SelectModifier.DISTINCT,
)
sql, params = query.to_sql()
print(f"SELECT DISTINCT SQL: {sql}")
print(f"Params: {params}")

options = ExecutionOptions(stmt_type=StatementType.DQL)
result = backend.execute(sql, params, options=options)
print(f"DISTINCT result: {result.data}")

# ============================================================
# SECTION: SELECT DISTINCT with multiple columns
# ============================================================
query_distinct = QueryExpression(
    dialect=dialect,
    select=[Column(dialect, "id"), Column(dialect, "name")],
    from_=TableExpression(dialect, "users"),
    select_modifier=SelectModifier.DISTINCT,
)
sql, params = query_distinct.to_sql()
print(f"SELECT DISTINCT multi-col SQL: {sql}")
result = backend.execute(sql, params, options=options)
print(f"Multi-col result: {result.data}")

# ============================================================
# SECTION: Teardown (necessary for execution, reference only)
# ============================================================
drop_orders = DropTableExpression(dialect=dialect, table="orders", if_exists=True)
sql, params = drop_orders.to_sql()
backend.execute(sql, params)

drop_expr = DropTableExpression(dialect=dialect, table="users", if_exists=True)
sql, params = drop_expr.to_sql()
backend.execute(sql, params)
backend.disconnect()

# ============================================================
# SECTION: Summary
# ============================================================
# Key points:
# 1. Use SelectModifier.DISTINCT in QueryExpression
# 2. SELECT DISTINCT removes duplicate rows
# 3. Works with multiple columns (distinct combo)

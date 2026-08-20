"""
Pagination using LIMIT/OFFSET - ClickHouse.

This example demonstrates:
1. LIMIT clause
2. OFFSET for pagination
3. LIMIT with OFFSET

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
from rhosocial.activerecord.backend.options import ExecutionOptions
from rhosocial.activerecord.backend.schema import StatementType

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
    CreateTableExpression,
    InsertExpression,
    ValuesSource,
    DropTableExpression,
)
from rhosocial.activerecord.backend.expression.core import Literal, Column  # noqa: E402
from rhosocial.activerecord.backend.expression.statements import (  # noqa: E402
    ColumnDefinition,
)

# Drop table first for clean setup
drop_table = DropTableExpression(dialect=dialect, table_name="users", if_exists=True)
sql, params = drop_table.to_sql()
backend.execute(sql, params)

create_table = CreateTableExpression(
    dialect=dialect,
    table_name="users",
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
            [Literal(dialect, 3), Literal(dialect, "Charlie")],
            [Literal(dialect, 4), Literal(dialect, "David")],
            [Literal(dialect, 5), Literal(dialect, "Eve")],
        ],
    ),
)
sql, params = insert.to_sql()
print(f"Insert SQL: {sql}")
backend.execute(sql, params)

# ============================================================
# SECTION: LIMIT (get first N rows)
# ============================================================
from rhosocial.activerecord.backend.expression import (  # noqa: E402
    QueryExpression,
    TableExpression,
    LimitOffsetClause,
)

query = QueryExpression(
    dialect=dialect,
    select=[Column(dialect, "id"), Column(dialect, "name")],
    from_=TableExpression(dialect, "users"),
    limit_offset=LimitOffsetClause(dialect, limit=3),
)
sql, params = query.to_sql()
print(f"LIMIT SQL: {sql}")
print(f"Params: {params}")

options = ExecutionOptions(stmt_type=StatementType.DQL)
result = backend.execute(sql, params, options=options)
print(f"LIMIT result: {result.data}")

# ============================================================
# SECTION: OFFSET (skip first N rows)
# ============================================================
query_offset = QueryExpression(
    dialect=dialect,
    select=[Column(dialect, "id"), Column(dialect, "name")],
    from_=TableExpression(dialect, "users"),
    limit_offset=LimitOffsetClause(dialect, limit=2, offset=2),
)
sql, params = query_offset.to_sql()
print(f"LIMIT OFFSET SQL: {sql}")
result = backend.execute(sql, params, options=options)
print(f"Pagination result: {result.data}")

# ============================================================
# SECTION: Teardown
# ============================================================
drop_expr = DropTableExpression(dialect=dialect, table_name="users", if_exists=True)
sql, params = drop_expr.to_sql()
backend.execute(sql, params)
backend.disconnect()

# ============================================================
# SECTION: Summary
# ============================================================
# Key points:
# 1. Use LimitOffsetClause with limit=N
# 2. Use offset=M to skip first M rows
# 3. For pagination: page=1 -> offset=0, page=2 -> offset=10

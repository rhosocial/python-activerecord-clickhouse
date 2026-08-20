"""
Query runtime functions and statement-level constants without a data source.

This example demonstrates:
1. SELECT CURRENT_TIMESTAMP, NOW(), etc. without FROM clause
2. How to use factory functions for SQL niladic functions in SELECT list
3. Various ClickHouse date/time functions as standalone queries
4. Expression API for constant expressions

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
    port=int(os.getenv("CLICKHOUSE_PORT", "3306")),
    database=os.getenv("CLICKHOUSE_DATABASE", "test"),
    username=os.getenv("CLICKHOUSE_USER", "root"),
    password=os.getenv("CLICKHOUSE_PASSWORD", ""),
)
backend = ClickHouseBackend(connection_config=config)
backend.connect()
dialect = backend.dialect

dql_options = ExecutionOptions(stmt_type=StatementType.DQL)

# ============================================================
# SECTION: SELECT CURRENT_TIMESTAMP
# ============================================================
# Use factory functions for SQL statement-level constants.
# current_timestamp(dialect) generates CURRENT_TIMESTAMP (no parentheses)
# which is the SQL:2003 standard niladic form, valid in both DDL DEFAULT
# and SELECT contexts. ClickHouse also accepts CURRENT_TIMESTAMP() with parentheses.

from rhosocial.activerecord.backend.expression import QueryExpression  # noqa: E402
from rhosocial.activerecord.backend.expression.core import FunctionCall  # noqa: E402
from rhosocial.activerecord.backend.expression.functions.datetime import (  # noqa: E402
    current_timestamp,
    now,
    current_date,
    current_time,
)

query_ts = QueryExpression(
    dialect=dialect,
    select=[current_timestamp(dialect)],
)
sql, params = query_ts.to_sql()
print(f"CURRENT_TIMESTAMP SQL: {sql}")
result = backend.execute(sql, params, options=dql_options)
print(f"Result: {result.data}")

# ============================================================
# SECTION: SELECT NOW()
# ============================================================
query_now = QueryExpression(
    dialect=dialect,
    select=[now(dialect)],
)
sql, params = query_now.to_sql()
print(f"NOW() SQL: {sql}")
result = backend.execute(sql, params, options=dql_options)
print(f"Result: {result.data}")

# ============================================================
# SECTION: SELECT CURRENT_DATE, CURRENT_TIME
# ============================================================
query_date = QueryExpression(
    dialect=dialect,
    select=[
        current_date(dialect),
        current_time(dialect),
    ],
)
sql, params = query_date.to_sql()
print(f"CURRENT_DATE/CURRENT_TIME SQL: {sql}")
result = backend.execute(sql, params, options=dql_options)
print(f"Result: {result.data}")

# ============================================================
# SECTION: SELECT with multiple functions
# ============================================================
from rhosocial.activerecord.backend.expression.core import Literal  # noqa: E402

query_multi = QueryExpression(
    dialect=dialect,
    select=[
        now(dialect).as_("current_time"),
        current_date(dialect).as_("current_date"),
        FunctionCall(dialect, "DATABASE").as_("db_name"),
        FunctionCall(dialect, "VERSION").as_("db_version"),
    ],
)
sql, params = query_multi.to_sql()
print(f"Multi-function SQL: {sql}")
result = backend.execute(sql, params, options=dql_options)
print(f"Result: {result.data}")

# ============================================================
# SECTION: SELECT with function arguments
# ============================================================
# FunctionCall supports arguments, e.g., DATE_FORMAT, ROUND

query_format = QueryExpression(
    dialect=dialect,
    select=[
        FunctionCall(dialect, "DATE_FORMAT", now(dialect), Literal(dialect, "%Y-%m-%d")).as_("formatted_date"),
    ],
)
sql, params = query_format.to_sql()
print(f"DATE_FORMAT SQL: {sql}")
result = backend.execute(sql, params, options=dql_options)
print(f"Result: {result.data}")

# ============================================================
# SECTION: SELECT with UUID() (ClickHouse 8.0+)
# ============================================================
query_uuid = QueryExpression(
    dialect=dialect,
    select=[FunctionCall(dialect, "UUID").as_("uuid_value")],
)
sql, params = query_uuid.to_sql()
print(f"UUID() SQL: {sql}")
result = backend.execute(sql, params, options=dql_options)
print(f"Result: {result.data}")

# ============================================================
# SECTION: Teardown (necessary for execution, reference only)
# ============================================================
backend.disconnect()

# ============================================================
# SECTION: Summary
# ============================================================
# Key points:
# 1. Use factory functions (current_timestamp, now, current_date, etc.) for SQL niladic functions
# 2. QueryExpression without from_ clause generates "SELECT ..." without FROM
# 3. Use FunctionCall(dialect, 'FUNC', arg1, arg2) for regular functions with arguments
# 4. Use .as_('alias') for column aliases in SELECT
# 5. SQL:2003 niladic functions (CURRENT_TIMESTAMP, CURRENT_DATE, etc.) omit parentheses
# 6. Common ClickHouse info functions: DATABASE, VERSION, USER, UUID

"""
ClickHouse Full-Text Search example - tokenbf_v1 skip index + hasToken.

ClickHouse does not support MySQL-style FULLTEXT indexes or MATCH...AGAINST.
Instead, use tokenbf_v1 skip indexes with the hasToken() function.

This example demonstrates:
1. Creating a tokenbf_v1 skip index for full-text search
2. Using hasToken() function for token-based search
3. Using hasTokenCaseInsensitive() for case-insensitive search
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
    username=os.getenv("CLICKHOUSE_USER", "test"),
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
    WhereClause,
)
from rhosocial.activerecord.backend.expression.core import Literal, FunctionCall  # noqa: E402
from rhosocial.activerecord.backend.expression.statements import (  # noqa: E402
    ColumnDefinition,
    ColumnConstraint,
    ColumnConstraintType,
)
from rhosocial.activerecord.backend.expression.predicates import ComparisonPredicate  # noqa: E402
from rhosocial.activerecord.backend.options import ExecutionOptions  # noqa: E402
from rhosocial.activerecord.backend.schema import StatementType  # noqa: E402

dql_options = ExecutionOptions(stmt_type=StatementType.DQL)

drop_table = DropTableExpression(dialect=dialect, table_name="articles", if_exists=True)
sql, params = drop_table.to_sql()
backend.execute(sql, params)

# Create table with a tokenbf_v1 skip index for full-text search
create_table = CreateTableExpression(
    dialect=dialect,
    table_name="articles",
    columns=[
        ColumnDefinition(
            "id",
            "UInt32",
            constraints=[
                ColumnConstraint(ColumnConstraintType.PRIMARY_KEY),
                ColumnConstraint(ColumnConstraintType.NOT_NULL),
            ],
        ),
        ColumnDefinition("title", "String"),
        ColumnDefinition("content", "String"),
    ],
    dialect_options={
        "engine": "MergeTree()",
        "order_by": "id",
    },
    if_not_exists=True,
)
sql, params = create_table.to_sql()
backend.execute(sql, params)

# Create a tokenbf_v1 skip index on the content column
index_sql = "ALTER TABLE articles ADD INDEX idx_content_tokenbf content TYPE tokenbf_v1(3072, 2, 0) GRANULARITY 1"
backend.execute(index_sql)
print(f"Skip index created: {index_sql}")

insert = InsertExpression(
    dialect=dialect,
    into="articles",
    columns=["title", "content"],
    source=ValuesSource(
        dialect,
        [
            [
                Literal(dialect, "ClickHouse Tutorial"),
                Literal(dialect, "This tutorial covers ClickHouse database basics and advanced features."),
            ],
            [
                Literal(dialect, "PostgreSQL Guide"),
                Literal(dialect, "Learn PostgreSQL from beginner to advanced level."),
            ],
            [
                Literal(dialect, "Database Design"),
                Literal(dialect, "Best practices for designing relational databases including ClickHouse and PostgreSQL."),
            ],
        ],
    ),
)
sql, params = insert.to_sql()
backend.execute(sql, params)

# ============================================================
# SECTION: Business Logic (the pattern to learn)
# ============================================================

# Use hasToken() for token-based full-text search
query = QueryExpression(
    dialect=dialect,
    select=[
        Column(dialect, "id"),
        Column(dialect, "title"),
        Column(dialect, "content"),
    ],
    from_=TableExpression(dialect, "articles"),
    where=WhereClause(
        dialect,
        condition=ComparisonPredicate(
            dialect,
            "=",
            FunctionCall(dialect, "hasToken", Column(dialect, "content"), Literal(dialect, "ClickHouse")),
            Literal(dialect, 1),
        ),
    ),
)

sql, params = query.to_sql()
print(f"hasToken SQL: {sql}")
print(f"Params: {params}")

# ============================================================
# SECTION: Execution (run the expression)
# ============================================================
result = backend.execute(sql, params, options=dql_options)
print(f"Rows returned: {len(result.data) if result.data else 0}")
for row in result.data or []:
    print(f"  {row}")

# ============================================================
# SECTION: Teardown (necessary for execution, reference only)
# ============================================================
backend.disconnect()
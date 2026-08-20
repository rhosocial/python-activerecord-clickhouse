"""
ClickHouse-specific full-text search using MATCH...AGAINST.
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

drop_table = DropTableExpression(dialect=dialect, table_name="articles", if_exists=True)
sql, params = drop_table.to_sql()
backend.execute(sql, params)

create_table = CreateTableExpression(
    dialect=dialect,
    table_name="articles",
    columns=[
        ColumnDefinition(
            "id",
            "INT",
            constraints=[
                ColumnConstraint(ColumnConstraintType.PRIMARY_KEY),
                ColumnConstraint(ColumnConstraintType.NOT_NULL, is_auto_increment=True),
            ],
        ),
        ColumnDefinition("title", "VARCHAR(200)"),
        ColumnDefinition("content", "TEXT"),
    ],
    if_not_exists=True,
)
sql, params = create_table.to_sql()
backend.execute(sql, params)

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

sql = "CREATE FULLTEXT INDEX ft_idx ON articles (title, content)"
backend.execute(sql)

# ============================================================
# SECTION: Business Logic (the pattern to learn)
# ============================================================
from rhosocial.activerecord.backend.expression import QueryExpression, Column, TableExpression  # noqa: E402
from rhosocial.activerecord.backend.impl.clickhouse.expression import ClickHouseMatchAgainstExpression, MatchAgainstMode  # noqa: E402

# Use ClickHouseMatchAgainstExpression for full-text search
match_expr = ClickHouseMatchAgainstExpression(
    dialect=dialect,
    columns=["title", "content"],
    search_string="ClickHouse",
    mode=MatchAgainstMode.NATURAL_LANGUAGE,
)

# Create separate instances - one for SELECT with alias, one for WHERE without alias
match_with_alias = ClickHouseMatchAgainstExpression(
    dialect=dialect,
    columns=["title", "content"],
    search_string="ClickHouse",
    mode=MatchAgainstMode.NATURAL_LANGUAGE,
)
match_with_alias = match_with_alias.as_("relevance")

match_for_where = ClickHouseMatchAgainstExpression(
    dialect=dialect,
    columns=["title", "content"],
    search_string="ClickHouse",
    mode=MatchAgainstMode.NATURAL_LANGUAGE,
)

# Build query using expression (supports alias via as_)
query = QueryExpression(
    dialect=dialect,
    select=[
        Column(dialect, "id"),
        Column(dialect, "title"),
        match_with_alias,
    ],
    from_=TableExpression(dialect, "articles"),
    where=(match_for_where > 0),
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

# ============================================================
# SECTION: Teardown (necessary for execution, reference only)
# ============================================================
backend.disconnect()

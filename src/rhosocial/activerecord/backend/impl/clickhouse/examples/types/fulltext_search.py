"""
ClickHouse Full-Text Search example - MATCH...AGAINST.

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
    username=os.getenv("CLICKHOUSE_USER", "test"),
    password=os.getenv("CLICKHOUSE_PASSWORD", ""),
)
backend = ClickHouseBackend(connection_config=config)
dialect = backend.dialect

# ============================================================
# SECTION: Business Logic (the pattern to learn)
# ============================================================
from rhosocial.activerecord.backend.impl.clickhouse.expression import ClickHouseMatchAgainstExpression, MatchAgainstMode  # noqa: E402
from rhosocial.activerecord.backend.expression.core import TableExpression  # noqa: E402

# Create a full-text search expression
# ClickHouse 5.6+ supports FULLTEXT indexes on InnoDB
articles = TableExpression(dialect, "articles")

# Natural language search (default)
match_expr = ClickHouseMatchAgainstExpression(
    dialect=dialect,
    columns=["title", "content"],
    search_string="database",
    mode=MatchAgainstMode.NATURAL_LANGUAGE,
)

sql, params = match_expr.to_sql()
print(f"Natural Language: {sql}")
print(f"Params: {params}")

# Boolean mode (allows wildcards, operators)
match_boolean = ClickHouseMatchAgainstExpression(
    dialect=dialect,
    columns=["title", "content"],
    search_string="+clickhouse -oracle",
    mode=MatchAgainstMode.BOOLEAN,
)

sql, params = match_boolean.to_sql()
print(f"Boolean: {sql}")

# With query expansion
match_expanded = ClickHouseMatchAgainstExpression(
    dialect=dialect,
    columns=["title", "content"],
    search_string="database",
    mode=MatchAgainstMode.NATURAL_LANGUAGE_WITH_QUERY_EXPANSION,
)

sql, params = match_expanded.to_sql()
print(f"With Query Expansion: {sql}")

# ============================================================
# SECTION: Output (reference)
# ============================================================
# Expected outputs:
# NATURAL LANGUAGE: MATCH(title, content) AGAINST(%s IN NATURAL LANGUAGE MODE)
# BOOLEAN: MATCH(title, content) AGAINST(%s IN BOOLEAN MODE)
# WITH QUERY EXPANSION: MATCH(title, content) AGAINST(%s IN NATURAL LANGUAGE MODE WITH QUERY EXPANSION)

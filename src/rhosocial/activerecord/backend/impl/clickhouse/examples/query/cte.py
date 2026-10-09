"""
Common Table Expressions (CTE) in ClickHouse.

ClickHouse supports ``WITH <identifier> AS [MATERIALIZED] <subquery expression>``,
and both plain and ``WITH RECURSIVE`` forms were measured working on 26.7.3.19
(``WITH cte AS (SELECT 1 AS x) SELECT * FROM cte`` → one row;
``WITH RECURSIVE t AS (SELECT 1 AS n UNION ALL SELECT n+1 FROM t WHERE n<3)
SELECT sum(n) FROM t`` → 6).

There is no version floor to state for the plain form — the ``WITH`` reference
page
(``https://clickhouse.com/docs/reference/statements/select/with``) documents it
with no version qualifier. The one version that matters here is for
**recursive** CTEs, and it comes from that same page: they rely on the query
analyzer, "introduced in version **24.3**, which is the default since that
version and mandatory since **26.9**"; on an older instance with the analyzer
disabled a recursive CTE raises ``(UNKNOWN_TABLE)`` or
``(UNSUPPORTED_METHOD)``. The ``MATERIALIZED`` keyword is a separate,
experimental feature that additionally needs the ``enable_materialized_cte``
setting.

This example demonstrates:
1. Basic CTE with WITH clause
2. Recursive CTE for hierarchical data
3. CTE for simplifying complex queries

"""

# ============================================================
# SECTION: Setup (necessary for execution, reference only)
# ============================================================
from rhosocial.activerecord.backend.expression.objects import Table
from rhosocial.activerecord.backend.expression.sources import NamedRelationRef
import os
from rhosocial.activerecord.backend.impl.clickhouse.backend import ClickHouseBackend
from rhosocial.activerecord.backend.impl.clickhouse.config import ClickHouseConnectionConfig

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
    QueryExpression,
    CTEExpression,
    WithQueryExpression,
)
from rhosocial.activerecord.backend.expression.core import Literal, Column  # noqa: E402
from rhosocial.activerecord.backend.expression.predicates import ComparisonPredicate  # noqa: E402
from rhosocial.activerecord.backend.expression.statements import (  # noqa: E402
    ColumnDefinition,
    ColumnConstraint,
    ColumnConstraintType,
)
from rhosocial.activerecord.backend.options import ExecutionOptions  # noqa: E402
from rhosocial.activerecord.backend.schema import StatementType  # noqa: E402

dql_options = ExecutionOptions(stmt_type=StatementType.DQL)

# Drop table first for clean setup
drop = DropTableExpression(dialect=dialect, table=Table(dialect, "employees"), if_exists=True)
sql, params = drop.to_sql()
backend.execute(sql, params)

create_table = CreateTableExpression(
    dialect=dialect,
    table=Table(dialect, "employees"),
    columns=[
        ColumnDefinition(
            "id",
            "UInt32",
            constraints=[
                ColumnConstraint(ColumnConstraintType.PRIMARY_KEY),
            ],
        ),
        ColumnDefinition("name", "String"),
        ColumnDefinition("manager_id", "UInt32"),
    ],
    if_not_exists=True,
)
sql, params = create_table.to_sql()
backend.execute(sql, params)

delete_sql = "DELETE FROM employees"
backend.execute(delete_sql)

insert_expr = InsertExpression(
    dialect=dialect,
    into=Table(dialect, "employees"),
    columns=["id", "name", "manager_id"],
    source=ValuesSource(
        dialect,
        [
            [Literal(dialect, 1), Literal(dialect, "CEO"), Literal(dialect, None)],
            [Literal(dialect, 2), Literal(dialect, "VP Sales"), Literal(dialect, 1)],
            [Literal(dialect, 3), Literal(dialect, "VP Engineering"), Literal(dialect, 1)],
            [Literal(dialect, 4), Literal(dialect, "Sales Manager"), Literal(dialect, 2)],
            [Literal(dialect, 5), Literal(dialect, "Engineer"), Literal(dialect, 3)],
        ],
    ),
)
sql, params = insert_expr.to_sql()
backend.execute(sql, params)

# ============================================================
# SECTION: Basic CTE
# ============================================================
# CTE simplifies complex queries by defining temporary named result sets

high_earners_cte = CTEExpression(
    dialect=dialect,
    name="high_earners",
    query=QueryExpression(
        dialect=dialect,
        select=[Column(dialect, "id"), Column(dialect, "name")],
        from_=NamedRelationRef(dialect, Table(dialect, "employees")),
        where=ComparisonPredicate(dialect, ">", Column(dialect, "id"), Literal(dialect, 2)),
    ),
)

cte_query = WithQueryExpression(
    dialect=dialect,
    ctes=[high_earners_cte],
    main_query=QueryExpression(
        dialect=dialect,
        select=[Column(dialect, "id"), Column(dialect, "name")],
        from_=NamedRelationRef(dialect, Table(dialect, "high_earners")),
    ),
)
sql, params = cte_query.to_sql()
print(f"Basic CTE SQL: {sql}")
result = backend.execute(sql, params, options=dql_options)
print(f"Basic CTE result: {result.data}")

# ============================================================
# SECTION: Recursive CTE
# ============================================================
# Recursive CTE for hierarchical data (organizational chart)

# Base case: top-level employees
base_query = QueryExpression(
    dialect=dialect,
    select=[
        Column(dialect, "id"),
        Column(dialect, "name"),
        Column(dialect, "manager_id"),
        Literal(dialect, 1),
    ],
    from_=NamedRelationRef(dialect, Table(dialect, "employees")),
    where=ComparisonPredicate(dialect, "IS", Column(dialect, "manager_id"), Literal(dialect, None)),
)

org_cte = CTEExpression(
    dialect=dialect,
    name="org_chart",
    query=base_query,
    columns=["id", "name", "manager_id", "level"],
)

recursive_query = WithQueryExpression(
    dialect=dialect,
    ctes=[org_cte],
    main_query=QueryExpression(
        dialect=dialect,
        select=[Column(dialect, "id"), Column(dialect, "name"), Column(dialect, "manager_id")],
        from_=NamedRelationRef(dialect, Table(dialect, "org_chart")),
    ),
    recursive=True,
)
sql, params = recursive_query.to_sql()
print(f"Recursive CTE SQL: {sql}")
result = backend.execute(sql, params, options=dql_options)
print("Recursive CTE result:")
for row in result.data or []:
    print(f"  {row}")

# ============================================================
# SECTION: Multiple CTEs
# ============================================================
# Multiple CTEs can be defined in a single WITH clause

active_cte = CTEExpression(
    dialect=dialect,
    name="active_employees",
    query=QueryExpression(
        dialect=dialect,
        select=[Column(dialect, "id"), Column(dialect, "name")],
        from_=NamedRelationRef(dialect, Table(dialect, "employees")),
        where=ComparisonPredicate(dialect, ">", Column(dialect, "id"), Literal(dialect, 0)),
    ),
)

top_cte = CTEExpression(
    dialect=dialect,
    name="top_employees",
    query=QueryExpression(
        dialect=dialect,
        select=[Column(dialect, "id"), Column(dialect, "name")],
        from_=NamedRelationRef(dialect, Table(dialect, "active_employees")),
        where=ComparisonPredicate(dialect, ">", Column(dialect, "id"), Literal(dialect, 2)),
    ),
)

multi_cte_query = WithQueryExpression(
    dialect=dialect,
    ctes=[active_cte, top_cte],
    main_query=QueryExpression(
        dialect=dialect,
        select=[Column(dialect, "id"), Column(dialect, "name")],
        from_=NamedRelationRef(dialect, Table(dialect, "top_employees")),
    ),
)
sql, params = multi_cte_query.to_sql()
print(f"Multiple CTEs SQL: {sql}")
result = backend.execute(sql, params, options=dql_options)
print(f"Multiple CTEs result: {result.data}")

# ============================================================
# SECTION: Teardown (necessary for execution, reference only)
# ============================================================
drop_table = DropTableExpression(dialect=dialect, table=Table(dialect, "employees"), if_exists=True)
sql, params = drop_table.to_sql()
backend.execute(sql, params)
backend.disconnect()

# ============================================================
# SECTION: Summary
# ============================================================
# Key points:
# 1. Plain `WITH name AS (subquery)` has no ClickHouse version floor; the
#    recursive form needs the query analyzer (default since 24.3, mandatory
#    since 26.9) — see https://clickhouse.com/docs/reference/statements/select/with
# 2. Use CTEExpression to define CTEs
# 3. Use WithQueryExpression to combine CTEs with a main query
# 4. Set recursive=True for recursive CTEs (hierarchical queries)
# 5. Multiple CTEs can be defined in a single WithQueryExpression

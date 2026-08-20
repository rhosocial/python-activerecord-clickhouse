"""
Subquery expressions - WHERE and FROM subqueries.

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

drop_departments = DropTableExpression(dialect=dialect, table_name="departments", if_exists=True)
sql, params = drop_departments.to_sql()
backend.execute(sql, params)

drop_employees = DropTableExpression(dialect=dialect, table_name="employees", if_exists=True)
sql, params = drop_employees.to_sql()
backend.execute(sql, params)

create_departments = CreateTableExpression(
    dialect=dialect,
    table_name="departments",
    columns=[
        ColumnDefinition(
            "id",
            "UInt32",
            constraints=[
                ColumnConstraint(ColumnConstraintType.PRIMARY_KEY),
                ColumnConstraint(ColumnConstraintType.NOT_NULL),
            ],
        ),
        ColumnDefinition("name", "String"),
        ColumnDefinition("budget", "Decimal(15, 2)"),
    ],
    if_not_exists=True,
)
sql, params = create_departments.to_sql()
backend.execute(sql, params)

create_employees = CreateTableExpression(
    dialect=dialect,
    table_name="employees",
    columns=[
        ColumnDefinition(
            "id",
            "UInt32",
            constraints=[
                ColumnConstraint(ColumnConstraintType.PRIMARY_KEY),
                ColumnConstraint(ColumnConstraintType.NOT_NULL),
            ],
        ),
        ColumnDefinition("name", "String"),
        ColumnDefinition("salary", "Decimal(10, 2)"),
        ColumnDefinition("department_id", "UInt32"),
    ],
    if_not_exists=True,
)
sql, params = create_employees.to_sql()
backend.execute(sql, params)

insert_departments = InsertExpression(
    dialect=dialect,
    into="departments",
    columns=["name", "budget"],
    source=ValuesSource(
        dialect,
        [
            [Literal(dialect, "Engineering"), Literal(dialect, 1000000)],
            [Literal(dialect, "Sales"), Literal(dialect, 500000)],
        ],
    ),
)
sql, params = insert_departments.to_sql()
backend.execute(sql, params)

insert_employees = InsertExpression(
    dialect=dialect,
    into="employees",
    columns=["name", "salary", "department_id"],
    source=ValuesSource(
        dialect,
        [
            [Literal(dialect, "Alice"), Literal(dialect, 80000), Literal(dialect, 1)],
            [Literal(dialect, "Bob"), Literal(dialect, 90000), Literal(dialect, 1)],
            [Literal(dialect, "Charlie"), Literal(dialect, 60000), Literal(dialect, 2)],
            [Literal(dialect, "David"), Literal(dialect, 70000), Literal(dialect, 2)],
        ],
    ),
)
sql, params = insert_employees.to_sql()
backend.execute(sql, params)

# ============================================================
# SECTION: Business Logic (the pattern to learn)
# ============================================================
from rhosocial.activerecord.backend.expression import (  # noqa: E402
    QueryExpression,
    TableExpression,
    Column,
    WhereClause,
    Subquery,
)
from rhosocial.activerecord.backend.expression.core import FunctionCall  # noqa: E402
from rhosocial.activerecord.backend.expression.predicates import ComparisonPredicate  # noqa: E402

subquery_query = QueryExpression(
    dialect=dialect,
    select=[FunctionCall(dialect, "AVG", Column(dialect, "salary"))],
    from_=TableExpression(dialect, "employees"),
)
sql, params = subquery_query.to_sql()
subquery = Subquery(dialect, sql, params)

query = QueryExpression(
    dialect=dialect,
    select=[
        Column(dialect, "name"),
        Column(dialect, "salary"),
    ],
    from_=TableExpression(dialect, "employees"),
    where=WhereClause(
        dialect,
        condition=ComparisonPredicate(
            dialect,
            ">",
            Column(dialect, "salary"),
            subquery,
        ),
    ),
)

sql, params = query.to_sql()
print(f"SQL: {sql}")
print(f"Params: {params}")

# ============================================================
# SECTION: Execution (run the expression)
# ============================================================
options = ExecutionOptions(stmt_type=StatementType.DQL)
result = backend.execute(sql, params, options=options)
print(f"Rows returned: {len(result.data) if result.data else 0}")
for row in result.data or []:
    print(f" {row}")

# ============================================================
# SECTION: Teardown (necessary for execution, reference only)
# ============================================================
backend.disconnect()

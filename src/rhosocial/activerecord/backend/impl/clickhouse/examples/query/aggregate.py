"""
Aggregate queries with GROUP BY and HAVING.

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
)
from rhosocial.activerecord.backend.expression.core import Literal  # noqa: E402
from rhosocial.activerecord.backend.expression.statements import (  # noqa: E402
    ColumnDefinition,
    ColumnConstraint,
    ColumnConstraintType,
)

drop_table = DropTableExpression(dialect=dialect, table="sales", if_exists=True)
sql, params = drop_table.to_sql()
backend.execute(sql, params)

create_table = CreateTableExpression(
    dialect=dialect,
    table="sales",
    columns=[
        ColumnDefinition(
            "id",
            "UInt32",
            constraints=[
                ColumnConstraint(ColumnConstraintType.PRIMARY_KEY),
                ColumnConstraint(ColumnConstraintType.NOT_NULL),
            ],
        ),
        ColumnDefinition("product", "String"),
        ColumnDefinition("quantity", "UInt32"),
        ColumnDefinition("price", "Decimal(10, 2)"),
        ColumnDefinition("region", "String"),
    ],
    if_not_exists=True,
)
sql, params = create_table.to_sql()
backend.execute(sql, params)

insert = InsertExpression(
    dialect=dialect,
    into="sales",
    columns=["product", "quantity", "price", "region"],
    source=ValuesSource(
        dialect,
        [
            [Literal(dialect, "Widget"), Literal(dialect, 10), Literal(dialect, 5.00), Literal(dialect, "North")],
            [Literal(dialect, "Widget"), Literal(dialect, 5), Literal(dialect, 5.00), Literal(dialect, "South")],
            [Literal(dialect, "Gadget"), Literal(dialect, 8), Literal(dialect, 10.00), Literal(dialect, "North")],
            [Literal(dialect, "Gadget"), Literal(dialect, 3), Literal(dialect, 10.00), Literal(dialect, "South")],
            [Literal(dialect, "Widget"), Literal(dialect, 7), Literal(dialect, 5.00), Literal(dialect, "East")],
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
    GroupByHavingClause,
)
from rhosocial.activerecord.backend.expression.core import FunctionCall  # noqa: E402
from rhosocial.activerecord.backend.expression.predicates import ComparisonPredicate  # noqa: E402

query = QueryExpression(
    dialect=dialect,
    select=[
        Column(dialect, "product"),
        FunctionCall(dialect, "SUM", Column(dialect, "quantity")).as_("total_qty"),
        FunctionCall(dialect, "AVG", Column(dialect, "price")).as_("avg_price"),
    ],
    from_=TableExpression(dialect, "sales"),
    group_by_having=GroupByHavingClause(
        dialect,
        group_by=[Column(dialect, "product")],
        having=ComparisonPredicate(
            dialect,
            ">",
            FunctionCall(dialect, "SUM", Column(dialect, "quantity")),
            Literal(dialect, 10),
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

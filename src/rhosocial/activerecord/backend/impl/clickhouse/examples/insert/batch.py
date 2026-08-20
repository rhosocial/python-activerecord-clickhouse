"""
Batch insert with multiple rows.

"""

# ============================================================
# SECTION: Setup (necessary for execution, reference only)
# ============================================================
import os
from rhosocial.activerecord.backend.impl.clickhouse import ClickHouseBackend
from rhosocial.activerecord.backend.impl.clickhouse.config import ClickHouseConnectionConfig
from rhosocial.activerecord.backend.expression import (
    CreateTableExpression,
    DropTableExpression,
)
from rhosocial.activerecord.backend.expression.functions.datetime import current_timestamp
from rhosocial.activerecord.backend.expression.statements import (
    ColumnDefinition,
    ColumnConstraint,
    ColumnConstraintType,
)
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

# Drop table first for clean setup
drop_table = DropTableExpression(dialect=dialect, table_name="logs", if_exists=True)
sql, params = drop_table.to_sql()
backend.execute(sql, params)

create_table = CreateTableExpression(
    dialect=dialect,
    table_name="logs",
    columns=[
        ColumnDefinition(
            "id",
            "UInt32",
            constraints=[
                ColumnConstraint(ColumnConstraintType.PRIMARY_KEY),
                ColumnConstraint(ColumnConstraintType.NOT_NULL),
            ],
        ),
        ColumnDefinition("level", "String"),
        ColumnDefinition("message", "String"),
        ColumnDefinition(
            "created_at",
            "DateTime",
            constraints=[
                ColumnConstraint(
                    ColumnConstraintType.DEFAULT,
                    default_value=current_timestamp(dialect),
                ),
            ],
        ),
    ],
    if_not_exists=True,
)
sql, params = create_table.to_sql()
backend.execute(sql, params)

# ============================================================
# SECTION: Business Logic (the pattern to learn)
# ============================================================
from rhosocial.activerecord.backend.expression import (  # noqa: E402
    InsertExpression,
    ValuesSource,
    TableExpression,
    QueryExpression,
)
from rhosocial.activerecord.backend.expression.core import Literal, WildcardExpression, Column  # noqa: E402
from rhosocial.activerecord.backend.expression.statements.dql import OrderByClause  # noqa: E402

insert_expr = InsertExpression(
    dialect=dialect,
    into=TableExpression(dialect, "logs"),
    source=ValuesSource(
        dialect,
        [
            [Literal(dialect, "INFO"), Literal(dialect, "System started")],
            [Literal(dialect, "DEBUG"), Literal(dialect, "Loading configuration")],
            [Literal(dialect, "INFO"), Literal(dialect, "Application ready")],
            [Literal(dialect, "WARNING"), Literal(dialect, "Memory usage high")],
        ],
    ),
    columns=["level", "message"],
)

sql, params = insert_expr.to_sql()
print(f"SQL: {sql}")
print(f"Params: {params}")

# ============================================================
# SECTION: Execution (run the expression)
# ============================================================
result = backend.execute(sql, params)
print(f"Affected rows: {result.affected_rows}")

verify_query = QueryExpression(
    dialect=dialect,
    select=[WildcardExpression(dialect)],
    from_=TableExpression(dialect, "logs"),
    order_by=OrderByClause(dialect, [Column(dialect, "id")]),
)
options = ExecutionOptions(stmt_type=StatementType.DQL)
sql, params = verify_query.to_sql()
result = backend.execute(sql, params, options=options)
print(f"Total rows in table: {len(result.data) if result.data else 0}")
for row in result.data or []:
    print(f"  {row}")

# ============================================================
# SECTION: Teardown (necessary for execution, reference only)
# ============================================================
backend.disconnect()

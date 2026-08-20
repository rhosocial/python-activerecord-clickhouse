"""
FOR UPDATE Row Locking awareness demonstration.

This example demonstrates:
1. ClickHouse does NOT support SELECT ... FOR UPDATE
2. Row-level locking is not available in ClickHouse
3. ForUpdateClause will raise UnsupportedFeatureError

For row locking, use a database engine that supports ACID
transactions (e.g., PostgreSQL, MySQL with InnoDB).
"""

# ============================================================
# SECTION: Setup (necessary for execution, reference only)
# ============================================================
import os
from rhosocial.activerecord.backend.impl.clickhouse import ClickHouseBackend
from rhosocial.activerecord.backend.impl.clickhouse.config import ClickHouseConnectionConfig

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
    QueryExpression,
    TableExpression,
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

drop_table = DropTableExpression(dialect=dialect, table_name="accounts", if_exists=True)
sql, params = drop_table.to_sql()
backend.execute(sql, params)

create_table = CreateTableExpression(
    dialect=dialect,
    table_name="accounts",
    columns=[
        ColumnDefinition(
            "id",
            "UInt32",
            constraints=[
                ColumnConstraint(ColumnConstraintType.PRIMARY_KEY),
                ColumnConstraint(ColumnConstraintType.NOT_NULL),
            ],
        ),
        ColumnDefinition(
            "name",
            "String",
            constraints=[
                ColumnConstraint(ColumnConstraintType.NOT_NULL),
            ],
        ),
        ColumnDefinition(
            "balance",
            "Decimal(10, 2)",
            constraints=[
                ColumnConstraint(ColumnConstraintType.DEFAULT, default_value=Literal(dialect, 0)),
            ],
        ),
    ],
    if_not_exists=True,
)
sql, params = create_table.to_sql()
backend.execute(sql, params)

insert_expr = InsertExpression(
    dialect=dialect,
    into="accounts",
    columns=["name", "balance"],
    source=ValuesSource(
        dialect,
        [
            [Literal(dialect, "Alice"), Literal(dialect, 1000)],
            [Literal(dialect, "Bob"), Literal(dialect, 500)],
        ],
    ),
)
sql, params = insert_expr.to_sql()
backend.execute(sql, params)

# ============================================================
# SECTION: FOR UPDATE is not supported
# ============================================================
print("ClickHouse does not support SELECT ... FOR UPDATE row locking.\n")

# Regular SELECT works fine
query = QueryExpression(
    dialect=dialect,
    select=[Column(dialect, "id"), Column(dialect, "name"), Column(dialect, "balance")],
    from_=TableExpression(dialect, "accounts"),
    where=ComparisonPredicate(dialect, "=", Column(dialect, "name"), Literal(dialect, "Alice")),
)
sql, params = query.to_sql()
result = backend.execute(sql, params, options=dql_options)
print(f"Regular SELECT: {result.data}")

# ============================================================
# SECTION: FOR UPDATE attempt (will raise)
# ============================================================
print("\nAttempting FOR UPDATE...")
try:
    from rhosocial.activerecord.backend.expression.query_parts import ForUpdateClause
    lock_query = QueryExpression(
        dialect=dialect,
        select=[Column(dialect, "id"), Column(dialect, "name"), Column(dialect, "balance")],
        from_=TableExpression(dialect, "accounts"),
        where=ComparisonPredicate(dialect, "=", Column(dialect, "name"), Literal(dialect, "Alice")),
        for_update=ForUpdateClause(dialect),
    )
    sql, params = lock_query.to_sql()
    print(f"  (unexpected: generated SQL: {sql})")
except Exception as e:
    print(f"  UnsupportedFeatureError: {e}")

# ============================================================
# SECTION: Teardown (necessary for execution, reference only)
# ============================================================
drop_table = DropTableExpression(dialect=dialect, table_name="accounts", if_exists=True)
sql, params = drop_table.to_sql()
backend.execute(sql, params)
backend.disconnect()

# ============================================================
# SECTION: Summary
# ============================================================
# Key points:
# 1. ClickHouse does NOT support SELECT ... FOR UPDATE
# 2. ForUpdateClause raises UnsupportedFeatureError
# 3. SKIP LOCKED and NOWAIT are also unsupported
# 4. Use a transactional database backend for row locking
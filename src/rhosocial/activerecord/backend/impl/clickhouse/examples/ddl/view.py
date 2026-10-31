"""
CREATE VIEW - ClickHouse.

This example demonstrates:
1. CREATE VIEW
2. CREATE OR REPLACE VIEW
3. Drop view

"""

# ============================================================
# SECTION: Setup (necessary for execution, reference only)
# ============================================================
from rhosocial.activerecord.backend.expression.objects import Table
from rhosocial.activerecord.backend.expression.sources import NamedRelationRef
import os
from rhosocial.activerecord.backend.impl.clickhouse.backend import ClickHouseBackend
from rhosocial.activerecord.backend.impl.clickhouse.config import ClickHouseConnectionConfig
from rhosocial.activerecord.backend.options import ExecutionOptions
from rhosocial.activerecord.backend.schema import StatementType

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
    CreateTableStatement,
    InsertStatement,
    ValuesSource,
    DropTableStatement,
)
from rhosocial.activerecord.backend.expression.core import Literal, Column  # noqa: E402
from rhosocial.activerecord.backend.expression.statements import (  # noqa: E402
    ColumnDefinition,
)

# Drop dependent tables first for clean setup (orders may reference users via FK)
drop_orders = DropTableStatement(dialect=dialect, table=Table(dialect, "orders"), if_exists=True)
sql, params = drop_orders.to_sql()
backend.execute(sql, params)

drop_users = DropTableStatement(dialect=dialect, table=Table(dialect, "users"), if_exists=True)
sql, params = drop_users.to_sql()
backend.execute(sql, params)

create_table = CreateTableStatement(
    dialect=dialect,
    table=Table(dialect, "users"),
    columns=[
        ColumnDefinition("id", "UInt32"),
        ColumnDefinition("name", "String"),
    ],
    if_not_exists=True,
)
sql, params = create_table.to_sql()
print(f"Create table SQL: {sql}")
backend.execute(sql, params)

insert = InsertStatement(
    dialect=dialect,
    into=Table(dialect, "users"),
    columns=["id", "name"],
    source=ValuesSource(
        dialect,
        [
            [Literal(dialect, 1), Literal(dialect, "Alice")],
            [Literal(dialect, 2), Literal(dialect, "Bob")],
        ],
    ),
)
sql, params = insert.to_sql()
print(f"Insert SQL: {sql}")
backend.execute(sql, params)

# ============================================================
# SECTION: CREATE VIEW
# ============================================================
from rhosocial.activerecord.backend.expression import (  # noqa: E402
    QueryStatement,
    CreateViewStatement,
    DropViewStatement,
)
from rhosocial.activerecord.backend.expression.core import AllColumnsWildcard  # noqa: E402

query = QueryStatement(
    dialect=dialect,
    select=[Column(dialect, "name")],
    from_=NamedRelationRef(dialect, Table(dialect, "users")),
)

view_expr = CreateViewStatement(
    dialect=dialect,
    view_name="user_names",
    query=query,
)
sql, params = view_expr.to_sql()
print(f"CREATE VIEW SQL: {sql}")
print(f"Params: {params}")

options = ExecutionOptions(stmt_type=StatementType.DDL)
backend.execute(sql, params, options=options)

verify_query = QueryStatement(
    dialect=dialect,
    select=[AllColumnsWildcard(dialect)],
    from_=NamedRelationRef(dialect, Table(dialect, "user_names")),
)
options = ExecutionOptions(stmt_type=StatementType.DQL)
sql, params = verify_query.to_sql()
result = backend.execute(sql, params, options=options)
print(f"View result: {result.data}")

# ============================================================
# SECTION: CREATE OR REPLACE VIEW
# ============================================================
view_expr_replace = CreateViewStatement(
    dialect=dialect,
    view_name="user_names",
    query=query,
    replace=True,
)
sql, params = view_expr_replace.to_sql()
print(f"CREATE OR REPLACE VIEW SQL: {sql}")
backend.execute(sql, params, options=options)

# ============================================================
# SECTION: DROP VIEW
# ============================================================
drop_view = DropViewStatement(
    dialect=dialect,
    view_name="user_names",
)
sql, params = drop_view.to_sql()
print(f"DROP VIEW SQL: {sql}")
backend.execute(sql, params, options=options)

# ============================================================
# SECTION: Teardown
# ============================================================
drop_orders = DropTableStatement(dialect=dialect, table=Table(dialect, "orders"), if_exists=True)
sql, params = drop_orders.to_sql()
backend.execute(sql, params)

drop_expr = DropTableStatement(dialect=dialect, table=Table(dialect, "users"), if_exists=True)
sql, params = drop_expr.to_sql()
backend.execute(sql, params)
backend.disconnect()

# ============================================================
# SECTION: Summary
# ============================================================
# Key points:
# 1. Use CreateViewStatement to create views
# 2. Use replace=True to replace existing view
# 3. Use DropViewStatement to drop views

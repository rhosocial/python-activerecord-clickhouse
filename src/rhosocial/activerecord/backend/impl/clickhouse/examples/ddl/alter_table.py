"""
Alter table statements - ADD_COLUMN.

Note: ClickHouse supports multiple actions in a single ALTER TABLE statement,
but for simplicity we demonstrate individual operations.

Note: MODIFY COLUMN is a ClickHouse-specific feature. The ClickHouse dialect's
format_modify_column_action is not yet implemented, so this example
only demonstrates ADD_COLUMN.

"""

# ============================================================
# SECTION: Setup (necessary for execution, reference only)
# ============================================================
from rhosocial.activerecord.backend.expression.objects import Table
import os
from rhosocial.activerecord.backend.impl.clickhouse.backend import ClickHouseBackend
from rhosocial.activerecord.backend.impl.clickhouse.config import ClickHouseConnectionConfig
from rhosocial.activerecord.backend.expression import (
    CreateTableStatement,
    InsertStatement,
    ValuesSource,
    DropTableStatement,
)
from rhosocial.activerecord.backend.expression.core import Literal
from rhosocial.activerecord.backend.expression.statements import (
    ColumnDefinition,
    ColumnConstraint,
    ColumnPrimaryKeyConstraint, ColumnNotNullConstraint, ColumnDefaultConstraint,
)

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

drop_orders = DropTableStatement(dialect=dialect, table=Table(dialect, "orders"), if_exists=True)
sql, params = drop_orders.to_sql()
backend.execute(sql, params)

drop_table = DropTableStatement(dialect=dialect, table=Table(dialect, "users"), if_exists=True)
sql, params = drop_table.to_sql()
backend.execute(sql, params)

create_table = CreateTableStatement(
    dialect=dialect,
    table=Table(dialect, "users"),
    columns=[
        ColumnDefinition(
            "id",
            "UInt32",
            constraints=[
                ColumnConstraint(dialect, branch=ColumnPrimaryKeyConstraint(dialect)),
                ColumnConstraint(dialect, branch=ColumnNotNullConstraint(dialect)),
            ],
        ),
        ColumnDefinition("name", "String"),
    ],
    if_not_exists=True,
)
sql, params = create_table.to_sql()
backend.execute(sql, params)

insert = InsertStatement(
    dialect=dialect,
    into=Table(dialect, "users"),
    columns=["name"],
    source=ValuesSource(
        dialect,
        [[Literal(dialect, "Alice")]],
    ),
)
sql, params = insert.to_sql()
backend.execute(sql, params)

# ============================================================
# SECTION: Business Logic (the pattern to learn)
# ============================================================
from rhosocial.activerecord.backend.expression import AlterTableStatement  # noqa: E402
from rhosocial.activerecord.backend.expression.statements.ddl_alter import AddColumn  # noqa: E402

add_col_action = AddColumn(
    dialect=dialect,
    column=ColumnDefinition(
        name="email",
        data_type="String",
    ),
)

add_col_expr = AlterTableStatement(
    dialect=dialect,
    table=Table(dialect, "users"),
    actions=[add_col_action],
)

sql, params = add_col_expr.to_sql()
print(f"SQL (Add Column email): {sql}")
print(f"Params: {params}")

backend.execute(sql, params)
print("Column email added successfully")

add_age_action = AddColumn(
    dialect=dialect,
    column=ColumnDefinition(
        "age",
        "UInt32",
        constraints=[
            ColumnConstraint(dialect,
                 branch=ColumnDefaultConstraint(dialect, Literal(dialect, 0))),
        ],
    ),
)

add_age_expr = AlterTableStatement(
    dialect=dialect,
    table=Table(dialect, "users"),
    actions=[add_age_action],
)

sql, params = add_age_expr.to_sql()
print(f"SQL (Add Column age): {sql}")
print(f"Params: {params}")

backend.execute(sql, params)
print("Column age added successfully")

# ============================================================
# SECTION: Execution (verify alterations)
# ============================================================

# Verify using introspector
columns = backend.introspector.list_columns("users")
print("Table structure after alterations:")
for col in columns:
    print(f"  {col}")

# ============================================================
# SECTION: Teardown (necessary for execution, reference only)
# ============================================================
backend.disconnect()

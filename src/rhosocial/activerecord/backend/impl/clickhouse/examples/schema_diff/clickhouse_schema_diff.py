"""
Schema diff: ClickHouse table structure changes (add column, modify type).

This example demonstrates how ClickHouseSchemaDiffer reports schema changes
between two snapshots of the same table:

1. Adding a new column (with a default value)
2. Modifying an existing column's data type (e.g. Decimal → Float64)
3. Table-level add/remove detection

ClickHouse ALTER TABLE statements are metadata-only and cheap, so schema
evolution is a common workflow.  After each ALTER, compare a fresh schema
snapshot with the previous one to keep migrations verifiable.

Supported versions: ClickHouse
"""

# ============================================================
# SECTION: Setup (necessary for execution, reference only)
# ============================================================
import os
from rhosocial.activerecord.backend.impl.clickhouse import ClickHouseBackend
from rhosocial.activerecord.backend.impl.clickhouse.config import ClickHouseConnectionConfig

config = ClickHouseConnectionConfig(
    host=os.getenv("CLICKHOUSE_HOST", "localhost"),
    port=int(os.getenv("CLICKHOUSE_PORT", "8123")),
    database=os.getenv("CLICKHOUSE_DATABASE", "test"),
    username=os.getenv("CLICKHOUSE_USER", "root"),
    password=os.getenv("CLICKHOUSE_PASSWORD", ""),
)
backend = ClickHouseBackend(connection_config=config)
backend.connect()
backend.introspect_and_adapt()
dialect = backend.dialect

from rhosocial.activerecord.backend.expression import (  # noqa: E402
    DropTableExpression,
    CreateTableExpression,
    ColumnDefinition,
    ColumnConstraint,
    ColumnConstraintType,
    InsertExpression,
    ValuesSource,
)
from rhosocial.activerecord.backend.expression.core import Literal  # noqa: E402
from rhosocial.activerecord.backend.impl.clickhouse.expression.types import (  # noqa: E402
    ClickHouseUInt32Type,
    ClickHouseDateTimeType,
    ClickHouseDecimalType,
    ClickHouseFloat64Type,
    ClickHouseStringType,
)

expr = DropTableExpression(dialect, "events", if_exists=True)
sql, params = expr.to_sql()
backend.execute(sql, params)

expr = CreateTableExpression(
    dialect=dialect,
    table="events",
    columns=[
        ColumnDefinition("id", ClickHouseUInt32Type(),
            constraints=[
                ColumnConstraint(constraint_type=ColumnConstraintType.NOT_NULL),
                ColumnConstraint(constraint_type=ColumnConstraintType.PRIMARY_KEY),
            ]),
        ColumnDefinition("ts", ClickHouseDateTimeType()),
        ColumnDefinition("message", ClickHouseStringType()),
        ColumnDefinition("value", ClickHouseDecimalType(precision=10, scale=2)),
    ],
    dialect_options={"engine": "MergeTree()", "order_by": "id"},
)
sql, params = expr.to_sql()
backend.execute(sql, params)

insert = InsertExpression(
    dialect=dialect,
    into="events",
    columns=["id", "message", "value"],
    source=ValuesSource(
        dialect,
        [
            [Literal(dialect, 1), Literal(dialect, "login"), Literal(dialect, 10.5)],
            [Literal(dialect, 2), Literal(dialect, "logout"), Literal(dialect, 3.25)],
        ],
    ),
)
sql, params = insert.to_sql()
backend.execute(sql, params)

# ============================================================
# SECTION: Business Logic (the pattern to learn)
# ============================================================
from rhosocial.activerecord.backend.schema import (  # noqa: E402
    SyncSchemaSnapshotBuilder,
)
from rhosocial.activerecord.backend.impl.clickhouse.schema.differ import (  # noqa: E402
    ClickHouseSchemaDiffer,
)
from rhosocial.activerecord.backend.expression.statements.ddl_alter import (  # noqa: E402
    AlterTableExpression,
    AddColumn,
    ModifyColumn,
)

builder = SyncSchemaSnapshotBuilder(backend.introspector, dialect)
snapshot_before = builder.build()

# Add a new column with a default value
add_status = AddColumn(
    dialect,
    ColumnDefinition(
        "status",
        ClickHouseStringType(),
        constraints=[
            ColumnConstraint(constraint_type=ColumnConstraintType.DEFAULT, default_value=Literal(dialect, "new")),
        ],
    ),
)
alter_expr = AlterTableExpression(dialect, "events", [add_status])
sql, params = alter_expr.to_sql()
print(f"ALTER (add column): {sql}")
backend.execute(sql, params)

# Modify an existing column's data type: Decimal(10, 2) -> Float64
modify_value = ModifyColumn(
    dialect,
    ColumnDefinition("value", ClickHouseFloat64Type()),
)
alter_expr = AlterTableExpression(dialect, "events", [modify_value])
sql, params = alter_expr.to_sql()
print(f"ALTER (modify type): {sql}")
backend.execute(sql, params)

snapshot_after = builder.build()

differ = ClickHouseSchemaDiffer()
diff = differ.compare(snapshot_before, snapshot_after)

# ============================================================
# SECTION: Execution (run the expression)
# ============================================================
print(f"\nAdded tables:    {diff.added_tables}")
print(f"Removed tables:  {diff.removed_tables}")
print(f"Modified tables: {diff.modified_tables}")

if "events" in diff.table_diffs:
    td = diff.table_diffs["events"]
    for cd in td.column_diffs:
        kind = "added" if cd.is_added else "modified" if cd.is_modified else "removed"
        old_type = cd.old.data_type if cd.old else "-"
        new_type = cd.new.data_type if cd.new else "-"
        print(f"  Column '{cd.column_name}': {kind} ({old_type} → {new_type})")

# ============================================================
# SECTION: Teardown (necessary for execution, reference only)
# ============================================================
expr = DropTableExpression(dialect, "events", if_exists=True)
sql, params = expr.to_sql()
backend.execute(sql, params)
backend.disconnect()
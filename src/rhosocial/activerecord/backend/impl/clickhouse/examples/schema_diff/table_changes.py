"""
Schema diff: detect table-level changes (add, remove, modify).

Supported versions: ClickHouse 5.6+

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
    username=os.getenv("CLICKHOUSE_USER", "root"),
    password=os.getenv("CLICKHOUSE_PASSWORD", ""),
)
backend = ClickHouseBackend(connection_config=config)
backend.connect()
backend.introspect_and_adapt()
dialect = backend.dialect

# Clean up any leftover tables
from rhosocial.activerecord.backend.expression import (  # noqa: E402
    DropTableExpression,
)
expr = DropTableExpression(dialect, "users", if_exists=True)
sql, params = expr.to_sql()
backend.execute(sql, params)
expr = DropTableExpression(dialect, "orders", if_exists=True)
sql, params = expr.to_sql()
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
from rhosocial.activerecord.backend.expression import (  # noqa: E402
    CreateTableExpression, ColumnDefinition,
    ColumnConstraint, ColumnConstraintType,
)
from rhosocial.activerecord.backend.expression.types import (  # noqa: E402
    IntegerType, VarCharType, DecimalType,
)

builder = SyncSchemaSnapshotBuilder(backend.introspector, dialect)
snapshot_before = builder.build()

# Create one table, drop another (if it existed)
expr = CreateTableExpression(
    dialect=dialect, table="users", columns=[
        ColumnDefinition("id", IntegerType(),
            constraints=[
                ColumnConstraint(constraint_type=ColumnConstraintType.NOT_NULL),
                ColumnConstraint(constraint_type=ColumnConstraintType.PRIMARY_KEY),
            ]),
        ColumnDefinition("name", VarCharType(100)),
    ]
)
sql, params = expr.to_sql()
backend.execute(sql, params)
expr = CreateTableExpression(
    dialect=dialect, table="orders", columns=[
        ColumnDefinition("id", IntegerType(),
            constraints=[
                ColumnConstraint(constraint_type=ColumnConstraintType.NOT_NULL),
                ColumnConstraint(constraint_type=ColumnConstraintType.PRIMARY_KEY),
            ]),
        ColumnDefinition("user_id", IntegerType()),
        ColumnDefinition("amount", DecimalType(10, 2)),
    ]
)
sql, params = expr.to_sql()
backend.execute(sql, params)

snapshot_after = builder.build()

differ = ClickHouseSchemaDiffer()
diff = differ.compare(snapshot_before, snapshot_after)

# ============================================================
# SECTION: Execution (run the expression)
# ============================================================
print(f"Added tables:   {diff.added_tables}")
print(f"Removed tables: {diff.removed_tables}")
print(f"Modified tables:{diff.modified_tables}")
print(f"Diff is empty:  {diff.is_empty}")

# ============================================================
# SECTION: Teardown (necessary for execution, reference only)
# ============================================================
expr = DropTableExpression(dialect, "users", if_exists=True)
sql, params = expr.to_sql()
backend.execute(sql, params)
expr = DropTableExpression(dialect, "orders", if_exists=True)
sql, params = expr.to_sql()
backend.execute(sql, params)
backend.disconnect()
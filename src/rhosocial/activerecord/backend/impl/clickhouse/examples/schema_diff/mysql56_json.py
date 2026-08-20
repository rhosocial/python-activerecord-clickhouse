"""
Schema diff: ClickHouse 5.6 vs 8.0 — JSON column type differences.

ClickHouse 5.6 does not natively support the JSON data type; columns declared as
JSON are stored as LONGTEXT. ClickHouse 5.7+ introduces a native JSON type with
compact binary storage.

When diff-ing a schema captured from ClickHouse 5.6 against one from 8.0, or
vice versa, the differ will detect the data type mapping change.

Supported versions: ClickHouse 5.6 — schema uses LONGTEXT for "JSON" columns.
                     ClickHouse 5.7+ — schema uses native JSON type.
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
    charset="utf8mb4",
)
backend = ClickHouseBackend(connection_config=config)
backend.connect()
backend.introspect_and_adapt()
dialect = backend.dialect

from rhosocial.activerecord.backend.expression import (  # noqa: E402
    DropTableExpression, CreateTableExpression, ColumnDefinition,
    ColumnConstraint, ColumnConstraintType,
)
from rhosocial.activerecord.backend.expression.types import (  # noqa: E402
    IntegerType, JsonType,
)
from rhosocial.activerecord.backend.impl.clickhouse.expression.types import (  # noqa: E402
    ClickHouseLongTextType,
)

expr = DropTableExpression(dialect, "documents56", if_exists=True)
sql, params = expr.to_sql()
backend.execute(sql, params)
expr = DropTableExpression(dialect, "documents57", if_exists=True)
sql, params = expr.to_sql()
backend.execute(sql, params)

# Simulate ClickHouse 5.6: store JSON as TEXT
expr = CreateTableExpression(
    dialect=dialect, table="documents56", columns=[
        ColumnDefinition("id", IntegerType(),
            constraints=[
                ColumnConstraint(constraint_type=ColumnConstraintType.NOT_NULL),
                ColumnConstraint(constraint_type=ColumnConstraintType.PRIMARY_KEY, is_auto_increment=True),
            ]),
        ColumnDefinition("data", ClickHouseLongTextType()),
    ]
)
sql, params = expr.to_sql()
backend.execute(sql, params)
# Simulate ClickHouse 5.7+: native JSON column
expr = CreateTableExpression(
    dialect=dialect, table="documents57", columns=[
        ColumnDefinition("id", IntegerType(),
            constraints=[
                ColumnConstraint(constraint_type=ColumnConstraintType.NOT_NULL),
                ColumnConstraint(constraint_type=ColumnConstraintType.PRIMARY_KEY, is_auto_increment=True),
            ]),
        ColumnDefinition("data", JsonType()),
    ]
)
sql, params = expr.to_sql()
backend.execute(sql, params)

# ============================================================
# SECTION: Business Logic (the pattern to learn)
# ============================================================
from rhosocial.activerecord.backend.schema import (  # noqa: E402
    SyncSchemaSnapshotBuilder,
)

builder = SyncSchemaSnapshotBuilder(backend.introspector, dialect)
snapshot = builder.build()

# ============================================================
# SECTION: Execution (run the expression)
# ============================================================
# Examine the introspected data_type for both tables
for tbl_name in ("documents56", "documents57"):
    if tbl_name in snapshot.tables:
        for col in snapshot.tables[tbl_name].columns:
            if col.name == "data":
                print(f"{tbl_name}.data: data_type='{col.data_type}',"
                      f" parsed_type={type(col.parsed_data_type).__name__ if col.parsed_data_type else 'None'}"
                      f" char_max_length={col.character_maximum_length}")

# ============================================================
# SECTION: Teardown (necessary for execution, reference only)
# ============================================================
expr = DropTableExpression(dialect, "documents56", if_exists=True)
sql, params = expr.to_sql()
backend.execute(sql, params)
expr = DropTableExpression(dialect, "documents57", if_exists=True)
sql, params = expr.to_sql()
backend.execute(sql, params)
backend.disconnect()
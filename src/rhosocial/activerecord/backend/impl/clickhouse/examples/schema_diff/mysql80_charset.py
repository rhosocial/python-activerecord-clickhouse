"""
Schema diff: ClickHouse 5.6 vs 8.0 — charset and collation differences.

ClickHouse 8.0 changed the default charset from latin1 to utf8mb4 and the
default collation from latin1_swedish_ci to utf8mb4_0900_ai_ci. This
manifests in introspected column metadata (charset, collation fields).

When comparing snapshots from different major versions, these metadata
differences may appear in the diff output.

Supported versions: ClickHouse 5.6/5.7 — defaults to latin1/charset per column.
                     ClickHouse 8.0+ — defaults to utf8mb4 per column.

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

from rhosocial.activerecord.backend.expression import (  # noqa: E402
    DropTableExpression, CreateTableExpression, ColumnDefinition,
    ColumnConstraint, ColumnConstraintType,
)
from rhosocial.activerecord.backend.expression.types import (  # noqa: E402
    IntegerType, VarCharType,
)

expr = DropTableExpression(dialect, "demo", if_exists=True)
sql, params = expr.to_sql()
backend.execute(sql, params)
# Create table without explicit charset to inherit database/server default
expr = CreateTableExpression(
    dialect=dialect, table="demo", columns=[
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

# ============================================================
# SECTION: Business Logic (the pattern to learn)
# ============================================================
from rhosocial.activerecord.backend.schema import (  # noqa: E402
    SyncSchemaSnapshotBuilder,
)

builder = SyncSchemaSnapshotBuilder(backend.introspector, dialect)
snapshot = builder.build()

# Inspect column-level charset/collation metadata (version-dependent)
if "demo" in snapshot.tables:
    for col in snapshot.tables["demo"].columns:
        print(f"Column '{col.name}':")
        print(f"  data_type:   {col.data_type}")
        print(f"  charset:     {col.charset}")
        print(f"  collation:   {col.collation}")
        print(f"  char_max_len: {col.character_maximum_length}")

# ============================================================
# SECTION: Teardown (necessary for execution, reference only)
# ============================================================
expr = DropTableExpression(dialect, "demo", if_exists=True)
sql, params = expr.to_sql()
backend.execute(sql, params)
backend.disconnect()
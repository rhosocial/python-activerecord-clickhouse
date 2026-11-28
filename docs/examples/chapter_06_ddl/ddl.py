# docs/examples/chapter_06_ddl/ddl.py
"""Chapter 6: create a MergeTree table with a DDL expression.

Every ClickHouse storage clause — ``ENGINE``, ``PARTITION BY``, ``ORDER BY``,
``TTL`` and ``SETTINGS`` — is declared as an expression node on
:class:`ClickHouseCreateTableOptions`. ``CreateTableStatement.to_sql()`` emits
complete native ClickHouse DDL; no hand-written SQL fragment is needed for the
clauses.

The generated table carries the two settings the lightweight UPDATE/DELETE path
requires. The example prints the SQL it generates, creates the table, reads its
engine back through introspection, then drops it.
"""

import os
import sys

from rhosocial.activerecord.backend.expression.column_types.column import Column
from rhosocial.activerecord.backend.expression.functions.function_call import FunctionCall
from rhosocial.activerecord.backend.expression.objects import Table
from rhosocial.activerecord.backend.expression.operators import RawSQL
from rhosocial.activerecord.backend.expression.statements import (
    ColumnDefinition,
    CreateTableStatement,
    DropTableStatement,
)
from rhosocial.activerecord.backend.impl.clickhouse.backend import ClickHouseBackend
from rhosocial.activerecord.backend.impl.clickhouse.config import ClickHouseConnectionConfig
from rhosocial.activerecord.backend.impl.clickhouse.expression import (
    ClickHouseCreateTableOptions,
    ClickHouseDateTime64Type,
    ClickHouseEngineSpec,
    ClickHouseInt64Type,
    ClickHouseSetting,
    ClickHouseStorageOptionKind,
    ClickHouseStringType,
    ClickHouseTableStorageOption,
)

TABLE_NAME = "example_events"


def build_config() -> ClickHouseConnectionConfig:
    return ClickHouseConnectionConfig(
        host=os.getenv("CLICKHOUSE_HOST", "localhost"),
        port=int(os.getenv("CLICKHOUSE_PORT", "8123")),
        database=os.getenv("CLICKHOUSE_DATABASE", "test_db"),
        username=os.getenv("CLICKHOUSE_USER", "root"),
        password=os.getenv("CLICKHOUSE_PASSWORD", "password"),
    )


def build_storage_clauses(dialect):
    """Declare the ClickHouse storage clauses as expression nodes."""
    kind = ClickHouseStorageOptionKind
    return [
        ClickHouseTableStorageOption(dialect, kind.ENGINE, value=ClickHouseEngineSpec(dialect, "MergeTree")),
        ClickHouseTableStorageOption(
            dialect,
            kind.PARTITION_BY,
            value=[FunctionCall(dialect, "toYYYYMM", Column(dialect, "ts"))],
        ),
        ClickHouseTableStorageOption(
            dialect,
            kind.ORDER_BY,
            value=[Column(dialect, "ts"), Column(dialect, "id")],
        ),
        ClickHouseTableStorageOption(
            dialect,
            kind.TTL,
            value=RawSQL(dialect, "ts + INTERVAL 90 DAY DELETE"),
        ),
        ClickHouseTableStorageOption(
            dialect,
            kind.SETTINGS,
            value=[
                ClickHouseSetting(dialect, "enable_block_number_column", 1),
                ClickHouseSetting(dialect, "enable_block_offset_column", 1),
            ],
        ),
    ]


def build_create_statement(dialect) -> CreateTableStatement:
    return CreateTableStatement(
        dialect,
        Table(dialect, TABLE_NAME),
        [
            ColumnDefinition(dialect, "ts", ClickHouseDateTime64Type(dialect, precision=6)),
            ColumnDefinition(dialect, "id", ClickHouseInt64Type(dialect)),
            ColumnDefinition(dialect, "url", ClickHouseStringType(dialect)),
        ],
        if_not_exists=True,
        table_options=ClickHouseCreateTableOptions(
            dialect,
            table_storage_options=build_storage_clauses(dialect),
        ),
    )


def main() -> None:
    config = build_config()
    backend = ClickHouseBackend(connection_config=config)
    try:
        backend.connect()
    except Exception as error:  # noqa: BLE001 - any connection failure is the same answer here
        print(f"Could not connect to ClickHouse at {config.host}:{config.port}: {error}", file=sys.stderr)
        sys.exit(1)

    dialect = backend.dialect
    try:
        expr = build_create_statement(dialect)
        sql, params = expr.to_sql()
        print("Generated DDL:")
        print(" ", sql)
        print()
        backend.execute(sql, params)

        # The renderer emits the clauses in ClickHouse's grammar order,
        # ENGINE -> PARTITION BY -> ORDER BY -> TTL -> SETTINGS, no matter
        # the order they were declared in.
        engine = backend.introspector.get_table_engine(TABLE_NAME)
        print("Engine read back from system.tables:")
        print("  engine        :", engine.engine)
        print("  sorting_key   :", engine.sorting_key)
        print("  partition_key :", engine.partition_key)
        print("  total_rows    :", engine.total_rows)
    finally:
        backend.execute(
            *DropTableStatement(dialect, Table(dialect, TABLE_NAME), if_exists=True).to_sql()
        )
        backend.disconnect()


if __name__ == "__main__":
    main()

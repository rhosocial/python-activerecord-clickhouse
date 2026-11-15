# tests/rhosocial/activerecord_clickhouse_test/feature/connection/pool_definitions.py
"""The connection-pool tests' own tables.

The concurrent tests create and drop these tables through the pool itself, so
their DDL belongs here rather than in the conftest or in a test body: a
definition class receives only a ``dialect`` and knows nothing about backends,
databases, connection pools or execution.

ClickHouse's storage clause is declared with the backend's expression objects
(``ClickHouseCreateTableOptions`` and its storage options), never as SQL text:
the engine, the sort key, and the block-number settings the lightweight
``UPDATE`` / ``DELETE`` path this backend runs mutations with.  The old
conftest wrote that clause as raw DDL; the tables it created had no declared
key -- the tests insert rows without an ``id`` -- so the sort key is named by
the storage options, which also keeps ``id`` out of the nullable wrapping a
portable declaration would otherwise get.
"""

from rhosocial.activerecord.backend.expression import (
    ColumnConstraint as Constraint,
    ColumnDefinition as Column,
    CreateTableStatement as CreateTable,
    DropTableStatement as DropTable,
)
from rhosocial.activerecord.backend.expression.core import Column as ColumnRef
from rhosocial.activerecord.backend.expression.functions import now
from rhosocial.activerecord.backend.expression.objects import Table
from rhosocial.activerecord.backend.expression.statements import (
    ColumnDefaultConstraint as Default,
    ColumnNotNullConstraint as NotNull,
)
from rhosocial.activerecord.backend.expression.types import (
    BigIntType as BigInt,
    DateTimeType,
    IntegerType as Int,
    VarCharType as VarChar,
)
from rhosocial.activerecord.backend.impl.clickhouse.expression import (
    ClickHouseCreateTableOptions,
    ClickHouseEngineSpec,
    ClickHouseSetting,
    ClickHouseStorageOptionKind,
    ClickHouseTableStorageOption,
)
from rhosocial.activerecord.testsuite.core.fixture_types import supports_drop_if_exists


class Definition:
    """Base class for the pool tests' table definitions."""

    table_name = ""

    def __init__(self, dialect):
        self.dialect = dialect
        self.create_table = CreateTable(
            self.dialect,
            table=Table(self.dialect, self.table_name),
            columns=self.columns(),
            table_options=self.table_options(),
        )
        self.drop_table = DropTable(
            self.dialect,
            table=Table(self.dialect, self.table_name),
            if_exists=supports_drop_if_exists(self.dialect),
        )

    def columns(self):
        raise NotImplementedError

    def table_options(self):
        """The table's storage clause: engine, sort key and mutation settings."""
        return ClickHouseCreateTableOptions(
            self.dialect,
            table_storage_options=(
                ClickHouseTableStorageOption(
                    self.dialect,
                    ClickHouseStorageOptionKind.ENGINE,
                    value=ClickHouseEngineSpec(self.dialect, "MergeTree"),
                ),
                ClickHouseTableStorageOption(
                    self.dialect,
                    ClickHouseStorageOptionKind.ORDER_BY,
                    value=[ColumnRef(self.dialect, "id")],
                ),
                ClickHouseTableStorageOption(
                    self.dialect,
                    ClickHouseStorageOptionKind.SETTINGS,
                    value=[
                        ClickHouseSetting(self.dialect, "enable_block_number_column", 1),
                        ClickHouseSetting(self.dialect, "enable_block_offset_column", 1),
                    ],
                ),
            ),
        )

    def column(self, name, sql_type, constraints=None):
        return Column(self.dialect, name, sql_type, constraints=constraints or [])

    def not_null(self, name, sql_type):
        return self.column(
            name,
            sql_type,
            [Constraint(self.dialect, branch=NotNull(self.dialect))],
        )

    def id(self):
        return self.column("id", BigInt(self.dialect))

    def thread_id(self):
        return self.column("thread_id", Int(self.dialect))

    def created_at(self):
        return self.column(
            "created_at",
            DateTimeType(self.dialect),
            constraints=[
                Constraint(self.dialect, branch=NotNull(self.dialect)),
                Constraint(self.dialect, branch=Default(self.dialect, now(self.dialect))),
            ],
        )


class ConcurrentTestUsersDefinition(Definition):
    """The synchronized users table."""

    table_name = "concurrent_test_users"

    def columns(self):
        return [
            self.id(),
            self.thread_id(),
            self.not_null("name", VarChar(self.dialect, 255)),
            self.created_at(),
        ]


class ConcurrentTestPostsDefinition(Definition):
    """The synchronized posts table."""

    table_name = "concurrent_test_posts"

    def columns(self):
        return [
            self.id(),
            self.thread_id(),
            self.not_null("user_id", BigInt(self.dialect)),
            self.not_null("title", VarChar(self.dialect, 255)),
            self.not_null("content", VarChar(self.dialect, 255)),
        ]

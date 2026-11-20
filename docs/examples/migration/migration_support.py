# docs/examples/migration/migration_support.py
"""Shared, importable pieces for the ClickHouse migration examples.

Kept in a module with a normal (non-numeric) name so both the ``migrate`` and
``named-migration`` entry points can resolve fully qualified names:

* ``migration_support:create_events``      (function style, ``module:function``)
* ``migration_support.CreateEventsTable``  (class style, ``module.Class``)

Only the synchronous APIs are used: ``clickhouse-connect`` is a sync-only driver
and ``AsyncClickHouseBackend`` is a placeholder that raises ``NotImplementedError``.
"""

from typing import Annotated, Optional

from rhosocial.activerecord.base import UseSqlType
from rhosocial.activerecord.backend.impl.clickhouse.expression import (
    ClickHouseInt64Type,
    ClickHouseStringType,
)
from rhosocial.activerecord.backend.migration import (
    MigrationContext,
    MigrationDirection,
    NamedMigration,
    migration,
)
from rhosocial.activerecord.model import ActiveRecord


class MigrationEvent(ActiveRecord):
    """Demo model; ClickHouse has no AUTO_INCREMENT, so the id is a client-side Int64."""

    @classmethod
    def table_name(cls) -> str:
        return "ch_migration_events"

    id: Annotated[Optional[int], UseSqlType(ClickHouseInt64Type())] = None
    name: Annotated[str, UseSqlType(ClickHouseStringType())]


# ---- Function style (primary API) -------------------------------------------------------

@migration("f001_create_events", description="create the ch_migration_events table")
def create_events(ctx):
    """UP creates the table; DOWN is an explicit compensating DROP (DDL cannot roll back)."""
    if ctx.direction == MigrationDirection.UP:
        ctx.apply(MigrationEvent.create_table_statement(backend=ctx.backend))
    else:
        ctx.apply(MigrationEvent.drop_table_statement(if_exists=True, backend=ctx.backend))


# ---- Class style (legacy-compatible) ----------------------------------------------------

class CreateEventsTable(NamedMigration):
    """The same schema change expressed as a ``NamedMigration`` subclass."""

    version = "c001_create_events"

    def up(self, ctx: MigrationContext) -> None:
        ctx.apply(MigrationEvent.create_table_statement(backend=ctx.backend))

    def down(self, ctx: MigrationContext) -> None:
        ctx.apply(MigrationEvent.drop_table_statement(if_exists=True, backend=ctx.backend))

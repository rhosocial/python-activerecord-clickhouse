# tests/providers/fixtures/_common.py
"""Shared helpers for the ClickHouse DDL expression fixtures.

The storage clauses ClickHouse appends to ``CREATE TABLE`` are declared as
expression nodes -- one :class:`ClickHouseTableStorageOption` per clause, on a
:class:`ClickHouseCreateTableOptions` -- so the rendered DDL is already
ClickHouse spelling: unquoted engine and sort-key values, clauses in grammar
order. :func:`default_table_options` is the single place the shared clause run
is built; a fixture whose sort key differs passes ``order_by``.

What the core renderer still emits and ClickHouse rejects is removed here:
``AUTO_INCREMENT``, ``UNIQUE`` and ``FOREIGN KEY`` -- the reference schemas
declare them and ClickHouse has no such constraints. ``ON DELETE`` /
``ON UPDATE`` referential actions are re-injected onto inline foreign keys
before the constraint columns are stripped, keeping the DDL equivalent to the
reference ``.sql`` files under
``tests/rhosocial/activerecord_clickhouse_test/feature/<feature>/schema/``.

Providers call :func:`create_table_sql` instead of ``expr.to_sql()`` directly
to obtain the canonical ``(sql, params)`` tuple.
"""

from __future__ import annotations

import re
from typing import Sequence, Tuple

from rhosocial.activerecord.backend.expression import (
    Column,
    CreateTableStatement,
    DropTableStatement,
)
from rhosocial.activerecord.backend.expression.objects import Table
from rhosocial.activerecord.backend.expression.statements import ReferentialAction

from rhosocial.activerecord.backend.impl.clickhouse.expression import (
    ClickHouseCreateTableOptions,
    ClickHouseEngineSpec,
    ClickHouseSetting,
    ClickHouseStorageOptionKind,
    ClickHouseTableStorageOption,
)

_FK_RE = re.compile(
    r"(FOREIGN KEY \([`A-Za-z0-9_ ,]+\) REFERENCES [`A-Za-z0-9_.]+ \([`A-Za-z0-9_ ,]+\))"
    r"(?=[,)])"
)
# Remove AUTO_INCREMENT, UNIQUE, and FOREIGN KEY constraints that ClickHouse rejects
_AUTOINC_RE = re.compile(r" AUTO_INCREMENT", re.IGNORECASE)
_UNIQUE_RE = re.compile(r"\s+UNIQUE", re.IGNORECASE)
_FOREIGN_KEY_COL_RE = re.compile(
    r",\s+FOREIGN KEY \([`A-Za-z0-9_ ,]+\) REFERENCES [`A-Za-z0-9_.]+ \([`A-Za-z0-9_ ,]+\)"
    r"( ON DELETE \w+)?( ON UPDATE \w+)?",
    re.IGNORECASE,
)


def default_table_options(
    dialect,
    *,
    order_by: Sequence[str] = ("id",),
) -> ClickHouseCreateTableOptions:
    """The clause run every fixture table shares.

    ``ENGINE = MergeTree`` and the two lightweight-update settings are the
    same everywhere; only the sort key varies, so it is the one argument.
    """
    return ClickHouseCreateTableOptions(
        dialect,
        table_storage_options=[
            ClickHouseTableStorageOption(
                dialect,
                ClickHouseStorageOptionKind.ENGINE,
                value=ClickHouseEngineSpec(dialect, "MergeTree"),
            ),
            ClickHouseTableStorageOption(
                dialect,
                ClickHouseStorageOptionKind.ORDER_BY,
                value=[Column(dialect, name) for name in order_by],
            ),
            ClickHouseTableStorageOption(
                dialect,
                ClickHouseStorageOptionKind.SETTINGS,
                value=[
                    ClickHouseSetting(dialect, "enable_block_number_column", 1),
                    ClickHouseSetting(dialect, "enable_block_offset_column", 1),
                ],
            ),
        ],
    )


def _append_fk_actions(expr: CreateTableStatement, sql: str) -> str:
    """Append ``ON DELETE`` / ``ON UPDATE`` clauses to inline FK constraints.

    The ClickHouse dialect's ``format_table_constraint`` does not currently emit
    referential actions even though :class:`ForeignKeyConstraint` carries them.
    This helper re-injects them so the generated DDL matches the reference SQL
    files that use ``ON DELETE CASCADE``.
    """
    # Build a lookup of "FOREIGN KEY (cols) REFERENCES ref_table (ref_cols)"
    # -> suffix to append for each matching constraint.
    fk_suffix_by_clause: dict = {}
    for t_const in expr.table_constraints:
        from rhosocial.activerecord.backend.expression.statements import (
            ForeignKeyConstraint,
            TableForeignKeyConstraint,
        )

        # S3: the kind is the branch class now; ``constraint_type`` is gone as a
        # field and what the production keeps in its place raises AttributeError.
        branch = getattr(t_const, "branch", None)
        if not isinstance(branch, TableForeignKeyConstraint):
            continue
        if not isinstance(t_const, ForeignKeyConstraint):
            continue
        cols = ", ".join(f"`{c}`" for c in (branch.columns or []))
        ref_table_obj, ref_columns = branch.references
        ref_cols = ", ".join(f"`{c}`" for c in (ref_columns or []))
        ref_table = f"`{ref_table_obj}`"
        clause = f"FOREIGN KEY ({cols}) REFERENCES {ref_table} ({ref_cols})"
        suffix_parts = []
        on_delete = getattr(branch, "on_delete", None)
        on_update = getattr(branch, "on_update", None)
        if on_delete and on_delete != ReferentialAction.NO_ACTION:
            suffix_parts.append(f"ON DELETE {on_delete.value}")
        if on_update and on_update != ReferentialAction.NO_ACTION:
            suffix_parts.append(f"ON UPDATE {on_update.value}")
        if suffix_parts:
            fk_suffix_by_clause[clause] = " " + " ".join(suffix_parts)

    def repl(match: re.Match) -> str:
        return match.group(1) + fk_suffix_by_clause.get(match.group(1), "")

    return _FK_RE.sub(repl, sql)


def to_clickhouse_ddl_sql(expr: CreateTableStatement) -> Tuple[str, tuple]:
    """Generate canonical ClickHouse DDL for a :class:`CreateTableStatement`.

    Post-processes the dialect output to:
    1. Re-insert ``ON DELETE`` / ``ON UPDATE`` referential actions for
       inline ``FOREIGN KEY`` table constraints.
    2. Remove ``AUTO_INCREMENT``, ``UNIQUE``, and ``FOREIGN KEY`` clauses
       that ClickHouse does not support.

    Returns the ``(sql, params)`` tuple suitable for ``backend.execute``.
    """
    sql, params = expr.to_sql()
    sql = _append_fk_actions(expr, sql)
    sql = _AUTOINC_RE.sub("", sql)
    sql = _UNIQUE_RE.sub("", sql)
    sql = _FOREIGN_KEY_COL_RE.sub("", sql)
    return sql, params


def create_table_sql(expr: CreateTableStatement) -> Tuple[str, tuple]:
    """Public alias for :func:`to_clickhouse_ddl_sql`."""
    return to_clickhouse_ddl_sql(expr)


def drop_table(dialect, table_name: str) -> DropTableStatement:
    """Build a canonical ``DROP TABLE IF EXISTS`` expression."""
    return DropTableStatement(
        dialect=dialect,
        table=Table(dialect, table_name),
        if_exists=True,
    )

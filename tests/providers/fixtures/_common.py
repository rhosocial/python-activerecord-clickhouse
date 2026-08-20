# tests/providers/fixtures/_common.py
"""Shared helpers for the ClickHouse DDL expression fixtures.

The ClickHouse backend's :meth:`format_storage_options` quotes string option
values (``ENGINE='InnoDB'``) and :meth:`format_table_constraint` does not
emit ``ON DELETE`` / ``ON UPDATE`` referential actions for
:class:`ForeignKeyConstraint` instances.  The authoritative ``.sql`` schema
files under ``tests/rhosocial/activerecord_clickhouse_test/feature/<feature>/schema/``
use the unquoted storage form and inline ``FOREIGN KEY ... ON DELETE CASCADE``
clauses.

Rather than modifying the ClickHouse backend library source (which is out of
scope for this refactor), :func:`to_clickhouse_ddl_sql` post-processes the SQL
produced by ``CreateTableExpression.to_sql()`` so that the generated DDL
matches the reference files byte-for-byte for the bits that matter:

* ``KEY='value'`` storage options become ``KEY=value``.
* ``FOREIGN KEY ... REFERENCES ...`` clauses have their declared
  ``on_delete`` / ``on_update`` referential actions appended.

Providers call :func:`create_table_sql` instead of ``expr.to_sql()`` directly
to obtain the canonical ``(sql, params)`` tuple.
"""

from __future__ import annotations

import re
from typing import Tuple

from rhosocial.activerecord.backend.expression import (
    CreateTableExpression,
    DropTableExpression,
    TableExpression,
)
from rhosocial.activerecord.backend.expression.statements import ReferentialAction


_STORAGE_OPTION_RE = re.compile(r"([A-Z_ ]+=)'([^']*)'")
_FK_RE = re.compile(
    r"(FOREIGN KEY \([`A-Za-z0-9_ ,]+\) REFERENCES [`A-Za-z0-9_.]+ \([`A-Za-z0-9_ ,]+\))"
    r"(?=[,)])"
)


def _strip_storage_option_quotes(sql: str) -> str:
    """Drop single quotes around storage option values (``ENGINE='InnoDB'`` -> ``ENGINE=InnoDB``)."""
    return _STORAGE_OPTION_RE.sub(lambda m: f"{m.group(1)}{m.group(2)}", sql)


def _append_fk_actions(expr: CreateTableExpression, sql: str) -> str:
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
            TableConstraintType,
            ForeignKeyConstraint,
        )
        if t_const.constraint_type != TableConstraintType.FOREIGN_KEY:
            continue
        if not isinstance(t_const, ForeignKeyConstraint):
            continue
        cols = ", ".join(f"`{c}`" for c in (t_const.columns or []))
        ref_cols = ", ".join(f"`{c}`" for c in (t_const.foreign_key_columns or []))
        ref_table = f"`{t_const.foreign_key_table}`"
        clause = f"FOREIGN KEY ({cols}) REFERENCES {ref_table} ({ref_cols})"
        suffix_parts = []
        on_delete = getattr(t_const, "on_delete", None)
        on_update = getattr(t_const, "on_update", None)
        if on_delete and on_delete != ReferentialAction.NO_ACTION:
            suffix_parts.append(f"ON DELETE {on_delete.value}")
        if on_update and on_update != ReferentialAction.NO_ACTION:
            suffix_parts.append(f"ON UPDATE {on_update.value}")
        if suffix_parts:
            fk_suffix_by_clause[clause] = " " + " ".join(suffix_parts)

    def repl(match: re.Match) -> str:
        return match.group(1) + fk_suffix_by_clause.get(match.group(1), "")

    return _FK_RE.sub(repl, sql)


def to_clickhouse_ddl_sql(expr: CreateTableExpression) -> Tuple[str, tuple]:
    """Generate canonical ClickHouse DDL for a :class:`CreateTableExpression`.

    Post-processes the dialect output to:
    1. Drop quotes around storage option values.
    2. Re-insert ``ON DELETE`` / ``ON UPDATE`` referential actions for
       inline ``FOREIGN KEY`` table constraints.

    Returns the ``(sql, params)`` tuple suitable for ``backend.execute``.
    """
    sql, params = expr.to_sql()
    sql = _strip_storage_option_quotes(sql)
    sql = _append_fk_actions(expr, sql)
    return sql, params


def create_table_sql(expr: CreateTableExpression) -> Tuple[str, tuple]:
    """Public alias for :func:`to_clickhouse_ddl_sql`."""
    return to_clickhouse_ddl_sql(expr)


def drop_table(dialect, table_name: str) -> DropTableExpression:
    """Build a canonical ``DROP TABLE IF EXISTS`` expression."""
    return DropTableExpression(
        dialect=dialect,
        table=TableExpression(dialect, table_name),
        if_exists=True,
    )

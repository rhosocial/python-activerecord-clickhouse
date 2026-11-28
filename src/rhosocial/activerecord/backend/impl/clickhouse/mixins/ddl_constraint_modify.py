# src/rhosocial/activerecord/backend/impl/clickhouse/mixins/ddl_constraint_modify.py
"""ClickHouse ``MODIFY CONSTRAINT`` capability and formatter.

The ALTER command grammar contains exactly three constraint verbs -- ``ADD``,
``MODIFY`` and ``DROP``. ``ALTER CONSTRAINT`` is a ``Code: 62`` syntax error
(``Expected COLUMN``), so the in-place redefinition ClickHouse offers is the
``MODIFY`` spelling, measured on 26.7.3.19::

    ALTER TABLE probe_t MODIFY CONSTRAINT ck CHECK c > 100   -- accepted
    ALTER TABLE probe_t MODIFY CONSTRAINT ak ASSUME c > 0    -- accepted

Only the expression is replaced; this verb cannot add enforcement control.
"""

from typing import Tuple

from ..expression.statements.constraint_modify import (
    MODIFY_CONSTRAINT_KINDS,
    ClickHouseModifyConstraintStatement,
)


class ClickHouseModifyConstraintMixin:
    """Capability probe and the ``MODIFY CONSTRAINT`` formatter."""

    def supports_modify_constraint(self) -> bool:
        """True: ClickHouse redefines a constraint with ``MODIFY CONSTRAINT``.

        Measured on 26.7.3.19 (see the module docstring): both ``CHECK`` and
        ``ASSUME`` are accepted and ``system.constraints`` re-reads the new
        expression. The sibling probe :meth:`supports_alter_constraint` stays
        ``False`` because it names the SQL ``ALTER CONSTRAINT`` verb, which this
        grammar rejects -- two different spellings, two different answers.
        """
        return True

    def format_clickhouse_modify_constraint_statement(
        self, expr: "ClickHouseModifyConstraintStatement"
    ) -> Tuple[str, tuple]:
        """Render ``ALTER TABLE <t> MODIFY CONSTRAINT <name> <kind> <condition>``.

        Validation lives here: the kind must be ``CHECK`` or ``ASSUME``, the
        table and constraint name must be non-empty, and the condition is
        rendered inline because DDL carries no bind parameters. A condition
        that yields parameters is refused rather than silently inlined. Every
        one of those checks describes a caller defect, so each raises
        ``TypeError``; only the capability probe below raises
        ``UnsupportedFeatureError``.
        """
        from rhosocial.activerecord.backend.dialect.exceptions import (
            UnsupportedFeatureError,
        )

        if not isinstance(expr, ClickHouseModifyConstraintStatement):
            raise TypeError(
                "format_clickhouse_modify_constraint_statement requires a "
                f"ClickHouseModifyConstraintStatement, got {type(expr).__name__}"
            )
        if not self.supports_modify_constraint():
            raise UnsupportedFeatureError(
                self.name,
                "ALTER TABLE MODIFY CONSTRAINT",
                "This dialect does not render MODIFY CONSTRAINT.",
            )
        kind = expr.kind.upper() if isinstance(expr.kind, str) else expr.kind
        if kind not in MODIFY_CONSTRAINT_KINDS:
            raise TypeError(
                f"unknown constraint kind {expr.kind!r}; expected one of "
                f"{MODIFY_CONSTRAINT_KINDS}"
            )
        if not isinstance(expr.table, str) or not expr.table.strip():
            raise TypeError("MODIFY CONSTRAINT requires a non-empty table name")
        if not isinstance(expr.name, str) or not expr.name.strip():
            raise TypeError("MODIFY CONSTRAINT requires a non-empty constraint name")
        if expr.condition is None:
            raise TypeError("MODIFY CONSTRAINT requires a condition expression")

        condition_sql, condition_params = expr.condition.to_sql()
        if condition_params:
            raise TypeError(
                "MODIFY CONSTRAINT takes no bind parameters: the condition must "
                "render inline (DDL has no parameter slot)"
            )

        from rhosocial.activerecord.backend.expression.objects import Table

        table_sql, _ = self.format_table_object(
            Table(self, expr.table, catalog_name=expr.schema)
        )
        name_sql = self.format_identifier(expr.name)
        return (
            f"ALTER TABLE {table_sql} MODIFY CONSTRAINT {name_sql} {kind} {condition_sql}",
            (),
        )

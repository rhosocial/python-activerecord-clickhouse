# src/rhosocial/activerecord/backend/impl/clickhouse/mixins/truncate.py
from typing import TYPE_CHECKING, Tuple

from rhosocial.activerecord.backend.dialect.exceptions import UnsupportedFeatureError
from rhosocial.activerecord.backend.expression.objects import Table

if TYPE_CHECKING:  # pragma: no cover
    from rhosocial.activerecord.backend.expression.statements.ddl_truncate import (
        TruncateExpression,
    )


class ClickHouseTruncateMixin:
    """ClickHouse TRUNCATE TABLE support.

    ClickHouse syntax is ``TRUNCATE [TABLE] tbl_name``. Unlike PostgreSQL,
    ClickHouse does not support RESTART IDENTITY, CONTINUE IDENTITY, CASCADE
    or RESTRICT; each is refused by name rather than dropped.
    """

    def supports_truncate(self) -> bool:
        return True

    def supports_truncate_table_keyword(self) -> bool:
        return True

    def supports_truncate_restart_identity(self) -> bool:
        return False

    def supports_truncate_cascade(self) -> bool:
        return False

    def supports_truncate_restrict(self) -> bool:
        """ClickHouse TRUNCATE has no RESTRICT spelling (measured: Code 62)."""
        return False

    def format_truncate_statement(self, expr: "TruncateExpression") -> Tuple[str, tuple]:
        """Format ClickHouse ``TRUNCATE [TABLE] tbl_name``.

        Raises:
            TypeError: ``expr.table`` is not a Table. Any other object kind
                carries its own ``format_method``, so the dialect would render a
                well-formed ``TRUNCATE TABLE`` over e.g. an index's name.
            UnsupportedFeatureError: ``RESTART IDENTITY``, ``CONTINUE IDENTITY``,
                ``CASCADE`` or ``RESTRICT``, none of which ClickHouse has.
        """
        if not isinstance(expr.table, Table):
            raise TypeError(
                f"TruncateExpression.table must be a Table, "
                f"got {type(expr.table).__name__}"
            )
        if expr.restart_identity or expr.continue_identity:
            raise UnsupportedFeatureError(
                self.name,
                "TRUNCATE ... RESTART IDENTITY"
                if expr.restart_identity
                else "TRUNCATE ... CONTINUE IDENTITY",
                suggestion=(
                    "ClickHouse TRUNCATE does not support RESTART IDENTITY; drop the option."
                    if expr.restart_identity
                    else "ClickHouse TRUNCATE does not support CONTINUE IDENTITY; drop the option."
                ),
            )
        if expr.cascade or expr.restrict:
            raise UnsupportedFeatureError(
                self.name,
                "TRUNCATE ... CASCADE" if expr.cascade else "TRUNCATE ... RESTRICT",
                suggestion=(
                    "ClickHouse does not support CASCADE on TRUNCATE."
                    if expr.cascade
                    else "ClickHouse does not support RESTRICT on TRUNCATE."
                ),
            )
        sql = f"TRUNCATE TABLE {expr.table.to_sql()[0]}"
        return sql, ()

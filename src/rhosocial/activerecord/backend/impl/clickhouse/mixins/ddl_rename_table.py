# src/rhosocial/activerecord/backend/impl/clickhouse/mixins/rename_table.py
from typing import TYPE_CHECKING, Tuple

if TYPE_CHECKING:  # pragma: no cover
    from rhosocial.activerecord.backend.impl.clickhouse.expression.rename_table import (
        ClickHouseRenameTableExpression,
    )


class ClickHouseRenameTableMixin:
    """ClickHouse RENAME TABLE support.

    ClickHouse supports atomic multi-table renames:

        RENAME TABLE t1 TO t2 [, t3 TO t4, ...]
    """

    def supports_rename_table(self) -> bool:
        return True

    def supports_multi_table_rename(self) -> bool:
        return True

    def format_rename_table_statement(
        self,
        expr: "ClickHouseRenameTableExpression",
    ) -> Tuple[str, tuple]:
        """Format a ClickHouse ``RENAME TABLE ...`` statement."""
        expr.validate(strict=self.strict_validation)

        parts = ["RENAME TABLE"]
        pairs = []
        for old_name, new_name in expr.renames:
            pairs.append(
                f"{self.format_identifier(old_name)} TO {self.format_identifier(new_name)}"
            )
        parts.append(", ".join(pairs))
        return " ".join(parts), ()
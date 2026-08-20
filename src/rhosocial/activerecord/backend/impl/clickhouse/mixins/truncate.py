# src/rhosocial/activerecord/backend/impl/clickhouse/mixins/truncate.py
from typing import TYPE_CHECKING, Tuple

from rhosocial.activerecord.backend.dialect.exceptions import UnsupportedFeatureError

if TYPE_CHECKING:  # pragma: no cover
    from rhosocial.activerecord.backend.expression.statements.ddl_truncate import (
        TruncateExpression,
    )


class ClickHouseTruncateMixin:
    """ClickHouse TRUNCATE TABLE support.

    ClickHouse 8.0 syntax is ``TRUNCATE [TABLE] tbl_name``. Unlike PostgreSQL,
    ClickHouse does not support RESTART IDENTITY or CASCADE, and a successful
    TRUNCATE always resets AUTO_INCREMENT counters.
    """

    def supports_truncate(self) -> bool:
        return True

    def supports_truncate_table_keyword(self) -> bool:
        return True

    def supports_truncate_restart_identity(self) -> bool:
        return False

    def supports_truncate_cascade(self) -> bool:
        return False

    def format_truncate_statement(self, expr: "TruncateExpression") -> Tuple[str, tuple]:
        """Format ClickHouse ``TRUNCATE [TABLE] tbl_name``."""
        if expr.restart_identity:
            raise UnsupportedFeatureError(
                self.name,
                "TRUNCATE ... RESTART IDENTITY",
                suggestion="ClickHouse TRUNCATE always resets AUTO_INCREMENT; drop the option.",
            )
        if expr.cascade:
            raise UnsupportedFeatureError(
                self.name,
                "TRUNCATE ... CASCADE",
                suggestion="ClickHouse does not support CASCADE on TRUNCATE.",
            )
        sql = f"TRUNCATE TABLE {self.format_identifier(expr.table_name)}"
        return sql, ()
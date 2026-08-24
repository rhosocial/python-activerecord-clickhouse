# src/rhosocial/activerecord/backend/impl/clickhouse/mixins/table_statement.py
from typing import Any, Tuple

from rhosocial.activerecord.backend.dialect.exceptions import UnsupportedFeatureError


class ClickHouseTableStatementMixin:
    """ClickHouse does not support the MySQL 8.0.19 ``TABLE`` / ``VALUES``
    table-value-constructor statements.

    ClickHouse exposes equivalent functionality through ``SELECT * FROM
    <table>`` and explicit ``SELECT ... UNION ALL ...`` row constructors.
    All methods fail fast.
    """

    def supports_table_statement(self) -> bool:
        return False

    def supports_values_table_constructor(self) -> bool:
        return False

    def format_table_statement(self, expr: Any) -> Tuple[str, tuple]:
        raise UnsupportedFeatureError(
            self.name, "TABLE statement",
            suggestion="Use SELECT * FROM <table> instead of TABLE.",
        )

    def format_values_statement(self, expr: Any) -> Tuple[str, tuple]:
        raise UnsupportedFeatureError(
            self.name, "VALUES table value constructor",
            suggestion="Use SELECT ... UNION ALL SELECT ... for row constructors.",
        )

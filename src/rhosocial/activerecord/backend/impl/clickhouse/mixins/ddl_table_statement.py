# src/rhosocial/activerecord/backend/impl/clickhouse/mixins/ddl_table_statement.py
from typing import Any, Tuple

from rhosocial.activerecord.backend.dialect.exceptions import UnsupportedFeatureError


class ClickHouseTableStatementMixin:
    """ClickHouse does not support the MySQL 8.0.19 ``TABLE`` / ``VALUES``
    table-value-constructor statements.

    ClickHouse exposes equivalent functionality through ``SELECT * FROM
    <table>`` and explicit ``SELECT ... UNION ALL ...`` row constructors.
    All methods fail fast.

    Measured on 26.7.3: ClickHouse has a ``values`` *table function*, so
    ``SELECT * FROM VALUES(1, 2)`` is accepted -- but that is a different
    shape from the SQL standard's table value constructor, which is
    ``VALUES (1), (2)``, and the standard spelling is a syntax error there
    ("failed at position 21"). The framework renders the standard shape, so
    the answer is False: the capability is not the one this probe asks
    about.
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

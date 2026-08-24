# src/rhosocial/activerecord/backend/impl/clickhouse/mixins/dml.py
from typing import Tuple

from rhosocial.activerecord.backend.dialect.exceptions import UnsupportedFeatureError


class ClickHouseDMLOperationMixin:
    """ClickHouse DML operations mixin.

    ClickHouse does not support INSERT IGNORE, REPLACE INTO, LOAD DATA,
    or ON DUPLICATE KEY UPDATE. All supports_* methods return False and
    format methods raise UnsupportedFeatureError.
    """

    def supports_insert_ignore(self) -> bool:
        return False

    def supports_replace_into(self) -> bool:
        return False

    def supports_load_data(self) -> bool:
        return False

    def format_load_data_statement(self, expr) -> Tuple[str, tuple]:
        raise UnsupportedFeatureError(
            self.name, "LOAD DATA",
            suggestion="ClickHouse does not support LOAD DATA INFILE; use INSERT or clickhouse-client --query."
        )

    def format_on_conflict_clause(self, expr) -> Tuple[str, tuple]:
        raise UnsupportedFeatureError(
            self.name, "ON DUPLICATE KEY UPDATE",
            suggestion=(
                "ClickHouse does not support ON DUPLICATE KEY UPDATE; "
                "use INSERT with ReplacingMergeTree or other merge mechanisms."
            ),
        )
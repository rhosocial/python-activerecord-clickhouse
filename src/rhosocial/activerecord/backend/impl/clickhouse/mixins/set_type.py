# src/rhosocial/activerecord/backend/impl/clickhouse/mixins/set_type.py
from typing import Any, List, Optional, Tuple

from rhosocial.activerecord.backend.dialect.exceptions import UnsupportedFeatureError


class ClickHouseSetTypeMixin:
    """ClickHouse does not support the MySQL ``SET`` type.

    ClickHouse has no ``SET`` column type and no ``FIND_IN_SET`` function.
    Use ``Enum16``/``LowCardinality(String)`` or an ``Array(String)`` column
    instead. All methods fail fast.
    """

    def supports_set_type(self) -> bool:
        return False

    def format_set_literal(
        self,
        values: List[str],
        column_values: Optional[List[str]] = None,
    ) -> Tuple[str, tuple]:
        raise UnsupportedFeatureError(
            self.name, "SET type",
            suggestion="ClickHouse has no SET type; use Enum16 or Array(String).",
        )

    def format_find_in_set(self, value: str, set_column: str) -> Tuple[str, tuple]:
        raise UnsupportedFeatureError(
            self.name, "FIND_IN_SET",
            suggestion="ClickHouse has no FIND_IN_SET function; use has() or indexOf().",
        )

    def format_set_contains(self, column: str, values: List[str]) -> Tuple[str, tuple]:
        raise UnsupportedFeatureError(
            self.name, "SET type",
            suggestion="ClickHouse has no SET type; use Array has() instead.",
        )

    def format_set_any(self, expr: Any) -> Tuple[str, tuple]:
        raise UnsupportedFeatureError(
            self.name, "SET type",
            suggestion="ClickHouse has no SET type.",
        )

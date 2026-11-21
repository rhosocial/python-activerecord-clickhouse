# src/rhosocial/activerecord/backend/impl/clickhouse/mixins/set_type.py
from typing import Any, Tuple

from rhosocial.activerecord.backend.dialect.exceptions import UnsupportedFeatureError


class ClickHouseSetTypeMixin:
    """ClickHouse does not support the MySQL ``SET`` type.

    ClickHouse has no ``SET`` column type and no ``FIND_IN_SET`` function.
    Use ``Enum16``/``LowCardinality(String)`` or an ``Array(String)`` column
    instead. All methods fail fast.
    """

    def supports_set_type(self) -> bool:
        return False

    def format_set_any(self, expr: Any) -> Tuple[str, tuple]:
        raise UnsupportedFeatureError(
            self.name, "SET type",
            suggestion="ClickHouse has no SET type.",
        )

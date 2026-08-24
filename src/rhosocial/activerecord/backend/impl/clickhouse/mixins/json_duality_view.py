# src/rhosocial/activerecord/backend/impl/clickhouse/mixins/json_duality_view.py
from typing import Any, Tuple

from rhosocial.activerecord.backend.dialect.exceptions import UnsupportedFeatureError


class ClickHouseJsonDualityViewMixin:
    """ClickHouse does not support JSON Relational Duality Views.

    JSON Duality Views are an Oracle/MySQL feature. ClickHouse exposes JSON
    data through the ``JSON`` type and the ``JSONExtract*`` function family.
    All methods fail fast.
    """

    def supports_json_duality_view(self) -> bool:
        return False

    def supports_json_duality_view_dml(self) -> bool:
        return False

    def format_create_json_duality_view_statement(self, expr: Any) -> Tuple[str, tuple]:
        raise UnsupportedFeatureError(
            self.name, "JSON Duality Views",
            suggestion="ClickHouse has no JSON Duality Views; use JSON type + JSONExtract* functions.",
        )

    def format_drop_json_duality_view_statement(self, expr: Any) -> Tuple[str, tuple]:
        raise UnsupportedFeatureError(
            self.name, "JSON Duality Views",
            suggestion="ClickHouse has no JSON Duality Views.",
        )

    def format_duality_object_select(self, spec: Any) -> str:
        raise UnsupportedFeatureError(
            self.name, "JSON Duality Views",
            suggestion="ClickHouse has no JSON Duality Views.",
        )

    def format_duality_object_body(self, spec: Any) -> str:
        raise UnsupportedFeatureError(
            self.name, "JSON Duality Views",
            suggestion="ClickHouse has no JSON Duality Views.",
        )

    def format_nested_duality(self, nested: Any) -> str:
        raise UnsupportedFeatureError(
            self.name, "JSON Duality Views",
            suggestion="ClickHouse has no JSON Duality Views.",
        )

# src/rhosocial/activerecord/backend/impl/clickhouse/mixins/json_duality_view.py
from typing import TYPE_CHECKING, Any, Tuple

from rhosocial.activerecord.backend.dialect.exceptions import UnsupportedFeatureError

if TYPE_CHECKING:
    from rhosocial.activerecord.backend.impl.clickhouse.expression.json_duality_view import (
        ClickHouseCreateJsonDualityViewStatement,
        ClickHouseDropJsonDualityViewStatement,
    )


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

    def format_clickhouse_create_json_duality_view_statement(
        self, expr: "ClickHouseCreateJsonDualityViewStatement"
    ) -> Tuple[str, tuple]:
        raise UnsupportedFeatureError(
            self.name,
            "JSON Duality Views",
            suggestion="ClickHouse has no JSON Duality Views; use JSON type + JSONExtract* functions.",
        )

    def format_clickhouse_drop_json_duality_view_statement(
        self, expr: "ClickHouseDropJsonDualityViewStatement"
    ) -> Tuple[str, tuple]:
        raise UnsupportedFeatureError(
            self.name,
            "JSON Duality Views",
            suggestion="ClickHouse has no JSON Duality Views.",
        )

    def _refuse_duality_object_select(self, expr: Any) -> str:
        raise UnsupportedFeatureError(
            self.name,
            "JSON Duality Views",
            suggestion="ClickHouse has no JSON Duality Views.",
        )

    def _refuse_duality_object_body(self, expr: Any) -> str:
        raise UnsupportedFeatureError(
            self.name,
            "JSON Duality Views",
            suggestion="ClickHouse has no JSON Duality Views.",
        )

    def _refuse_nested_duality(self, expr: Any) -> str:
        raise UnsupportedFeatureError(
            self.name,
            "JSON Duality Views",
            suggestion="ClickHouse has no JSON Duality Views.",
        )

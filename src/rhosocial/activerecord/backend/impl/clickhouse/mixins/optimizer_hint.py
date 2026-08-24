# src/rhosocial/activerecord/backend/impl/clickhouse/mixins/optimizer_hint.py
from typing import Any, Tuple

from rhosocial.activerecord.backend.dialect.exceptions import UnsupportedFeatureError


class ClickHouseOptimizerHintMixin:
    """ClickHouse does not support MySQL-style optimizer hints.

    ClickHouse does not implement ``/*+ SET_VAR(...) */`` optimizer hints.
    Query tuning is done via ``SETTINGS`` clauses on each statement instead.
    All methods fail fast.
    """

    def supports_optimizer_hint(self) -> bool:
        return False

    def supports_hypergraph_optimizer(self) -> bool:
        return False

    def format_optimizer_hint(self, expr: Any) -> Tuple[str, tuple]:
        raise UnsupportedFeatureError(
            self.name, "optimizer hints",
            suggestion="ClickHouse does not support /*+ SET_VAR */ hints; use SETTINGS.",
        )

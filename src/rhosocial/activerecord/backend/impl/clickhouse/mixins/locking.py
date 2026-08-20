# src/rhosocial/activerecord/backend/impl/clickhouse/mixins/locking.py
from typing import Tuple

from rhosocial.activerecord.backend.dialect.exceptions import UnsupportedFeatureError


class ClickHouseLockingMixin:
    """ClickHouse row-level locking mixin.

    ClickHouse does not support FOR SHARE, NOWAIT, or SKIP LOCKED.
    All supports_* methods return False and format methods raise
    UnsupportedFeatureError.
    """

    def supports_for_share(self) -> bool:
        return False

    def supports_for_update_nowait(self) -> bool:
        return False

    def supports_for_update_skip_locked(self) -> bool:
        return False

    def format_for_update_clause(self, clause) -> Tuple[str, tuple]:
        raise UnsupportedFeatureError(
            self.name, "FOR UPDATE / FOR SHARE / NOWAIT / SKIP LOCKED",
            suggestion="ClickHouse does not support row-level locking clauses."
        )
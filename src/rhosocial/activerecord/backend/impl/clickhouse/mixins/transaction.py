# src/rhosocial/activerecord/backend/impl/clickhouse/mixins/transaction.py
import logging
from typing import Dict, Optional, Tuple

from rhosocial.activerecord.backend.transaction import IsolationLevel


class ClickHouseTransactionMixin:
    """ClickHouse transaction common functionality."""

    _ISOLATION_LEVELS: Dict[IsolationLevel, str] = {
        IsolationLevel.READ_UNCOMMITTED: "READ UNCOMMITTED",
        IsolationLevel.READ_COMMITTED: "READ COMMITTED",
        IsolationLevel.REPEATABLE_READ: "REPEATABLE READ",
        IsolationLevel.SERIALIZABLE: "SERIALIZABLE",
    }

    @property
    def isolation_level(self) -> Optional[IsolationLevel]:
        """Get current transaction isolation level."""
        return self._isolation_level

    @isolation_level.setter
    def isolation_level(self, level: Optional[IsolationLevel]):
        """Set transaction isolation level."""
        from rhosocial.activerecord.backend.transaction import IsolationLevelError

        self.log(logging.DEBUG, f"Setting isolation level to {level}")
        if self.is_active:
            self.log(logging.ERROR, "Cannot change isolation level during active transaction")
            raise IsolationLevelError("Cannot change isolation level during active transaction")

        if level is not None and level not in self._ISOLATION_LEVELS:
            error_msg = f"Unsupported isolation level: {level}"
            self.log(logging.ERROR, error_msg)
            raise IsolationLevelError(error_msg)

        self._isolation_level = level
        self.log(logging.INFO, f"Isolation level set to {level}")

    def _build_set_isolation_sql(self, level: IsolationLevel) -> Tuple[str, tuple]:
        """Build SET TRANSACTION ISOLATION LEVEL SQL statement."""
        from rhosocial.activerecord.backend.transaction import IsolationLevelError

        level_str = self._ISOLATION_LEVELS.get(level)
        if not level_str:
            raise IsolationLevelError(f"Unsupported isolation level: {level}")
        return f"SET TRANSACTION ISOLATION LEVEL {level_str}", ()

    def supports_transaction_mode(self) -> bool:
        """ClickHouse does not support transactions."""
        return False

    def supports_isolation_level_in_begin(self) -> bool:
        return False

    def supports_read_only_transaction(self) -> bool:
        return False

    def supports_deferrable_transaction(self) -> bool:
        return False

    def supports_savepoint(self) -> bool:
        return False

    def format_set_transaction(self, expr) -> Tuple[str, tuple]:
        """ClickHouse does not support transactions."""
        from rhosocial.activerecord.backend.dialect.exceptions import UnsupportedFeatureError

        raise UnsupportedFeatureError(
            self.name, "transactions",
            "ClickHouse does not support SET TRANSACTION."
        )

    def format_begin_transaction(self, expr) -> Tuple[str, tuple]:
        """ClickHouse does not support transactions."""
        from rhosocial.activerecord.backend.dialect.exceptions import UnsupportedFeatureError

        raise UnsupportedFeatureError(
            self.name, "transactions",
            "ClickHouse does not support START TRANSACTION."
        )

# src/rhosocial/activerecord/backend/impl/clickhouse/transaction.py
"""ClickHouse synchronous transaction manager implementation.

ClickHouse does not support ACID transactions in the general backend protocol.
Only experimental, asynchronous transactions are available (and not on ClickHouse
Cloud), so the backend fails fast when a transaction is requested.
"""

import logging
from typing import TYPE_CHECKING, Optional

from rhosocial.activerecord.backend.transaction import (
    TransactionManager,
)

from .mixins import ClickHouseTransactionMixin

if TYPE_CHECKING:
    from .backend import ClickHouseBackend


class ClickHouseTransactionManager(ClickHouseTransactionMixin, TransactionManager):
    """ClickHouse synchronous transaction manager implementation.

    ClickHouse does not support ACID transactions. Attempting to begin a
    transaction raises UnsupportedFeatureError.
    """

    def __init__(
        self,
        backend: "ClickHouseBackend",
        logger: Optional[logging.Logger] = None,
    ) -> None:
        """Initialize ClickHouse transaction manager.

        Args:
            backend: ClickHouseBackend instance.
            logger: Optional logger instance.
        """
        super().__init__(backend, logger)

    def _do_begin(self) -> None:
        """Begin a new transaction is not supported in ClickHouse."""
        from rhosocial.activerecord.backend.dialect.exceptions import UnsupportedFeatureError

        raise UnsupportedFeatureError(
            "ClickHouse",
            "transactions",
            "ClickHouse does not support ACID transactions.",
        )

    def _do_commit(self) -> None:
        """Commit is not supported in ClickHouse."""
        from rhosocial.activerecord.backend.dialect.exceptions import UnsupportedFeatureError

        raise UnsupportedFeatureError(
            "ClickHouse",
            "transactions",
            "ClickHouse does not support ACID transactions.",
        )

    def _do_rollback(self) -> None:
        """Rollback is not supported in ClickHouse."""
        from rhosocial.activerecord.backend.dialect.exceptions import UnsupportedFeatureError

        raise UnsupportedFeatureError(
            "ClickHouse",
            "transactions",
            "ClickHouse does not support ACID transactions.",
        )

    def _do_rollback_savepoint(self, savepoint: str) -> None:
        """Rollback to savepoint is not supported in ClickHouse."""
        from rhosocial.activerecord.backend.dialect.exceptions import UnsupportedFeatureError

        raise UnsupportedFeatureError(
            "ClickHouse",
            "savepoints",
            "ClickHouse does not support savepoints.",
        )

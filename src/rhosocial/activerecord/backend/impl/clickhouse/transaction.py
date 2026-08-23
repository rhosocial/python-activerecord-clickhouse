# src/rhosocial/activerecord/backend/impl/clickhouse/transaction.py
"""ClickHouse synchronous transaction manager implementation.

ClickHouse does not support ACID transactions in the general backend protocol.
Only experimental, asynchronous transactions are available (and not on ClickHouse
Cloud), so the backend fails fast when a transaction is requested.
"""

import logging
from contextlib import contextmanager
from typing import TYPE_CHECKING, Generator, Optional

from rhosocial.activerecord.backend.transaction import (
    TransactionManager,
)

from .mixins import ClickHouseTransactionMixin

if TYPE_CHECKING:
    from .backend import ClickHouseBackend


class ClickHouseTransactionManager(ClickHouseTransactionMixin, TransactionManager):
    """ClickHouse synchronous transaction manager implementation.

    ClickHouse does not support ACID transactions. Explicit ``BEGIN`` /
    ``COMMIT`` / ``ROLLBACK`` raise :class:`UnsupportedFeatureError`, while
    the :meth:`transaction` context manager degrades to a no-op so that
    generic model operations that wrap work in a transaction context (e.g.
    ``bulk_create``) continue to work without atomicity guarantees.
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

    @contextmanager
    def transaction(
        self,
        isolation_level: Optional[str] = None,
        mode: Optional[str] = None,
    ) -> Generator[None, None, None]:
        """No-op transaction context manager.

        ClickHouse does not support ACID transactions, so ``with
        manager.transaction():`` degrades to a no-op. This keeps generic
        model operations (e.g. ``bulk_create``) usable without atomicity.
        """
        yield


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

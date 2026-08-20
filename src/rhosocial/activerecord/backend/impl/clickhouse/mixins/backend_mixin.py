# src/rhosocial/activerecord/backend/impl/clickhouse/mixins/backend_mixin.py
import logging
from typing import Any, Dict, Tuple, Type

from rhosocial.activerecord.backend.type_adapter import SQLTypeAdapter


class ClickHouseBackendMixin:
    """ClickHouse backend common functionality."""

    def _register_clickhouse_adapters(self):
        """Register ClickHouse-specific type adapters."""
        from ..adapters import (
            ClickHouseBlobAdapter,
            ClickHouseBooleanAdapter,
            ClickHouseDateAdapter,
            ClickHouseDatetimeAdapter,
            ClickHouseDecimalAdapter,
            ClickHouseEnumAdapter,
            ClickHouseJSONAdapter,
            ClickHouseSetAdapter,
            ClickHouseTimeAdapter,
            ClickHouseUUIDAdapter,
        )

        clickhouse_adapters = [
            ClickHouseBlobAdapter(),
            ClickHouseBooleanAdapter(),
            ClickHouseDateAdapter(),
            ClickHouseDatetimeAdapter(self._version),
            ClickHouseDecimalAdapter(),
            ClickHouseEnumAdapter(use_int_storage=False),
            ClickHouseJSONAdapter(),
            ClickHouseSetAdapter(),
            ClickHouseTimeAdapter(),
            ClickHouseUUIDAdapter(),
        ]

        for adapter in clickhouse_adapters:
            for py_type, db_types in adapter.supported_types.items():
                for db_type in db_types:
                    self.adapter_registry.register(adapter, py_type, db_type, allow_override=True)

        self.log(logging.DEBUG, "Registered ClickHouse-specific type adapters")

    @property
    def dialect(self):
        """Get the ClickHouse dialect instance (lazy loads with configured version)."""
        from ..dialect import ClickHouseDialect

        if self._dialect is None:
            self._dialect = ClickHouseDialect(self._version)
        return self._dialect

    @property
    def transaction_manager(self):
        """Get the ClickHouse transaction manager."""
        return self._transaction_manager

    @property
    def threadsafety(self) -> int:
        """Return driver threadsafety level."""
        import clickhouse.connector

        return clickhouse.connector.threadsafety

    def requires_manual_commit(self) -> bool:
        """Check if manual commit is required for this database."""
        return not getattr(self.config, "autocommit", True)

    def _check_returning_compatibility(self, _returning_clause):
        """Check if RETURNING clause is compatible with this ClickHouse version."""
        from rhosocial.activerecord.backend.dialect.exceptions import UnsupportedFeatureError

        if self.dialect.supports_returning_clause():
            return True
        else:
            raise UnsupportedFeatureError(
                self.name,
                "RETURNING clause",
                "ClickHouse does not support RETURNING clause. Consider using LAST_INSERT_ID() or alternative approaches.",
            )

    def get_default_adapter_suggestions(self) -> Dict[Type, Tuple[SQLTypeAdapter, Type]]:
        """Provides default type adapter suggestions for ClickHouse."""
        from datetime import date, datetime, time
        from decimal import Decimal
        from uuid import UUID
        from enum import Enum

        suggestions: Dict[Type, Tuple[SQLTypeAdapter, Type]] = {}

        type_mappings = [
            (bool, int),
            (datetime, str),
            (date, str),
            (time, str),
            (Decimal, float),
            (UUID, str),
            (dict, str),
            (list, str),
            (Enum, str),
            (set, str),
            (frozenset, str),
        ]

        for py_type, db_type in type_mappings:
            adapter = self.adapter_registry.get_adapter(py_type, db_type)
            if adapter:
                suggestions[py_type] = (adapter, db_type)
            else:
                self.log(
                    logging.DEBUG,
                    f"No adapter found for ({py_type.__name__}, {db_type.__name__}). "
                    "Suggestion will not be provided for this type.",
                )

        return suggestions

    def log(self, level: int, message: str):
        """Log a message with the specified level."""
        if hasattr(self, "_logger") and self._logger:
            self._logger.log(level, message)
        else:
            print(f"[{logging.getLevelName(level)}] {message}")

    CONNECTION_ERROR_CODES = {
        2003,
        2006,
        2013,
        2048,
        2055,
    }

    def _is_connection_error(self, error: Exception) -> bool:
        """Check if an error indicates a connection loss."""
        if hasattr(error, "errno"):
            if error.errno in self.CONNECTION_ERROR_CODES:
                return True

        error_str = str(error).lower()
        connection_error_patterns = [
            "server has gone away",
            "lost connection",
            "can't connect to clickhouse server",
            "connection refused",
            "broken pipe",
            "connection reset",
        ]
        return any(pattern in error_str for pattern in connection_error_patterns)

    def _handle_error(self, error: Exception) -> None:
        """Handle ClickHouse-specific errors."""
        from clickhouse.connector.errors import (
            DatabaseError as ClickHouseDatabaseError,
            Error as ClickHouseError,
            IntegrityError as ClickHouseIntegrityError,
            OperationalError as ClickHouseOperationalError,
        )
        from rhosocial.activerecord.backend.errors import (
            DatabaseError,
            DeadlockError,
            IntegrityError,
            OperationalError,
        )

        error_msg = str(error)

        if isinstance(error, ClickHouseIntegrityError):
            if "Duplicate entry" in error_msg:
                self.log(logging.ERROR, f"Unique constraint violation: {error_msg}")
                raise IntegrityError(f"Unique constraint violation: {error_msg}")
            elif "Cannot delete or update" in error_msg or "a foreign key constraint fails" in error_msg:
                self.log(logging.ERROR, f"Foreign key constraint violation: {error_msg}")
                raise IntegrityError(f"Foreign key constraint violation: {error_msg}")
            self.log(logging.ERROR, f"Integrity error: {error_msg}")
            raise IntegrityError(error_msg)
        elif isinstance(error, ClickHouseDatabaseError):
            if "Deadlock found" in error_msg:
                self.log(logging.ERROR, f"Deadlock error: {error_msg}")
                raise DeadlockError(error_msg)
            self.log(logging.ERROR, f"Database error: {error_msg}")
            raise DatabaseError(error_msg)
        elif isinstance(error, ClickHouseOperationalError):
            if "Lock wait timeout exceeded" in error_msg:
                self.log(logging.ERROR, f"Lock timeout error: {error_msg}")
                raise OperationalError(error_msg)
            self.log(logging.ERROR, f"Operational error: {error_msg}")
            raise OperationalError(error_msg)
        elif isinstance(error, ClickHouseError):
            self.log(logging.ERROR, f"ClickHouse error: {error_msg}")
            raise DatabaseError(error_msg)
        else:
            self.log(logging.ERROR, f"Unexpected error: {error_msg}")
            raise error

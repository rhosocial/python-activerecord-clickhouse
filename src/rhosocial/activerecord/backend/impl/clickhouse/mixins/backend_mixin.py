# src/rhosocial/activerecord/backend/impl/clickhouse/mixins/backend_mixin.py
import logging
from typing import Dict, List, Optional, Tuple

from rhosocial.activerecord.backend.suggestion.definitions import (
    DataAdapterSuggestion,
    ExtraDataAdapterSuggestion,
)
from rhosocial.activerecord.backend.type_adapter import SQLTypeAdapter


class ClickHouseBackendMixin:
    """ClickHouse backend common functionality."""

    def _register_clickhouse_adapters(self):
        """Register ClickHouse-specific type adapters."""
        from ..adapters import (
            ClickHouseArrayAdapter,
            ClickHouseBitStringAdapter,
            ClickHouseBlobAdapter,
            ClickHouseBooleanAdapter,
            ClickHouseDateAdapter,
            ClickHouseDatetimeAdapter,
            ClickHouseDecimalAdapter,
            ClickHouseEnumAdapter,
            ClickHouseGeometryAdapter,
            ClickHouseIPAddressAdapter,
            ClickHouseJSONAdapter,
            ClickHouseMacAddressAdapter,
            ClickHouseRangeAdapter,
            ClickHouseSetAdapter,
            ClickHouseTimeAdapter,
            ClickHouseUUIDAdapter,
            ClickHouseVectorAdapter,
        )

        clickhouse_adapters = [
            ClickHouseBitStringAdapter(),
            ClickHouseBlobAdapter(),
            ClickHouseBooleanAdapter(),
            ClickHouseDateAdapter(),
            ClickHouseDatetimeAdapter(self._version),
            ClickHouseDecimalAdapter(),
            ClickHouseEnumAdapter(use_int_storage=False),
            ClickHouseGeometryAdapter(),
            ClickHouseIPAddressAdapter(),
            ClickHouseJSONAdapter(),
            ClickHouseMacAddressAdapter(),
            ClickHouseRangeAdapter(),
            ClickHouseSetAdapter(),
            ClickHouseTimeAdapter(),
            ClickHouseUUIDAdapter(),
            ClickHouseVectorAdapter(),
            # Registered last on purpose: it and the JSON adapter both claim
            # ``list``/``tuple`` -> ``str``, and ClickHouse binds a list as an
            # array literal, so the array adapter must win the override.
            ClickHouseArrayAdapter(),
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
        """Return driver threadsafety level.

        clickhouse-connect is not safe to share across threads without locking.
        """
        return 1

    def requires_manual_commit(self) -> bool:
        """Check if manual commit is required for this database."""
        return not getattr(self.config, "autocommit", True)

    def _check_returning_compatibility(self, _returning_clause):
        """Check if RETURNING clause is compatible with this ClickHouse version."""
        from rhosocial.activerecord.backend.dialect.exceptions import UnsupportedFeatureError

        if (self.dialect.supports_returning_insert() or
                self.dialect.supports_returning_update() or
                self.dialect.supports_returning_delete()):
            return True
        else:
            raise UnsupportedFeatureError(
                self.name,
                "RETURNING clause",
                "ClickHouse does not support RETURNING clause for UPDATE/DELETE.",
            )

    def suggest_data_adapters(self) -> DataAdapterSuggestion:
        """Provides type adapter suggestions for ClickHouse.

        Core supplies no default table: it starts from ``PORTABLE_TYPE_MAPPINGS``
        resolved against this backend's adapter registry, and ClickHouse merges
        its own pairs on top, including the neutral families it carries as
        ``String`` text (or as a ``list`` for native array columns).
        clickhouse-connect natively supports list/dict (Array/Map/Tuple), bool,
        datetime, date, time, UUID and Decimal parameters, so only the types that
        need Python-level conversion are named here.
        """
        from datetime import date, datetime, time
        from decimal import Decimal
        from enum import Enum
        from uuid import UUID

        from rhosocial.activerecord.backend.adapters.bitstring import BitString
        from rhosocial.activerecord.backend.adapters.geometry import Geometry
        from rhosocial.activerecord.backend.adapters.network import IPAddress, MacAddress
        from rhosocial.activerecord.backend.adapters.range import Multirange, Range
        from rhosocial.activerecord.backend.adapters.vector import Vector
        from rhosocial.activerecord.backend.adapters.portable import PORTABLE_TYPE_MAPPINGS
        from rhosocial.activerecord.backend.base.type_adaption import (
            merge_adapter_suggestions,
        )

        base = merge_adapter_suggestions({}, PORTABLE_TYPE_MAPPINGS, self.adapter_registry)

        type_mappings = [
            (bool, bool),
            (datetime, datetime),
            (date, date),
            (time, time),
            (Decimal, Decimal),
            (UUID, str),
            (Enum, str),
            # dict -> JSON string; list/tuple -> ClickHouse array literal.
            (dict, str),
            (list, str),
            (tuple, str),
            # Neutral families: ClickHouse has no OGC geometry, range, MAC or
            # IP column, so those are carried as text; a vector is carried as
            # JSON text on a String column and as a list on Array(Float32).
            (Geometry, str),
            (Vector, str),
            (BitString, str),
            (Range, str),
            (Multirange, str),
            (MacAddress, str),
            (IPAddress, str),
        ]

        suggestions = merge_adapter_suggestions(base, type_mappings, self.adapter_registry)
        for py_type, db_type in type_mappings:
            if py_type not in suggestions:
                self.log(
                    logging.DEBUG,
                    f"No adapter found for ({py_type.__name__}, {db_type.__name__}). "
                    "Suggestion will not be provided for this type.",
                )
        return DataAdapterSuggestion(table=suggestions)

    def suggest_extra_data_adapters(self) -> ExtraDataAdapterSuggestion:
        """No backend-owned adapter types beyond the framework's value classes."""
        return ExtraDataAdapterSuggestion(table={})

    def get_type_adapters(self) -> List["SQLTypeAdapter"]:
        """Return the adapter instances this backend provides.

        This is a plain inventory: it says which adapters exist for this backend.
        It carries no suggestion/default/priority semantics; the caller decides.

        Two sources the backend already owns are combined: the adapter registry
        (every adapter registered for this backend, including ones that carry
        no default suggestion) and the adapters named by
        :meth:`suggest_data_adapters` (a suggestion may name an adapter instance
        that is not in the registry). Instances are deduplicated by class --
        ``(module, qualname)`` -- and sorted by that pair, so the order is
        deterministic and a new list is returned on every call.
        """
        adapters = list(self.adapter_registry.get_all_adapters().values())
        adapters.extend(
            suggestion[0] for suggestion in self.suggest_data_adapters().table.values()
        )
        unique: Dict[Tuple[str, str], SQLTypeAdapter] = {}
        for adapter in adapters:
            adapter_cls = type(adapter)
            unique.setdefault((adapter_cls.__module__, adapter_cls.__qualname__), adapter)
        return [unique[key] for key in sorted(unique)]

    # clickhouse-connect 1.7.x exposes the ClickHouse server error code as
    # ``Error.code`` and its symbolic name as ``Error.name``. Codes come from
    # ClickHouse's ErrorCodes.cpp and are stable across server versions, so they
    # are checked before message text.
    INTEGRITY_ERROR_CODES = {
        57,  # TABLE_ALREADY_EXISTS: a duplicate object name
        70,  # CANNOT_CONVERT_TYPE: includes NULL into a non-nullable column
    }
    QUERY_ERROR_CODES = {
        47,  # UNKNOWN_IDENTIFIER
        60,  # UNKNOWN_TABLE
        62,  # SYNTAX_ERROR
        81,  # UNKNOWN_DATABASE
    }
    TRANSIENT_ERROR_CODES = {
        159,  # TIMEOUT_EXCEEDED
        202,  # TOO_MANY_SIMULTANEOUS_QUERIES
        241,  # MEMORY_LIMIT_EXCEEDED
    }
    AUTHENTICATION_ERROR_CODES = {
        497,  # ACCESS_DENIED
        516,  # AUTHENTICATION_FAILED
    }
    READONLY_ERROR_CODES = {
        164,  # READONLY: the server or session refuses writes
    }
    CONNECTION_ERROR_CODES = {
        209,  # SOCKET_TIMEOUT
        210,  # NETWORK_ERROR
        279,  # ALL_CONNECTION_TRIES_FAILED
        # HTTP-level codes some driver versions surface instead of a
        # ClickHouse server code.
        503,
        504,
        1000,
        1002,
    }

    def _error_code(self, error: Exception) -> Optional[int]:
        """Return the ClickHouse server error code when the driver exposes one."""
        code = getattr(error, "code", None)
        if code is None:
            code = getattr(error, "errno", None)
        return code

    def _is_connection_error(self, error: Exception) -> bool:
        """Check if an error indicates a connection loss."""
        if self._error_code(error) in self.CONNECTION_ERROR_CODES:
            return True

        error_str = str(error).lower()
        connection_error_patterns = [
            "connection refused",
            "connection reset",
            "connection closed",
            "broken pipe",
            "cannot connect",
            "lost connection",
            "network error",
            "timeout expired",
            "unreachable",
        ]
        return any(pattern in error_str for pattern in connection_error_patterns)

    def _is_authentication_error(self, error: Exception) -> bool:
        """Check if an error means the credentials or permissions were refused."""
        if self._error_code(error) in self.AUTHENTICATION_ERROR_CODES:
            return True

        error_str = str(error).lower()
        authentication_error_patterns = [
            "authentication failed",
            "access denied",
            "not enough privileges",
            "invalid password",
            "unknown user",
            "there is no user",
        ]
        return any(pattern in error_str for pattern in authentication_error_patterns)

    def _handle_error(self, error: Exception) -> None:
        """Handle ClickHouse-specific errors.

        A framework :class:`DatabaseError` is re-raised unchanged: it was
        already translated once, and re-classifying it here would rewrite a
        ``QueryError`` or ``TransactionError`` produced by a later stage of the
        execution pipeline into a generic driver failure.

        Recognition order for driver exceptions: driver exception class,
        ClickHouse server error code, then message text.

        ClickHouse has no general-purpose transactions and no deadlock
        detector: the server cannot report a deadlock, so no ``DeadlockError``
        mapping exists here. Raising one would tell callers to retry a failure
        that never arrives. Concurrent-query pressure (code 202) and memory
        exhaustion (code 241) are infrastructure failures and are marked
        transient instead.
        """
        from clickhouse_connect.driver.exceptions import (
            DatabaseError as ClickHouseDatabaseError,
            Error as ClickHouseError,
            IntegrityError as ClickHouseIntegrityError,
            OperationalError as ClickHouseOperationalError,
            ProgrammingError as ClickHouseProgrammingError,
        )
        from rhosocial.activerecord.backend.errors import (
            ConnectionError,
            DatabaseError,
            IntegrityError,
            OperationalError,
            QueryError,
            attach_diagnostics,
        )

        if isinstance(error, DatabaseError):
            raise error

        error_msg = str(error)
        error_lower = error_msg.lower()
        code = self._error_code(error)
        backend = "clickhouse"

        if isinstance(error, ClickHouseIntegrityError):
            if (
                code in self.INTEGRITY_ERROR_CODES
                or "unique constraint" in error_lower
                or "violates unique constraint" in error_lower
            ):
                self.log(logging.DEBUG, f"Unique constraint violation: {error_msg}")
                raise attach_diagnostics(
                    IntegrityError(f"Unique constraint violation: {error_msg}"),
                    operation="execute",
                    driver_code=code,
                    backend=backend,
                ) from error
            self.log(logging.DEBUG, f"Integrity error: {error_msg}")
            raise attach_diagnostics(
                IntegrityError(error_msg),
                operation="execute",
                driver_code=code,
                backend=backend,
            ) from error
        elif (
            code in self.INTEGRITY_ERROR_CODES
            or "cannot convert null" in error_lower
            or "non-nullable" in error_lower
        ):
            # ClickHouse enforces NOT NULL through its type system, so assigning
            # NULL to a non-nullable column arrives as CANNOT_CONVERT_TYPE
            # (code 70) rather than as a driver integrity error. Preserve the
            # cross-backend contract and classify it as a not-null violation.
            if "cannot convert null" in error_lower or "non-nullable" in error_lower:
                self.log(logging.DEBUG, f"NULL in non-nullable column: {error_msg}")
                raise attach_diagnostics(
                    IntegrityError(f"cannot be null: {error_msg}"),
                    operation="execute",
                    driver_code=code,
                    backend=backend,
                ) from error
            self.log(logging.DEBUG, f"Integrity violation: {error_msg}")
            raise attach_diagnostics(
                IntegrityError(f"Integrity violation: {error_msg}"),
                operation="execute",
                driver_code=code,
                backend=backend,
            ) from error
        elif self._is_authentication_error(error):
            # Credentials and permissions do not improve on retry, so this is
            # a non-transient ConnectionError rather than OperationalError.
            self.log(logging.DEBUG, f"Authentication or permission failure: {error_msg}")
            raise attach_diagnostics(
                ConnectionError(error_msg),
                operation="execute",
                driver_code=code,
                backend=backend,
                transient=False,
            ) from error
        elif isinstance(error, ClickHouseOperationalError):
            # The HTTP layer raises OperationalError after retrying, so it is
            # already a transient infrastructure failure.
            transient = (
                code in self.TRANSIENT_ERROR_CODES
                or code in self.CONNECTION_ERROR_CODES
                or self._is_connection_error(error)
                or "timeout exceeded" in error_lower
                or "timeout expired" in error_lower
            )
            self.log(logging.DEBUG, f"Operational error: {error_msg}")
            raise attach_diagnostics(
                OperationalError(error_msg),
                operation="execute",
                driver_code=code,
                backend=backend,
                transient=transient,
            ) from error
        elif code in self.TRANSIENT_ERROR_CODES or any(
            hint in error_lower
            for hint in (
                "timeout exceeded",
                "timeout expired",
                "memory limit",
                "too many simultaneous",
            )
        ):
            self.log(logging.DEBUG, f"Transient server pressure: {error_msg}")
            raise attach_diagnostics(
                OperationalError(error_msg),
                operation="execute",
                driver_code=code,
                backend=backend,
                transient=True,
            ) from error
        elif (
            code in self.READONLY_ERROR_CODES
            or "readonly" in error_lower
            or "read-only" in error_lower
        ):
            # A read-only server/session is not a model policy failure: report
            # it as infrastructure so it is never confused with ReadOnlyError.
            self.log(logging.DEBUG, f"Read-only server: {error_msg}")
            raise attach_diagnostics(
                OperationalError(error_msg),
                operation="execute",
                driver_code=code,
                backend=backend,
                transient=False,
            ) from error
        elif self._is_connection_error(error):
            self.log(logging.DEBUG, f"Connection lost: {error_msg}")
            raise attach_diagnostics(
                OperationalError(error_msg),
                operation="execute",
                driver_code=code,
                backend=backend,
                transient=True,
            ) from error
        elif (
            code in self.QUERY_ERROR_CODES
            or isinstance(error, ClickHouseProgrammingError)
            or any(
                hint in error_lower
                for hint in (
                    "syntax error",
                    "unknown identifier",
                    "unknown table",
                    "unknown column",
                    "unknown database",
                    "missing columns",
                    "no such column",
                    "doesn't exist",
                    "cannot parse",
                )
            )
        ):
            self.log(logging.DEBUG, f"Query error: {error_msg}")
            raise attach_diagnostics(
                QueryError(error_msg),
                operation="execute",
                driver_code=code,
                backend=backend,
            ) from error
        elif isinstance(error, ClickHouseDatabaseError):
            self.log(logging.DEBUG, f"Database error: {error_msg}")
            raise attach_diagnostics(
                DatabaseError(error_msg),
                operation="execute",
                driver_code=code,
                backend=backend,
            ) from error
        elif isinstance(error, ClickHouseError):
            self.log(logging.DEBUG, f"ClickHouse error: {error_msg}")
            raise attach_diagnostics(
                DatabaseError(error_msg),
                operation="execute",
                driver_code=code,
                backend=backend,
            ) from error
        else:
            self.log(logging.DEBUG, f"Unexpected error: {error_msg}")
            raise error

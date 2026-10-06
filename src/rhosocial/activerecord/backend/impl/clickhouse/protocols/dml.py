# src/rhosocial/activerecord/backend/impl/clickhouse/protocols/dml.py
"""ClickHouse DML operation protocol.

Split out of the former single-module ``clickhouse/protocols.py``; one
concern per module so the protocol surface stays legible.
"""

from typing import Protocol, runtime_checkable, Tuple, Any, TYPE_CHECKING

if TYPE_CHECKING:  # pragma: no cover
    from rhosocial.activerecord.backend.expression.statements import (
        InsertExpression,
        OnConflictClause,
    )
    from rhosocial.activerecord.backend.impl.clickhouse.expression.load_data import (
        ClickHouseLoadDataExpression,
    )


@runtime_checkable
class ClickHouseDMLOperationSupport(Protocol):
    """ClickHouse-specific DML operations protocol.

    Feature Source: Not supported by ClickHouse (MySQL-originated concepts)

    ClickHouse does NOT support the following MySQL DML features:
    - INSERT IGNORE: Not supported (no duplicate-key silencing)
    - REPLACE INTO: Not supported (no delete-and-re-insert on duplicate key)
    - LOAD DATA INFILE: Not supported (use INSERT or clickhouse-client --query)

    All ``supports_*`` methods return False and ``format_*`` methods raise
    ``UnsupportedFeatureError``.
    """

    def supports_insert_ignore(self) -> bool:
        """Whether INSERT IGNORE is supported.

        ClickHouse does not support INSERT IGNORE (no duplicate-key handling).
        """
        ...

    def supports_replace_into(self) -> bool:
        """Whether REPLACE INTO is supported.

        ClickHouse does not support REPLACE INTO (no delete-and-re-insert on
        duplicate key).
        """
        ...

    def supports_load_data(self) -> bool:
        """Whether LOAD DATA INFILE is supported.

        ClickHouse does not support LOAD DATA INFILE.
        """
        ...

    def format_load_data_statement(self, expr: "ClickHouseLoadDataExpression") -> Tuple[str, tuple]:
        """Format LOAD DATA INFILE statement.

        Raises:
            UnsupportedFeatureError: ClickHouse does not support LOAD DATA INFILE.

        Args:
            expr: ClickHouseLoadDataExpression instance

        Returns:
            Tuple of (SQL string, parameters tuple)
        """
        ...

    def format_on_conflict_clause(self, expr: "OnConflictClause") -> Tuple[str, tuple]:
        """Format ON CONFLICT / ON DUPLICATE KEY UPDATE clause.

        ClickHouse does not support upsert clauses (ON CONFLICT or MySQL's
        ON DUPLICATE KEY UPDATE).

        Args:
            expr: OnConflictExpression or equivalent instance

        Returns:
            Tuple of (SQL string, parameters tuple)
        """
        ...

    def format_insert_statement(self, expr: "InsertExpression") -> Tuple[str, tuple]:
        """Format INSERT statement.

        Args:
            expr: InsertExpression instance

        Returns:
            Tuple of (SQL string, parameters tuple)
        """
        ...

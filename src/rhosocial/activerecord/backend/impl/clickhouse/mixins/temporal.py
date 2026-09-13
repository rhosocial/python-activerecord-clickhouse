# src/rhosocial/activerecord/backend/impl/clickhouse/mixins/temporal.py


class ClickHouseTemporalMixin:
    """ClickHouse temporal/qualify clause support."""

    def supports_qualify_clause(self) -> bool:
        """Whether QUALIFY clause is supported in ClickHouse."""
        return True

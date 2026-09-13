# src/rhosocial/activerecord/backend/impl/clickhouse/mixins/cte.py


class ClickHouseCTEMixin:
    """ClickHouse CTE (Common Table Expression) support."""

    def supports_basic_cte(self) -> bool:
        """Basic CTEs (WITH clause) are supported in ClickHouse."""
        return True

    def supports_recursive_cte(self) -> bool:
        """Recursive CTEs are supported in ClickHouse."""
        return True

    def supports_materialized_cte(self) -> bool:
        """ClickHouse supports MATERIALIZED / NOT MATERIALIZED CTE hints."""
        return True

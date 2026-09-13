# src/rhosocial/activerecord/backend/impl/clickhouse/mixins/upsert.py


class ClickHouseUpsertMixin:
    """ClickHouse upsert support check."""

    def get_upsert_syntax_type(self) -> str:
        """ClickHouse has no upsert syntax."""
        return "none"

    def supports_on_conflict_clause(self) -> bool:
        """Whether INSERT can carry an ON CONFLICT style clause."""
        return False

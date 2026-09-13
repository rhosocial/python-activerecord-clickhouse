# src/rhosocial/activerecord/backend/impl/clickhouse/mixins/sequence.py


class ClickHouseSequenceMixin:
    """ClickHouse sequence support check."""

    def supports_create_sequence(self) -> bool:
        """Whether CREATE SEQUENCE is supported."""
        return False

    def supports_drop_sequence(self) -> bool:
        """Whether DROP SEQUENCE is supported."""
        return False

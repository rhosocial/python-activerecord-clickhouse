# src/rhosocial/activerecord/backend/impl/clickhouse/mixins/sequence.py


class ClickHouseSequenceMixin:
    """ClickHouse sequence support check."""

    def supports_create_sequence(self) -> bool:
        """Whether CREATE SEQUENCE is supported."""
        return False

    def supports_drop_sequence(self) -> bool:
        """Whether DROP SEQUENCE is supported."""
        return False

    def supports_sequence_owned_by(self) -> bool:
        """Whether a sequence can be owned by a column.

        ``False``: there is no sequence object at all, so there is nothing to
        own. Declared so the answer is a measurement rather than an inherited
        default.
        """
        return False

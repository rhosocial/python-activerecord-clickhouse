# src/rhosocial/activerecord/backend/impl/clickhouse/mixins/index.py


class ClickHouseIndexMixin:
    """ClickHouse index support."""

    def supports_create_index(self) -> bool:
        """Whether CREATE INDEX is supported."""
        return True

    def supports_drop_index(self) -> bool:
        """Whether DROP INDEX is supported."""
        return True

    def supports_drop_index_on_table(self) -> bool:
        """ClickHouse drops indexes by name (no ON <table> suffix)."""
        return False

    def supports_unique_index(self) -> bool:
        """Whether UNIQUE indexes are supported."""
        return False  # ClickHouse cannot enforce uniqueness on indexes

    def supports_index_if_not_exists(self) -> bool:
        """Whether CREATE INDEX IF NOT EXISTS is supported."""
        return True

    def supports_index_if_exists(self) -> bool:
        """Whether DROP INDEX IF EXISTS is supported."""
        return True

    def supports_invisible_index(self) -> bool:
        """Whether INVISIBLE indexes are supported."""
        return False

    def supports_descending_index(self) -> bool:
        """Whether descending indexes are supported."""
        return False

    def supports_functional_index(self) -> bool:
        """Whether functional (expression) indexes are supported.

        ClickHouse skip indexes can be based on expressions.
        """
        return True

    def supports_index_type(self) -> bool:
        """ClickHouse skip indexes support USING keyword for index type."""
        return True

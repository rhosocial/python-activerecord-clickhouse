# src/rhosocial/activerecord/backend/impl/clickhouse/mixins/auto_increment.py


class ClickHouseAutoIncrementMixin:
    """ClickHouse auto-increment support check."""

    def supports_auto_increment(self) -> bool:
        """ClickHouse does not natively support AUTO_INCREMENT/IDENTITY primary keys.

        Primary keys must be supplied explicitly (e.g. a snowflake ID or UUID)
        before inserting new records.
        """
        return False

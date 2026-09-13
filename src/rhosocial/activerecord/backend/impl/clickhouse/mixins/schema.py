# src/rhosocial/activerecord/backend/impl/clickhouse/mixins/schema.py


class ClickHouseSchemaMixin:
    """ClickHouse schema (database) support."""

    def supports_schema(self) -> bool:
        """Whether schema (database) namespace is supported."""
        return True

    def supports_create_schema(self) -> bool:
        """Whether CREATE SCHEMA is supported."""
        return True

    def supports_drop_schema(self) -> bool:
        """Whether DROP SCHEMA is supported."""
        return True

    def supports_schema_if_not_exists(self) -> bool:
        """Whether CREATE SCHEMA IF NOT EXISTS is supported."""
        return True

    def supports_schema_if_exists(self) -> bool:
        """Whether DROP SCHEMA IF EXISTS is supported."""
        return True

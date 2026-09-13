# src/rhosocial/activerecord/backend/impl/clickhouse/mixins/array.py


class ClickHouseArrayMixin:
    """ClickHouse array type support."""

    def supports_array_type(self) -> bool:
        """ClickHouse has native Array types."""
        return True

    def supports_array_constructor(self) -> bool:
        """ClickHouse supports ARRAY constructor syntax [1, 2, 3]."""
        return True

    def supports_array_access(self) -> bool:
        """ClickHouse supports array subscript access arr[1] (1-based)."""
        return True

# src/rhosocial/activerecord/backend/impl/clickhouse/mixins/grouping.py


class ClickHouseGroupingMixin:
    """ClickHouse advanced grouping support."""

    def supports_rollup(self) -> bool:
        """ROLLUP is supported using WITH ROLLUP syntax."""
        return True

    def supports_cube(self) -> bool:
        """CUBE is supported using WITH CUBE syntax."""
        return True

    def supports_grouping_sets(self) -> bool:
        """GROUPING SETS is supported."""
        return True

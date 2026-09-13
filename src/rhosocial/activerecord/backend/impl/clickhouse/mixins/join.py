# src/rhosocial/activerecord/backend/impl/clickhouse/mixins/join.py


class ClickHouseJoinMixin:
    """ClickHouse join support."""

    def supports_right_join(self) -> bool:
        """RIGHT JOIN is supported."""
        return True

    def supports_full_join(self) -> bool:
        """FULL JOIN is supported."""
        return True

    def supports_natural_join(self) -> bool:
        """NATURAL JOIN is not supported in ClickHouse."""
        return False

    def supports_wildcard(self) -> bool:
        """Wildcard (*) is supported."""
        return True

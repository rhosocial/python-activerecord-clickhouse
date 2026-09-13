# src/rhosocial/activerecord/backend/impl/clickhouse/mixins/window.py


class ClickHouseWindowMixin:
    """ClickHouse window function support."""

    def supports_window_functions(self) -> bool:
        """Window functions are supported in ClickHouse."""
        return True

    def supports_window_frame_clause(self) -> bool:
        """Whether window frame clauses (ROWS/RANGE/GROUPS) are supported."""
        return True

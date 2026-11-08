# src/rhosocial/activerecord/backend/impl/clickhouse/mixins/datetime.py
from typing import Any, Tuple, TYPE_CHECKING

if TYPE_CHECKING:
    pass


class ClickHouseDateTimeMixin:
    """ClickHouse date/time function formatting."""

    def format_date_trunc_expression(self, expr: "Any") -> Tuple[str, tuple]:
        """Format date_trunc using ClickHouse's date_trunc function."""
        source_sql, source_params = expr.source.to_sql()
        field = expr.field.value.upper()
        sql = f"date_trunc({self.p()}, {source_sql})"
        return self.apply_alias(sql, source_params + (field,), expr)

    def format_interval_expression(self, expr: "Any") -> Tuple[str, tuple]:
        sql = f"INTERVAL {self.p()} {expr.unit.value.upper()}"
        return self.apply_alias(sql, (expr.value,), expr)

    def format_datetime_add_expression(self, expr: "Any") -> Tuple[str, tuple]:
        source_sql, source_params = expr.source.to_sql()
        interval_sql, interval_params = expr.interval.to_sql()
        sql = f"date_add({expr.interval.unit.value.upper()}, {interval_sql}, {source_sql})"
        return self.apply_alias(sql, source_params + interval_params, expr)

    def format_datetime_subtract_expression(self, expr: "Any") -> Tuple[str, tuple]:
        source_sql, source_params = expr.source.to_sql()
        interval_sql, interval_params = expr.interval.to_sql()
        sql = f"date_sub({expr.interval.unit.value.upper()}, {interval_sql}, {source_sql})"
        return self.apply_alias(sql, source_params + interval_params, expr)

    def format_datetime_diff_expression(self, expr: "Any") -> Tuple[str, tuple]:
        start_sql, start_params = expr.start.to_sql()
        end_sql, end_params = expr.end.to_sql()
        sql = f"dateDiff({self.p()}, {start_sql}, {end_sql})"
        return self.apply_alias(sql, start_params + end_params + (expr.unit.value.upper(),), expr)

    def format_seconds_between_expression(self, expr: "Any") -> Tuple[str, tuple]:
        """Format signed elapsed seconds using ClickHouse's ``dateDiff``.

        ``dateDiff`` counts whole units only, so the finest unit it can count
        is the millisecond; dividing that count by ``1000.0`` returns the
        fraction as a Float64 rather than an integer number of seconds. The
        sign comes from the argument order -- ``dateDiff(unit, start, end)``
        is ``end - start`` -- so an ``end`` earlier than the start renders the
        same SQL and subtracts to a negative value. A ``DateTime64(6)`` value
        is counted to the millisecond: its microseconds are truncated, which
        is the finest resolution this engine's ``dateDiff`` offers.

        The rendered SQL writes ``start`` before ``end``, so its parameters
        are collected in that order as well -- bind order follows the SQL, not
        the node's argument order.
        """
        start_sql, start_params = expr.start.to_sql()
        end_sql, end_params = expr.end.to_sql()
        sql = f"dateDiff('millisecond', {start_sql}, {end_sql}) / 1000.0"
        return self.apply_alias(sql, start_params + end_params, expr)

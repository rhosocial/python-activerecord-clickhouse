# src/rhosocial/activerecord/backend/impl/clickhouse/mixins/set_operation.py
from typing import Tuple, TYPE_CHECKING

if TYPE_CHECKING:
    from rhosocial.activerecord.backend.expression import bases


class ClickHouseSetOperationMixin:
    """ClickHouse set operation support (UNION, INTERSECT, EXCEPT)."""

    def supports_union(self) -> bool:
        """UNION is supported."""
        return True

    def supports_union_all(self) -> bool:
        """UNION ALL is supported."""
        return True

    def supports_intersect(self) -> bool:
        """INTERSECT is supported."""
        return True

    def supports_except(self) -> bool:
        """EXCEPT is supported."""
        return True

    def supports_set_operation_order_by(self) -> bool:
        """Set operations support ORDER BY."""
        return True

    def supports_set_operation_limit_offset(self) -> bool:
        """Set operations support LIMIT and OFFSET."""
        return True

    def format_set_operation_expression(self, expr: "bases.BaseExpression") -> Tuple[str, tuple]:
        """Format set operations with an explicit ALL/DISTINCT modifier.

        ClickHouse rejects a bare ``UNION`` when ``union_default_mode`` is
        empty (the default): ``Expected ALL or DISTINCT in SelectWithUnion
        query``. A bare SQL-standard ``UNION`` means ``UNION DISTINCT``, so
        we always emit the explicit modifier.
        """
        left, right = expr.left, expr.right
        operation = expr.operation
        all_ = expr.all_
        alias = expr.alias
        order_by_clause = expr.order_by_clause
        limit_offset_clause = expr.limit_offset_clause
        for_update_clause = expr.for_update_clause

        if for_update_clause and not self.supports_set_operation_for_update():
            from rhosocial.activerecord.backend.dialect.exceptions import UnsupportedFeatureError
            raise UnsupportedFeatureError(
                self.name,
                "FOR UPDATE in set operations",
                "ClickHouse does not support FOR UPDATE clauses.",
            )

        left_sql, left_params = left.to_sql()
        right_sql, right_params = right.to_sql()
        modifier = "ALL" if all_ else "DISTINCT"
        base_sql = f"{left_sql} {operation} {modifier} {right_sql}"
        all_params = list(left_params + right_params)

        sql_parts = [base_sql]
        if alias:
            sql_parts.append(f"AS {self.format_identifier(alias)}")
        if order_by_clause:
            order_by_sql, order_by_params = order_by_clause.to_sql()
            sql_parts.append(order_by_sql)
            all_params.extend(order_by_params)
        if limit_offset_clause:
            limit_offset_sql, limit_offset_params = limit_offset_clause.to_sql()
            sql_parts.append(limit_offset_sql)
            all_params.extend(limit_offset_params)
        return " ".join(sql_parts), tuple(all_params)

# src/rhosocial/activerecord/backend/impl/clickhouse/mixins/set_type.py
from typing import List, Optional, Tuple


class ClickHouseSetTypeMixin:
    """ClickHouse SET type implementation."""

    def supports_set_type(self) -> bool:
        return True

    def format_set_literal(self, values: List[str], column_values: Optional[List[str]] = None) -> Tuple[str, tuple]:
        """Format SET literal value."""
        if len(values) > 64:
            raise ValueError("ClickHouse SET type supports maximum 64 members")

        if column_values is not None:
            invalid_values = [v for v in values if v not in column_values]
            if invalid_values:
                raise ValueError(f"Invalid SET values: {invalid_values}. Allowed values: {column_values}")

        if not values:
            return "'", ()

        sorted_values = sorted(values)
        literal = ",".join(sorted_values)
        return "%s", (literal,)

    def format_find_in_set(self, value: str, set_column: str) -> Tuple[str, tuple]:
        """Format FIND_IN_SET function."""
        return f"FIND_IN_SET(%s, {self.format_identifier(set_column)}) > 0", (value,)

    def format_set_contains(self, column: str, values: List[str]) -> Tuple[str, tuple]:
        """Format SET contains check."""
        conditions = []
        params: List[str] = []

        for value in values:
            conditions.append(f"FIND_IN_SET(%s, {self.format_identifier(column)}) > 0")
            params.append(value)

        return " AND ".join(conditions), tuple(params)

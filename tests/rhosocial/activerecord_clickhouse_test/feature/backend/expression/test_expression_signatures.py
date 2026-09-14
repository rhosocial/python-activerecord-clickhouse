# tests/rhosocial/activerecord_clickhouse_test/feature/backend/expression/test_expression_signatures.py
"""
Tests for ClickHouse expression signature compliance.

This module verifies that expression classes follow the format signature
compliance pattern where each expression declares a format_method property
that returns the name of the dialect method used to render it.
"""

import pytest

from rhosocial.activerecord.backend.impl.clickhouse.dialect import ClickHouseDialect
from rhosocial.activerecord.backend.impl.clickhouse.expression.partition import (
    ClickHousePartitionNameListExpression,
)


class TestClickHousePartitionNameListExpression:
    """Test ClickHousePartitionNameListExpression class."""

    def test_partition_name_list_basic(self):
        """Test basic partition name list expression creation."""
        dialect = ClickHouseDialect(version=(8, 0, 0))

        expr = ClickHousePartitionNameListExpression(
            dialect, partitions=["2024_01", "2024_02", "2024_03"]
        )

        assert expr.partitions == ["2024_01", "2024_02", "2024_03"]
        assert expr.format_method == "format_partition_name_list"

    def test_partition_name_list_empty_raises(self):
        """Test that empty partitions list raises ValueError."""
        dialect = ClickHouseDialect(version=(8, 0, 0))

        with pytest.raises(ValueError, match="partitions must not be empty"):
            ClickHousePartitionNameListExpression(dialect, partitions=[])

    def test_partition_name_list_non_string_raises(self):
        """Test that non-string partition names raise TypeError."""
        dialect = ClickHouseDialect(version=(8, 0, 0))

        with pytest.raises(TypeError, match="partition name at index 1 must be a string"):
            ClickHousePartitionNameListExpression(
                dialect, partitions=["2024_01", 123, "2024_03"]
            )

    def test_partition_name_list_single_partition(self):
        """Test partition name list with single partition."""
        dialect = ClickHouseDialect(version=(8, 0, 0))

        expr = ClickHousePartitionNameListExpression(
            dialect, partitions=["2024_01"]
        )

        assert expr.partitions == ["2024_01"]
        assert len(expr.partitions) == 1

# tests/rhosocial/activerecord_clickhouse_test/feature/backend/test_vector_expressions.py
"""
Tests for ClickHouse vector expression classes.

This module tests the following expression classes:
- ClickHouseVectorExpression
- ClickHouseDistanceEuclideanExpression
- ClickHouseDistanceCosineExpression
- ClickHouseDistanceDotExpression
"""

from rhosocial.activerecord.backend.impl.clickhouse.dialect import ClickHouseDialect
from rhosocial.activerecord.backend.impl.clickhouse.expression import (
    ClickHouseVectorExpression,
    ClickHouseDistanceEuclideanExpression,
    ClickHouseDistanceCosineExpression,
    ClickHouseDistanceDotExpression,
)


class TestClickHouseVectorExpression:
    """Test ClickHouseVectorExpression class."""

    def test_vector_expression_basic(self):
        """Test basic vector literal creation."""
        dialect = ClickHouseDialect(version=(9, 0, 0))

        expr = ClickHouseVectorExpression(dialect, "[1, 2, 3]")
        sql, params = expr.to_sql()

        assert "STRING_TO_VECTOR" in sql
        assert "[" in params[0] or "1" in params[0]

    def test_vector_expression_with_alias(self):
        """Test vector expression with alias."""
        dialect = ClickHouseDialect(version=(9, 0, 0))

        expr = ClickHouseVectorExpression(dialect, "[1, 2, 3]").as_("embedding")
        sql, params = expr.to_sql()

        assert "STRING_TO_VECTOR" in sql
        assert "AS `embedding`" in sql

    def test_vector_expression_version_check(self):
        """Test vector support requires ClickHouse 9.0+."""
        dialect_old = ClickHouseDialect(version=(8, 0, 0))
        dialect_new = ClickHouseDialect(version=(9, 0, 0))

        assert not dialect_old.supports_vector_type()
        assert dialect_new.supports_vector_type()


class TestClickHouseDistanceEuclideanExpression:
    """Test ClickHouseDistanceEuclideanExpression class."""

    def test_distance_euclidean_expression(self):
        """Test Euclidean distance calculation."""
        dialect = ClickHouseDialect(version=(9, 0, 0))

        expr = ClickHouseDistanceEuclideanExpression(dialect, "vec1", "vec2")
        sql, params = expr.to_sql()

        assert "DISTANCE_EUCLIDEAN" in sql
        assert "vec1" in sql
        assert "vec2" in sql

    def test_distance_euclidean_with_alias(self):
        """Test Euclidean distance with alias."""
        dialect = ClickHouseDialect(version=(9, 0, 0))

        expr = ClickHouseDistanceEuclideanExpression(dialect, "vec1", "vec2").as_("dist")
        sql, params = expr.to_sql()

        assert "DISTANCE_EUCLIDEAN" in sql
        assert "AS `dist`" in sql


class TestClickHouseDistanceCosineExpression:
    """Test ClickHouseDistanceCosineExpression class."""

    def test_distance_cosine_expression(self):
        """Test Cosine distance calculation."""
        dialect = ClickHouseDialect(version=(9, 0, 0))

        expr = ClickHouseDistanceCosineExpression(dialect, "vec1", "vec2")
        sql, params = expr.to_sql()

        assert "DISTANCE_COSINE" in sql
        assert "vec1" in sql
        assert "vec2" in sql

    def test_distance_cosine_with_alias(self):
        """Test Cosine distance with alias."""
        dialect = ClickHouseDialect(version=(9, 0, 0))

        expr = ClickHouseDistanceCosineExpression(dialect, "vec1", "vec2").as_("cos_dist")
        sql, params = expr.to_sql()

        assert "DISTANCE_COSINE" in sql
        assert "AS `cos_dist`" in sql


class TestClickHouseDistanceDotExpression:
    """Test ClickHouseDistanceDotExpression class."""

    def test_distance_dot_expression(self):
        """Test Dot product calculation."""
        dialect = ClickHouseDialect(version=(9, 0, 0))

        expr = ClickHouseDistanceDotExpression(dialect, "vec1", "vec2")
        sql, params = expr.to_sql()

        assert "DISTANCE_DOT" in sql
        assert "vec1" in sql
        assert "vec2" in sql

    def test_distance_dot_with_alias(self):
        """Test Dot product with alias."""
        dialect = ClickHouseDialect(version=(9, 0, 0))

        expr = ClickHouseDistanceDotExpression(dialect, "vec1", "vec2").as_("dot_prod")
        sql, params = expr.to_sql()

        assert "DISTANCE_DOT" in sql
        assert "AS `dot_prod`" in sql

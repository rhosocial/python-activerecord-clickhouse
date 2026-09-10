# src/rhosocial/activerecord/backend/impl/clickhouse/expression/vector.py
"""
ClickHouse-specific vector expression functions.

This module provides expression classes for ClickHouse vector functions:
- ClickHouseVectorExpression
- ClickHouseDistanceEuclideanExpression
- ClickHouseDistanceCosineExpression
- ClickHouseDistanceDotExpression

Note: Vector support requires ClickHouse 9.0+
"""

from typing import TYPE_CHECKING, Optional

from rhosocial.activerecord.backend.expression.bases import SQLValueExpression
from rhosocial.activerecord.backend.expression.mixins import (
    AliasableMixin,
    ComparisonMixin,
)

if TYPE_CHECKING:
    from rhosocial.activerecord.backend.dialect import SQLDialectBase


class ClickHouseVectorExpression(AliasableMixin, SQLValueExpression):
    """ClickHouse vector literal expression.

    Creates a vector value from array string.

    Example:
        >>> expr = ClickHouseVectorExpression(dialect, '[1,2,3]')
    """

    def __init__(
        self,
        dialect: "SQLDialectBase",
        vector: str,
        *,
        alias: Optional[str] = None,
    ):
        super().__init__(dialect)
        self.vector = vector
        self.alias = alias

    @property
    def format_method(self) -> str:
        """The dialect formatting method that renders this expression."""
        return "format_vector_literal"


class ClickHouseDistanceEuclideanExpression(AliasableMixin, ComparisonMixin, SQLValueExpression):
    """ClickHouse Euclidean distance expression.

    Example:
        >>> expr = ClickHouseDistanceEuclideanExpression(dialect, 'vec1', 'vec2')
    """

    def __init__(
        self,
        dialect: "SQLDialectBase",
        vec1: str,
        vec2: str,
        *,
        alias: Optional[str] = None,
    ):
        super().__init__(dialect)
        self.vec1 = vec1
        self.vec2 = vec2
        self.alias = alias

    @property
    def format_method(self) -> str:
        """The dialect formatting method that renders this expression."""
        return "format_distance_euclidean"


class ClickHouseDistanceCosineExpression(AliasableMixin, ComparisonMixin, SQLValueExpression):
    """ClickHouse Cosine distance expression.

    Example:
        >>> expr = ClickHouseDistanceCosineExpression(dialect, 'vec1', 'vec2')
    """

    def __init__(
        self,
        dialect: "SQLDialectBase",
        vec1: str,
        vec2: str,
        *,
        alias: Optional[str] = None,
    ):
        super().__init__(dialect)
        self.vec1 = vec1
        self.vec2 = vec2
        self.alias = alias

    @property
    def format_method(self) -> str:
        """The dialect formatting method that renders this expression."""
        return "format_distance_cosine"


class ClickHouseDistanceDotExpression(AliasableMixin, ComparisonMixin, SQLValueExpression):
    """ClickHouse Dot product distance expression.

    Example:
        >>> expr = ClickHouseDistanceDotExpression(dialect, 'vec1', 'vec2')
    """

    def __init__(
        self,
        dialect: "SQLDialectBase",
        vec1: str,
        vec2: str,
        *,
        alias: Optional[str] = None,
    ):
        super().__init__(dialect)
        self.vec1 = vec1
        self.vec2 = vec2
        self.alias = alias

    @property
    def format_method(self) -> str:
        """The dialect formatting method that renders this expression."""
        return "format_distance_dot"


__all__ = [
    "ClickHouseVectorExpression",
    "ClickHouseDistanceEuclideanExpression",
    "ClickHouseDistanceCosineExpression",
    "ClickHouseDistanceDotExpression",
]

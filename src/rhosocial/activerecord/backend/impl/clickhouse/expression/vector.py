# src/rhosocial/activerecord/backend/impl/clickhouse/expression/vector.py
"""
ClickHouse-specific vector expression functions.

This module provides expression classes for ClickHouse vector functions:
- ClickHouseVectorLiteralExpression
- ClickHouseStringToVectorExpression
- ClickHouseVectorToStringExpression
- ClickHouseVectorDimExpression
- ClickHouseDistanceEuclideanExpression
- ClickHouseDistanceCosineExpression
- ClickHouseDistanceDotExpression
- ClickHouseCreateVectorIndexExpression

Note: Vector support requires ClickHouse 9.0+
"""

from typing import TYPE_CHECKING, List, Optional

from rhosocial.activerecord.backend.expression.bases import SQLValueExpression
from rhosocial.activerecord.backend.expression.mixins import (
    AliasableMixin,
    ComparisonMixin,
)

if TYPE_CHECKING:
    from rhosocial.activerecord.backend.dialect import SQLDialectBase


class ClickHouseVectorLiteralExpression(AliasableMixin, SQLValueExpression):
    """ClickHouse vector literal expression.

    Creates a vector value from a list of floats.

    Example:
        >>> expr = ClickHouseVectorLiteralExpression(dialect, [1.0, 2.0, 3.0])
    """

    def __init__(
        self,
        dialect: "SQLDialectBase",
        values: List[float],
        *,
        alias: Optional[str] = None,
    ):
        super().__init__(dialect)
        self.values = values
        self.alias = alias

    @property
    def format_method(self) -> str:
        """The dialect formatting method that renders this expression."""
        return "format_vector_literal"


class ClickHouseStringToVectorExpression(AliasableMixin, SQLValueExpression):
    """ClickHouse STRING_TO_VECTOR expression.

    Converts a string representation to a vector.

    Example:
        >>> expr = ClickHouseStringToVectorExpression(dialect, '[1,2,3]')
    """

    def __init__(
        self,
        dialect: "SQLDialectBase",
        vector_str: str,
        *,
        alias: Optional[str] = None,
    ):
        super().__init__(dialect)
        self.vector_str = vector_str
        self.alias = alias

    @property
    def format_method(self) -> str:
        """The dialect formatting method that renders this expression."""
        return "format_string_to_vector"


class ClickHouseVectorToStringExpression(AliasableMixin, SQLValueExpression):
    """ClickHouse VECTOR_TO_STRING expression.

    Converts a vector to a string representation.

    Example:
        >>> expr = ClickHouseVectorToStringExpression(dialect, 'vec_col')
    """

    def __init__(
        self,
        dialect: "SQLDialectBase",
        vector_col: str,
        *,
        alias: Optional[str] = None,
    ):
        super().__init__(dialect)
        self.vector_col = vector_col
        self.alias = alias

    @property
    def format_method(self) -> str:
        """The dialect formatting method that renders this expression."""
        return "format_vector_to_string"


class ClickHouseVectorDimExpression(AliasableMixin, SQLValueExpression):
    """ClickHouse VECTOR_DIM expression.

    Returns the dimension of a vector.

    Example:
        >>> expr = ClickHouseVectorDimExpression(dialect, 'vec_col')
    """

    def __init__(
        self,
        dialect: "SQLDialectBase",
        vector_col: str,
        *,
        alias: Optional[str] = None,
    ):
        super().__init__(dialect)
        self.vector_col = vector_col
        self.alias = alias

    @property
    def format_method(self) -> str:
        """The dialect formatting method that renders this expression."""
        return "format_vector_dim"


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


class ClickHouseCreateVectorIndexExpression(SQLValueExpression):
    """ClickHouse CREATE VECTOR INDEX expression.

    Example:
        >>> expr = ClickHouseCreateVectorIndexExpression(dialect, 'idx', 'table', 'column')
    """

    def __init__(
        self,
        dialect: "SQLDialectBase",
        index_name: str,
        table_name: str,
        column_name: str,
    ):
        super().__init__(dialect)
        self.index_name = index_name
        self.table_name = table_name
        self.column_name = column_name

    @property
    def format_method(self) -> str:
        """The dialect formatting method that renders this expression."""
        return "format_create_vector_index"


__all__ = [
    "ClickHouseVectorLiteralExpression",
    "ClickHouseStringToVectorExpression",
    "ClickHouseVectorToStringExpression",
    "ClickHouseVectorDimExpression",
    "ClickHouseDistanceEuclideanExpression",
    "ClickHouseDistanceCosineExpression",
    "ClickHouseDistanceDotExpression",
    "ClickHouseCreateVectorIndexExpression",
]

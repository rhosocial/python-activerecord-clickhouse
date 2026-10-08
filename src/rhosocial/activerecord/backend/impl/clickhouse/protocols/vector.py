# src/rhosocial/activerecord/backend/impl/clickhouse/protocols/vector.py
"""ClickHouse vector data type protocol.

Split out of the former single-module ``clickhouse/protocols.py``; one
concern per module so the protocol surface stays legible.
"""

from typing import Protocol, runtime_checkable, Tuple, TYPE_CHECKING

@runtime_checkable
class ClickHouseVectorSupport(Protocol):
    """ClickHouse vector data type protocol.

    Feature Source: ClickHouse 8.0+ (optional feature in 8.0.16+, GA in 8.0.17+)

    ClickHouse vector features:
    - VECTOR data type for embedding vectors
    - Vector operations and functions

    Official Documentation:
    - Vector Type: https://dev.clickhouse.com/doc/refman/8.0/en/vector-type.html

    Version Requirements:
    - VECTOR type: ClickHouse 8.0.16+ (experimental), 8.0.17+ (GA)
    """

    def supports_vector_type(self) -> bool:
        """Whether VECTOR data type is supported (ClickHouse 8.0.17+)."""
        ...

    def supports_vector_index(self) -> bool:
        """Whether vector index is supported (ClickHouse 8.0.17+)."""
        ...

    def get_max_vector_dimension(self) -> int:
        """Get the maximum supported vector dimension.

        Returns:
            Maximum number of dimensions supported for VECTOR type
        """
        ...

    def format_vector_literal(self, expr) -> Tuple[str, tuple]:
        """Format vector literal from a list of float values."""
        ...

    def format_string_to_vector(self, expr) -> Tuple[str, tuple]:
        """Format STRING_TO_VECTOR function call."""
        ...

    def format_vector_to_string(self, expr) -> Tuple[str, tuple]:
        """Format VECTOR_TO_STRING function call."""
        ...

    def format_vector_dim(self, expr) -> Tuple[str, tuple]:
        """Format VECTOR_DIM function call to get vector dimension."""
        ...

    def format_distance_euclidean(self, expr) -> Tuple[str, tuple]:
        """Format EUCLIDEAN_DISTANCE function call."""
        ...

    def format_distance_cosine(self, expr) -> Tuple[str, tuple]:
        """Format COSINE_DISTANCE function call."""
        ...

    def format_distance_dot(self, expr) -> Tuple[str, tuple]:
        """Format DOT_PRODUCT function call."""
        ...

    def format_create_vector_index(self, expr) -> Tuple[str, tuple]:
        """Format CREATE VECTOR INDEX statement."""
        ...

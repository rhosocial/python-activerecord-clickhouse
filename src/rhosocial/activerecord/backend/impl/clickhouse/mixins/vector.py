# src/rhosocial/activerecord/backend/impl/clickhouse/mixins/vector.py
from typing import List, Tuple

from rhosocial.activerecord.backend.dialect.exceptions import UnsupportedFeatureError


class ClickHouseVectorMixin:
    """ClickHouse does not support the MySQL 9.0 ``VECTOR`` type.

    ClickHouse has no ``VECTOR`` column type and no ``STRING_TO_VECTOR`` /
    ``VECTOR_TO_STRING`` / ``VECTOR_DIM`` / ``DISTANCE_*`` function family.
    Store embeddings as ``Array(Float32)`` and compute distance with
    ClickHouse array functions (``L2Distance``, ``cosineDistance``). All
    methods fail fast.
    """

    MAX_VECTOR_DIMENSION = 16384

    def supports_vector_type(self) -> bool:
        return False

    def supports_vector_index(self) -> bool:
        return False

    def get_max_vector_dimension(self) -> int:
        return self.MAX_VECTOR_DIMENSION

    def format_vector_literal(self, values: List[float]) -> Tuple[str, tuple]:
        raise UnsupportedFeatureError(
            self.name, "VECTOR type",
            suggestion="ClickHouse has no VECTOR type; use Array(Float32) + L2Distance.",
        )

    def format_string_to_vector(self, vector_str: str) -> Tuple[str, tuple]:
        raise UnsupportedFeatureError(
            self.name, "STRING_TO_VECTOR",
            suggestion="ClickHouse has no VECTOR type; use Array(Float32).",
        )

    def format_vector_to_string(self, vector_col: str) -> Tuple[str, tuple]:
        raise UnsupportedFeatureError(
            self.name, "VECTOR_TO_STRING",
            suggestion="ClickHouse has no VECTOR type; use Array(Float32).",
        )

    def format_vector_dim(self, vector_col: str) -> Tuple[str, tuple]:
        raise UnsupportedFeatureError(
            self.name, "VECTOR_DIM",
            suggestion="ClickHouse has no VECTOR type; use length(Array).",
        )

    def format_distance_euclidean(self, vector1: str, vector2: str) -> Tuple[str, tuple]:
        raise UnsupportedFeatureError(
            self.name, "VECTOR distance functions",
            suggestion="Use ClickHouse L2Distance on Array(Float32).",
        )

    def format_distance_cosine(self, vector1: str, vector2: str) -> Tuple[str, tuple]:
        raise UnsupportedFeatureError(
            self.name, "VECTOR distance functions",
            suggestion="Use ClickHouse cosineDistance on Array(Float32).",
        )

    def format_distance_dot(self, vector1: str, vector2: str) -> Tuple[str, tuple]:
        raise UnsupportedFeatureError(
            self.name, "VECTOR distance functions",
            suggestion="Use ClickHouse dotProduct on Array(Float32).",
        )

    def format_create_vector_index(self, index_name: str, table_name: str, column: str) -> Tuple[str, tuple]:
        raise UnsupportedFeatureError(
            self.name, "VECTOR indexes",
            suggestion="ClickHouse has no VECTOR indexes; use skip indexes (e.g. vector_similarity).",
        )

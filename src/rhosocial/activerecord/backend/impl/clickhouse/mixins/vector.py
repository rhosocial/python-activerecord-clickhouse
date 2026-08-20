# src/rhosocial/activerecord/backend/impl/clickhouse/mixins/vector.py
from typing import List, Tuple


class ClickHouseVectorMixin:
    """ClickHouse vector data type implementation."""

    MAX_VECTOR_DIMENSION = 16384

    def supports_vector_type(self) -> bool:
        return self.version >= (9, 0, 0)

    def supports_vector_index(self) -> bool:
        return self.version >= (9, 0, 1)

    def get_max_vector_dimension(self) -> int:
        return self.MAX_VECTOR_DIMENSION

    def format_vector_literal(self, values: List[float]) -> Tuple[str, tuple]:
        """Format VECTOR literal value."""
        if len(values) > self.MAX_VECTOR_DIMENSION:
            raise ValueError(
                f"Vector dimension {len(values)} exceeds maximum supported dimension {self.MAX_VECTOR_DIMENSION}"
            )
        vector_str = "[" + ",".join(str(v) for v in values) + "]"
        return "STRING_TO_VECTOR(%s)", (vector_str,)

    def format_string_to_vector(self, vector_str: str) -> Tuple[str, tuple]:
        return "STRING_TO_VECTOR(%s)", (vector_str,)

    def format_vector_to_string(self, vector_col: str) -> Tuple[str, tuple]:
        return f"VECTOR_TO_STRING({vector_col})", ()

    def format_vector_dim(self, vector_col: str) -> Tuple[str, tuple]:
        return f"VECTOR_DIM({vector_col})", ()

    def format_distance_euclidean(self, vector1: str, vector2: str) -> Tuple[str, tuple]:
        return f"DISTANCE_EUCLIDEAN({vector1}, {vector2})", ()

    def format_distance_cosine(self, vector1: str, vector2: str) -> Tuple[str, tuple]:
        return f"DISTANCE_COSINE({vector1}, {vector2})", ()

    def format_distance_dot(self, vector1: str, vector2: str) -> Tuple[str, tuple]:
        return f"DISTANCE_DOT({vector1}, {vector2})", ()

    def format_create_vector_index(self, index_name: str, table_name: str, column: str) -> Tuple[str, tuple]:
        """Format CREATE VECTOR INDEX statement."""
        if not self.supports_vector_index():
            from rhosocial.activerecord.backend.dialect.exceptions import UnsupportedFeatureError
            raise UnsupportedFeatureError(self.name, "VECTOR indexes (requires ClickHouse 9.0.1+)")
        return (
            f"CREATE VECTOR INDEX {self.format_identifier(index_name)} "
            f"ON {self.format_identifier(table_name)} "
            f"({self.format_identifier(column)})",
            (),
        )

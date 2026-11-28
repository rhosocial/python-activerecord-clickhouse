# src/rhosocial/activerecord/backend/impl/clickhouse/expression/column_types.py
"""ClickHouse's own column classes.

A vector column on this server carries ``Array(Float32)`` or the QBit vector
type. The distance functions are built into the engine, so this class gives a
field the server's own distance operations. It uses the dialect's
``_engine_function`` rather than a generic ``FunctionCall``: ClickHouse spells
these names in camelCase and case-folding them to ``L2DISTANCE`` makes the
server answer ``Function with name ... does not exist``.
"""

from typing import TYPE_CHECKING

from rhosocial.activerecord.backend.expression.column_types import VectorColumn

if TYPE_CHECKING:  # pragma: no cover
    from rhosocial.activerecord.backend.impl.clickhouse.expression.engine_function import (
        ClickHouseEngineFunctionExpression,
    )


class ClickHouseVectorColumn(VectorColumn):
    """A vector column with ClickHouse's built-in distance functions."""

    def l2_distance(self, other) -> "ClickHouseEngineFunctionExpression":
        """``L2Distance(col, other)``: Euclidean distance."""
        return self._dialect._engine_function("L2Distance", self, other)

    def cosine_distance(self, other) -> "ClickHouseEngineFunctionExpression":
        """``cosineDistance(col, other)``: cosine distance."""
        return self._dialect._engine_function("cosineDistance", self, other)


__all__ = ["ClickHouseVectorColumn"]

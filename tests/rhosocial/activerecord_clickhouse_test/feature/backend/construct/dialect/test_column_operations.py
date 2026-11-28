# tests/rhosocial/activerecord_clickhouse_test/feature/backend/construct/dialect/test_column_operations.py
"""The operations on ClickHouse's own vector column class.

The distance functions are engine built-ins and have camelCase names, so the
class uses the dialect's ``_engine_function`` rather than a case-folding
``FunctionCall``. These assertions pin the spelling as well as the call.
"""

import pytest

from rhosocial.activerecord.backend.impl.clickhouse.expression.column_types.column_types import (
    ClickHouseVectorColumn,
)
from rhosocial.activerecord.backend.impl.clickhouse.dialect import ClickHouseDialect


@pytest.fixture
def dialect():
    return ClickHouseDialect(version=(26, 7, 3))


@pytest.fixture
def vector(dialect):
    return ClickHouseVectorColumn(dialect, "v")


@pytest.mark.parametrize(
    "method, name", [("l2_distance", "L2Distance"), ("cosine_distance", "cosineDistance")]
)
def test_distance_functions(vector, dialect, method, name):
    other = ClickHouseVectorColumn(dialect, "h")
    sql, params = getattr(vector, method)(other).to_sql()
    assert sql == f"{name}(`v`, `h`)"
    assert params == ()


def test_a_vector_field_resolves_to_the_clickhouse_class(dialect):
    from rhosocial.activerecord.backend.adapters import Vector

    assert dialect.suggest_column_types().table[Vector] is ClickHouseVectorColumn

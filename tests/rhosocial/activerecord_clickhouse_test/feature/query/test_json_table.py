# tests/rhosocial/activerecord_clickhouse_test/feature/query/test_json_table.py
"""
ClickHouse JSON_TABLE tests.

ClickHouse has no SQL-standard ``JSON_TABLE``; per this backend's fast-fail
design principle the dialect reports ``supports_json_table() == False`` and
raises :class:`UnsupportedFeatureError` instead of emulating it.  These tests
verify that contract (use ``JSONExtract`` / ``arrayJoin`` instead).
"""

import pytest

from rhosocial.activerecord.backend.dialect.exceptions import UnsupportedFeatureError
from rhosocial.activerecord.backend.impl.clickhouse.expression import ClickHouseJSONTableExpression, JSONTableColumn, NestedPath


class TestClickHouseJSONTable:
    """JSON_TABLE fast-fail contract for the ClickHouse dialect."""

    def test_supports_json_table(self, clickhouse_backend):
        """ClickHouse does not support SQL-standard JSON_TABLE."""
        assert clickhouse_backend.dialect.supports_json_table() is False

    def _build_expr(self, dialect, **kwargs):
        defaults = dict(
            json_doc="'[1, 2, 3]'",
            path="$[*]",
            columns=[JSONTableColumn(name="value", type="INT", path="$")],
            alias="jt",
        )
        defaults.update(kwargs)
        return ClickHouseJSONTableExpression(dialect=dialect, **defaults)

    def test_json_table_basic_expression(self, clickhouse_backend):
        """Basic JSON_TABLE expression must fast-fail."""
        expr = self._build_expr(
            clickhouse_backend.dialect,
            json_doc=r"'[{" "name" ": " "Alice" ", " "age" ": 30}]'",
            columns=[
                JSONTableColumn(name="name", type="VARCHAR(255)", path="$.name"),
                JSONTableColumn(name="age", type="INT", path="$.age"),
            ],
        )
        with pytest.raises(UnsupportedFeatureError):
            expr.to_sql()

    def test_json_table_for_ordinality(self, clickhouse_backend):
        """FOR ORDINALITY columns must fast-fail too."""
        expr = self._build_expr(
            clickhouse_backend.dialect,
            columns=[
                JSONTableColumn(name="row_num", ordinality=True),
                JSONTableColumn(name="value", type="INT", path="$"),
            ],
        )
        with pytest.raises(UnsupportedFeatureError):
            expr.to_sql()

    def test_json_table_exists_path(self, clickhouse_backend):
        """EXISTS PATH columns must fast-fail too."""
        expr = self._build_expr(
            clickhouse_backend.dialect,
            json_doc=r"'{" "a" ": 1, " "b" ": 2}'",
            path="$",
            columns=[
                JSONTableColumn(name="has_a", type="BOOLEAN", path="$.a", exists=True),
                JSONTableColumn(name="has_c", type="BOOLEAN", path="$.c", exists=True),
            ],
        )
        with pytest.raises(UnsupportedFeatureError):
            expr.to_sql()

    def test_json_table_nested_path(self, clickhouse_backend):
        """NESTED PATH columns must fast-fail too."""
        expr = self._build_expr(
            clickhouse_backend.dialect,
            json_doc=r"'[{" "name" ": " "Alice" ", " "orders" ": [{" "id" ": 1}, {" "id" ": 2}]}]'",
            columns=[
                JSONTableColumn(name="customer_name", type="VARCHAR(255)", path="$.name"),
            ],
            nested_paths=[
                NestedPath(
                    path="$.orders[*]",
                    columns=[
                        JSONTableColumn(name="order_id", type="INT", path="$.id"),
                    ],
                    alias="orders",
                )
            ],
        )
        with pytest.raises(UnsupportedFeatureError):
            expr.to_sql()

    def test_json_table_with_alias(self, clickhouse_backend):
        """Aliases do not change the fast-fail behaviour."""
        expr = self._build_expr(clickhouse_backend.dialect, alias="my_table")
        with pytest.raises(UnsupportedFeatureError):
            expr.to_sql()

    def test_json_table_error_handling_null(self, clickhouse_backend):
        """NULL ON ERROR columns must fast-fail too."""
        expr = self._build_expr(
            clickhouse_backend.dialect,
            columns=[
                JSONTableColumn(name="value", type="VARCHAR(255)", path="$.nonexistent", error_handling="NULL"),
            ],
        )
        with pytest.raises(UnsupportedFeatureError):
            expr.to_sql()

    def test_json_table_multiple_columns(self, clickhouse_backend):
        """Multiple columns must fast-fail too."""
        expr = self._build_expr(
            clickhouse_backend.dialect,
            json_doc=r"'[{" "id" ": 1, " "name" ": " "Alice" ", " "email" ": " "alice@example.com" "}]'",
            columns=[
                JSONTableColumn(name="id", type="INT", path="$.id"),
                JSONTableColumn(name="name", type="VARCHAR(255)", path="$.name"),
                JSONTableColumn(name="email", type="VARCHAR(255)", path="$.email"),
            ],
        )
        with pytest.raises(UnsupportedFeatureError):
            expr.to_sql()


class TestClickHouseAsyncJSONTable:
    """Async variant follows the same fast-fail contract."""

    async def test_json_table_expression_async(self, async_clickhouse_backend):
        expr = ClickHouseJSONTableExpression(
            dialect=async_clickhouse_backend.dialect,
            json_doc="'[1, 2, 3]'",
            path="$[*]",
            columns=[
                JSONTableColumn(name="value", type="INT", path="$"),
            ],
            alias="jt",
        )
        with pytest.raises(UnsupportedFeatureError):
            expr.to_sql()
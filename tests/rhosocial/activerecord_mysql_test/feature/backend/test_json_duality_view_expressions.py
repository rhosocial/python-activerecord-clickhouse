# tests/rhosocial/activerecord_clickhouse_test/feature/backend/test_json_duality_view_expressions.py
"""
Tests for ClickHouse JSON Duality View expression classes (ClickHouse 9.7+).

Tests SQL generation for:
- CreateJsonDualityViewExpression
- DropJsonDualityViewExpression
- DualityObjectSpec with various tag combinations
- Nested duality objects
"""

import pytest
from rhosocial.activerecord.backend.impl.clickhouse.dialect import ClickHouseDialect
from rhosocial.activerecord.backend.impl.clickhouse.expression import (
    CreateJsonDualityViewExpression,
    DropJsonDualityViewExpression,
    DualityObjectSpec,
    DualityColumnMapping,
    DualityNestedMapping,
    DualityViewDMLTag,
)


@pytest.fixture
def dialect_97():
    return ClickHouseDialect(version=(9, 7, 0))


@pytest.fixture
def dialect_84():
    return ClickHouseDialect(version=(8, 4, 0))


class TestJsonDualityViewSupport:
    """Test version-gated capability detection."""

    def test_supported_on_97(self, dialect_97):
        assert dialect_97.supports_json_duality_view()
        assert dialect_97.supports_json_duality_view_dml()

    def test_not_supported_on_84(self, dialect_84):
        assert not dialect_84.supports_json_duality_view()
        assert not dialect_84.supports_json_duality_view_dml()


class TestCreateJsonDualityViewExpression:
    """Test CREATE JSON RELATIONAL DUALITY VIEW SQL generation."""

    def test_basic_read_only_view(self, dialect_97):
        spec = DualityObjectSpec(
            columns=[
                DualityColumnMapping("_id", "`t`.`id`"),
                DualityColumnMapping("name", "`t`.`name`"),
            ],
            from_table="users",
            from_alias="t",
        )
        expr = CreateJsonDualityViewExpression(dialect_97, "users_dv", spec)
        sql, params = expr.to_sql()

        assert "CREATE JSON RELATIONAL DUALITY VIEW" in sql
        assert "`users_dv`" in sql
        assert "JSON_DUALITY_OBJECT(" in sql
        assert "'_id': `t`.`id`" in sql
        assert "'name': `t`.`name`" in sql
        assert "FROM `users` `t`" in sql
        assert "WITH(" not in sql
        assert params == ()

    def test_writable_view_all_tags(self, dialect_97):
        spec = DualityObjectSpec(
            tags=[DualityViewDMLTag.INSERT, DualityViewDMLTag.UPDATE, DualityViewDMLTag.DELETE],
            columns=[
                DualityColumnMapping("_id", "`orders`.`id`"),
                DualityColumnMapping("total", "`orders`.`total`"),
            ],
            from_table="orders",
        )
        expr = CreateJsonDualityViewExpression(dialect_97, "orders_dv", spec)
        sql, params = expr.to_sql()

        assert "WITH(INSERT,UPDATE,DELETE)" in sql
        assert "'_id': `orders`.`id`" in sql
        assert "FROM `orders`" in sql
        assert params == ()

    def test_partial_tags_insert_only(self, dialect_97):
        spec = DualityObjectSpec(
            tags=[DualityViewDMLTag.INSERT],
            columns=[
                DualityColumnMapping("_id", "`t`.`id`"),
            ],
            from_table="items",
            from_alias="t",
        )
        expr = CreateJsonDualityViewExpression(dialect_97, "items_dv", spec)
        sql, _ = expr.to_sql()

        assert "WITH(INSERT)" in sql
        assert "UPDATE" not in sql
        assert "DELETE" not in sql

    def test_or_replace(self, dialect_97):
        spec = DualityObjectSpec(
            tags=[DualityViewDMLTag.INSERT, DualityViewDMLTag.UPDATE],
            columns=[DualityColumnMapping("_id", "`t`.`id`")],
            from_table="products",
            from_alias="t",
        )
        expr = CreateJsonDualityViewExpression(dialect_97, "products_dv", spec, replace=True)
        sql, _ = expr.to_sql()

        assert "CREATE OR REPLACE JSON RELATIONAL DUALITY VIEW" in sql

    def test_nested_object(self, dialect_97):
        child_spec = DualityObjectSpec(
            tags=[DualityViewDMLTag.INSERT, DualityViewDMLTag.UPDATE],
            columns=[
                DualityColumnMapping("lineId", "`li`.`id`"),
                DualityColumnMapping("product", "`li`.`product_name`"),
            ],
            from_table="order_lines",
            from_alias="li",
            join_condition="`li`.`order_id` = `o`.`id`",
        )
        root_spec = DualityObjectSpec(
            tags=[DualityViewDMLTag.INSERT, DualityViewDMLTag.UPDATE, DualityViewDMLTag.DELETE],
            columns=[
                DualityColumnMapping("_id", "`o`.`id`"),
                DualityColumnMapping("status", "`o`.`status`"),
            ],
            nested=[DualityNestedMapping("lines", child_spec)],
            from_table="orders",
            from_alias="o",
        )
        expr = CreateJsonDualityViewExpression(dialect_97, "orders_full_dv", root_spec)
        sql, params = expr.to_sql()

        assert "WITH(INSERT,UPDATE,DELETE)" in sql
        assert "'lines':" in sql
        assert "JSON_ARRAYAGG(" in sql
        assert "WITH(INSERT,UPDATE)" in sql
        assert "'lineId': `li`.`id`" in sql
        assert "WHERE `li`.`order_id` = `o`.`id`" in sql
        assert params == ()


class TestDropJsonDualityViewExpression:
    """Test DROP VIEW SQL generation for duality views."""

    def test_drop_view(self, dialect_97):
        expr = DropJsonDualityViewExpression(dialect_97, "orders_dv")
        sql, params = expr.to_sql()

        assert sql == "DROP VIEW `orders_dv`"
        assert params == ()

    def test_drop_view_if_exists(self, dialect_97):
        expr = DropJsonDualityViewExpression(dialect_97, "orders_dv", if_exists=True)
        sql, params = expr.to_sql()

        assert sql == "DROP VIEW IF EXISTS `orders_dv`"
        assert params == ()

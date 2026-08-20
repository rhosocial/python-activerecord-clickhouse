# tests/rhosocial/activerecord_clickhouse_test/feature/backend/clickhouse/test_json_duality_view_execution.py
"""
Tests for ClickHouse JSON Duality View functionality with actual ClickHouse 9.7 execution.

These tests verify that generated DDL/DML statements execute correctly
against an actual ClickHouse 9.7+ database.
"""

import pytest
from rhosocial.activerecord.backend.impl.clickhouse.expression import (
    CreateJsonDualityViewExpression,
    DropJsonDualityViewExpression,
    DualityObjectSpec,
    DualityColumnMapping,
    DualityViewDMLTag,
)
from rhosocial.activerecord.backend.options import ExecutionOptions
from rhosocial.activerecord.backend.schema import StatementType


def _requires_clickhouse_97(backend):
    """Skip test if ClickHouse version < 9.7."""
    if backend.dialect.version < (9, 7, 0):
        pytest.skip("Requires ClickHouse 9.7+ for JSON Duality Views")


def _product_columns(*names):
    columns = {
        "_id": "`dv_products`.`id`",
        "name": "`dv_products`.`name`",
        "price": "`dv_products`.`price`",
    }
    return [DualityColumnMapping(name, columns[name]) for name in names]


def _product_spec(*columns, tags=()):
    return DualityObjectSpec(
        tags=list(tags),
        columns=_product_columns(*columns),
        from_table="dv_products",
    )


def _create_products_view(backend, spec, *, replace=False):
    expr = CreateJsonDualityViewExpression(
        backend.dialect,
        "products_dv",
        spec,
        replace=replace,
    )
    backend.execute(*expr.to_sql(), options=ExecutionOptions(stmt_type=StatementType.DDL))


def _select_products_view_metadata(backend):
    return backend.execute(
        "SELECT * FROM information_schema.JSON_DUALITY_VIEWS "
        "WHERE TABLE_SCHEMA = %s AND TABLE_NAME = 'products_dv'",
        (backend.config.database,),
    )


@pytest.fixture
def duality_backend(clickhouse_backend):
    """Provides a backend with test tables for duality view tests."""
    backend = clickhouse_backend
    _requires_clickhouse_97(backend)

    ddl_opts = ExecutionOptions(stmt_type=StatementType.DDL)

    backend.execute("DROP VIEW IF EXISTS orders_dv", (), options=ddl_opts)
    backend.execute("DROP VIEW IF EXISTS products_dv", (), options=ddl_opts)
    backend.execute("DROP TABLE IF EXISTS order_lines", (), options=ddl_opts)
    backend.execute("DROP TABLE IF EXISTS dv_orders", (), options=ddl_opts)
    backend.execute("DROP TABLE IF EXISTS dv_products", (), options=ddl_opts)

    backend.execute(
        """
        CREATE TABLE dv_products (
            id INT AUTO_INCREMENT PRIMARY KEY,
            name VARCHAR(100) NOT NULL,
            price DECIMAL(10, 2) NOT NULL
        )
    """,
        (),
        options=ddl_opts,
    )

    backend.execute(
        """
        CREATE TABLE dv_orders (
            id INT AUTO_INCREMENT PRIMARY KEY,
            customer VARCHAR(100) NOT NULL,
            total DECIMAL(10, 2) DEFAULT 0
        )
    """,
        (),
        options=ddl_opts,
    )

    backend.execute(
        """
        CREATE TABLE order_lines (
            id INT AUTO_INCREMENT PRIMARY KEY,
            order_id INT NOT NULL,
            product_name VARCHAR(100),
            qty INT DEFAULT 1,
            FOREIGN KEY (order_id) REFERENCES dv_orders(id)
        )
    """,
        (),
        options=ddl_opts,
    )

    yield backend

    backend.execute("DROP VIEW IF EXISTS orders_dv", (), options=ddl_opts)
    backend.execute("DROP VIEW IF EXISTS products_dv", (), options=ddl_opts)
    backend.execute("DROP TABLE IF EXISTS order_lines", (), options=ddl_opts)
    backend.execute("DROP TABLE IF EXISTS dv_orders", (), options=ddl_opts)
    backend.execute("DROP TABLE IF EXISTS dv_products", (), options=ddl_opts)


class TestJsonDualityViewDDL:
    """Test CREATE/DROP JSON RELATIONAL DUALITY VIEW execution."""

    def test_create_read_only_view(self, duality_backend):
        backend = duality_backend
        _create_products_view(backend, _product_spec("_id", "name", "price"))

        result = _select_products_view_metadata(backend)
        assert len(result.data) > 0

    def test_create_writable_view(self, duality_backend):
        backend = duality_backend
        tags = (DualityViewDMLTag.INSERT, DualityViewDMLTag.UPDATE, DualityViewDMLTag.DELETE)
        _create_products_view(backend, _product_spec("_id", "name", "price", tags=tags))

        result = backend.execute(
            "SELECT ALLOW_INSERT, ALLOW_UPDATE, ALLOW_DELETE "
            "FROM information_schema.JSON_DUALITY_VIEW_TABLES "
            "WHERE TABLE_SCHEMA = %s AND TABLE_NAME = 'products_dv' AND IS_ROOT_TABLE = 1",
            (backend.config.database,),
        )
        assert len(result.data) > 0
        row = result.data[0]
        assert row["ALLOW_INSERT"] == 1
        assert row["ALLOW_UPDATE"] == 1
        assert row["ALLOW_DELETE"] == 1

    def test_create_or_replace(self, duality_backend):
        backend = duality_backend
        _create_products_view(backend, _product_spec("_id"))
        _create_products_view(
            backend,
            _product_spec("_id", "name", tags=(DualityViewDMLTag.INSERT,)),
            replace=True,
        )

        result = _select_products_view_metadata(backend)
        assert len(result.data) > 0

    def test_drop_view(self, duality_backend):
        backend = duality_backend
        _create_products_view(backend, _product_spec("_id"))

        drop_expr = DropJsonDualityViewExpression(backend.dialect, "products_dv")
        backend.execute(*drop_expr.to_sql(), options=ExecutionOptions(stmt_type=StatementType.DDL))

        result = _select_products_view_metadata(backend)
        assert len(result.data) == 0


class TestJsonDualityViewDML:
    """Test DML operations on JSON Duality Views."""

    def test_insert_and_select(self, duality_backend):
        backend = duality_backend
        tags = (DualityViewDMLTag.INSERT, DualityViewDMLTag.UPDATE, DualityViewDMLTag.DELETE)
        _create_products_view(backend, _product_spec("_id", "name", "price", tags=tags))

        backend.execute(
            "INSERT INTO products_dv VALUES (%s)",
            ('{"_id": 1, "name": "Widget", "price": 9.99}',),
        )

        result = backend.execute("SELECT * FROM products_dv WHERE data->>'$._id' = '1'", ())
        assert len(result.data) == 1

    def test_insert_auto_increment(self, duality_backend):
        backend = duality_backend
        tags = (DualityViewDMLTag.INSERT, DualityViewDMLTag.UPDATE, DualityViewDMLTag.DELETE)
        _create_products_view(backend, _product_spec("_id", "name", "price", tags=tags))

        backend.execute(
            "INSERT INTO products_dv VALUES (%s)",
            ('{"name": "Gadget", "price": 19.99}',),
        )

        result = backend.execute("SELECT * FROM products_dv", ())
        assert len(result.data) == 1

    def test_delete(self, duality_backend):
        backend = duality_backend
        tags = (DualityViewDMLTag.INSERT, DualityViewDMLTag.UPDATE, DualityViewDMLTag.DELETE)
        _create_products_view(backend, _product_spec("_id", "name", "price", tags=tags))

        backend.execute(
            "INSERT INTO products_dv VALUES (%s)",
            ('{"_id": 1, "name": "Temp", "price": 1.00}',),
        )

        backend.execute("DELETE FROM products_dv WHERE data->>'$._id' = '1'", ())

        result = backend.execute("SELECT * FROM products_dv", ())
        assert len(result.data) == 0

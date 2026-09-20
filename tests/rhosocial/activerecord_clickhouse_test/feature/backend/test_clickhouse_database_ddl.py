# tests/rhosocial/activerecord_clickhouse_test/feature/backend/test_clickhouse_database_ddl.py
"""Explicit ClickHouseDialect database DDL capability + rendering tests."""

from rhosocial.activerecord.backend.expression.statements.ddl_database import (
    CreateDatabaseExpression,
    DropDatabaseExpression,
)
from rhosocial.activerecord.backend.impl.clickhouse.dialect import ClickHouseDialect


def _dialect():
    return ClickHouseDialect()


def test_database_capabilities():
    dialect = _dialect()
    assert dialect.supports_create_database() is True
    assert dialect.supports_drop_database() is True


def test_create_database_renders():
    sql, params = CreateDatabaseExpression(_dialect(), database_name="app").to_sql()
    assert "CREATE DATABASE" in sql
    assert params == ()


def test_drop_database_renders():
    sql, _ = DropDatabaseExpression(_dialect(), database_name="app").to_sql()
    assert "DROP DATABASE" in sql

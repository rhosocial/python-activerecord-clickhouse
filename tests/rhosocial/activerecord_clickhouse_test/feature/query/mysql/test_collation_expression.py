# tests/rhosocial/activerecord_clickhouse_test/feature/query/clickhouse/test_collation_expression.py
"""
Tests for expression-level COLLATE support on ClickHouse.
"""

import pytest

from rhosocial.activerecord.backend.expression import Column, Literal
from rhosocial.activerecord.backend.impl.clickhouse import (
    ClickHouseCollation,
    ClickHouseCollationValidator,
    ClickHouseDialect,
)


@pytest.fixture
def dialect():
    return ClickHouseDialect(version=(8, 0, 0))


@pytest.fixture
def collation_table(clickhouse_backend):
    clickhouse_backend.execute("DROP TABLE IF EXISTS test_collation_expression")
    clickhouse_backend.execute("""
        CREATE TABLE test_collation_expression (
            id INT AUTO_INCREMENT PRIMARY KEY,
            name VARCHAR(191) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
    """)
    clickhouse_backend.execute("""
        INSERT INTO test_collation_expression (name)
        VALUES ('Alice'), ('alice'), ('Bob')
    """)
    yield "test_collation_expression"
    clickhouse_backend.execute("DROP TABLE IF EXISTS test_collation_expression")


class TestClickHouseCollationValidator:
    def test_supports_known_legacy_collation(self):
        assert ClickHouseCollationValidator.is_supported("utf8mb4_unicode_ci", (5, 7, 0))

    def test_rejects_clickhouse_8_collation_on_older_version(self):
        assert not ClickHouseCollationValidator.is_supported("utf8mb4_0900_ai_ci", (5, 7, 0))
        assert ClickHouseCollationValidator.is_supported("utf8mb4_0900_ai_ci", (8, 0, 0))

    def test_validate_normalizes_case(self):
        assert ClickHouseCollationValidator.validate("UTF8MB4_BIN", (5, 7, 0)) == "utf8mb4_bin"

    def test_validate_rejects_unknown_collation(self):
        with pytest.raises(ValueError, match="Unsupported ClickHouse collation"):
            ClickHouseCollationValidator.validate("unknown_ci", (8, 0, 0))

    def test_enum_contains_representative_collations(self):
        values = {collation.value for collation in ClickHouseCollation}

        assert "binary" in values
        assert "latin1_swedish_ci" in values
        assert "utf8mb4_unicode_ci" in values
        assert "utf8mb4_0900_ai_ci" in values
        assert "utf8mb4_ja_0900_as_cs" in values


class TestClickHouseCollationExpression:
    def test_column_collate_generates_sql(self, dialect):
        expr = Column(dialect, "name", table="users").collate(ClickHouseCollation.UTF8MB4_BIN)

        sql, params = expr.to_sql()

        assert sql == "`users`.`name` COLLATE utf8mb4_bin"
        assert params == ()

    def test_literal_collate_preserves_parameter_binding(self, dialect):
        expr = Literal(dialect, "Alice").collate(ClickHouseCollation.UTF8MB4_0900_AI_CI)

        sql, params = expr.to_sql()

        assert sql == "%s COLLATE utf8mb4_0900_ai_ci"
        assert params == ("Alice",)

    def test_rejects_schema_qualified_collation(self, dialect):
        expr = Column(dialect, "name").collate("utf8mb4_bin", schema="public")

        with pytest.raises(Exception, match="COLLATE options: schema"):
            expr.to_sql()

    def test_rejects_unsupported_collation(self, dialect):
        expr = Column(dialect, "name").collate("unknown_ci")

        with pytest.raises(ValueError, match="Unsupported ClickHouse collation"):
            expr.to_sql()

    def test_rejects_clickhouse_8_collation_on_older_version(self):
        dialect = ClickHouseDialect(version=(5, 7, 0))
        expr = Column(dialect, "name").collate(ClickHouseCollation.UTF8MB4_0900_AI_CI)

        with pytest.raises(ValueError, match="requires ClickHouse 8.0"):
            expr.to_sql()

    def test_collate_executes_case_sensitive_match(self, clickhouse_backend, collation_table):
        expr = Column(clickhouse_backend.dialect, "name", table=collation_table).collate(ClickHouseCollation.UTF8MB4_BIN)
        sql, params = expr.to_sql()

        rows = clickhouse_backend.fetch_all(
            f"SELECT name FROM `{collation_table}` WHERE {sql} = %s ORDER BY id",
            (*params, "Alice"),
        )

        assert [row["name"] for row in rows] == ["Alice"]

    def test_collate_executes_case_insensitive_match(self, clickhouse_backend, collation_table):
        expr = Column(clickhouse_backend.dialect, "name", table=collation_table).collate(ClickHouseCollation.UTF8MB4_UNICODE_CI)
        sql, params = expr.to_sql()

        rows = clickhouse_backend.fetch_all(
            f"SELECT name FROM `{collation_table}` WHERE {sql} = %s ORDER BY id",
            (*params, "Alice"),
        )

        assert [row["name"] for row in rows] == ["Alice", "alice"]

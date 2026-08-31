# tests/rhosocial/activerecord_clickhouse_test/feature/backend/test_clickhouse_ddl_generation.py
"""
ClickHouse DDL generation tests (pure dialect, no database).

Covers ClickHouseTableMixin.format_create_table_statement and
ClickHouseTypeSupportMixin type formatting.
"""

import pytest

from rhosocial.activerecord.backend.impl.clickhouse.dialect import ClickHouseDialect
from rhosocial.activerecord.backend.expression.statements import ColumnDefinition, CreateTableExpression
from rhosocial.activerecord.backend.expression.core import TableExpression
from rhosocial.activerecord.backend.expression.types import (
    IntegerType,
    VarCharType,
    DecimalType,
    DateTimeType,
    BooleanType,
)


@pytest.fixture
def dialect():
    return ClickHouseDialect(version=(26, 7, 3))


class TestClickHouseDDLGeneration:
    def test_create_table_basic(self, dialect):
        """CREATE TABLE with ClickHouse storage options."""
        expr = CreateTableExpression(
            dialect,
            TableExpression(dialect, "users"),
            [
                ColumnDefinition("id", IntegerType()),
                ColumnDefinition("name", VarCharType(length=100)),
            ],
            storage_options={"ENGINE": "MergeTree()", "ORDER BY": "id"},
        )
        sql, _ = expr.to_sql()
        assert "CREATE TABLE" in sql
        assert "ENGINE = MergeTree()" in sql
        assert "ORDER BY = id" in sql or "ORDER BY id" in sql

    def test_create_table_if_not_exists(self, dialect):
        expr = CreateTableExpression(
            dialect,
            TableExpression(dialect, "events"),
            [ColumnDefinition("id", IntegerType())],
            if_not_exists=True,
            storage_options={"ENGINE": "MergeTree()", "ORDER BY": "id"},
        )
        sql, _ = expr.to_sql()
        assert "IF NOT EXISTS" in sql

    def test_create_table_types_map_to_clickhouse(self, dialect):
        """Core types map to ClickHouse equivalents."""
        expr = CreateTableExpression(
            dialect,
            TableExpression(dialect, "t"),
            [
                ColumnDefinition("id", IntegerType()),
                ColumnDefinition("name", VarCharType(length=100)),
                ColumnDefinition("amount", DecimalType(precision=10, scale=2)),
                ColumnDefinition("ts", DateTimeType()),
                ColumnDefinition("active", BooleanType()),
            ],
            storage_options={"ENGINE": "MergeTree()", "ORDER BY": "id"},
        )
        sql, _ = expr.to_sql()
        assert "Int32" in sql          # IntegerType
        assert "String" in sql         # VarCharType
        assert "Decimal(10, 2)" in sql
        assert "DateTime" in sql
        assert "Bool" in sql           # BooleanType

    def test_create_table_engine_clauses(self, dialect):
        """Full ENGINE / ORDER BY / PARTITION BY clauses."""
        expr = CreateTableExpression(
            dialect,
            TableExpression(dialect, "metrics"),
            [ColumnDefinition("id", IntegerType()), ColumnDefinition("ts", DateTimeType())],
            storage_options={
                "ENGINE": "MergeTree()",
                "ORDER BY": "id",
                "PARTITION BY": "toYYYYMM(ts)",
            },
        )
        sql, _ = expr.to_sql()
        assert "ENGINE = MergeTree()" in sql
        assert "PARTITION BY = toYYYYMM(ts)" in sql or "PARTITION BY toYYYYMM(ts)" in sql


class TestClickHouseTableEngineClauses:
    def test_table_engine_clauses_formatting(self, dialect):
        result = dialect.format_table_engine_clauses({
            "ENGINE": "MergeTree()",
            "ORDER BY": ["id", "ts"],
            "PARTITION BY": "toYYYYMM(ts)",
            "TTL": "ts + INTERVAL 30 DAY",
            "SETTINGS": "index_granularity = 8192",
        })
        assert "ENGINE = MergeTree()" in result
        assert "ORDER BY (id, ts)" in result
        assert "PARTITION BY toYYYYMM(ts)" in result
        assert "TTL ts + INTERVAL 30 DAY" in result
        assert "SETTINGS index_granularity = 8192" in result

    def test_table_engine_capabilities(self, dialect):
        assert dialect.supports_table_engine() is True
        assert dialect.supports_order_by_key() is True
        assert dialect.supports_partition_by_clause() is True
        assert dialect.supports_ttl_clause() is True
        assert dialect.supports_sample_clause() is True
        assert dialect.supports_table_settings() is True
        assert dialect.supports_final_modifier() is True
        assert dialect.supports_array_join() is True


class TestClickHouseTypeFormatting:
    """ClickHouseTypeSupportMixin type formatting."""

    def test_native_type_formatting(self, dialect):
        from rhosocial.activerecord.backend.impl.clickhouse.expression.types import (
            ClickHouseUInt32Type,
            ClickHouseStringType,
            ClickHouseDateTime64Type,
            ClickHouseArrayType,
            ClickHouseNullableType,
            ClickHouseMapType,
            ClickHouseDecimalType,
        )

        cases = {
            ClickHouseUInt32Type(): "UInt32",
            ClickHouseStringType(): "String",
            ClickHouseDateTime64Type(precision=3): "DateTime64(3)",
            ClickHouseArrayType(element_type=ClickHouseStringType()): "Array(String)",
            ClickHouseNullableType(inner_type=ClickHouseUInt32Type()): "Nullable(UInt32)",
            ClickHouseMapType(key_type=ClickHouseStringType(), value_type=ClickHouseUInt32Type()): "Map(String, UInt32)",
            ClickHouseDecimalType(precision=18, scale=4): "Decimal(18, 4)",
        }
        for data_type, expected in cases.items():
            sql, _ = data_type.to_sql(dialect)
            assert sql == expected, f"{type(data_type).__name__}: got {sql}, expected {expected}"

    def test_parse_type_roundtrip(self, dialect):
        """parse_type parses ClickHouse type strings back to DataType."""
        type_strs = [
            "Int8", "Int16", "Int32", "Int64",
            "UInt8", "UInt16", "UInt32", "UInt64",
            "Float32", "Float64",
            "Decimal(10, 2)",
            "String", "FixedString(16)",
            "Date", "Date32", "DateTime", "DateTime64(3)",
            "Bool", "UUID", "IPv4", "IPv6", "JSON",
            "Array(Int32)", "Map(String, Int32)",
            "Nullable(Int32)", "LowCardinality(String)",
        ]
        for type_str in type_strs:
            parsed = dialect.parse_type(type_str)
            sql, _ = parsed.to_sql(dialect)
            # Compare with whitespace normalized (Decimal(10, 2) == Decimal(10,2))
            assert type_str.lower().replace(" ", "") == sql.lower().replace(" ", ""), (
                f"{type_str} -> {sql}"
            )

    def test_parse_enum_type(self, dialect):
        parsed = dialect.parse_type("Enum8('a' = 1, 'b' = 2)")
        sql, _ = parsed.to_sql(dialect)
        assert sql.startswith("Enum8(")
        assert "'a'" in sql and "'b'" in sql

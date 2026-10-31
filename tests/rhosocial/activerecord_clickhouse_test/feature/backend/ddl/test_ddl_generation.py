# tests/rhosocial/activerecord_clickhouse_test/feature/backend/ddl/test_ddl_generation.py
"""
ClickHouse DDL generation tests (pure dialect, no database).

Covers ClickHouseTableMixin.format_create_table_statement and
ClickHouseTypeSupportMixin type formatting.
"""

import pytest

from rhosocial.activerecord.backend.expression.core import Column, FunctionCall
from rhosocial.activerecord.backend.expression.objects import Table
from rhosocial.activerecord.backend.expression.statements import (
    ColumnDefinition,
    CreateTableStatement,
)
from rhosocial.activerecord.backend.expression.types import (
    BooleanType,
    DateTimeType,
    DecimalType,
    IntegerType,
    VarCharType,
)
from rhosocial.activerecord.backend.impl.clickhouse.dialect import ClickHouseDialect
from rhosocial.activerecord.backend.impl.clickhouse.expression import (
    ClickHouseCreateTableOptions,
    ClickHouseEngineSpec,
    ClickHouseSetting,
    ClickHouseStorageOptionKind,
    ClickHouseTableStorageOption,
)


def _storage(dialect, engine=None, *, order_by=(), partition_by=None, settings=()):
    """Build the ClickHouse storage clause run for a CREATE TABLE."""
    clauses = []
    if engine is not None:
        clauses.append(
            ClickHouseTableStorageOption(
                dialect,
                ClickHouseStorageOptionKind.ENGINE,
                value=ClickHouseEngineSpec(dialect, engine),
            )
        )
    if order_by:
        clauses.append(
            ClickHouseTableStorageOption(
                dialect,
                ClickHouseStorageOptionKind.ORDER_BY,
                value=[Column(dialect, name) for name in order_by],
            )
        )
    if partition_by is not None:
        clauses.append(
            ClickHouseTableStorageOption(
                dialect,
                ClickHouseStorageOptionKind.PARTITION_BY,
                value=[partition_by],
            )
        )
    if settings:
        clauses.append(
            ClickHouseTableStorageOption(
                dialect,
                ClickHouseStorageOptionKind.SETTINGS,
                value=[ClickHouseSetting(dialect, name, value) for name, value in settings],
            )
        )
    return clauses


@pytest.fixture
def dialect():
    return ClickHouseDialect(version=(26, 7, 3))


class TestClickHouseDDLGeneration:
    def test_create_table_basic(self, dialect):
        """CREATE TABLE with ClickHouse storage options."""
        expr = CreateTableStatement(
            dialect,
            Table(dialect, "users"),
            [
                ColumnDefinition(dialect, "id", IntegerType(dialect)),
                ColumnDefinition(dialect, "name", VarCharType(length=100, dialect=dialect)),
            ],
            table_options=ClickHouseCreateTableOptions(
                dialect,
                table_storage_options=_storage(dialect, "MergeTree", order_by=("id",)),
            ),
        )
        sql, _ = expr.to_sql()
        assert "CREATE TABLE" in sql
        assert "ENGINE = MergeTree" in sql
        assert "ORDER BY `id`" in sql

    def test_create_table_if_not_exists(self, dialect):
        expr = CreateTableStatement(
            dialect,
            Table(dialect, "events"),
            [ColumnDefinition(dialect, "id", IntegerType(dialect))],
            if_not_exists=True,
            table_options=ClickHouseCreateTableOptions(
                dialect,
                table_storage_options=_storage(dialect, "MergeTree", order_by=("id",)),
            ),
        )
        sql, _ = expr.to_sql()
        assert "IF NOT EXISTS" in sql

    def test_create_table_types_map_to_clickhouse(self, dialect):
        """Core types map to ClickHouse equivalents."""
        expr = CreateTableStatement(
            dialect,
            Table(dialect, "t"),
            [
                ColumnDefinition(dialect, "id", IntegerType(dialect)),
                ColumnDefinition(dialect, "name", VarCharType(length=100, dialect=dialect)),
                ColumnDefinition(dialect, "amount", DecimalType(precision=10, scale=2, dialect=dialect)),
                ColumnDefinition(dialect, "ts", DateTimeType(dialect)),
                ColumnDefinition(dialect, "active", BooleanType(dialect)),
            ],
        )
        sql, _ = expr.to_sql()
        assert "Int32" in sql          # IntegerType
        assert "String" in sql         # VarCharType
        assert "Decimal(10, 2)" in sql
        assert "DateTime" in sql
        assert "Bool" in sql           # BooleanType

    def test_create_table_engine_clauses(self, dialect):
        """Full ENGINE / ORDER BY / PARTITION BY clauses."""
        expr = CreateTableStatement(
            dialect,
            Table(dialect, "metrics"),
            [
                ColumnDefinition(dialect, "id", IntegerType(dialect)),
                ColumnDefinition(dialect, "ts", DateTimeType(dialect)),
            ],
            table_options=ClickHouseCreateTableOptions(
                dialect,
                table_storage_options=_storage(
                    dialect,
                    "MergeTree",
                    order_by=("id",),
                    partition_by=FunctionCall(dialect, "toYYYYMM", Column(dialect, "ts")),
                ),
            ),
        )
        sql, _ = expr.to_sql()
        assert "ENGINE = MergeTree" in sql
        assert "PARTITION BY TOYYYYMM(" in sql


class TestClickHouseTableEngineClauses:
    def test_table_engine_clauses_formatting(self, dialect):
        from rhosocial.activerecord.backend.expression.operators import RawSQL

        clauses = _storage(
            dialect,
            "MergeTree",
            order_by=("id", "ts"),
            partition_by=FunctionCall(dialect, "toYYYYMM", Column(dialect, "ts")),
            settings=[("index_granularity", 8192)],
        )
        clauses.append(
            ClickHouseTableStorageOption(
                dialect,
                ClickHouseStorageOptionKind.TTL,
                value=RawSQL(dialect, "ts + INTERVAL 30 DAY"),
            )
        )
        rendered = []
        for clause in sorted(clauses, key=lambda item: item.option.rank):
            clause_sql, _ = clause.to_sql()
            rendered.append(clause_sql)
        result = " ".join(rendered)

        assert "ENGINE = MergeTree" in result
        assert "ORDER BY (`id`, `ts`)" in result
        assert "PARTITION BY TOYYYYMM(" in result
        assert "TTL ts + INTERVAL 30 DAY" in result
        assert "SETTINGS index_granularity = 8192" in result
        # ENGINE comes first, SETTINGS last, whatever order they were declared in.
        assert result.startswith("ENGINE = ")
        assert result.endswith("= 8192")

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
            ClickHouseUInt32Type(dialect): "UInt32",
            ClickHouseStringType(dialect): "String",
            ClickHouseDateTime64Type(dialect, precision=3): "DateTime64(3)",
            ClickHouseArrayType(element_type=ClickHouseStringType(dialect), dialect=dialect): "Array(String)",
            ClickHouseNullableType(dialect, inner_type=ClickHouseUInt32Type(dialect)): "Nullable(UInt32)",
            ClickHouseMapType(
                dialect, key_type=ClickHouseStringType(dialect), value_type=ClickHouseUInt32Type(dialect)
            ): "Map(String, UInt32)",
            ClickHouseDecimalType(dialect, precision=18, scale=4): "Decimal(18, 4)",
        }
        for data_type, expected in cases.items():
            sql, _ = data_type.to_sql()
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
            sql, _ = parsed.to_sql()
            # Compare with whitespace normalized (Decimal(10, 2) == Decimal(10,2))
            assert type_str.lower().replace(" ", "") == sql.lower().replace(" ", ""), (
                f"{type_str} -> {sql}"
            )

    def test_parse_enum_type(self, dialect):
        parsed = dialect.parse_type("Enum8('a' = 1, 'b' = 2)")
        sql, _ = parsed.to_sql()
        assert sql.startswith("Enum8(")
        assert "'a'" in sql and "'b'" in sql


class TestClickHouseStorageOptionContract:
    """The validation and spelling rules the option nodes own."""

    def test_repeated_option_is_refused_at_construction(self, dialect):
        engine = ClickHouseEngineSpec(dialect, "MergeTree")

        def clause():
            return ClickHouseTableStorageOption(
                dialect, ClickHouseStorageOptionKind.ENGINE, value=engine
            )

        with pytest.raises(ValueError, match="repeats ENGINE"):
            ClickHouseCreateTableOptions(dialect, table_storage_options=[clause(), clause()])

    def test_wrong_payload_names_the_member_and_the_type(self, dialect):
        with pytest.raises(TypeError, match="ENGINE takes a ClickHouseEngineSpec, got str"):
            ClickHouseTableStorageOption(
                dialect, ClickHouseStorageOptionKind.ENGINE, value="MergeTree"
            )

    def test_empty_expression_list_is_refused(self, dialect):
        with pytest.raises(ValueError, match="ORDER BY takes at least one expression"):
            ClickHouseTableStorageOption(
                dialect, ClickHouseStorageOptionKind.ORDER_BY, value=[]
            )

    def test_option_accepts_its_spelling_back(self, dialect):
        """A reader rebuilding the node hands the artifact's word, not a member."""
        clause = ClickHouseTableStorageOption(
            dialect, "ORDER BY", value=[Column(dialect, "id")]
        )
        assert clause.option is ClickHouseStorageOptionKind.ORDER_BY
        assert clause.to_sql() == ("ORDER BY `id`", ())

    def test_unknown_spelling_is_refused(self, dialect):
        with pytest.raises(ValueError, match="NOT A CLAUSE"):
            ClickHouseTableStorageOption(
                dialect, "NOT A CLAUSE", value=[Column(dialect, "id")]
            )


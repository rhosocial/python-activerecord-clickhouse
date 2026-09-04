# tests/rhosocial/activerecord_clickhouse_test/feature/backend/dialect/test_dialect_security.py
"""
Tests for ClickHouse dialect SQL injection security fixes.

This test module verifies that string escaping and validation
methods properly sanitize user input to prevent SQL injection.
Tests are run against the actual ClickHouse dialect.
"""

import pytest

from rhosocial.activerecord.backend.impl.clickhouse.dialect import ClickHouseDialect
from rhosocial.activerecord.backend.expression.statements import (
    ColumnDefinition,
    ColumnConstraint,
    ColumnConstraintType,
)
from rhosocial.activerecord.backend.expression.types import VarCharType
from rhosocial.activerecord.backend.impl.clickhouse.expression.json_table import (
    ClickHouseJSONTableExpression,
    JSONTableColumn,
)


@pytest.fixture
def dialect():
    """Create a ClickHouse test dialect."""
    return ClickHouseDialect()


def test_clickhouse_format_column_definition_default_string_escaping(dialect):
    """Test DEFAULT constraint string is escaped in ClickHouse."""
    constraint = ColumnConstraint(
        constraint_type=ColumnConstraintType.DEFAULT,
        default_value="test's value",
    )

    col_def = ColumnDefinition(
        name="test_col",
        data_type=VarCharType(length=255),
        constraints=[constraint],
    )

    sql, params = dialect.format_column_definition(col_def, ColumnConstraintType)
    assert "test''s value" in sql


def test_clickhouse_format_column_definition_comment_string_escaping(dialect):
    """Test COMMENT string is escaped in ClickHouse column definition."""
    col_def = ColumnDefinition(
        name="test_col",
        data_type=VarCharType(length=255),
        comment="Comment with 'single quote'",
    )

    sql, params = dialect.format_column_definition(col_def, ColumnConstraintType)
    assert "Comment with ''single quote''" in sql


def test_clickhouse_escape_sql_string(dialect):
    """Test ClickHouse inherits _escape_sql_string."""
    result = dialect._escape_sql_string("Table's comment")
    assert result == "Table''s comment"


def test_clickhouse_validate_data_type(dialect):
    """Test ClickHouse inherits _validate_data_type."""
    assert dialect._validate_data_type("VARCHAR(255)")
    assert dialect._validate_data_type("INT")
    assert dialect._validate_data_type("BIGINT")
    assert not dialect._validate_data_type("INT; DROP TABLE users--")


def test_clickhouse_format_column_definition_data_type_validation(dialect):
    """Test column definition validates data_type (VarChar maps to String)."""
    col_def = ColumnDefinition(
        name="test_col",
        data_type=VarCharType(length=255),
    )

    sql, params = dialect.format_column_definition(col_def)
    assert "String" in sql


def test_clickhouse_format_column_definition_data_type_rejects_injection(dialect):
    """Test that malicious data_type is rejected at construction time."""
    with pytest.raises(TypeError, match="data_type must be a DataType instance"):
        ColumnDefinition(
            name="test_col",
            data_type="VARCHAR(255); DROP TABLE users--",
        )


def test_clickhouse_json_table_unsupported(dialect):
    """ClickHouse does not support JSON_TABLE; formatting fails fast."""
    from rhosocial.activerecord.backend.dialect.exceptions import UnsupportedFeatureError

    expr = ClickHouseJSONTableExpression(
        dialect=dialect,
        json_doc='{"key": "value"}',
        path="$.key's",
        columns=[
            JSONTableColumn(
                name="col1",
                type="VARCHAR(255)",
                path="$.name",
            ),
        ],
    )

    with pytest.raises(UnsupportedFeatureError):
        dialect.format_json_table_expression(expr)

    assert dialect.supports_json_table() is False


def test_clickhouse_json_table_unsupported_validates_expression(dialect):
    """JSON_TABLE expression is rejected via validate when unsupported."""
    from rhosocial.activerecord.backend.dialect.exceptions import UnsupportedFeatureError

    expr = ClickHouseJSONTableExpression(
        dialect=dialect,
        json_doc='{"data": "test"}',
        path="$.data",
        columns=[
            JSONTableColumn(
                name="col1",
                type="VARCHAR(255)",
                path="$.field's",
            ),
        ],
        alias="test_alias",
    )

    with pytest.raises(UnsupportedFeatureError):
        dialect.format_json_table_expression(expr)


def test_clickhouse_format_cast_expression_valid(dialect):
    """Test that CAST expression validates target_type."""
    sql, params = dialect.format_cast_expression("column", "INTEGER", (), None)
    assert "INTEGER" in sql


def test_clickhouse_format_cast_expression_rejects_injection(dialect):
    """Test that malicious target_type is rejected."""
    with pytest.raises(ValueError, match="Invalid target type"):
        dialect.format_cast_expression("column", "INTEGER; DROP TABLE users--", (), None)


class TestClickHouseEscapeSqlStringBackslash:
    """Tests for ClickHouse _escape_sql_string with backslash escaping."""

    def test_escape_sql_string_backslash_escaped(self, dialect):
        """Test backslash is properly escaped in ClickHouse."""
        result = dialect._escape_sql_string("test\\value")
        assert "\\\\" in result

    def test_escape_sql_string_backslash_and_quote(self, dialect):
        """Test both backslash and single quote are escaped."""
        result = dialect._escape_sql_string("test\\'value")
        assert "\\\\" in result
        assert "''" in result

    def test_escape_sql_string_preserves_others(self, dialect):
        """Test other characters are preserved."""
        result = dialect._escape_sql_string('test"double"value')
        assert 'test"double"value' in result


class TestClickHouseJSONTableTypeValidation:
    """Tests for JSON_TABLE col.type validation (fast-fail on unsupported)."""

    def test_json_table_valid_data_type(self, dialect):
        """Test valid data type in JSON_TABLE column still constructs, then fails fast."""
        from rhosocial.activerecord.backend.dialect.exceptions import UnsupportedFeatureError

        expr = ClickHouseJSONTableExpression(
            dialect=dialect,
            json_doc='{"data": "test"}',
            path="$.data",
            columns=[
                JSONTableColumn(
                    name="col1",
                    type="VARCHAR(255)",
                    path="$.col1",
                ),
            ],
        )

        with pytest.raises(UnsupportedFeatureError):
            dialect.format_json_table_expression(expr)

    def test_json_table_invalid_data_type_rejected(self, dialect):
        """Test invalid data type in JSON_TABLE column fails fast as unsupported."""
        from rhosocial.activerecord.backend.dialect.exceptions import UnsupportedFeatureError

        expr = ClickHouseJSONTableExpression(
            dialect=dialect,
            json_doc='{"data": "test"}',
            path="$.data",
            columns=[
                JSONTableColumn(
                    name="col1",
                    type="VARCHAR(255); DROP TABLE users--",
                    path="$.col1",
                ),
            ],
        )

        with pytest.raises(UnsupportedFeatureError):
            dialect.format_json_table_expression(expr)


class TestClickHouseJSONTableErrorHandling:
    """Tests for JSON_TABLE col.error_handling validation (fast-fail on unsupported)."""

    def test_json_table_valid_error_handling_null(self, dialect):
        """Test valid error_handling: NULL still constructs, then fails fast."""
        from rhosocial.activerecord.backend.dialect.exceptions import UnsupportedFeatureError

        expr = ClickHouseJSONTableExpression(
            dialect=dialect,
            json_doc='{"data": "test"}',
            path="$.data",
            columns=[
                JSONTableColumn(
                    name="col1",
                    type="VARCHAR(255)",
                    path="$.col1",
                    error_handling="NULL",
                ),
            ],
        )

        with pytest.raises(UnsupportedFeatureError):
            dialect.format_json_table_expression(expr)

    def test_json_table_valid_error_handling_error(self, dialect):
        """Test valid error_handling: ERROR still constructs, then fails fast."""
        from rhosocial.activerecord.backend.dialect.exceptions import UnsupportedFeatureError

        expr = ClickHouseJSONTableExpression(
            dialect=dialect,
            json_doc='{"data": "test"}',
            path="$.data",
            columns=[
                JSONTableColumn(
                    name="col1",
                    type="VARCHAR(255)",
                    path="$.col1",
                    error_handling="ERROR",
                ),
            ],
        )

        with pytest.raises(UnsupportedFeatureError):
            dialect.format_json_table_expression(expr)

    def test_json_table_valid_error_handling_default(self, dialect):
        """Test valid error_handling: DEFAULT with default_value still constructs, then fails fast."""
        from rhosocial.activerecord.backend.dialect.exceptions import UnsupportedFeatureError

        expr = ClickHouseJSONTableExpression(
            dialect=dialect,
            json_doc='{"data": "test"}',
            path="$.data",
            columns=[
                JSONTableColumn(
                    name="col1",
                    type="VARCHAR(255)",
                    path="$.col1",
                    error_handling="DEFAULT",
                    default_value="fallback",
                ),
            ],
        )

        with pytest.raises(UnsupportedFeatureError):
            dialect.format_json_table_expression(expr)

    def test_json_table_invalid_error_handling_rejected(self, dialect):
        """Test invalid error_handling fails fast as unsupported."""
        from rhosocial.activerecord.backend.dialect.exceptions import UnsupportedFeatureError

        expr = ClickHouseJSONTableExpression(
            dialect=dialect,
            json_doc='{"data": "test"}',
            path="$.data",
            columns=[
                JSONTableColumn(
                    name="col1",
                    type="VARCHAR(255)",
                    path="$.col1",
                    error_handling="INVALID",
                ),
            ],
        )

        with pytest.raises(UnsupportedFeatureError):
            dialect.format_json_table_expression(expr)


class TestClickHouseJSONTableDefaultValueEscaping:
    """Tests for JSON_TABLE col.default_value escaping (fast-fail on unsupported)."""

    def test_json_table_default_value_escaped(self, dialect):
        """Test default_value with single quotes still constructs, then fails fast."""
        from rhosocial.activerecord.backend.dialect.exceptions import UnsupportedFeatureError

        expr = ClickHouseJSONTableExpression(
            dialect=dialect,
            json_doc='{"data": "test"}',
            path="$.data",
            columns=[
                JSONTableColumn(
                    name="col1",
                    type="VARCHAR(255)",
                    path="$.col1",
                    error_handling="DEFAULT",
                    default_value="it's broken",
                ),
            ],
        )

        with pytest.raises(UnsupportedFeatureError):
            dialect.format_json_table_expression(expr)


class TestClickHouseJSONTableJsonDocSecurity:
    """Tests for JSON_TABLE json_doc type validation (fast-fail on unsupported)."""

    def test_json_table_json_doc_string(self, dialect):
        """Test json_doc as string still constructs, then fails fast."""
        from rhosocial.activerecord.backend.dialect.exceptions import UnsupportedFeatureError

        expr = ClickHouseJSONTableExpression(
            dialect=dialect,
            json_doc='{"key": "value"}',
            path="$.key",
            columns=[
                JSONTableColumn(
                    name="col1",
                    type="VARCHAR(255)",
                    path="$.col1",
                ),
            ],
        )

        with pytest.raises(UnsupportedFeatureError):
            dialect.format_json_table_expression(expr)

    def test_json_table_json_doc_to_sql_protocol_rejected_by_validate(self, dialect):
        """Test json_doc as ToSQLProtocol still constructs, then fails fast.

        Note: The dialect previously rejected ToSQLProtocol json_doc in strict
        mode, but JSON_TABLE itself is unsupported so formatting always fails fast.
        """
        from rhosocial.activerecord.backend.dialect.exceptions import UnsupportedFeatureError
        from rhosocial.activerecord.backend.expression.bases import BaseExpression

        class MockExpression(BaseExpression):
            def __init__(self):
                self._sql = "JSON_COLUMN"
                self._params = ()

            def to_sql(self):
                return self._sql, self._params

        expr = ClickHouseJSONTableExpression(
            dialect=dialect,
            json_doc=MockExpression(),
            path="$.key",
            columns=[
                JSONTableColumn(
                    name="col1",
                    type="VARCHAR(255)",
                    path="$.col1",
                ),
            ],
        )

        with pytest.raises(UnsupportedFeatureError):
            dialect.format_json_table_expression(expr)

    def test_json_table_json_doc_invalid_type_rejected(self, dialect):
        """Test json_doc with invalid type still constructs, then fails fast."""
        from rhosocial.activerecord.backend.dialect.exceptions import UnsupportedFeatureError

        expr = ClickHouseJSONTableExpression(
            dialect=dialect,
            json_doc={"key": "value"},
            path="$.key",
            columns=[
                JSONTableColumn(
                    name="col1",
                    type="VARCHAR(255)",
                    path="$.col1",
                ),
            ],
        )

        with pytest.raises(UnsupportedFeatureError):
            dialect.format_json_table_expression(expr)


class TestClickHouseCreateTableCommentEscaping:
    """Tests for CREATE TABLE COMMENT escaping."""

    def test_create_table_comment_escaped(self, dialect):
        """Test table-level COMMENT is properly escaped."""
        from rhosocial.activerecord.backend.expression.statements import CreateTableExpression

        expr = CreateTableExpression(
            dialect=dialect,
            table="test_table",
            columns=[],
            dialect_options={
                "comment": "Table's comment with 'quotes'",
            },
        )

        sql, params = dialect.format_create_table_statement(expr)

        assert "Table''s comment" in sql
        assert "quotes''" in sql
        assert "'; DROP" not in sql

    def test_create_table_comment_with_backslash(self, dialect):
        """Test table-level COMMENT with backslash is properly escaped."""
        from rhosocial.activerecord.backend.expression.statements import CreateTableExpression

        expr = CreateTableExpression(
            dialect=dialect,
            table="test_table",
            columns=[],
            dialect_options={
                "comment": "Test\\value",
            },
        )

        sql, params = dialect.format_create_table_statement(expr)

        assert "\\\\" in sql


# ============================================================
# format_storage_options — ClickHouse native ENGINE / ORDER BY / TTL syntax
# ============================================================


def test_storage_options_normal_key_and_value(dialect):
    """ClickHouse storage option key/value are joined with ' = ' and not quoted."""
    sql = dialect.format_storage_options({"ENGINE": "MergeTree()"})
    assert "ENGINE = MergeTree()" in sql


def test_storage_options_multiple_keys(dialect):
    """Multiple storage options are space separated."""
    sql = dialect.format_storage_options({"ENGINE": "MergeTree()", "ORDER BY": "id"})
    assert "ENGINE = MergeTree()" in sql
    assert "ORDER BY = id" in sql


def test_storage_options_int_value(dialect):
    """Integer value is rendered without quotes."""
    sql = dialect.format_storage_options({"PARTITION_BY": 1000})
    assert "PARTITION_BY = 1000" in sql


def test_storage_options_string_value_preserved(dialect):
    """ClickHouse storage option values are NOT quoted (engine/expression names)."""
    sql = dialect.format_storage_options({"ENGINE": "MergeTree()"})
    assert "ENGINE = MergeTree()" == sql
    assert "'" not in sql


# ============================================================
# format_identifier — identifier quoting equivalence and injection immunity
# ============================================================


def test_format_identifier_normal(dialect):
    """Normal identifier is backtick-quoted."""
    result = dialect.format_identifier("users")
    assert result == "`users`"


def test_format_identifier_with_backtick(dialect):
    """Identifier with embedded backtick is properly escaped."""
    result = dialect.format_identifier("table`name")
    assert result == "`table``name`"


def test_format_identifier_injection_payload(dialect):
    """Identifier with injection payload is safely contained (balanced backticks)."""
    payload = "users`; DROP TABLE users--"
    result = dialect.format_identifier(payload)
    assert result.count("`") % 2 == 0, f"Unbalanced backticks: {result}"
    assert result == "`users``; DROP TABLE users--`"


def test_format_identifier_naive_vs_proper_safe(dialect):
    """For safe input, naive and proper quoting produce same structure."""
    names = ["users", "orders", "products", "table_1", "camelCase"]
    for name in names:
        naive = f"`{name}`"
        proper = dialect.format_identifier(name)
        assert naive == proper, f"Mismatch for '{name}': naive={naive}, proper={proper}"


def test_format_identifier_naive_vs_proper_malicious(dialect):
    """For malicious input, proper quoting prevents breakout that naive allows."""
    payloads = [
        "x`; DROP TABLE users--",
        "y`; DELETE FROM t--",
        "z`; UPDATE t SET a=1--",
    ]
    for payload in payloads:
        naive = f"`{payload}`"
        proper = dialect.format_identifier(payload)

        assert naive.count("`") % 2 != 0, f"Naive should unbalance backticks for '{payload}': {naive}"
        assert proper.count("`") % 2 == 0, f"Proper should balance backticks for '{payload}': {proper}"


def test_format_identifier_empty_string(dialect):
    """Empty identifier produces empty backticks."""
    assert dialect.format_identifier("") == "``"


# ── _escape_literal_percent ────────────────────────────────────────────


def test_escape_literal_percent_preserves_placeholders():
    """_escape_literal_percent escapes literal % but preserves %s markers."""
    from rhosocial.activerecord.backend.impl.clickhouse.backend import ClickHouseBackend

    # %s placeholder → unchanged
    assert ClickHouseBackend._escape_literal_percent(
        "SELECT * FROM users WHERE name = %s"
    ) == "SELECT * FROM users WHERE name = %s"

    # Literal % outside %s → %%
    assert ClickHouseBackend._escape_literal_percent(
        "SELECT * FROM users WHERE name LIKE 'foo%' AND id = %s"
    ) == "SELECT * FROM users WHERE name LIKE 'foo%%' AND id = %s"

    # Multiple %s with literal % between
    assert ClickHouseBackend._escape_literal_percent(
        "SELECT * FROM t WHERE a = %s AND b LIKE '100%' AND c = %s"
    ) == "SELECT * FROM t WHERE a = %s AND b LIKE '100%%' AND c = %s"

    # Pre-escaped %% → %%%% (preserved, then % formatting folds back to %%)
    assert ClickHouseBackend._escape_literal_percent(
        "SELECT * FROM system.tables WHERE name LIKE '%%view%%'"
    ) == "SELECT * FROM system.tables WHERE name LIKE '%%%%view%%%%'"

    # No params → no %s → all % are literal and should be escaped
    assert ClickHouseBackend._escape_literal_percent(
        "SELECT * FROM t WHERE name LIKE '100%'"
    ) == "SELECT * FROM t WHERE name LIKE '100%%'"

    # Empty string
    assert ClickHouseBackend._escape_literal_percent("") == ""

    # No % at all
    assert ClickHouseBackend._escape_literal_percent(
        "SELECT 1"
    ) == "SELECT 1"

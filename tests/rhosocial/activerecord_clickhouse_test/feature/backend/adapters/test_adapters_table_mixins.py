# tests/rhosocial/activerecord_clickhouse_test/feature/backend/adapters/test_adapters_table_mixins.py
"""
Coverage tests for ClickHouse adapters, table mixin, and transaction mixin.
"""

import uuid
from datetime import date, datetime, time
from decimal import Decimal
from enum import Enum

import pytest

from rhosocial.activerecord.backend.impl.clickhouse.adapters import (
    ClickHouseBlobAdapter,
    ClickHouseBooleanAdapter,
    ClickHouseDateAdapter,
    ClickHouseDatetimeAdapter,
    ClickHouseDecimalAdapter,
    ClickHouseEnumAdapter,
    ClickHouseJSONAdapter,
    ClickHouseTimeAdapter,
    ClickHouseUUIDAdapter,
    ClickHouseVectorAdapter,
)
from rhosocial.activerecord.backend.impl.clickhouse.dialect import ClickHouseDialect
from rhosocial.activerecord.backend.impl.clickhouse.mixins.table import ClickHouseTableMixin


@pytest.fixture
def dialect():
    return ClickHouseDialect(version=(26, 7, 3))


# ===========================================================================
# adapters.py coverage
# ===========================================================================


class TestAdapters:
    def test_blob_adapter(self):
        a = ClickHouseBlobAdapter()
        assert a.to_database(b"\x00\x01", bytes) == b"\x00\x01"
        assert a.to_database(None, bytes) is None
        assert a.from_database(b"\x00\x01", bytes) == b"\x00\x01"
        assert a.from_database(None, bytes) is None
        assert a.supported_types == {bytes: [bytes]}

    def test_json_adapter(self):
        a = ClickHouseJSONAdapter()
        assert a.to_database({"a": 1}, str) == '{"a": 1}'
        assert a.to_database([1, 2], str) == "[1, 2]"
        assert a.to_database(None, str) is None
        assert a.from_database('{"a": 1}', str) == {"a": 1}
        assert a.from_database({"a": 1}, str) == {"a": 1}  # already dict
        assert a.from_database([1, 2], str) == [1, 2]  # already list
        assert a.from_database(None, str) is None

    def test_uuid_adapter(self):
        a = ClickHouseUUIDAdapter()
        uid = uuid.uuid4()
        assert a.to_database(uid, str) == str(uid)
        assert a.to_database(None, str) is None
        assert a.from_database(str(uid), uuid.UUID) == uid
        assert a.from_database(uid, uuid.UUID) == uid  # already UUID
        assert a.from_database(None, uuid.UUID) is None

    def test_boolean_adapter(self):
        a = ClickHouseBooleanAdapter()
        assert a.to_database(True, int) == 1
        assert a.to_database(False, int) == 0
        assert a.to_database(None, int) is None
        assert a.from_database(1, bool) is True
        assert a.from_database(0, bool) is False
        assert a.from_database(True, bool) is True
        assert a.from_database(None, bool) is None

    def test_decimal_adapter(self):
        a = ClickHouseDecimalAdapter()
        d = Decimal("123.45")
        assert a.from_database(d, Decimal) == d
        assert a.from_database("123.45", Decimal) == Decimal("123.45")
        assert a.from_database(123.45, Decimal) == Decimal("123.45")
        assert a.from_database(None, Decimal) is None
        # to_database accepts Decimal
        assert a.to_database(d, Decimal) == d

    def test_date_adapter(self):
        a = ClickHouseDateAdapter()
        d = date(2024, 6, 15)
        assert a.from_database(d, date) == d
        assert a.from_database("2024-06-15", date) == d
        assert a.from_database(None, date) is None

    def test_time_adapter(self):
        a = ClickHouseTimeAdapter()
        t = time(10, 30, 45)
        assert a.from_database(t, time) == t
        assert a.from_database("10:30:45", time) == t
        assert a.from_database(None, time) is None

    def test_datetime_adapter(self):
        a = ClickHouseDatetimeAdapter((26, 7, 3))
        dt = datetime(2024, 6, 15, 10, 30, 45)
        # datetime input passes through; string input is parsed (carries UTC tz)
        result = a.from_database(dt, datetime)
        assert result.year == 2024 and result.month == 6 and result.day == 15
        assert result.hour == 10 and result.minute == 30 and result.second == 45
        parsed = a.from_database("2024-06-15 10:30:45", datetime)
        assert parsed.year == 2024 and parsed.hour == 10
        assert a.from_database(None, datetime) is None

    def test_vector_adapter(self):
        a = ClickHouseVectorAdapter()
        assert a.to_database([1.0, 2.0], list) == "[1.0,2.0]"
        assert a.to_database(None, list) is None
        assert a.from_database("[1.0, 2.0]", list) == [1.0, 2.0]
        assert a.from_database(None, list) is None


class TestEnumAdapter:
    def test_enum_adapter_string(self):
        a = ClickHouseEnumAdapter(use_int_storage=False)
        class Color(Enum):
            RED = "red"
            BLUE = "blue"

        assert a.to_database(Color.RED, str) == "red"
        assert a.from_database("red", Color) == Color.RED
        assert a.from_database(None, Color) is None


# ===========================================================================
# mixins/table.py coverage
# ===========================================================================


class TestTableMixin:
    def test_validate_data_type(self):
        assert ClickHouseTableMixin._validate_data_type("UInt32") is True
        assert ClickHouseTableMixin._validate_data_type("Decimal(10, 2)") is True
        assert ClickHouseTableMixin._validate_data_type("Enum8('a')") is True
        assert ClickHouseTableMixin._validate_data_type("bad sql; DROP") is False

    def test_supports_flags(self):
        m = ClickHouseTableMixin()
        assert m.supports_table_like_syntax() is True
        assert m.supports_inline_index() is True
        assert m.supports_storage_engine_option() is True
        assert m.supports_charset_option() is True

    def test_format_storage_options(self, dialect):
        # dialect exposes format_storage_options via MRO (ClickHouseTableMixin)
        result = dialect.format_storage_options({"ENGINE": "MergeTree()", "ORDER BY": "id"})
        assert "ENGINE = MergeTree()" in result
        assert "ORDER BY = id" in result
        assert "'MergeTree()'" not in result

    def test_format_inline_index(self, dialect):
        from types import SimpleNamespace
        idx = SimpleNamespace(unique=False, name="idx1", columns=["a", "b"], type="minmax")
        result = dialect.format_inline_index(idx)
        assert "INDEX" in result
        assert "idx1" in result
        assert "a" in result and "b" in result
        assert "minmax" in result

    def test_format_inline_index_unique_raises(self, dialect):
        from rhosocial.activerecord.backend.dialect.exceptions import UnsupportedFeatureError
        from types import SimpleNamespace
        idx = SimpleNamespace(unique=True, name="idx1", columns=["a"], type=None)
        with pytest.raises(UnsupportedFeatureError):
            dialect.format_inline_index(idx)

    def test_format_table_constraint_primary_key(self, dialect):
        from rhosocial.activerecord.backend.expression.statements import TableConstraintType
        from types import SimpleNamespace
        tc = SimpleNamespace(name="pk", constraint_type=TableConstraintType.PRIMARY_KEY, columns=["id"])
        result, _ = dialect.format_table_constraint(tc)
        assert "PRIMARY KEY" in result
        assert "id" in result

    def test_format_table_constraint_unique_raises(self, dialect):
        from rhosocial.activerecord.backend.expression.statements import TableConstraintType
        from rhosocial.activerecord.backend.dialect.exceptions import UnsupportedFeatureError
        from types import SimpleNamespace
        tc = SimpleNamespace(name=None, constraint_type=TableConstraintType.UNIQUE, columns=["email"])
        with pytest.raises(UnsupportedFeatureError):
            dialect.format_table_constraint(tc)

    def test_format_table_constraint_fk_raises(self, dialect):
        from rhosocial.activerecord.backend.expression.statements import TableConstraintType
        from rhosocial.activerecord.backend.dialect.exceptions import UnsupportedFeatureError
        from types import SimpleNamespace
        tc = SimpleNamespace(name=None, constraint_type=TableConstraintType.FOREIGN_KEY, columns=["user_id"])
        with pytest.raises(UnsupportedFeatureError):
            dialect.format_table_constraint(tc)

    def test_format_column_definition_auto_increment_raises(self, dialect):
        from rhosocial.activerecord.backend.dialect.exceptions import UnsupportedFeatureError
        from rhosocial.activerecord.backend.expression.statements import ColumnConstraint, ColumnConstraintType
        from rhosocial.activerecord.backend.expression.statements import ColumnDefinition
        from rhosocial.activerecord.backend.expression.types import IntegerType

        col_def = ColumnDefinition(
            "id",
            IntegerType(),
            constraints=[ColumnConstraint(ColumnConstraintType.PRIMARY_KEY, is_auto_increment=True)],
        )
        with pytest.raises(UnsupportedFeatureError):
            dialect.format_column_definition(col_def)


# ===========================================================================
# mixins/transaction.py coverage
# ===========================================================================


class TestTransactionMixin:
    @pytest.fixture
    def tx_mixin(self):
        from rhosocial.activerecord.backend.impl.clickhouse.mixins.transaction import ClickHouseTransactionMixin
        from rhosocial.activerecord.backend.transaction import IsolationLevel

        class Stub(ClickHouseTransactionMixin):
            def __init__(s):
                s._isolation_level = None
                s._transaction_level = 0
            @property
            def is_active(s):
                return False
            def log(s, level, msg):
                pass

        return Stub()

    def test_isolation_level_getter(self, tx_mixin):
        assert tx_mixin.isolation_level is None

    def test_isolation_level_setter_valid(self, tx_mixin):
        from rhosocial.activerecord.backend.transaction import IsolationLevel
        tx_mixin.isolation_level = IsolationLevel.READ_COMMITTED
        assert tx_mixin.isolation_level == IsolationLevel.READ_COMMITTED

    def test_isolation_level_setter_invalid(self, tx_mixin):
        from rhosocial.activerecord.backend.transaction import IsolationLevelError
        with pytest.raises(IsolationLevelError):
            tx_mixin.isolation_level = "INVALID"

    def test_build_set_isolation_sql(self, tx_mixin):
        from rhosocial.activerecord.backend.transaction import IsolationLevel
        sql, params = tx_mixin._build_set_isolation_sql(IsolationLevel.SERIALIZABLE)
        assert "SERIALIZABLE" in sql
        assert params == ()

    def test_build_set_isolation_sql_invalid(self, tx_mixin):
        from rhosocial.activerecord.backend.transaction import IsolationLevelError
        with pytest.raises(IsolationLevelError):
            tx_mixin._build_set_isolation_sql("INVALID")

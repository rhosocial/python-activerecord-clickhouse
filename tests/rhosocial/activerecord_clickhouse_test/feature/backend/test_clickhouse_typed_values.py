# tests/rhosocial/activerecord_clickhouse_test/feature/backend/test_clickhouse_typed_values.py
"""ClickHouse spellings for the typed value nodes, pinned to live measurements.

Every literal asserted here was measured against the instance
``tests/config/clickhouse_scenarios.yaml`` names ``clickhouse_http``:
**ClickHouse 26.7.3.19 (official build)**, HTTP on ``127.0.0.1:18682``,
database ``test_db``. The statements and readbacks behind each verdict are
recorded in ``mixins/typed_value.py``; this module pins the rendered text and
re-verifies the two tier-2 spellings against the live server (CREATE TABLE
with the literal as a DEFAULT, INSERT, read back, compare).

The tier-1 kinds (NULL, booleans, numbers, strings, dates) render through the
base's ``format_literal`` and were measured accepted verbatim, so they are
asserted for the wiring only -- exact text, no override expected.
"""

import datetime
import uuid as uuidlib
from decimal import Decimal

import pytest

from rhosocial.activerecord.backend.dialect.mixins import TypedValueMixin
from rhosocial.activerecord.backend.expression.values import (
    BinaryValue,
    BooleanValue,
    DateValue,
    DecimalValue,
    FloatValue,
    IntegerValue,
    IntervalValue,
    NullValue,
    StringValue,
    TimeValue,
    TimestampValue,
    UUIDValue,
)
from rhosocial.activerecord.backend.impl.clickhouse.dialect import ClickHouseDialect
from rhosocial.activerecord.backend.impl.clickhouse.mixins import ClickHouseTypedValueMixin

#: The exact release every verdict below was measured on. Hard-coded on
#: purpose, the same way ``test_clickhouse_constraint_capabilities.py`` does
#: it: reading it back from the dialect would let a version bump silently
#: re-label the evidence.
MEASURED_VERSION = (26, 7, 3)

_UUID = uuidlib.UUID("01234567-89ab-cdef-0123-456789abcdef")
_UUID_TEXT = "01234567-89ab-cdef-0123-456789abcdef"


# ---------------------------------------------------------------------------
# DDL-position spellings of the value classes.
#
# ``inline_params`` is a class-level rendering strategy: a node inlines
# because *its class* owns the DDL position, never because an instance or a
# call site flipped a switch. The subclasses below are that class, spelled
# the way the core's own DDL lift (``Literal`` -> ``DdlLiteral``) spells it.
# ---------------------------------------------------------------------------


class DdlNullValue(NullValue):
    """The DDL-position spelling of a NULL value."""

    inline_params = True


class DdlBooleanValue(BooleanValue):
    """The DDL-position spelling of a boolean value."""

    inline_params = True


class DdlIntegerValue(IntegerValue):
    """The DDL-position spelling of an integer value."""

    inline_params = True


class DdlFloatValue(FloatValue):
    """The DDL-position spelling of a float value."""

    inline_params = True


class DdlDecimalValue(DecimalValue):
    """The DDL-position spelling of a decimal value."""

    inline_params = True


class DdlStringValue(StringValue):
    """The DDL-position spelling of a string value."""

    inline_params = True


class DdlBinaryValue(BinaryValue):
    """The DDL-position spelling of a binary value."""

    inline_params = True


class DdlDateValue(DateValue):
    """The DDL-position spelling of a date value."""

    inline_params = True


class DdlTimeValue(TimeValue):
    """The DDL-position spelling of a time value."""

    inline_params = True


class DdlTimestampValue(TimestampValue):
    """The DDL-position spelling of a timestamp value."""

    inline_params = True


class DdlIntervalValue(IntervalValue):
    """The DDL-position spelling of an interval value."""

    inline_params = True


class DdlUUIDValue(UUIDValue):
    """The DDL-position spelling of a UUID value."""

    inline_params = True


class TestTierOneWiring:
    """The tier-1 kinds render through the base spellings, measured accepted."""

    @pytest.fixture()
    def dialect(self) -> ClickHouseDialect:
        return ClickHouseDialect(version=MEASURED_VERSION)

    def test_data_positions_bind_the_host_value(self, dialect):
        """A data position emits the placeholder and hands the value to the driver."""
        cases = (
            (NullValue(dialect), None),
            (BooleanValue(dialect, True), True),
            (IntegerValue(dialect, 42), 42),
            (FloatValue(dialect, 1.5), 1.5),
            (DecimalValue(dialect, Decimal("3.14")), Decimal("3.14")),
            (StringValue(dialect, "it's"), "it's"),
            (DateValue(dialect, datetime.date(2026, 1, 1)), datetime.date(2026, 1, 1)),
            (TimeValue(dialect, datetime.time(12, 30)), datetime.time(12, 30)),
            (
                TimestampValue(dialect, datetime.datetime(2026, 1, 1, 12, 0)),
                datetime.datetime(2026, 1, 1, 12, 0),
            ),
        )
        for node, host_value in cases:
            sql, params = node.to_sql()
            assert sql == "%s"
            assert params == (host_value,)

    def test_ddl_positions_render_the_base_spellings(self, dialect):
        """A DDL position renders the exact inline text measured accepted:
        ``DEFAULT '2026-01-01'``, ``DEFAULT TRUE`` and friends all answered
        accepted on 26.7.3.19, so the base spellings are ClickHouse's own."""
        cases = (
            (DdlNullValue(dialect), "NULL"),
            (DdlBooleanValue(dialect, True), "TRUE"),
            (DdlBooleanValue(dialect, False), "FALSE"),
            (DdlIntegerValue(dialect, 42), "42"),
            (DdlFloatValue(dialect, 1.5), "1.5"),
            (DdlDecimalValue(dialect, Decimal("3.14")), "3.14"),
            (DdlStringValue(dialect, "it's"), "'it''s'"),
            (DdlDateValue(dialect, datetime.date(2026, 1, 1)), "'2026-01-01'"),
            (DdlTimeValue(dialect, datetime.time(12, 30)), "'12:30:00'"),
            (
                DdlTimestampValue(dialect, datetime.datetime(2026, 1, 1, 12, 0)),
                "'2026-01-01 12:00:00'",
            ),
        )
        for node, expected in cases:
            sql, params = node.to_sql()
            assert sql == expected
            assert params == ()


class TestTierTwoOverrides:
    """ClickHouse's own spellings for binary and UUID, and the deliberate
    INTERVAL refusal."""

    @pytest.fixture()
    def dialect(self) -> ClickHouseDialect:
        return ClickHouseDialect(version=MEASURED_VERSION)

    def test_binary_data_position_binds_bytes(self, dialect):
        node = BinaryValue(dialect, b"\x01\x02")
        sql, params = node.to_sql()
        assert sql == "%s"
        assert params == (b"\x01\x02",)

    def test_binary_ddl_position_renders_unhex(self, dialect):
        """``unhex('0102')``: the measured DEFAULT accepted it and a row read
        back ``hex(s) = '0102'`` (see the mixin docstring)."""
        node = DdlBinaryValue(dialect, b"\x01\x02")
        sql, params = node.to_sql()
        assert sql == "unhex('0102')"
        assert params == ()

    def test_uuid_data_position_binds_the_uuid(self, dialect):
        node = UUIDValue(dialect, _UUID)
        sql, params = node.to_sql()
        assert sql == "%s"
        assert params == (_UUID,)

    def test_uuid_ddl_position_renders_bare_quoted_text(self, dialect):
        """The ``UUID`` type parses the canonical form, so the literal is the
        bare quoted text -- measured accepted as a DEFAULT and read back
        verbatim through ``toString(u)``."""
        node = DdlUUIDValue(dialect, _UUID)
        sql, params = node.to_sql()
        assert sql == f"'{_UUID_TEXT}'"
        assert params == ()

    def test_interval_data_position_binds_the_timedelta(self, dialect):
        """The data position is unaffected by the refusal: the driver takes
        the ``timedelta`` and ClickHouse's parameter binding is the caller's
        concern."""
        span = datetime.timedelta(days=1)
        node = IntervalValue(dialect, span)
        sql, params = node.to_sql()
        assert sql == "%s"
        assert params == (span,)

    def test_interval_ddl_position_fails_explicitly(self, dialect):
        """The DDL position is the refused one: the grammar's ``INTERVAL``
        names its own unit and a mixed-unit span degrades to a tuple (see
        the mixin docstring), so the base's explicit failure is the answer."""
        with pytest.raises(NotImplementedError, match="INTERVAL literals"):
            DdlIntervalValue(dialect, datetime.timedelta(days=1)).to_sql()

    def test_interval_override_is_structurally_absent(self):
        """The refusal is a missing method, not a method that raises: a future
        subclass of ClickHouseTypedValueMixin that accidentally grows one
        would change the answer without touching this package's dialect
        wiring, so the absence itself is asserted."""
        assert "format_interval_value" not in vars(ClickHouseTypedValueMixin)

    def test_backend_mixin_outranks_the_core_one(self):
        """``ClickHouseTypedValueMixin`` must resolve ahead of the core's
        ``TypedValueMixin`` in the MRO, or the tier-2 spellings would never
        be reached (the core's are explicit ``NotImplementedError``)."""
        mro = ClickHouseDialect.__mro__
        assert mro.index(ClickHouseTypedValueMixin) < mro.index(TypedValueMixin)


class TestLiveDatabaseRoundTrips:
    """The two tier-2 spellings, verified end to end on the scenario server:
    CREATE TABLE with the rendered literal as a DEFAULT, INSERT a row, read
    the stored value back and compare."""

    def _drop(self, backend, name):
        backend.execute(f"DROP TABLE IF EXISTS {name}")

    def test_binary_default_roundtrip(self, clickhouse_backend):
        from rhosocial.activerecord.backend.expression.objects import Table
        from rhosocial.activerecord.backend.expression.statements import (
            ColumnConstraint,
            ColumnDefaultConstraint,
            ColumnDefinition,
            CreateTableStatement,
        )
        from rhosocial.activerecord.backend.expression.types import (
            IntegerType,
            VarCharType,
        )

        backend = clickhouse_backend
        dialect = backend.dialect
        name = "probe_typed_value_bin"
        self._drop(backend, name)
        try:
            create = CreateTableStatement(
                dialect,
                Table(dialect, name),
                [
                    ColumnDefinition(dialect, "id", IntegerType(dialect)),
                    ColumnDefinition(
                        dialect,
                        "s",
                        VarCharType(dialect=dialect),
                        constraints=[
                            ColumnConstraint(
                                dialect,
                                branch=ColumnDefaultConstraint(
                                    dialect, DdlBinaryValue(dialect, b"\x01\x02")
                                ),
                            )
                        ],
                    ),
                ],
                storage_options={"ENGINE": "MergeTree()", "ORDER BY": "id"},
            )
            sql, params = create.to_sql()
            assert params == ()
            backend.execute(sql, params)
            backend.execute(f"INSERT INTO {name} (id) VALUES (1)")
            result = backend.execute(f"SELECT hex(s) FROM {name}")
            assert [row["hex(s)"] for row in result.data] == ["0102"]
        finally:
            self._drop(backend, name)

    def test_uuid_default_roundtrip(self, clickhouse_backend):
        from rhosocial.activerecord.backend.expression.objects import Table
        from rhosocial.activerecord.backend.expression.statements import (
            ColumnConstraint,
            ColumnDefaultConstraint,
            ColumnDefinition,
            CreateTableStatement,
        )
        from rhosocial.activerecord.backend.expression.types import (
            IntegerType,
            UUIDType,
        )

        backend = clickhouse_backend
        dialect = backend.dialect
        name = "probe_typed_value_uuid"
        self._drop(backend, name)
        try:
            create = CreateTableStatement(
                dialect,
                Table(dialect, name),
                [
                    ColumnDefinition(dialect, "id", IntegerType(dialect)),
                    ColumnDefinition(
                        dialect,
                        "u",
                        UUIDType(dialect),
                        constraints=[
                            ColumnConstraint(
                                dialect,
                                branch=ColumnDefaultConstraint(
                                    dialect, DdlUUIDValue(dialect, _UUID)
                                ),
                            )
                        ],
                    ),
                ],
                storage_options={"ENGINE": "MergeTree()", "ORDER BY": "id"},
            )
            sql, params = create.to_sql()
            assert params == ()
            backend.execute(sql, params)
            backend.execute(f"INSERT INTO {name} (id) VALUES (1)")
            result = backend.execute(f"SELECT toString(u) FROM {name}")
            assert [row["toString(u)"] for row in result.data] == [_UUID_TEXT]
        finally:
            self._drop(backend, name)

# tests/rhosocial/activerecord_clickhouse_test/feature/backend/dialect/test_column_type.py
"""ClickHouse's eighteen-entry column-type table.

Pure dialect tests -- no server. What is asserted here is the *declaration*:
that the dialect answers every entry of the protocol's common-type list, that
the cells are the ones the 26.7.3.19 probe measured, and that nothing is
refused without a written-down reason. The rendering those cells imply is
Phase 2b's work and is deliberately not asserted here.

The answers are read through the model layer's own selection
(``resolve_column_class``) wherever that is possible, because a table that
answers correctly but is not reachable by the selection would fail only at
query time.
"""

import datetime
import decimal
import enum
import uuid

import pytest
from rhosocial.activerecord.backend.dialect.mixins import ColumnTypeMixin
from rhosocial.activerecord.backend.expression.column_types import (
    ArrayColumn,
    BinaryColumn,
    BooleanColumn,
    ColumnBase,
    IntegerColumn,
    JSONColumn,
    NumericColumn,
    StringColumn,
    TimestampColumn,
    UUIDColumn,
)
from rhosocial.activerecord.backend.impl.clickhouse.dialect import ClickHouseDialect
from rhosocial.activerecord.backend.impl.clickhouse.mixins import (
    ClickHouseColumnTypeMixin,
)
from rhosocial.activerecord.testsuite.feature.query.typed_column.column_helpers import (
    COMMON_TYPES,
    resolve_column_class,
)

#: The version every probe behind this table ran on.
MEASURED = (26, 7, 3)

#: ``{entry: answer}`` as ClickHouse states it. Written out in full rather than
#: derived, because a derived table would restate the code's own answer back at
#: itself and could not catch a change to it.
_CLICKHOUSE_ANSWERS = [
    (bool, BooleanColumn),
    (int, IntegerColumn),
    (float, NumericColumn),
    (decimal.Decimal, NumericColumn),
    (str, StringColumn),
    (bytes, BinaryColumn),
    (bytearray, BinaryColumn),
    (datetime.date, TimestampColumn),
    (datetime.time, TimestampColumn),
    (datetime.datetime, TimestampColumn),
    (datetime.timedelta, NumericColumn),
    (uuid.UUID, UUIDColumn),
    (dict, JSONColumn),
    (list, ArrayColumn),
    (tuple, ArrayColumn),
    (set, ArrayColumn),
    (frozenset, ArrayColumn),
    (enum.Enum, StringColumn),
]

_ENTRY_IDS = [getattr(entry, "__name__", str(entry)) for entry, _ in _CLICKHOUSE_ANSWERS]

#: The entries this backend answers ``None`` for, each with the reason it was
#: measured to be inexpressible. Empty: the 26.7.3.19 probe found a working
#: pairing for all eighteen -- ClickHouse has a native array, a native JSON type
#: and ``ILIKE``, which are exactly the three things the backends that *do*
#: refuse lack. Kept as a declaration so that adding a ``None`` later means
#: adding its reason here, and so a ``None`` nobody justified is a test failure
#: rather than a quiet gap.
_REFUSALS: dict = {}


@pytest.fixture
def dialect():
    return ClickHouseDialect(version=MEASURED)


class TestTableCompleteness:
    """A hole in the table is a silent gap, and the protocol forbids one."""

    def test_the_dialect_carries_the_mixin(self, dialect):
        assert isinstance(dialect, ClickHouseColumnTypeMixin)
        assert isinstance(dialect, ColumnTypeMixin)

    def test_the_clickhouse_half_comes_first_in_the_mro(self, dialect):
        """The load-bearing part of the dialect's base list.

        ``ClickHouseColumnTypeMixin`` overrides ``suggested_column_types()``, so
        C3 has to see it before ``ColumnTypeMixin`` or the answer would be the
        NotImplementedError core raises. Nothing in a query would look wrong
        either way -- the failure names the table, not the composition -- which
        is exactly why it takes an assertion to notice.
        """
        mro = type(dialect).__mro__
        assert mro.index(ClickHouseColumnTypeMixin) < mro.index(ColumnTypeMixin)

    def test_every_entry_of_the_contract_is_answered(self, dialect):
        """All eighteen, by name -- an omission fails here rather than at lookup."""
        table = dialect.suggested_column_types()
        assert [e for e in COMMON_TYPES if e not in table] == []

    def test_the_table_has_no_entry_beyond_the_contract(self, dialect):
        """No extra key of ClickHouse's own; an extension would be a deliberate act."""
        table = dialect.suggested_column_types()
        assert set(table) == set(COMMON_TYPES)

    def test_every_answer_is_a_class_or_none(self, dialect):
        """The protocol's two answer states, and no third one."""
        table = dialect.suggested_column_types()
        malformed = [
            (getattr(entry, "__name__", str(entry)), value)
            for entry, value in table.items()
            if value is not None and not (isinstance(value, type) and issubclass(value, ColumnBase))
        ]
        assert malformed == []

    def test_no_entry_is_refused_without_a_reason(self, dialect):
        """``None`` is a last resort and must be justified, or answered as a class.

        The probe found a pairing for all eighteen here, so the honest answer is
        a class for all of them: Firebird's ``dict`` and ``list`` (no JSON
        functions, no arrays at all) and MySQL 5.6's (no JSON functions) have
        something to refuse and ClickHouse does not.
        """
        table = dialect.suggested_column_types()
        refused = [entry for entry in COMMON_TYPES if table[entry] is None]
        assert refused == []
        assert set(_REFUSALS) == {e for e in COMMON_TYPES if table[e] is None}

    @pytest.mark.parametrize("entry", COMMON_TYPES, ids=_ENTRY_IDS)
    def test_every_answer_is_a_column_class(self, dialect, entry):
        answer = dialect.suggested_column_types()[entry]
        assert isinstance(answer, type)
        assert issubclass(answer, ColumnBase)

    @pytest.mark.parametrize("entry", COMMON_TYPES, ids=_ENTRY_IDS)
    def test_every_entry_resolves_through_the_selection(self, dialect, entry):
        """Through the model layer's own lookup, not by reading the dict."""
        assert resolve_column_class(dialect, entry) is (dialect.suggested_column_types()[entry])

    @pytest.mark.parametrize("entry", COMMON_TYPES, ids=_ENTRY_IDS)
    def test_every_answer_builds_a_column(self, dialect, entry):
        """A class in the table is only real if a column can be built from it."""
        column = resolve_column_class(dialect, entry)(dialect, "c")
        assert isinstance(column, ColumnBase)

    def test_the_table_is_a_copy(self, dialect):
        """Mutating the answer must not corrupt the table the next lookup reads."""
        first = dialect.suggested_column_types()
        first[str] = IntegerColumn
        assert dialect.suggested_column_types()[str] is StringColumn


class TestMeasuredCells:
    """The 26.7.3.19 answers, cell by cell."""

    @pytest.mark.parametrize("entry, expected", _CLICKHOUSE_ANSWERS, ids=_ENTRY_IDS)
    def test_measured_entry(self, dialect, entry, expected):
        assert dialect.suggested_column_types()[entry] is expected

    @pytest.mark.parametrize("entry, expected", _CLICKHOUSE_ANSWERS, ids=_ENTRY_IDS)
    def test_measured_entry_through_the_selection(self, dialect, entry, expected):
        assert resolve_column_class(dialect, entry) is expected

    def test_int_stays_integer_column(self, dialect):
        """议题 C is open: this is not a ruling that ClickHouse has no UInt class.

        ClickHouse has ``UInt8``..``UInt256``. Whether "non-negative only" earns
        a column class of its own is undecided, so ``int`` answers the whole
        number every backend answers. The test exists so that a future ruling is
        a deliberate change here rather than an accident.
        """
        assert resolve_column_class(dialect, int) is IntegerColumn

    def test_the_numeric_family_answers_the_one_numeric_class(self, dialect):
        """``float``, ``Decimal`` and ``timedelta`` all answer NumericColumn.

        The measurement behind the float and Decimal cells is that they are
        genuinely different surfaces on this server: Float64 yields inf on
        overflow and carries nan natively, and ``AVG`` of a Decimal answers
        Float64 rather than a Decimal. That difference is real but it is not a
        *column* difference any more -- core carries one class for every numeric
        width and precision, and the difference between a ``Decimal(18, 4)`` and
        a ``Float64`` belongs to the DDL layer's DataType, which this table never
        reads. A duration is a number of seconds here, so it answers the same
        class as the other numbers.
        """
        assert resolve_column_class(dialect, float) is NumericColumn
        assert resolve_column_class(dialect, decimal.Decimal) is NumericColumn
        assert resolve_column_class(dialect, datetime.timedelta) is NumericColumn

    def test_time_is_provisional(self, dialect):
        """Core has no TimeColumn yet, so the shared TimestampColumn stands.

        Worth pinning because it is wrong twice over in the meantime: this
        backend's own ``TimeType`` still renders ``DateTime`` while ClickHouse
        has had ``Time``/``Time64`` for a while (investigation appendix D-①).
        """
        assert resolve_column_class(dialect, datetime.time) is TimestampColumn


class TestArrayCells:
    """``Array(T)`` is native here, which is the whole reason for these cells."""

    @pytest.mark.parametrize("entry", [list, tuple, set, frozenset])
    def test_container_entry_is_an_array(self, dialect, entry):
        assert resolve_column_class(dialect, entry) is ArrayColumn

    def test_tuple_carries_no_narrowing(self, dialect):
        """议题 A is open and this cell is its subject, not its answer.

        ClickHouse's ``Tuple`` is a heterogeneous positional group and core has
        no column class for it. ``ArrayColumn`` is the agreed table's answer and
        the permissive fallback this entry used to reach is gone; if 议题 A
        decides ``Tuple`` gets a class, this moves with it.
        """
        assert resolve_column_class(dialect, tuple) is ArrayColumn


class TestJSONCell:
    """``dict`` is JSONColumn at every version, and no operation is gated."""

    def test_dict_is_json_column(self, dialect):
        assert resolve_column_class(dialect, dict) is JSONColumn

    def test_dict_is_json_column_on_an_old_version_too(self):
        """Below the JSON type it is still answerable -- hence never refused.

        What carries it there is the ``JSONExtract`` / ``JSONHas`` /
        ``isValidJSON`` function family over ``String`` storage, not the type.
        Refusing it would be a limit ClickHouse does not have.
        """
        old = ClickHouseDialect(version=(25, 8, 0))
        assert resolve_column_class(old, dict) is JSONColumn

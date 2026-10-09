# tests/rhosocial/activerecord_clickhouse_test/feature/backend/dialect/test_column_suggestion.py
"""ClickHouse's eighteen-entry column-type suggestion table and its narrowing.

Pure dialect tests -- no server. What is asserted here is the *declaration*: that
the table answers every entry of the protocol's closed list, that the cells
ClickHouse deviates on are the ones the 26.7.3.19 probe measured, and that the
single narrowing is gated on the version it was measured against. The rendering
those cells imply is Phase 2b's work and is deliberately not asserted here.
"""

import datetime
import decimal
import enum
import uuid

import pytest

from rhosocial.activerecord.backend.dialect.mixins import ColumnSuggestionMixin
from rhosocial.activerecord.backend.expression.column_suggestions import (
    COLUMN_TYPE_ENTRIES,
    UNSUPPORTED,
)
from rhosocial.activerecord.backend.expression.column_types import (
    ArrayColumn,
    BinaryColumn,
    BooleanColumn,
    ColumnBase,
    DateTimeColumn,
    DecimalColumn,
    FloatColumn,
    IntegerColumn,
    JSONColumn,
    NumericColumn,
    StringColumn,
    UUIDColumn,
)
from rhosocial.activerecord.backend.impl.clickhouse.dialect import ClickHouseDialect
from rhosocial.activerecord.backend.impl.clickhouse.mixins import (
    ClickHouseColumnSuggestionMixin,
)

#: The version every probe behind this table ran on.
MEASURED = (26, 7, 3)

#: The first version this backend declares for the native ``JSON`` type.
JSON_TYPE_MIN = (26, 0, 0)


@pytest.fixture
def dialect():
    return ClickHouseDialect(version=MEASURED)


_ENTRY_IDS = [getattr(entry, "__name__", str(entry)) for entry in COLUMN_TYPE_ENTRIES]


def _entry_ids():
    return list(_ENTRY_IDS)


class TestTableCompleteness:
    """A hole in the table is a silent gap, and the protocol forbids one."""

    def test_the_dialect_carries_the_mixin(self, dialect):
        assert isinstance(dialect, ColumnSuggestionMixin)

    def test_the_clickhouse_half_comes_first_in_the_mro(self, dialect):
        """The load-bearing part of the dialect's base list.

        ``ClickHouseColumnSuggestionMixin`` overrides both members, so C3 has to
        see it before ``ColumnSuggestionMixin`` or the table and the narrowing
        would be core's. Nothing in the query would look wrong either way -- the
        generic answers are all valid column classes -- which is exactly why it
        takes an assertion to notice.
        """
        mro = type(dialect).__mro__
        assert mro.index(ClickHouseColumnSuggestionMixin) < mro.index(ColumnSuggestionMixin)

    def test_every_entry_is_answered(self, dialect):
        """All eighteen, by name -- an omission fails here rather than at lookup."""
        missing = [e for e in COLUMN_TYPE_ENTRIES if e not in dialect.suggested_column_types()]
        assert missing == []

    def test_no_entry_is_answered_none(self, dialect):
        """``None`` would be indistinguishable from "not filled in yet"."""
        table = dialect.suggested_column_types()
        assert [e for e in COLUMN_TYPE_ENTRIES if table[e] is None] == []

    @pytest.mark.parametrize("entry", COLUMN_TYPE_ENTRIES, ids=_entry_ids())
    def test_every_answer_is_a_column_class(self, dialect, entry):
        answer = dialect.suggested_column_types()[entry]
        assert isinstance(answer, type)
        assert issubclass(answer, ColumnBase)

    @pytest.mark.parametrize("entry", COLUMN_TYPE_ENTRIES, ids=_entry_ids())
    def test_every_entry_resolves_to_its_own_answer(self, dialect, entry):
        assert dialect.column_class_for(entry) is dialect.suggested_column_types()[entry]

    def test_no_clickhouse_entry_is_unsupported(self, dialect):
        """The refusal is real elsewhere and unnecessary here -- see the mixin.

        Firebird has no JSON functions and no arrays, and MySQL 5.6 has no JSON
        functions; ClickHouse has both, natively. A refusal would be a limit
        ClickHouse does not have, which is as wrong as a hole.
        """
        table = dialect.suggested_column_types()
        assert [e for e in COLUMN_TYPE_ENTRIES if table[e] is UNSUPPORTED] == []

    def test_the_table_is_a_copy(self, dialect):
        """Mutating the answer must not corrupt the class attribute."""
        first = dialect.suggested_column_types()
        first[str] = FloatColumn
        assert dialect.suggested_column_types()[str] is StringColumn


class TestBaselineCells:
    """The shared ten-backend baseline, restated cell by cell."""

    @pytest.mark.parametrize(
        "entry, expected",
        [
            (bool, BooleanColumn),
            (int, IntegerColumn),
            (float, FloatColumn),
            (decimal.Decimal, DecimalColumn),
            (str, StringColumn),
            (bytes, BinaryColumn),
            (bytearray, BinaryColumn),
            (datetime.date, DateTimeColumn),
            (datetime.time, DateTimeColumn),
            (datetime.datetime, DateTimeColumn),
            (uuid.UUID, UUIDColumn),
            (enum.Enum, StringColumn),
        ],
        ids=_entry_ids()[:12],
    )
    def test_baseline_entry(self, dialect, entry, expected):
        assert dialect.suggested_column_types()[entry] is expected

    def test_int_stays_integer_column(self, dialect):
        """议题 C is open: this is not a ruling that ClickHouse has no UInt class.

        ClickHouse has ``UInt8``..``UInt256``. Whether "non-negative only" earns
        a column class of its own is undecided, so ``int`` answers the whole
        number every backend answers. The test exists so that a future ruling is
        a deliberate change here rather than an accident.
        """
        assert dialect.suggested_column_types()[int] is IntegerColumn

    def test_timedelta_is_numeric_not_interval(self, dialect):
        """A native ``Interval`` exists; its arithmetic surface was not measured.

        The 26.7 aggregate fact table found ``sum`` / ``avg`` over ``Interval*``
        rejected with ``ILLEGAL_TYPE_OF_ARGUMENT`` even though the docs promise
        a same-type result, so the numeric answer is the honest one until core
        has an ``IntervalColumn`` to aim at.
        """
        assert dialect.suggested_column_types()[datetime.timedelta] is NumericColumn

    def test_time_is_provisional(self, dialect):
        """Core has no TimeColumn yet, so the shared DateTimeColumn stands.

        Worth pinning because it is wrong twice over in the meantime: this
        backend's own ``TimeType`` still renders ``DateTime`` while ClickHouse
        has had ``Time``/``Time64`` for a while (investigation appendix D-①).
        """
        assert dialect.suggested_column_types()[datetime.time] is DateTimeColumn


class TestArrayCells:
    """``Array(T)`` is native here, which is the whole reason for these cells."""

    @pytest.mark.parametrize("entry", [list, tuple, set, frozenset], ids=_entry_ids()[13:17])
    def test_container_entry_is_an_array(self, dialect, entry):
        assert dialect.suggested_column_types()[entry] is ArrayColumn

    def test_tuple_carries_no_narrowing(self, dialect):
        """议题 A is open and this cell is its subject, not its answer.

        ClickHouse's ``Tuple`` is a heterogeneous positional group and core has
        no column class for it. ``ArrayColumn`` is the agreed table's answer and
        the permissive fallback this entry used to reach is gone; if 议题 A
        decides ``Tuple`` gets a class, this moves with it.
        """
        assert dialect.column_class_for(tuple) is ArrayColumn


class TestJSONCell:
    """``dict`` is JSONColumn at every version, and only one operation is gated."""

    def test_dict_is_json_column(self, dialect):
        assert dialect.suggested_column_types()[dict] is JSONColumn

    def test_dict_is_json_column_on_an_old_version_too(self):
        """Below the JSON type it is still answerable -- hence never UNSUPPORTED.

        What carries it there is the ``JSONExtract`` / ``JSONHas`` /
        ``isValidJSON`` function family over ``String`` storage, not the type.
        Refusing it would be a limit ClickHouse does not have.
        """
        old = ClickHouseDialect(version=(25, 8, 0))
        assert old.column_class_for(dict) is JSONColumn


class TestOperationNarrowing:
    """One narrowing, gated on a version -- and ``ilike`` explicitly not."""

    def test_json_value_is_available_on_the_measured_version(self, dialect):
        assert dialect.supports_column_operation("JSONColumn", "json_value") is True

    def test_json_value_is_narrowed_below_the_json_type(self):
        """The version gate, in the direction that matters.

        ``json_value`` is core's chainable document accessor; on a native ``JSON``
        column ``JSONExtractRaw`` answers with the JSON type and the contract
        holds. Below 26.0 it answers with text, so the operation is narrowed
        rather than offered as a text-shaped impostor.
        """
        old = ClickHouseDialect(version=(25, 8, 0))
        assert old.supports_column_operation("JSONColumn", "json_value") is False

    def test_the_gate_opens_exactly_at_the_declared_version(self):
        """Closed on the last release line before it, open on the version itself.

        This is the same ``26.0`` the DDL side declares in
        ``ClickHouseJSONFunctionMixin``, so the capability gate and the type gate
        cannot disagree about which servers have a JSON type.
        """
        before = ClickHouseDialect(version=(JSON_TYPE_MIN[0] - 1, 12, 0))
        at = ClickHouseDialect(version=JSON_TYPE_MIN)
        assert before.supports_column_operation("JSONColumn", "json_value") is False
        assert at.supports_column_operation("JSONColumn", "json_value") is True

    def test_json_path_is_not_gated(self, dialect):
        """``json_path`` yields a scalar, which ``JSONExtractString`` gives over
        ``String`` storage too -- so there is nothing to narrow."""
        old = ClickHouseDialect(version=(25, 8, 0))
        assert old.supports_column_operation("JSONColumn", "json_path") is True
        assert dialect.supports_column_operation("JSONColumn", "json_path") is True

    def test_ilike_is_not_narrowed(self, dialect):
        """ClickHouse is one of only two backends that has ``ILIKE``.

        Measured hitting both 'aXc' and 'ABC' on 26.7.3.19. Six backends narrow
        it; narrowing it here would refuse a query this server answers.
        """
        assert dialect.supports_column_operation("StringColumn", "ilike") is True
        old = ClickHouseDialect(version=(25, 8, 0))
        assert old.supports_column_operation("StringColumn", "ilike") is True

    @pytest.mark.parametrize(
        "column_name, op",
        [
            ("ArrayColumn", "array_length"),
            ("ArrayColumn", "unnest"),
            ("StringColumn", "like"),
            ("BooleanColumn", "is_true"),
            ("UUIDColumn", "eq"),
            ("BinaryColumn", "cast"),
        ],
    )
    def test_nothing_else_is_narrowed(self, dialect, column_name, op):
        """Investigation appendix D-③: the "core has it, ClickHouse cannot" list
        is nearly empty -- the array family and ``ILIKE`` are both native. A
        narrowing here would need a probe behind it, and there is none."""
        assert dialect.supports_column_operation(column_name, op) is True

    def test_an_unknown_operation_is_not_narrowed_by_accident(self, dialect):
        """The default is True, so an operation nobody declared stays available.

        The narrowing is a statement about ClickHouse, not a whitelist: refusing
        every operation this table does not name would refuse the array function
        family and every other capability wider than core's.
        """
        assert dialect.supports_column_operation("ArrayColumn", "arrayJoin") is True

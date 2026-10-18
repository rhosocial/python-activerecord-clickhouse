# tests/rhosocial/activerecord_clickhouse_test/feature/backend/test_clickhouse_literal_values.py
"""ClickHouse's tier-2 literal spellings, pinned to live measurements.

``Literal`` is the one node that carries a value and the one decision that
matters at a syntax position: bind, or write the text. The text itself comes
from ``format_literal``, whose second tier is the backend's own -- and this
backend has exactly two spellings there: ``unhex('...')`` for bytes and the
bare quoted text for a UUID.

Every literal asserted here was measured against the instance
``tests/config/clickhouse_scenarios.yaml`` names ``clickhouse_http``:
**ClickHouse 26.7.3.19 (official build)**, HTTP on ``127.0.0.1:18682``,
database ``test_db``. The statements and readbacks behind each verdict are
recorded in ``mixins/literal.py``; this module pins the rendered text and
re-verifies both tier-2 spellings against the live server (CREATE TABLE with
the literal as a DEFAULT, INSERT, read back, compare).

The tier-1 kinds (NULL, booleans, numbers, strings, dates) render through
the base's portable spellings and were measured accepted verbatim as
DEFAULTs on Date / DateTime / Bool columns, so they are asserted for the
wiring only -- exact text, no override expected.

``timedelta`` is deliberately not spelled: the base refuses it, and the
module docstring in ``mixins/literal.py`` records the measurements that make
the refusal the answer rather than a gap.
"""

import datetime
import uuid as uuidlib

import pytest

from rhosocial.activerecord.backend.expression.core import Literal
from rhosocial.activerecord.backend.impl.clickhouse.dialect import ClickHouseDialect
from rhosocial.activerecord.backend.impl.clickhouse.mixins import (
    ClickHouseLiteralValueMixin,
)
from rhosocial.activerecord.backend.dialect.base import SQLDialectBase

#: The exact release every verdict below was measured on. Hard-coded on
#: purpose, the same way ``test_clickhouse_constraint_capabilities.py`` does
#: it: reading it back from the dialect would let a version bump silently
#: re-label the evidence.
MEASURED_VERSION = (26, 7, 3)

_UUID = uuidlib.UUID("01234567-89ab-cdef-0123-456789abcdef")
_UUID_TEXT = "01234567-89ab-cdef-0123-456789abcdef"


@pytest.fixture()
def dialect() -> ClickHouseDialect:
    return ClickHouseDialect(version=MEASURED_VERSION)


class TestBindingDecision:
    """``inline`` decides bind-or-text; the dialect's placeholder is ClickHouse's."""

    def test_data_position_binds_the_host_value(self, dialect):
        node = Literal(dialect, 42)
        sql, params = node.to_sql()
        assert sql == "%s"
        assert params == (42,)

    def test_inline_position_writes_text(self, dialect):
        node = Literal(dialect, 42, inline=True)
        sql, params = node.to_sql()
        assert sql == "42"
        assert params == ()


class TestTierOneSpellings:
    """The base's portable forms, measured accepted verbatim on 26.7.3.19."""

    @pytest.mark.parametrize(
        ("value", "expected"),
        [
            (None, "NULL"),
            (True, "TRUE"),
            (False, "FALSE"),
            (42, "42"),
            (1.5, "1.5"),
            ("it's", "'it''s'"),
            (datetime.date(2026, 1, 1), "'2026-01-01'"),
            (datetime.time(12, 30), "'12:30:00'"),
            (datetime.datetime(2026, 1, 1, 12, 0), "'2026-01-01 12:00:00'"),
        ],
    )
    def test_base_spelling_verbatim(self, dialect, value, expected):
        assert dialect.format_literal(value) == expected


class TestTierTwoSpellings:
    """ClickHouse's own two: unhex for bytes, quoted text for UUID."""

    def test_binary_renders_unhex(self, dialect):
        assert dialect.format_literal(b"\x01\x02") == "unhex('0102')"

    def test_binary_via_the_literal_node(self, dialect):
        node = Literal(dialect, b"\x01\x02", inline=True)
        sql, params = node.to_sql()
        assert sql == "unhex('0102')"
        assert params == ()

    def test_uuid_renders_bare_quoted_text(self, dialect):
        assert dialect.format_literal(_UUID) == f"'{_UUID_TEXT}'"

    def test_uuid_via_the_literal_node(self, dialect):
        node = Literal(dialect, _UUID, inline=True)
        sql, params = node.to_sql()
        assert sql == f"'{_UUID_TEXT}'"
        assert params == ()

    def test_timedelta_is_refused_by_the_base(self, dialect):
        """No override for ``timedelta``: the grammar's INTERVAL is
        date-arithmetic syntax whose unit is part of the spelling, and a
        mixed-unit span degrades to a tuple (see ``mixins/literal.py``), so
        the base's explicit refusal is the answer."""
        with pytest.raises(TypeError, match="no inline SQL literal form"):
            dialect.format_literal(datetime.timedelta(days=1))

    def test_override_is_structurally_narrow(self):
        """The override spells exactly the two host types it owns; a third
        would be a decision this package did not record."""
        import inspect

        branches = inspect.getsource(ClickHouseLiteralValueMixin.format_literal)
        assert branches.count("isinstance(value,") == 2

    def test_backend_mixin_outranks_the_base(self):
        """``ClickHouseLiteralValueMixin`` must resolve ahead of
        ``SQLDialectBase`` in the MRO: it overrides ``format_literal``, and a
        mixin placed after the class it overrides never wins."""
        mro = ClickHouseDialect.__mro__
        assert mro.index(ClickHouseLiteralValueMixin) < mro.index(SQLDialectBase)


class TestLiveDatabaseRoundTrips:
    """The two tier-2 spellings, verified end to end on the scenario server:
    CREATE TABLE with the literal as a DEFAULT, INSERT a row, read the
    stored value back and compare."""

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
        name = "probe_literal_bin"
        self._drop(backend, name)
        try:
            # The bare bytes scalar: the DEFAULT clause normalises it into
            # an inline Literal, which is the path under test.
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
                                branch=ColumnDefaultConstraint(dialect, b"\x01\x02"),
                            )
                        ],
                    ),
                ],
                storage_options={"ENGINE": "MergeTree()", "ORDER BY": "id"},
            )
            sql, params = create.to_sql()
            assert params == ()
            assert "unhex('0102')" in sql
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
        name = "probe_literal_uuid"
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
                                branch=ColumnDefaultConstraint(dialect, _UUID),
                            )
                        ],
                    ),
                ],
                storage_options={"ENGINE": "MergeTree()", "ORDER BY": "id"},
            )
            sql, params = create.to_sql()
            assert params == ()
            assert f"'{_UUID_TEXT}'" in sql
            backend.execute(sql, params)
            backend.execute(f"INSERT INTO {name} (id) VALUES (1)")
            result = backend.execute(f"SELECT toString(u) FROM {name}")
            assert [row["toString(u)"] for row in result.data] == [_UUID_TEXT]
        finally:
            self._drop(backend, name)

# tests/rhosocial/activerecord_clickhouse_test/feature/backend/functions/test_string_function_entry_points.py
"""The classed string function nodes on ClickHouse's entry points.

``CharLengthFunction`` is the one with a ClickHouse-specific answer: the
engine's ``LENGTH`` counts **bytes**, so this dialect renders the node as
``lengthUTF8`` -- the character count. The measurement, on the scenario
server ``tests/config/clickhouse_scenarios.yaml`` names ``clickhouse_http``
(**ClickHouse 26.7.3.19**, HTTP on ``127.0.0.1:18682``, database
``test_db``)::

    SELECT length('héllo')      -- 6 (bytes)
    SELECT lengthUTF8('héllo')  -- 5 (characters)

``UPPER`` / ``LOWER`` are ClickHouse's own spellings, so they render through
the shared defaults.
"""

import pytest

from rhosocial.activerecord.backend.expression.core import Column
from rhosocial.activerecord.backend.expression.functions import (
    CharLengthFunction,
    LowerFunction,
    UpperFunction,
)
from rhosocial.activerecord.backend.impl.clickhouse.dialect import ClickHouseDialect

#: The exact release the lengthUTF8 verdict was measured on; see the module
#: docstring for the measured answers.
MEASURED_VERSION = (26, 7, 3)


@pytest.fixture()
def dialect() -> ClickHouseDialect:
    return ClickHouseDialect(version=MEASURED_VERSION)


class TestCharLength:
    """``CHAR_LENGTH`` is character semantics, and ``lengthUTF8`` carries it."""

    def test_renders_length_utf8(self, dialect):
        node = CharLengthFunction(dialect, Column(dialect, "name"))
        sql, params = node.to_sql()
        assert sql == "lengthUTF8(`name`)"
        assert params == ()

    def test_alias_rides_along(self, dialect):
        node = CharLengthFunction(dialect, Column(dialect, "name")).as_("len")
        sql, params = node.to_sql()
        assert sql == "lengthUTF8(`name`) AS `len`"
        assert params == ()

    def test_live_engine_answers_characters(self, clickhouse_backend):
        """The spelling the dialect picks answers the character question on
        the live engine, where ``LENGTH`` would answer 6 (bytes)."""
        result = clickhouse_backend.execute("SELECT lengthUTF8('héllo')")
        assert [row["lengthUTF8('héllo')"] for row in result.data] == [5]


class TestSharedSpellings:
    """``UPPER`` / ``LOWER`` exist natively; the shared defaults are the answer."""

    def test_upper(self, dialect):
        sql, params = UpperFunction(dialect, Column(dialect, "name")).to_sql()
        assert sql == "UPPER(`name`)"
        assert params == ()

    def test_lower(self, dialect):
        sql, params = LowerFunction(dialect, Column(dialect, "name")).to_sql()
        assert sql == "LOWER(`name`)"
        assert params == ()

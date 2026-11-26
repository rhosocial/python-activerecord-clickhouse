# tests/rhosocial/activerecord_clickhouse_test/feature/backend/construct/introspection/test_catalogue_capabilities.py
"""The version-gated introspection statements, checked without a server.

The live object-state suite runs one job per ClickHouse release line, so a
statement that names a column an older line does not have can pass review and
still fail in CI. That is what happened to the skipping-index ``creation``
column, ``system.constraints`` and ``system.tables.target_table``: all three
exist on the newest line and none of them on the oldest ones, and a fixture
cannot tell.

This guard reads the recorded surface in
``impl.clickhouse.catalogue.CAPABILITY_MATRIX`` -- measured against 25.8.33.6,
26.3.71.3, 26.7 (the CI line) and 26.10.3.7 -- and renders each statement for
every recorded line. Every ``system`` catalogue table and every column the
rendered statement names must be one the line's entry records, so a statement
that reaches for a newer column fails here instead of on the oldest server.

The lines are pinned by name as well: deleting 25.8 from the matrix, or claiming
``creation`` for it, fails rather than silently reducing coverage.
"""

import re
from types import SimpleNamespace

import pytest
from rhosocial.activerecord.backend.introspection import IntrospectionNotSupportedError

from rhosocial.activerecord.backend.impl.clickhouse.catalogue import (
    CAPABILITY_MATRIX,
    capabilities_for_version,
)
from rhosocial.activerecord.backend.impl.clickhouse.dialect import ClickHouseDialect
from rhosocial.activerecord.backend.impl.clickhouse.expression.introspection import (
    ClickHouseConstraintStateListQuery,
    ClickHouseIndexStateListQuery,
    ClickHouseMaterializedViewListQuery,
    ClickHouseProjectionListQuery,
)
from rhosocial.activerecord.backend.impl.clickhouse.introspection import (
    ClickHouseIntrospector,
)

#: The release lines the matrix must keep, oldest first.
MEASURED_LINES = [(25, 8), (26, 3), (26, 7), (26, 10)]

_FROM = re.compile(r"FROM `system`\.`([^`]+)`")
_BACKTICKED = re.compile(r"`([^`]+)`")


def _statement_catalogue(sql):
    """``(table, identifiers)`` for the ``system`` table a statement reads.

    A rendered statement quotes every identifier, so the identifiers after
    ``FROM`` are exactly the catalogue columns plus the ``system`` / table pair
    of the relation itself. Those two are removed; everything else must be a
    column the release line answers.
    """
    matched = _FROM.search(sql)
    assert matched is not None, sql
    table = matched.group(1)
    identifiers = set(_BACKTICKED.findall(sql)) - {"system", table}
    return table, identifiers


def _assert_only_recorded(sql, table, recorded_columns):
    """The statement reads *table* and names only columns *recorded_columns*."""
    read_table, identifiers = _statement_catalogue(sql)
    assert read_table == table, (read_table, table)
    unknown = identifiers - recorded_columns
    assert not unknown, f"{read_table} on this line has no {sorted(unknown)}"


def _dialect(line):
    return ClickHouseDialect(version=(line[0], line[1], 0))


def _index_sql(line):
    return ClickHouseIndexStateListQuery(_dialect(line), "analytics", "events").to_sql()[0]


def _projection_sql(line):
    return ClickHouseProjectionListQuery(_dialect(line), "analytics", "events").to_sql()[0]


def _materialized_view_sql(line):
    return ClickHouseMaterializedViewListQuery(_dialect(line), "analytics").to_sql()[0]


def _constraint_sql(line):
    return ClickHouseConstraintStateListQuery(_dialect(line), "analytics", "events").to_sql()[0]


class TestTheGuardDetectsAViolation:
    """The checker is exercised on fabricated statements, so it cannot pass vacuously."""

    def test_a_column_the_line_does_not_have_is_flagged(self):
        creation_free = CAPABILITY_MATRIX[(25, 8)].skipping_index_columns
        sql = (
            "SELECT `name`, `type`, `creation` FROM `system`.`data_skipping_indices` "
            "WHERE `database` = %s ORDER BY `name`"
        )
        with pytest.raises(AssertionError, match="creation"):
            _assert_only_recorded(sql, "data_skipping_indices", creation_free)

    def test_a_statement_the_line_answers_is_accepted(self):
        sql = (
            "SELECT `name`, `type` FROM `system`.`data_skipping_indices` "
            "WHERE `database` = %s ORDER BY `name`"
        )
        _assert_only_recorded(
            sql,
            "data_skipping_indices",
            CAPABILITY_MATRIX[(25, 8)].skipping_index_columns,
        )


class TestTheRecordedSurfaceIsMeasured:
    """The facts the live failures turned on are pinned by release line."""

    def test_every_measured_line_is_recorded_in_order(self):
        assert list(CAPABILITY_MATRIX) == MEASURED_LINES
        assert all(
            CAPABILITY_MATRIX[line].line == line for line in MEASURED_LINES
        )

    def test_the_skipping_index_creation_column_arrives_by_26_3(self):
        assert "creation" not in CAPABILITY_MATRIX[(25, 8)].skipping_index_columns
        for line in [(26, 3), (26, 7), (26, 10)]:
            assert "creation" in CAPABILITY_MATRIX[line].skipping_index_columns

    def test_the_constraint_catalogue_does_not_exist_before_26_7(self):
        assert CAPABILITY_MATRIX[(25, 8)].constraint_columns is None
        assert CAPABILITY_MATRIX[(26, 3)].constraint_columns is None
        for line in [(26, 7), (26, 10)]:
            assert CAPABILITY_MATRIX[line].has_constraint_catalogue()
            assert CAPABILITY_MATRIX[line].constraint_columns == {
                "database",
                "table",
                "name",
                "type",
                "expression",
            }

    def test_the_materialized_view_target_table_arrives_by_26_7(self):
        for line in [(25, 8), (26, 3)]:
            assert "target_table" not in CAPABILITY_MATRIX[line].system_table_columns
        for line in [(26, 7), (26, 10)]:
            assert "target_table" in CAPABILITY_MATRIX[line].system_table_columns


class TestTheStatementsNameOnlyRecordedColumns:
    """One statement per catalogue family, rendered for every measured line."""

    @pytest.mark.parametrize("line", MEASURED_LINES)
    def test_the_skipping_index_statement(self, line):
        capabilities = CAPABILITY_MATRIX[line]
        _assert_only_recorded(
            _index_sql(line),
            "data_skipping_indices",
            capabilities.skipping_index_columns,
        )

    @pytest.mark.parametrize("line", MEASURED_LINES)
    def test_the_projection_statement(self, line):
        capabilities = CAPABILITY_MATRIX[line]
        _assert_only_recorded(
            _projection_sql(line),
            "projections",
            capabilities.projection_columns,
        )

    @pytest.mark.parametrize("line", MEASURED_LINES)
    def test_the_materialized_view_statement(self, line):
        capabilities = CAPABILITY_MATRIX[line]
        _assert_only_recorded(
            _materialized_view_sql(line),
            "tables",
            capabilities.system_table_columns,
        )

    @pytest.mark.parametrize("line", MEASURED_LINES)
    def test_the_constraint_statement_or_its_refusal(self, line):
        capabilities = CAPABILITY_MATRIX[line]
        if capabilities.constraint_columns is None:
            with pytest.raises(IntrospectionNotSupportedError, match="system.constraints"):
                _constraint_sql(line)
            return
        _assert_only_recorded(
            _constraint_sql(line),
            "constraints",
            capabilities.constraint_columns,
        )

    def test_the_control_line_without_creation_does_not_name_it(self):
        sql = _index_sql((25, 8))
        assert "`creation`" not in sql
        assert "`granularity`" in sql

    def test_the_newest_line_names_creation_and_target_table(self):
        assert "`creation`" in _index_sql((26, 10))
        assert "`target_table`" in _materialized_view_sql((26, 10))


class TestUnrecordedLinesFallBackConservatively:
    """A line nobody measured never inherits a newer line's surface."""

    def test_a_line_between_measurements_keeps_the_older_surface(self):
        line = capabilities_for_version((26, 5, 0))
        assert line.line == (26, 3)
        assert line.constraint_columns is None

    def test_a_line_after_the_newest_measurement_keeps_the_newest_surface(self):
        assert capabilities_for_version((27, 1, 0)).line == (26, 10)

    def test_an_unknown_version_answers_the_oldest_surface(self):
        assert capabilities_for_version(None).line == (25, 8)


class _StubBackend:
    """The two attributes the introspector reads before it builds SQL."""

    def __init__(self, dialect):
        self.dialect = dialect
        self.config = SimpleNamespace(database="analytics")

    def get_cached_server_version(self):
        return None


class TestTheStateMethodRefusesByName:
    """The method, not only the formatter, answers a name where the table is absent."""

    def test_constraint_states_refuse_on_a_line_without_the_catalogue(self):
        introspector = ClickHouseIntrospector(_StubBackend(_dialect((25, 8))), executor=None)
        with pytest.raises(IntrospectionNotSupportedError) as caught:
            introspector.list_constraint_states("events")
        message = str(caught.value)
        assert "system.constraints" in message
        assert "25.8.0" in message

    def test_the_refusal_is_not_an_empty_answer(self):
        introspector = ClickHouseIntrospector(_StubBackend(_dialect((26, 3))), executor=None)
        with pytest.raises(IntrospectionNotSupportedError):
            introspector.list_constraint_states("events")

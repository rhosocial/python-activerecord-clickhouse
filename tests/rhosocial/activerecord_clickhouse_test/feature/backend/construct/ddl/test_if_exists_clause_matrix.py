# tests/rhosocial/activerecord_clickhouse_test/feature/backend/construct/ddl/test_if_exists_clause_matrix.py
"""The ``IF [NOT] EXISTS`` capability matrix, pinned to the official reference.

Each probe here answers a question about a clause the official ClickHouse SQL
reference spells. The matrix is offline: it asserts the probe values and the
one rendering rule that the values alone cannot express (``OR REPLACE`` and
``IF NOT EXISTS`` are mutually exclusive on ``CREATE VIEW``).

Reference pages:

* ALTER TABLE ... COLUMN (ADD COLUMN / DROP COLUMN / RENAME COLUMN):
  https://clickhouse.com/docs/sql-reference/statements/alter/column
* ALTER TABLE ... CONSTRAINT (ADD / MODIFY / DROP CONSTRAINT):
  https://clickhouse.com/docs/sql-reference/statements/alter/constraint
* ALTER TABLE ... INDEX (ADD / DROP / MATERIALIZE INDEX):
  https://clickhouse.com/docs/sql-reference/statements/alter/skipping-index
* CREATE TABLE:
  https://clickhouse.com/docs/sql-reference/statements/create/table
* CREATE VIEW:
  https://clickhouse.com/docs/sql-reference/statements/create/view
* CREATE DATABASE:
  https://clickhouse.com/docs/sql-reference/statements/create/database
* DROP (DATABASE / TABLE / VIEW):
  https://clickhouse.com/docs/sql-reference/statements/drop
"""

import pytest

from rhosocial.activerecord.backend.dialect.exceptions import UnsupportedFeatureError
from rhosocial.activerecord.backend.expression import (
    Column,
    CreateViewStatement,
    QueryStatement,
)
from rhosocial.activerecord.backend.expression.objects import Table, View
from rhosocial.activerecord.backend.expression.sources import NamedRelationRef
from rhosocial.activerecord.backend.impl.clickhouse.dialect import ClickHouseDialect
from rhosocial.activerecord.backend.impl.clickhouse.mixins.ddl_table import (
    ClickHouseTableMixin,
)


#: ``(probe, value, clause)`` for the clauses the matrix asked about. The
#: clause column is documentation: it names what the reference spells, so a
#: value flip fails next to the keyword it is about instead of only as a
#: boolean mismatch.
IF_EXISTS_PROBES = (
    ("supports_add_column_if_not_exists", True, "ADD COLUMN [IF NOT EXISTS]"),
    ("supports_drop_column_if_exists", True, "DROP COLUMN [IF EXISTS]"),
    ("supports_drop_constraint_if_exists", True, "DROP CONSTRAINT [IF EXISTS]"),
    ("supports_index_if_not_exists", True, "ADD INDEX [IF NOT EXISTS]"),
    ("supports_index_if_exists", True, "DROP INDEX [IF EXISTS]"),
    ("supports_if_not_exists_table", True, "CREATE TABLE [IF NOT EXISTS]"),
    ("supports_if_exists_table", True, "DROP TABLE [IF EXISTS]"),
    ("supports_if_not_exists_view", True, "CREATE VIEW [IF NOT EXISTS]"),
    ("supports_if_exists_view", True, "DROP VIEW [IF EXISTS]"),
    ("supports_database_if_not_exists", True, "CREATE DATABASE [IF NOT EXISTS]"),
    ("supports_database_if_exists", True, "DROP DATABASE [IF EXISTS]"),
)


def _dialect(version=(26, 7, 3)) -> ClickHouseDialect:
    return ClickHouseDialect(version=version)


class TestIfExistsProbeMatrix:
    @pytest.mark.parametrize(
        "probe, value, clause",
        IF_EXISTS_PROBES,
        ids=[probe for probe, _value, _clause in IF_EXISTS_PROBES],
    )
    def test_probe_answers_a_bool(self, probe, value, clause):
        """A probe is a bool, on a version whose reference page spells the clause."""
        answer = getattr(_dialect(), probe)()

        assert isinstance(answer, bool), probe
        assert answer is value, f"{probe} ({clause})"


class TestRenameColumnVersionGate:
    """``RENAME COLUMN`` has one home and one version gate.

    ``ClickHouseDialect`` declares the probe with
    ``version_at_least((21, 1, 0))``. The DDL-table mixin used to carry a
    second, unconditional ``True``; it was shadowed by the dialect's class-body
    method, so it never answered but still read as a claim. It is gone now, and
    the absence is asserted here so it cannot quietly return.
    """

    def test_the_mixin_does_not_declare_a_second_answer(self):
        assert "supports_rename_column" not in ClickHouseTableMixin.__dict__

    def test_the_dialect_owns_the_answer(self):
        assert (
            ClickHouseDialect.supports_rename_column.__qualname__
            == "ClickHouseDialect.supports_rename_column"
        )

    @pytest.mark.parametrize(
        "version, expected",
        [((20, 8, 0), False), ((21, 1, 0), True), ((26, 7, 3), True)],
        ids=["20.8", "21.1", "26.7"],
    )
    def test_the_gate_is_21_1(self, version, expected):
        assert _dialect(version).supports_rename_column() is expected

    def test_the_reference_spells_the_clause(self):
        """The clause the gate is about is in the official ALTER ... COLUMN page."""
        assert _dialect().supports_rename_column() is True


class TestCreateViewClausePair:
    """``OR REPLACE`` and ``IF NOT EXISTS`` are in the grammar, but not together."""

    def _statement(self, dialect, **flags) -> CreateViewStatement:
        query = QueryStatement(
            dialect,
            select=[Column(dialect, "id")],
            from_=NamedRelationRef(dialect, Table(dialect, "source")),
        )
        return CreateViewStatement(dialect, View(dialect, "v"), query, **flags)

    def test_if_not_exists_renders(self):
        sql, params = self._statement(_dialect(), if_not_exists=True).to_sql()

        assert sql == "CREATE VIEW IF NOT EXISTS `v` AS SELECT `id` FROM `source`"
        assert params == ()

    def test_or_replace_renders(self):
        sql, params = self._statement(_dialect(), replace=True).to_sql()

        assert sql == "CREATE OR REPLACE VIEW `v` AS SELECT `id` FROM `source`"
        assert params == ()

    def test_the_pair_is_refused_by_name(self):
        """The reference calls the combination a syntax error; so does the renderer."""
        with pytest.raises(UnsupportedFeatureError) as excinfo:
            self._statement(_dialect(), replace=True, if_not_exists=True).to_sql()

        assert (
            excinfo.value.feature_name
            == "CREATE OR REPLACE VIEW ... IF NOT EXISTS"
        )
        assert "mutually exclusive" in excinfo.value.suggestion

# tests/rhosocial/activerecord_clickhouse_test/feature/backend/construct/ddl/test_comment_and_modify_constraint.py
"""ClickHouse ``MODIFY COMMENT`` and ``MODIFY CONSTRAINT`` statements.

ClickHouse has no ``COMMENT ON``: a table comment changes with
``ALTER TABLE ... MODIFY COMMENT`` (23.9+, ``''`` clears it), a column comment
with the ``COMMENT`` modifier of ``MODIFY COLUMN``, and an existing
``CHECK``/``ASSUME`` constraint is redefined with ``MODIFY CONSTRAINT``
(``ALTER CONSTRAINT`` is a syntax error on this server).

Pure-construction tests: no database connection is required.
"""

import pytest

from rhosocial.activerecord.backend.dialect.exceptions import UnsupportedFeatureError
from rhosocial.activerecord.backend.expression.core import Column, Literal
from rhosocial.activerecord.backend.expression.predicates import ComparisonPredicate
from rhosocial.activerecord.backend.impl.clickhouse.dialect import ClickHouseDialect
from rhosocial.activerecord.backend.impl.clickhouse.expression import (
    ClickHouseModifyColumnCommentStatement,
    ClickHouseModifyConstraintStatement,
    ClickHouseModifyTableCommentStatement,
)


@pytest.fixture
def dialect():
    return ClickHouseDialect((26, 7, 0))


class TestCommentProbes:
    def test_probe_true_on_26_7(self, dialect):
        assert dialect.supports_modify_comment() is True

    def test_probe_false_below_23_9(self):
        assert ClickHouseDialect((23, 8, 0)).supports_modify_comment() is False


class TestTableComment:
    def test_plain(self, dialect):
        sql, params = ClickHouseModifyTableCommentStatement(
            dialect, "events", "orders"
        ).to_sql()
        assert sql == "ALTER TABLE `events` MODIFY COMMENT 'orders'"
        assert params == ()

    def test_schema_qualified(self, dialect):
        sql, _ = ClickHouseModifyTableCommentStatement(
            dialect, "events", "orders", schema="db"
        ).to_sql()
        assert sql == "ALTER TABLE `db`.`events` MODIFY COMMENT 'orders'"

    def test_empty_comment_clears(self, dialect):
        sql, _ = ClickHouseModifyTableCommentStatement(dialect, "events", "").to_sql()
        assert sql == "ALTER TABLE `events` MODIFY COMMENT ''"

    def test_table_level_if_exists_is_refused(self, dialect):
        with pytest.raises(UnsupportedFeatureError) as excinfo:
            ClickHouseModifyTableCommentStatement(
                dialect, "events", "x", if_table_exists=True
            ).to_sql()
        assert excinfo.value.feature_name == "ALTER TABLE IF EXISTS MODIFY COMMENT"

    def test_blank_table_is_refused(self, dialect):
        with pytest.raises(ValueError, match="non-empty table name"):
            ClickHouseModifyTableCommentStatement(dialect, "  ", "x").to_sql()

    def test_non_string_comment_is_refused(self, dialect):
        with pytest.raises(TypeError, match="comment to be a string"):
            ClickHouseModifyTableCommentStatement(dialect, "t", 1).to_sql()

    def test_below_the_floor_is_refused(self):
        old = ClickHouseDialect((23, 8, 0))
        with pytest.raises(UnsupportedFeatureError) as excinfo:
            ClickHouseModifyTableCommentStatement(old, "events", "x").to_sql()
        assert excinfo.value.feature_name == "ALTER TABLE MODIFY COMMENT"


class TestColumnComment:
    def test_plain(self, dialect):
        sql, params = ClickHouseModifyColumnCommentStatement(
            dialect, "events", "note", "text"
        ).to_sql()
        assert sql == "ALTER TABLE `events` MODIFY COLUMN `note` COMMENT 'text'"
        assert params == ()

    def test_if_exists_belongs_after_modify_column(self, dialect):
        sql, _ = ClickHouseModifyColumnCommentStatement(
            dialect, "events", "note", "text", if_exists=True
        ).to_sql()
        assert sql == "ALTER TABLE `events` MODIFY COLUMN IF EXISTS `note` COMMENT 'text'"

    def test_schema_qualified(self, dialect):
        sql, _ = ClickHouseModifyColumnCommentStatement(
            dialect, "events", "note", "text", schema="db"
        ).to_sql()
        assert sql == "ALTER TABLE `db`.`events` MODIFY COLUMN `note` COMMENT 'text'"

    def test_table_level_if_exists_is_refused(self, dialect):
        with pytest.raises(UnsupportedFeatureError) as excinfo:
            ClickHouseModifyColumnCommentStatement(
                dialect, "events", "note", "x", if_table_exists=True
            ).to_sql()
        assert excinfo.value.feature_name == (
            "ALTER TABLE IF EXISTS MODIFY COLUMN COMMENT"
        )

    def test_blank_column_is_refused(self, dialect):
        with pytest.raises(ValueError, match="non-empty column name"):
            ClickHouseModifyColumnCommentStatement(dialect, "t", " ", "x").to_sql()


class TestModifyConstraint:
    def _condition(self, dialect):
        return ComparisonPredicate(
            dialect, "gt", Column(dialect, "c"), Literal(dialect, 100, inline=True)
        )

    def test_check(self, dialect):
        sql, params = ClickHouseModifyConstraintStatement(
            dialect, "events", "ck", "CHECK", self._condition(dialect)
        ).to_sql()
        assert sql == "ALTER TABLE `events` MODIFY CONSTRAINT `ck` CHECK `c` > 100"
        assert params == ()

    def test_assume(self, dialect):
        sql, _ = ClickHouseModifyConstraintStatement(
            dialect, "events", "ak", "assume", self._condition(dialect)
        ).to_sql()
        assert sql == "ALTER TABLE `events` MODIFY CONSTRAINT `ak` ASSUME `c` > 100"

    def test_schema_qualified(self, dialect):
        sql, _ = ClickHouseModifyConstraintStatement(
            dialect, "events", "ck", "CHECK", self._condition(dialect), schema="db"
        ).to_sql()
        assert sql == "ALTER TABLE `db`.`events` MODIFY CONSTRAINT `ck` CHECK `c` > 100"

    def test_probe_true(self, dialect):
        assert dialect.supports_modify_constraint() is True

    def test_unknown_kind_is_refused(self, dialect):
        with pytest.raises(ValueError, match="unknown constraint kind"):
            ClickHouseModifyConstraintStatement(
                dialect, "events", "ck", "UNIQUE", self._condition(dialect)
            ).to_sql()

    def test_blank_name_is_refused(self, dialect):
        with pytest.raises(ValueError, match="non-empty constraint name"):
            ClickHouseModifyConstraintStatement(
                dialect, "events", " ", "CHECK", self._condition(dialect)
            ).to_sql()

    def test_missing_condition_is_refused(self, dialect):
        with pytest.raises(ValueError, match="requires a condition"):
            ClickHouseModifyConstraintStatement(
                dialect, "events", "ck", "CHECK", None
            ).to_sql()

    def test_bind_carrying_condition_is_refused(self, dialect):
        bound = ComparisonPredicate(
            dialect, "gt", Column(dialect, "c"), Literal(dialect, 100)
        )
        with pytest.raises(ValueError, match="no bind parameters"):
            ClickHouseModifyConstraintStatement(
                dialect, "events", "ck", "CHECK", bound
            ).to_sql()

    def test_wrong_node_kind_is_refused(self, dialect):
        with pytest.raises(TypeError):
            dialect.format_clickhouse_modify_constraint_statement(
                ClickHouseModifyTableCommentStatement(dialect, "t", "x")
            )

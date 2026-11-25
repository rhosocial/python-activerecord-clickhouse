# tests/rhosocial/activerecord_clickhouse_test/feature/backend/construct/ddl/test_index_alter.py
"""``ALTER TABLE ... ADD INDEX`` / ``DROP INDEX`` for skipping indexes.

Construction -> render only, no connection. The grammar asserted here is the
one on the official reference:

    ALTER TABLE [db.]table ADD INDEX [IF NOT EXISTS] name expression TYPE type
        [GRANULARITY value]
    ALTER TABLE [db.]table DROP INDEX [IF EXISTS] name

https://clickhouse.com/docs/sql-reference/statements/alter/skipping-index

The nodes are parameter collectors: a caller may put a qualifier in a position
the grammar does not accept, and it is the formatter's job to refuse it by name
rather than silently dropping it or inventing a new spelling.
"""

import pytest

from rhosocial.activerecord.backend.dialect.exceptions import UnsupportedFeatureError
from rhosocial.activerecord.backend.expression.core import Column, Literal
from rhosocial.activerecord.backend.impl.clickhouse.dialect import ClickHouseDialect
from rhosocial.activerecord.backend.impl.clickhouse.expression.index import (
    ClickHouseAddIndexStatement,
    ClickHouseDropIndexStatement,
)


@pytest.fixture
def dialect():
    return ClickHouseDialect((26, 7, 3))


def _add(dialect, **kwargs):
    params = {
        "table": "events",
        "name": "idx",
        "expression": Column(dialect, "val"),
        "type": "minmax",
        "granularity": 1,
    }
    params.update(kwargs)
    return ClickHouseAddIndexStatement(dialect, **params)


def _drop(dialect, **kwargs):
    params = {"table": "events", "name": "idx"}
    params.update(kwargs)
    return ClickHouseDropIndexStatement(dialect, **params)


class TestExactSql:
    def test_add_index_with_default_granularity(self, dialect):
        assert _add(dialect, granularity=None).to_sql() == (
            "ALTER TABLE `events` ADD INDEX `idx` `val` TYPE minmax",
            (),
        )

    def test_add_index_with_granularity(self, dialect):
        assert _add(dialect).to_sql() == (
            "ALTER TABLE `events` ADD INDEX `idx` `val` TYPE minmax GRANULARITY 1",
            (),
        )

    def test_add_index_if_not_exists(self, dialect):
        assert _add(dialect, if_not_exists=True).to_sql() == (
            "ALTER TABLE `events` ADD INDEX IF NOT EXISTS `idx` `val` "
            "TYPE minmax GRANULARITY 1",
            (),
        )

    def test_add_index_schema_qualifies_the_table(self, dialect):
        assert _add(dialect, schema="analytics").to_sql()[0] == (
            "ALTER TABLE `analytics`.`events` ADD INDEX `idx` `val` "
            "TYPE minmax GRANULARITY 1"
        )

    def test_add_index_expression_can_be_a_function(self, dialect):
        from rhosocial.activerecord.backend.expression.core import FunctionCall

        expr = FunctionCall(dialect, "toYYYYMM", Column(dialect, "ts"))
        assert _add(dialect, expression=expr, type="minmax").to_sql()[0] == (
            "ALTER TABLE `events` ADD INDEX `idx` TOYYYYMM(`ts`) TYPE minmax "
            "GRANULARITY 1"
        )

    def test_add_index_index_type_with_parameter(self, dialect):
        assert _add(dialect, type="bloom_filter(0.01)").to_sql()[0] == (
            "ALTER TABLE `events` ADD INDEX `idx` `val` "
            "TYPE bloom_filter(0.01) GRANULARITY 1"
        )

    def test_drop_index_unqualified(self, dialect):
        assert _drop(dialect).to_sql() == (
            "ALTER TABLE `events` DROP INDEX `idx`",
            (),
        )

    def test_drop_index_if_exists(self, dialect):
        assert _drop(dialect, if_exists=True).to_sql() == (
            "ALTER TABLE `events` DROP INDEX IF EXISTS `idx`",
            (),
        )

    def test_drop_index_schema_qualifies_the_table(self, dialect):
        assert _drop(dialect, schema="analytics", if_exists=True).to_sql()[0] == (
            "ALTER TABLE `analytics`.`events` DROP INDEX IF EXISTS `idx`"
        )

    def test_names_are_quoted_identifiers(self, dialect):
        sql = _add(dialect, name="select", table="order").to_sql()[0]
        assert sql.startswith("ALTER TABLE `order` ADD INDEX `select` ")


class TestFormatMethod:
    def test_each_node_names_its_dialect_formatter(self, dialect):
        for cls, method in (
            (ClickHouseAddIndexStatement, "format_clickhouse_add_index_statement"),
            (ClickHouseDropIndexStatement, "format_clickhouse_drop_index_statement"),
        ):
            assert cls.format_method.fget(cls) == method
            assert callable(getattr(dialect, method))

    def test_constructors_only_collect_parameters(self):
        """No validation in the node: a None dialect and raw values are carried."""
        add = ClickHouseAddIndexStatement(None, "", "", "expr", type=None)
        # ``dialect`` is a validating property, so the construction-time state
        # is the private binding; it stays None until a dialect is supplied.
        assert add._dialect is None
        assert add.table == "" and add.name == ""
        assert add.expression == "expr" and add.type is None
        drop = ClickHouseDropIndexStatement(
            None, "", "", if_table_exists=True, if_not_exists=True
        )
        assert drop._dialect is None
        assert drop.if_table_exists is True and drop.if_not_exists is True


class TestRefusals:
    @pytest.mark.parametrize(
        "kwargs,feature",
        [
            ({"if_table_exists": True}, "ALTER TABLE IF EXISTS"),
            ({"if_exists": True}, "ADD INDEX IF EXISTS"),
        ],
    )
    def test_add_rejects_misplaced_qualifiers(self, dialect, kwargs, feature):
        """The reference only allows IF NOT EXISTS, after ADD INDEX."""
        with pytest.raises(UnsupportedFeatureError, match=feature):
            _add(dialect, **kwargs).to_sql()

    @pytest.mark.parametrize(
        "kwargs,feature",
        [
            ({"if_table_exists": True}, "ALTER TABLE IF EXISTS"),
            ({"if_not_exists": True}, "DROP INDEX IF NOT EXISTS"),
        ],
    )
    def test_drop_rejects_misplaced_qualifiers(self, dialect, kwargs, feature):
        """The reference only allows IF EXISTS, after DROP INDEX."""
        with pytest.raises(UnsupportedFeatureError, match=feature):
            _drop(dialect, **kwargs).to_sql()

    @pytest.mark.parametrize("table", ["", "  ", None, 42])
    def test_add_rejects_an_unaimable_table(self, dialect, table):
        with pytest.raises(UnsupportedFeatureError, match="ADD INDEX"):
            _add(dialect, table=table).to_sql()

    @pytest.mark.parametrize("name", ["", "  ", None, 42])
    def test_add_rejects_an_unnamed_index(self, dialect, name):
        with pytest.raises(UnsupportedFeatureError, match="ADD INDEX"):
            _add(dialect, name=name).to_sql()

    @pytest.mark.parametrize("type_", [None, "", "  ", 42, "minmax; DROP TABLE t"])
    def test_add_rejects_a_missing_or_unsafe_type(self, dialect, type_):
        with pytest.raises(UnsupportedFeatureError, match="ADD INDEX TYPE"):
            _add(dialect, type=type_).to_sql()

    @pytest.mark.parametrize("expression", [None, "val", 7])
    def test_add_rejects_a_non_node_expression(self, dialect, expression):
        with pytest.raises(UnsupportedFeatureError, match="ADD INDEX <expression>"):
            _add(dialect, expression=expression).to_sql()

    def test_add_rejects_an_expression_that_would_bind(self, dialect):
        with pytest.raises(UnsupportedFeatureError, match="bind parameters"):
            _add(dialect, expression=Literal(dialect, 1)).to_sql()

    @pytest.mark.parametrize("granularity", [0, -1, True, 1.5, "4"])
    def test_add_rejects_an_invalid_granularity(self, dialect, granularity):
        with pytest.raises(UnsupportedFeatureError, match="ADD INDEX GRANULARITY"):
            _add(dialect, granularity=granularity).to_sql()

    @pytest.mark.parametrize("table", ["", "  ", None])
    def test_drop_rejects_an_unaimable_table(self, dialect, table):
        with pytest.raises(UnsupportedFeatureError, match="DROP INDEX"):
            _drop(dialect, table=table).to_sql()

    @pytest.mark.parametrize("name", ["", "  ", None])
    def test_drop_rejects_an_unnamed_index(self, dialect, name):
        with pytest.raises(UnsupportedFeatureError, match="DROP INDEX"):
            _drop(dialect, name=name).to_sql()

    def test_wrong_node_kind_is_a_type_error(self, dialect):
        with pytest.raises(TypeError, match="ClickHouseAddIndexStatement"):
            dialect.format_clickhouse_add_index_statement(_drop(dialect))
        with pytest.raises(TypeError, match="ClickHouseDropIndexStatement"):
            dialect.format_clickhouse_drop_index_statement(_add(dialect))


class TestProbeGating:
    def test_if_not_exists_is_gated_by_its_probe(self, dialect, monkeypatch):
        monkeypatch.setattr(dialect, "supports_index_if_not_exists", lambda: False)
        with pytest.raises(UnsupportedFeatureError, match="ADD INDEX IF NOT EXISTS"):
            _add(dialect, if_not_exists=True).to_sql()
        # Without the qualifier, the plain statement still renders.
        assert _add(dialect).to_sql()[0].startswith("ALTER TABLE `events` ADD INDEX ")

    def test_if_exists_is_gated_by_its_probe(self, dialect, monkeypatch):
        monkeypatch.setattr(dialect, "supports_index_if_exists", lambda: False)
        with pytest.raises(UnsupportedFeatureError, match="DROP INDEX IF EXISTS"):
            _drop(dialect, if_exists=True).to_sql()
        assert _drop(dialect).to_sql()[0] == "ALTER TABLE `events` DROP INDEX `idx`"

    def test_the_verbs_are_gated_by_their_probes(self, dialect, monkeypatch):
        monkeypatch.setattr(dialect, "supports_create_index", lambda: False)
        with pytest.raises(UnsupportedFeatureError, match="ALTER TABLE ADD INDEX"):
            _add(dialect).to_sql()
        monkeypatch.setattr(dialect, "supports_drop_index", lambda: False)
        with pytest.raises(UnsupportedFeatureError, match="ALTER TABLE DROP INDEX"):
            _drop(dialect).to_sql()

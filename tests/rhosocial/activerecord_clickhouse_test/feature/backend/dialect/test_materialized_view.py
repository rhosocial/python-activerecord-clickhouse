# tests/rhosocial/activerecord_clickhouse_test/feature/backend/dialect/test_materialized_view.py
"""ClickHouse MATERIALIZED VIEW DDL tests (SQL generation only, no database).

ClickHouse has two MV flavours whose DDL shares almost nothing with the
SQL-standard statement:

* incremental — insert trigger, materialized into ``TO <table>`` or an
  ``ENGINE``, optionally backfilled with ``POPULATE``;
* refreshable — ``REFRESH EVERY|AFTER`` schedule, ``APPEND``, ``EMPTY``.

Removal uses ``DROP VIEW`` and refresh uses ``SYSTEM REFRESH VIEW``.
"""

import pytest

from rhosocial.activerecord.backend.dialect.exceptions import UnsupportedFeatureError
from rhosocial.activerecord.backend.expression import Column, QueryExpression, TableExpression
from rhosocial.activerecord.backend.expression.statements.ddl_view import (
    CreateMaterializedViewExpression,
    DropMaterializedViewExpression,
    RefreshMaterializedViewExpression,
)
from rhosocial.activerecord.backend.impl.clickhouse.dialect import ClickHouseDialect
from rhosocial.activerecord.backend.impl.clickhouse.expression.materialized_view import (
    ClickHouseCreateMaterializedViewExpression,
    ClickHouseDropMaterializedViewExpression,
    ClickHouseModifyMaterializedViewRefreshExpression,
    ClickHouseRefreshMaterializedViewExpression,
    ClickHouseRefreshSchedule,
)

QUERY = "SELECT grp, sum(v) AS s FROM src GROUP BY grp"


@pytest.fixture
def dialect():
    return ClickHouseDialect()


def _generic_query(dialect):
    return QueryExpression(
        dialect=dialect,
        select=[Column(dialect, "grp")],
        from_=TableExpression(dialect, "src"),
    )


class TestCapabilities:
    def test_probes(self, dialect):
        assert dialect.supports_materialized_view() is True
        assert dialect.supports_refresh_materialized_view() is True
        assert dialect.supports_materialized_view_refresh_schedule() is True
        assert dialect.supports_materialized_view_populate() is True

    def test_formatter_ownership(self, dialect):
        """The CH MV mixin must precede ClickHouseViewMixin and the core ViewMixin."""
        mro = ClickHouseDialect.__mro__
        names = [c.__name__ for c in mro]
        assert names.index("ClickHouseMaterializedViewMixin") < names.index(
            "ClickHouseViewMixin"
        )
        assert names.index("ClickHouseMaterializedViewMixin") < names.index("ViewMixin")
        owner = dialect.format_create_materialized_view_statement.__qualname__
        assert owner.startswith("ClickHouseMaterializedViewMixin.")


class TestIncrementalMaterializedView:
    def test_engine_form(self, dialect):
        """Without TO an ENGINE is mandatory — that is ClickHouse's rule."""
        expr = ClickHouseCreateMaterializedViewExpression(
            dialect, "mv_agg", QUERY, engine="MergeTree ORDER BY grp"
        )
        sql, params = expr.to_sql()
        assert sql == (
            "CREATE MATERIALIZED VIEW `mv_agg` "
            "ENGINE = MergeTree ORDER BY grp AS "
            "SELECT grp, sum(v) AS s FROM src GROUP BY grp"
        )
        assert params == ()

    def test_to_table_form(self, dialect):
        expr = ClickHouseCreateMaterializedViewExpression(
            dialect, "mv_to", QUERY, to_table="target_table"
        )
        assert "TO `target_table`" in expr.to_sql()[0]

    def test_to_table_with_columns(self, dialect):
        expr = ClickHouseCreateMaterializedViewExpression(
            dialect, "mv_to", QUERY, to_table="target", to_columns=["grp", "s"]
        )
        assert "TO `target` (grp, s)" in expr.to_sql()[0]

    def test_populate(self, dialect):
        expr = ClickHouseCreateMaterializedViewExpression(
            dialect, "mv", QUERY, to_table="target", populate=True
        )
        assert "POPULATE" in expr.to_sql()[0]

    def test_database_qualified(self, dialect):
        expr = ClickHouseCreateMaterializedViewExpression(
            dialect, "mv_agg", QUERY, database="analytics", engine="MergeTree ORDER BY grp"
        )
        assert "`analytics`.`mv_agg`" in expr.to_sql()[0]

    def test_on_cluster_and_comment(self, dialect):
        expr = ClickHouseCreateMaterializedViewExpression(
            dialect,
            "mv",
            QUERY,
            to_table="target",
            on_cluster="cluster_1",
            comment="nightly rollup",
        )
        sql, _ = expr.to_sql()
        # cluster name goes through format_identifier, matching format_drop_database_statement
        assert "ON CLUSTER `cluster_1`" in sql
        assert "COMMENT 'nightly rollup'" in sql

    def test_or_replace_and_if_not_exists(self, dialect):
        expr = ClickHouseCreateMaterializedViewExpression(
            dialect, "mv", QUERY, to_table="t", or_replace=True
        )
        assert expr.to_sql()[0].startswith("CREATE OR REPLACE MATERIALIZED VIEW")
        expr = ClickHouseCreateMaterializedViewExpression(
            dialect, "mv", QUERY, to_table="t", if_not_exists=True
        )
        assert "IF NOT EXISTS" in expr.to_sql()[0]

    def test_or_replace_and_if_not_exists_are_exclusive(self, dialect):
        with pytest.raises(ValueError, match="OR REPLACE"):
            ClickHouseCreateMaterializedViewExpression(
                dialect, "mv", QUERY, to_table="t", or_replace=True, if_not_exists=True
            )

    def test_engine_or_to_is_mandatory(self, dialect):
        """The server rejects a materialized view with neither."""
        with pytest.raises(ValueError, match="TO target table or an"):
            ClickHouseCreateMaterializedViewExpression(dialect, "mv", QUERY)

    def test_clause_order(self, dialect):
        expr = ClickHouseCreateMaterializedViewExpression(
            dialect,
            "mv",
            QUERY,
            on_cluster="c1",
            to_table="target",
            populate=True,
            comment="c",
        )
        sql, _ = expr.to_sql()
        assert sql.index("ON CLUSTER") < sql.index("TO ")
        assert sql.index("TO ") < sql.index("POPULATE")
        assert sql.index("POPULATE") < sql.index(" AS ")
        assert sql.index(" AS ") < sql.index("COMMENT")

    def test_expression_query_accepted(self, dialect):
        expr = ClickHouseCreateMaterializedViewExpression(
            dialect, "mv", _generic_query(dialect), to_table="t"
        )
        sql, _ = expr.to_sql()
        assert "AS SELECT `grp` FROM `src`" in sql


class TestRefreshableMaterializedView:
    def test_every(self, dialect):
        expr = ClickHouseCreateMaterializedViewExpression(
            dialect,
            "mv",
            QUERY,
            to_table="t",
            refresh=ClickHouseRefreshSchedule(every="1 DAY"),
        )
        sql, _ = expr.to_sql()
        assert "REFRESH EVERY 1 DAY" in sql
        assert expr.is_refreshable is True

    def test_every_with_offset(self, dialect):
        expr = ClickHouseCreateMaterializedViewExpression(
            dialect,
            "mv",
            QUERY,
            to_table="t",
            refresh=ClickHouseRefreshSchedule(every="1 MONTH", offset="5 DAY 2 HOUR"),
        )
        assert "REFRESH EVERY 1 MONTH OFFSET 5 DAY 2 HOUR" in expr.to_sql()[0]

    def test_after(self, dialect):
        expr = ClickHouseCreateMaterializedViewExpression(
            dialect,
            "mv",
            QUERY,
            to_table="t",
            refresh=ClickHouseRefreshSchedule(after="30 MINUTE"),
        )
        assert "REFRESH AFTER 30 MINUTE" in expr.to_sql()[0]

    def test_randomize_for_and_settings(self, dialect):
        expr = ClickHouseCreateMaterializedViewExpression(
            dialect,
            "mv",
            QUERY,
            to_table="t",
            refresh=ClickHouseRefreshSchedule(
                every="1 HOUR", randomize_for="1 HOUR", settings={"refresh_retries": 5}
            ),
        )
        sql, _ = expr.to_sql()
        assert "RANDOMIZE FOR 1 HOUR" in sql
        assert "SETTINGS refresh_retries = 5" in sql

    def test_depends_on(self, dialect):
        expr = ClickHouseCreateMaterializedViewExpression(
            dialect,
            "mv",
            QUERY,
            to_table="t",
            refresh=ClickHouseRefreshSchedule(depends_on=["upstream_mv"]),
        )
        assert "DEPENDS ON `upstream_mv`" in expr.to_sql()[0]

    def test_append_and_append_incremental(self, dialect):
        base = dict(dialect=dialect, view_name="mv", query=QUERY, to_table="t")
        append = ClickHouseCreateMaterializedViewExpression(
            **base, refresh=ClickHouseRefreshSchedule(every="1 HOUR", append=True)
        )
        assert "APPEND" in append.to_sql()[0]
        assert "APPEND INCREMENTAL" not in append.to_sql()[0]
        incremental = ClickHouseCreateMaterializedViewExpression(
            **base,
            refresh=ClickHouseRefreshSchedule(
                every="1 HOUR", append=True, incremental=True
            ),
        )
        assert "APPEND INCREMENTAL" in incremental.to_sql()[0]

    def test_empty_skips_first_refresh(self, dialect):
        expr = ClickHouseCreateMaterializedViewExpression(
            dialect,
            "mv",
            QUERY,
            to_table="t",
            refresh=ClickHouseRefreshSchedule(every="1 DAY"),
            empty=True,
        )
        assert "EMPTY" in expr.to_sql()[0]

    def test_bare_refresh_rejected(self, dialect):
        """The server rejects REFRESH without EVERY/AFTER/DEPENDS ON."""
        with pytest.raises(ValueError, match="at least one of EVERY"):
            ClickHouseCreateMaterializedViewExpression(
                dialect,
                "mv",
                QUERY,
                to_table="t",
                refresh=ClickHouseRefreshSchedule(),
            )

    def test_offset_requires_every(self, dialect):
        with pytest.raises(ValueError, match="OFFSET is only valid with EVERY"):
            ClickHouseRefreshSchedule(after="1 HOUR", offset="1 HOUR").validate()

    def test_incremental_requires_append(self, dialect):
        with pytest.raises(ValueError, match="INCREMENTAL requires APPEND"):
            ClickHouseRefreshSchedule(every="1 HOUR", incremental=True).validate()

    def test_populate_conflicts_with_refresh(self, dialect):
        """POPULATE and REFRESH are mutually exclusive per the docs."""
        with pytest.raises(ValueError, match="POPULATE cannot be combined"):
            ClickHouseCreateMaterializedViewExpression(
                dialect,
                "mv",
                QUERY,
                to_table="t",
                populate=True,
                refresh=ClickHouseRefreshSchedule(every="1 HOUR"),
            )

    def test_empty_requires_refresh(self, dialect):
        with pytest.raises(ValueError, match="EMPTY is only meaningful"):
            ClickHouseCreateMaterializedViewExpression(
                dialect, "mv", QUERY, to_table="t", empty=True
            )


class TestRefreshAndDrop:
    def test_drop_uses_drop_view(self, dialect):
        """ClickHouse removes materialized views with DROP VIEW."""
        expr = ClickHouseDropMaterializedViewExpression(dialect, "mv_agg")
        assert expr.to_sql()[0] == "DROP VIEW IF EXISTS `mv_agg`"

    def test_drop_without_if_exists(self, dialect):
        expr = ClickHouseDropMaterializedViewExpression(
            dialect, "mv_agg", if_exists=False
        )
        assert expr.to_sql()[0] == "DROP VIEW `mv_agg`"

    def test_drop_database_qualified(self, dialect):
        expr = ClickHouseDropMaterializedViewExpression(
            dialect, "mv", database="analytics"
        )
        assert "`analytics`.`mv`" in expr.to_sql()[0]

    def test_system_refresh_view(self, dialect):
        expr = ClickHouseRefreshMaterializedViewExpression(dialect, "mv_ref")
        assert expr.to_sql()[0] == "SYSTEM REFRESH VIEW `mv_ref`"

    def test_system_refresh_and_wait(self, dialect):
        expr = ClickHouseRefreshMaterializedViewExpression(dialect, "mv_ref", wait=True)
        assert expr.to_sql()[0] == (
            "SYSTEM REFRESH VIEW `mv_ref`; SYSTEM WAIT VIEW `mv_ref`"
        )

    def test_modify_refresh_schedule(self, dialect):
        expr = ClickHouseModifyMaterializedViewRefreshExpression(
            dialect, "mv_ref", ClickHouseRefreshSchedule(every="30 MINUTE")
        )
        assert expr.to_sql()[0] == (
            "ALTER TABLE `mv_ref` MODIFY REFRESH EVERY 30 MINUTE"
        )

    def test_modify_refresh_requires_schedule(self, dialect):
        with pytest.raises(ValueError, match="at least one of EVERY"):
            ClickHouseModifyMaterializedViewRefreshExpression(
                dialect, "mv_ref", ClickHouseRefreshSchedule()
            )

    def test_generic_refresh_routes_here(self, dialect):
        expr = RefreshMaterializedViewExpression(dialect=dialect, view_name="mv_ref")
        assert expr.to_sql()[0] == "SYSTEM REFRESH VIEW `mv_ref`"

    def test_generic_concurrent_is_rejected(self, dialect):
        expr = RefreshMaterializedViewExpression(
            dialect=dialect, view_name="mv_ref", concurrent=True
        )
        with pytest.raises(UnsupportedFeatureError) as exc:
            expr.to_sql()
        assert "CONCURRENTLY" in str(exc.value)

    def test_generic_with_data_is_rejected(self, dialect):
        expr = RefreshMaterializedViewExpression(
            dialect=dialect, view_name="mv_ref", with_data=False
        )
        with pytest.raises(UnsupportedFeatureError):
            expr.to_sql()


class TestRejectsNonClickHouseClauses:
    def test_generic_column_aliases(self, dialect):
        expr = CreateMaterializedViewExpression(
            dialect=dialect, view_name="mv", query=QUERY, column_aliases=["a"]
        )
        with pytest.raises(UnsupportedFeatureError) as exc:
            expr.to_sql()
        assert "COLUMN ALIASES" in str(exc.value)

    def test_generic_tablespace(self, dialect):
        expr = CreateMaterializedViewExpression(
            dialect=dialect, view_name="mv", query=QUERY, tablespace="fast_ssd"
        )
        with pytest.raises(UnsupportedFeatureError) as exc:
            expr.to_sql()
        assert "TABLESPACE" in str(exc.value)

    def test_generic_storage_options(self, dialect):
        expr = CreateMaterializedViewExpression(
            dialect=dialect, view_name="mv", query=QUERY, storage_options={"fillfactor": 70}
        )
        with pytest.raises(UnsupportedFeatureError):
            expr.to_sql()

    def test_generic_with_no_data(self, dialect):
        """The regression that started all this: no WITH DATA in ClickHouse."""
        expr = CreateMaterializedViewExpression(
            dialect=dialect, view_name="mv", query=QUERY, with_data=False
        )
        with pytest.raises(UnsupportedFeatureError) as exc:
            expr.to_sql()
        assert "WITH NO DATA" in str(exc.value)
        assert "POPULATE" in str(exc.value)  # points at the ClickHouse alternative

    def test_generic_drop_cascade(self, dialect):
        expr = DropMaterializedViewExpression(
            dialect=dialect, view_name="mv", if_exists=True, cascade=True
        )
        with pytest.raises(UnsupportedFeatureError) as exc:
            expr.to_sql()
        assert "CASCADE" in str(exc.value)

    def test_generic_create_without_engine_or_to_is_rejected(self, dialect):
        """The generic expression carries neither, so it cannot satisfy the rule."""
        expr = CreateMaterializedViewExpression(dialect=dialect, view_name="mv", query=QUERY)
        with pytest.raises(UnsupportedFeatureError):
            expr.to_sql()

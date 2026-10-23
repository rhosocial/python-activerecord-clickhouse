# tests/rhosocial/activerecord_clickhouse_test/feature/backend/introspection/test_introspection_query_nodes.py
"""
The introspection and status reads are expression trees, not SQL strings.

Every statement this backend asks the server about its own catalogs is built
from nodes -- ``QueryStatement``, ``Column``, ``ComparisonPredicate``,
``InPredicate``, ``WhereClause``, ``OrderByClause``, ``Literal`` -- and rendered
by the dialect. What this file pins is the half that can be checked without a
server: the projection, in order and with its aliases; the parameter tuple, in
order; and the engine-specific spellings that a concatenated string used to
carry without anything asserting them.

Why this matters beyond tidiness: a string assembled one clause at a time has no
single place the query exists, and its bind parameters were counted by hand
(``offset=len(sql_params)``). Nothing checked the count against the branches
above it. The tree carries the order instead -- a ``Literal`` binds or inlines at
its own position -- so the tuple below is the whole parameter contract.

No database is involved; a dialect instance is the only input.
"""

import pytest

from rhosocial.activerecord.backend.expression.introspection import (
    ColumnInfoQueryStatement,
    DatabaseInfoQueryStatement,
    IndexInfoQueryStatement,
    TableListQueryStatement,
    ViewInfoQueryStatement,
    ViewListQueryStatement,
)
from rhosocial.activerecord.backend.impl.clickhouse.dialect import ClickHouseDialect
from rhosocial.activerecord.backend.impl.clickhouse.expression.status import (
    ClickHouseConnectionProbeQuery,
    ClickHouseDatabaseTotalSizeQuery,
    ClickHouseDiskListQuery,
    ClickHouseSettingQuery,
    ClickHouseTableCountQuery,
)


@pytest.fixture(scope="module")
def dialect():
    """The scenario server's version shape (26.7.3)."""
    return ClickHouseDialect(version=(26, 7, 3))


class TestIntrospectionQueriesAreTrees:
    """Each ``format_*_query`` builds a statement and hands it to the dialect."""

    def test_database_info_reads_system_databases_by_name(self, dialect):
        sql, params = DatabaseInfoQueryStatement(dialect, schema="analytics").to_sql()
        assert "FROM `system`.`databases`" in sql
        assert "`engine` AS `DEFAULT_CHARACTER_SET_NAME`" in sql
        assert "CAST('' AS String) AS `DEFAULT_COLLATION_NAME`" in sql
        assert params == ("analytics",)

    def test_table_list_keeps_the_projection_order_and_aliases(self, dialect):
        sql, params = TableListQueryStatement(dialect, schema="default").to_sql()
        assert sql.index("`name` AS `TABLE_NAME`") < sql.index("`engine` AS `TABLE_TYPE`")
        assert sql.index("`engine` AS `TABLE_TYPE`") < sql.index("`comment` AS `TABLE_COMMENT`")
        assert sql.index("`metadata_modification_time` AS `MODIFICATION_TIME`") > sql.index(
            "`total_bytes` AS `DATA_LENGTH`"
        )
        assert params == ("default",)

    def test_table_list_excludes_views_with_the_declared_engine_set(self, dialect):
        sql, params = TableListQueryStatement(
            dialect, schema="default", include_views=False
        ).to_sql()
        assert "NOT (`engine` IN (" in sql
        assert params == (
            "default",
            "View",
            "MaterializedView",
            "LiveView",
            "WindowView",
        )

    def test_table_list_excludes_the_system_database_inline(self, dialect):
        """``'system'`` is a fixed word of the query, so it never becomes a parameter."""
        sql, params = TableListQueryStatement(dialect, schema="default").to_sql()
        assert "`database` <> 'system'" in sql
        assert "system" not in params

    def test_column_info_derives_nullability_from_the_type_name(self, dialect):
        sql, params = ColumnInfoQueryStatement(dialect, "users", schema="default").to_sql()
        # Doubled `%`: this statement bypasses Backend.execute, so it bypasses
        # the escape that adds the second `%` for the driver's interpolation.
        assert "IF(`type` LIKE 'Nullable(%%', 'YES', 'NO') AS `IS_NULLABLE`" in sql
        assert params == ("default", "users")
        assert sql.endswith("ORDER BY `position`")

    def test_index_info_reports_clickhouses_own_columns(self, dialect):
        sql, params = IndexInfoQueryStatement(dialect, "users", schema="default").to_sql()
        assert "FROM `system`.`data_skipping_indices`" in sql
        assert "CAST(NULL AS Nullable(String)) AS `SUB_PART`" in sql
        assert params == ("default", "users")

    def test_view_list_binds_the_engine_set_and_inlines_the_system_exclusion(
        self, dialect
    ):
        sql, params = ViewListQueryStatement(dialect, schema="default").to_sql()
        assert "`engine` IN (" in sql
        assert "`database` <> 'system'" in sql
        assert params == (
            "default",
            "View",
            "MaterializedView",
            "LiveView",
            "WindowView",
        )

    def test_view_info_filters_by_name_then_engine(self, dialect):
        sql, params = ViewInfoQueryStatement(dialect, "v", schema="default").to_sql()
        assert "`name` = %s" in sql
        assert params == ("default", "v", "View", "MaterializedView", "LiveView", "WindowView")


class TestStatusQueriesAreTrees:
    """The status reads build the same kind of tree, one formatter each."""

    def test_setting_query_binds_the_setting_name(self, dialect):
        sql, params = ClickHouseSettingQuery(dialect, "max_concurrent_queries").to_sql()
        assert sql == (
            "SELECT `value` FROM `system`.`settings` WHERE `name` = %s"
        )
        assert params == ("max_concurrent_queries",)

    def test_database_total_size_uses_the_sum_aggregate(self, dialect):
        sql, params = ClickHouseDatabaseTotalSizeQuery(dialect, "default").to_sql()
        assert sql == (
            "SELECT SUM(`total_bytes`) AS `total_size` FROM `system`.`tables` "
            "WHERE `database` = %s"
        )
        assert params == ("default",)

    def test_disk_list_projects_every_flag(self, dialect):
        sql, params = ClickHouseDiskListQuery(dialect).to_sql()
        for column in (
            "`name`",
            "`path`",
            "`type`",
            "`total_space`",
            "`free_space`",
            "`unreserved_space`",
            "`keep_free_space`",
            "`is_encrypted`",
            "`is_read_only`",
            "`is_remote`",
            "`is_broken`",
        ):
            assert column in sql
        assert params == ()

    def test_table_count_groups_by_schema_and_type(self, dialect):
        sql, params = ClickHouseTableCountQuery(dialect, ["default", "analytics"]).to_sql()
        assert "FROM `information_schema`.`TABLES`" in sql
        assert "GROUP BY `table_schema`, `table_type`" in sql
        assert params == ("default", "analytics")

    def test_connection_probe_is_a_relation_less_scalar(self, dialect):
        assert ClickHouseConnectionProbeQuery(dialect).to_sql() == ("SELECT 1", ())

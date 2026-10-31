# tests/rhosocial/activerecord_clickhouse_test/feature/backend/introspection/test_introspection_parsing.py
"""What the ClickHouse introspection parsers report, without a server.

Three defects are pinned here, all in the half of introspection that needs no
connection:

* ``system.tables`` answers an *engine*, not a standard table type. The parser
  used to look up ``TABLE_TYPE`` against ``BASE TABLE`` / ``VIEW`` /
  ``SYSTEM VIEW``, which no ClickHouse server reports, so every relation came
  back as a base table and the engine name stood in for the kind. The kind is
  now derived from the engine through the dialect's declared view-engine set,
  and the engine travels beside it in ``extra``.
* ``system.databases`` answers a name and an engine; it has no per-database
  charset or collation. The parser used to report the engine as ``encoding``
  and ``0.0.0`` as the version. It now reports ``encoding=None`` and reads the
  version through ``server_version``, falling back to the ``"unknown"``
  convention rather than to a release number that does not exist.
* The table-list ``table_type`` filter compared it to ``engine`` verbatim, so
  ``VIEW`` selected nothing (no engine is called ``VIEW``). It now reads the
  introspection vocabulary and selects the engines that store that kind.

Only a dialect and a two-attribute backend stub are needed; nothing here talks
to ClickHouse.
"""

from types import SimpleNamespace

import pytest

from rhosocial.activerecord.backend.expression.introspection import (
    DatabaseInfoQueryStatement,
    TableListQueryStatement,
)
from rhosocial.activerecord.backend.impl.clickhouse.dialect import ClickHouseDialect
from rhosocial.activerecord.backend.impl.clickhouse.introspection import (
    SyncClickHouseIntrospector,
)
from rhosocial.activerecord.backend.introspection.types import TableType


class _StubBackend:
    """The facts the parsers read from their backend, and nothing else."""

    def __init__(self, dialect, database="analytics", cached_version=None):
        self.dialect = dialect
        self.config = SimpleNamespace(database=database)
        self._cached_version = cached_version

    def get_cached_server_version(self):
        return self._cached_version


def _introspector(dialect, database="analytics", cached_version=None):
    return SyncClickHouseIntrospector(
        _StubBackend(dialect, database, cached_version), executor=None
    )


@pytest.fixture(scope="module")
def dialect():
    """The scenario server's version shape (26.7.3)."""
    return ClickHouseDialect(version=(26, 7, 3))


def _table_row(name, engine):
    return {
        "TABLE_NAME": name,
        "ENGINE": engine,
        "TABLE_COMMENT": "",
        "TABLE_ROWS": 0,
        "DATA_LENGTH": 0,
    }


class TestTableKindFromEngine:
    """The kind comes from the engine, and the engine is not discarded."""

    @pytest.mark.parametrize(
        "engine, expected",
        [
            ("MergeTree", TableType.BASE_TABLE),
            ("ReplicatedMergeTree", TableType.BASE_TABLE),
            ("Log", TableType.BASE_TABLE),
            ("View", TableType.VIEW),
            ("LiveView", TableType.VIEW),
            ("WindowView", TableType.VIEW),
            ("MaterializedView", TableType.MATERIALIZED_VIEW),
        ],
    )
    def test_engine_maps_to_its_relation_kind(self, dialect, engine, expected):
        (info,) = _introspector(dialect).parse_tables([_table_row("rel", engine)], "analytics")
        assert info.table_type is expected
        assert info.extra == {"engine": engine}

    def test_every_declared_view_engine_is_a_view_kind(self, dialect):
        for engine in dialect.VIEW_ENGINES:
            assert dialect.engine_kind(engine) in (
                TableType.VIEW,
                TableType.MATERIALIZED_VIEW,
            )

    def test_kind_groups_partition_the_declared_view_engines(self, dialect):
        """The per-kind groups and the SQL filter read one closed set."""
        grouped = [engine for _, engines in dialect.VIEW_ENGINE_KINDS for engine in engines]
        assert sorted(grouped) == sorted(dialect.VIEW_ENGINES)
        assert len(grouped) == len(set(grouped))

    def test_only_materialized_view_gets_its_own_kind(self, dialect):
        materialized = dict(dialect.VIEW_ENGINE_KINDS)["MATERIALIZED_VIEW"]
        for engine in materialized:
            assert dialect.engine_kind(engine) is TableType.MATERIALIZED_VIEW

    def test_rows_from_the_system_database_are_system_tables(self, dialect):
        (info,) = _introspector(dialect, database="system").parse_tables(
            [_table_row("query_log", "MergeTree")], "system"
        )
        assert info.table_type is TableType.SYSTEM_TABLE
        assert info.extra == {"engine": "MergeTree"}

    def test_a_known_table_is_still_a_base_table_in_a_user_database(self, dialect):
        (info,) = _introspector(dialect).parse_tables(
            [_table_row("events", "MergeTree")], "analytics"
        )
        assert info.table_type is TableType.BASE_TABLE


class TestDatabaseInfo:
    """Version, encoding and collation are what the server answered."""

    def test_version_comes_from_the_adapted_dialect(self, dialect):
        info = _introspector(dialect).parse_database_info(
            [{"DATABASE_NAME": "analytics", "ENGINE": "Atomic"}]
        )
        assert info.name == "analytics"
        assert info.version == "26.7.3"
        assert info.version_tuple == (26, 7, 3)
        assert info.encoding is None
        assert info.collation is None
        assert info.extra == {"engine": "Atomic"}

    def test_version_uses_the_cached_server_version_without_adapting(self):
        introspector = _introspector(
            ClickHouseDialect(), cached_version=(25, 8, 0)
        )
        info = introspector.parse_database_info([])
        assert info.version == "25.8.0"
        assert info.version_tuple == (25, 8, 0)

    def test_unknown_version_is_reported_as_unknown_not_as_zero(self):
        introspector = _introspector(ClickHouseDialect())
        info = introspector.parse_database_info([])
        assert info.version == "unknown"
        assert info.version_tuple == (0, 0, 0)
        # The schema still answers what it is, and nothing invents a charset.
        assert info.name == "analytics"
        assert info.encoding is None
        assert info.collation is None
        assert info.extra == {}

    def test_database_info_query_projects_no_charset(self, dialect):
        sql, params = DatabaseInfoQueryStatement(dialect, schema="analytics").to_sql()
        assert params == ("analytics",)
        assert "`engine` AS `ENGINE`" in sql
        assert "DEFAULT_CHARACTER_SET_NAME" not in sql
        assert "DEFAULT_COLLATION_NAME" not in sql


class TestTableTypeFilter:
    """``table_type`` is a kind, and an engine name is still accepted."""

    def test_view_selects_the_engines_that_store_a_view(self, dialect):
        sql, params = TableListQueryStatement(
            dialect, schema="analytics", table_type="VIEW"
        ).to_sql()
        assert "`engine` IN (%s, %s, %s)" in sql
        assert "`engine` = %s" not in sql
        assert params == ("analytics", "View", "LiveView", "WindowView")

    def test_materialized_view_selects_only_its_engine(self, dialect):
        sql, params = TableListQueryStatement(
            dialect, schema="analytics", table_type=TableType.MATERIALIZED_VIEW
        ).to_sql()
        assert "`engine` IN (%s)" in sql
        assert params == ("analytics", "MaterializedView")

    @pytest.mark.parametrize("spelling", ["BASE_TABLE", "TABLE"])
    def test_base_table_is_everything_outside_the_view_engines(
        self, dialect, spelling
    ):
        sql, params = TableListQueryStatement(
            dialect, schema="analytics", table_type=spelling
        ).to_sql()
        assert "NOT (`engine` IN (%s, %s, %s, %s))" in sql
        assert params == (
            "analytics",
            "View",
            "MaterializedView",
            "LiveView",
            "WindowView",
        )

    def test_an_engine_name_is_still_an_engine_filter(self, dialect):
        sql, params = TableListQueryStatement(
            dialect, schema="analytics", table_type="MergeTree"
        ).to_sql()
        assert "`engine` = %s" in sql
        assert params == ("analytics", "MergeTree")

    def test_system_tables_are_selected_by_their_database(self, dialect):
        sql, params = TableListQueryStatement(
            dialect, schema="system", table_type="SYSTEM_TABLE"
        ).to_sql()
        assert "`database` = 'system'" in sql
        # Asking for system tables by kind is the request ``include_system``
        # exists for; the exclusion must not be conjoined with it.
        assert "`database` <> 'system'" not in sql
        assert params == ("system",)

    def test_a_kind_this_catalogue_never_reports_selects_nothing(self, dialect):
        sql, params = TableListQueryStatement(
            dialect, schema="analytics", table_type="PARTITIONED_TABLE"
        ).to_sql()
        assert "1 = 0" in sql
        assert params == ("analytics",)

    def test_the_list_tables_entry_point_uses_the_same_filter(self, dialect):
        """``list_tables`` — what the CLI calls — asks the corrected question."""
        introspector = _introspector(dialect)
        sql, params = introspector.table_list_statement(
            schema=None, include_system=False, table_type="VIEW"
        ).to_sql()
        assert "`engine` IN (%s, %s, %s)" in sql
        assert params == ("analytics", "View", "LiveView", "WindowView")

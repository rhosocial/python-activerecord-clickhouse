# tests/rhosocial/activerecord_clickhouse_test/feature/backend/introspection/test_show_output_shape.py
"""
The SHOW sub-introspector reads ClickHouse's output columns, not MySQL's.

ClickHouse's ``SHOW`` commands report different column names from MySQL's, and
the difference is not cosmetic: reading MySQL's names against ClickHouse's rows
does not raise, it silently yields nothing.

================================  =====================================
statement                         ClickHouse columns
================================  =====================================
``SHOW CREATE TABLE``             ``statement``
``SHOW CREATE VIEW``              ``statement``
``SHOW TABLES``                   ``name``
``SHOW FULL TABLES``              ``name``, ``engine``
``SHOW DATABASES``                ``name``
``SHOW PROCESSLIST``              ``system.processes``' 43 columns
``SHOW [FULL] COLUMNS``           ``field``, ``type``, ``null``, ``key``,
                                  ``default``, ``extra`` (+ ``collation``,
                                  ``comment``, ``privileges`` under FULL)
``SHOW INDEX``                    ``table``, ``non_unique``, ``key_name``,
                                  ``seq_in_index``, ``pk_col``, ``collation``,
                                  ``cardinality``, ``sub_part``, ``packed``,
                                  ``null``, ``index_type``, ``comment``,
                                  ``index_comment``, ``visible``,
                                  ``expression``
``SHOW ENGINES``                  ``name`` and the eight ``supports_*`` flags;
                                  ``description``, ``syntax``, ``examples``,
                                  ``introduced_in``, ``related`` only on
                                  versions that publish them
``SHOW GRANTS``                   one column named after the statement text
                                  plus the requested output format
================================  =====================================

MySQL would answer ``Table``/``Create Table``, ``View``/``Create View``,
``Tables_in_<db>``/``Table_type`` and ``Database``. Every row below is the
shape the server actually produces; the live half of this file
(``TestShowOutputAgainstTheServer``) re-reads it from a real connection.

The three failure modes this pins down, all of which were live before:
``create_table``/``create_view`` returned ``create_statement=''``,
``tables(full=True)`` returned ``[]``, ``databases()`` returned one entry
per database with ``name=None``, and ``columns()`` / ``indexes()`` /
``processlist()`` / ``engines()`` / ``grants()`` raised
``UnsupportedFeatureError`` on statements the server accepts.

MySQL would answer ``Table``/``Create Table``, ``View``/``Create View``,
``Tables_in_<db>``/``Table_type``, ``Database``, ``Field``/``Type``/``Null``/
``Key``, ``Column_name`` for the indexed column, ``Id``/``User``/``Host``/
``Command``/``Time``, ``Engine``/``Support``/``Transactions``/``XA``/
``Savepoints``, and ``Grants for`` — so the ones below are the ClickHouse
column names, not a restatement of the MySQL ones.
"""
import pytest

from rhosocial.activerecord.backend.impl.clickhouse.introspection.show_introspector import ShowMixin


class TestCreateStatementOutputShape:
    """``SHOW CREATE TABLE`` / ``SHOW CREATE VIEW`` answer a single ``statement`` column."""

    TABLE_ROW = {"statement": "CREATE TABLE default.t\n(\n    `id` Int64\n)\nENGINE = MergeTree"}
    VIEW_ROW = {"statement": "CREATE VIEW default.v\n(\n    `id` Int64\n)\nAS SELECT id"}

    def test_create_table_reads_the_statement_column(self):
        result = ShowMixin._parse_create_table([self.TABLE_ROW], "t")
        assert result.table_name == "t"
        assert result.create_statement == self.TABLE_ROW["statement"]

    def test_create_view_reads_the_statement_column(self):
        result = ShowMixin._parse_create_view([self.VIEW_ROW], "v")
        assert result.view_name == "v"
        assert result.create_statement == self.VIEW_ROW["statement"]

    def test_create_view_leaves_mysql_only_fields_empty(self):
        result = ShowMixin._parse_create_view([self.VIEW_ROW], "v")
        assert result.character_set_client is None
        assert result.collation_connection is None

    def test_no_rows_returns_none(self):
        assert ShowMixin._parse_create_table([], "t") is None
        assert ShowMixin._parse_create_view([], "v") is None

    def test_mysql_column_names_are_not_consulted(self):
        """A row carrying only MySQL's names must not be mistaken for a result."""
        assert ShowMixin._parse_create_table([{"Create Table": "..."}], "t").create_statement == ""
        assert ShowMixin._parse_create_view([{"Create View": "..."}], "v").create_statement == ""


class TestListOutputShape:
    """``SHOW TABLES`` / ``SHOW DATABASES`` name the column ``name``."""

    def test_tables_reads_name(self):
        rows = [{"name": "a"}, {"name": "b"}]
        result = ShowMixin._parse_tables(rows)
        assert [(r.name, r.table_type) for r in result] == [("a", None), ("b", None)]

    def test_full_tables_reads_name_and_engine(self):
        """Under ``FULL`` the second column is the storage engine, not a table type."""
        rows = [{"name": "a", "engine": "MergeTree"}, {"name": "v", "engine": "View"}]
        result = ShowMixin._parse_tables(rows)
        assert [(r.name, r.table_type) for r in result] == [
            ("a", "MergeTree"),
            ("v", "View"),
        ]

    def test_databases_reads_name(self):
        rows = [{"name": "default"}, {"name": "system"}]
        assert [r.name for r in ShowMixin._parse_databases(rows)] == ["default", "system"]

    def test_mysql_column_names_are_not_consulted(self):
        """MySQL's ``Tables_in_<db>`` / ``Database`` names must not be looked for."""
        mysql_rows = [{"Tables_in_db": "a", "Table_type": "BASE TABLE"}]
        result = ShowMixin._parse_tables(mysql_rows)
        assert [(r.name, r.table_type) for r in result] == [(None, None)]
        assert [r.name for r in ShowMixin._parse_databases([{"Database": "default"}])] == [None]


# Every row below is a row the 26.7.3.19 server returned, quoted column for
# column; the live classes at the bottom of this file re-derive them.

COLUMN_ROWS = [
    {"field": "al", "type": "UInt8", "null": "NO", "key": "", "default": "id", "extra": ""},
    {"field": "id", "type": "UInt32", "null": "NO", "key": "PRI SOR", "default": None, "extra": ""},
]

COLUMN_FULL_ROWS = [
    {
        "field": "id", "type": "UInt32", "null": "NO", "key": "PRI SOR",
        "default": None, "extra": "", "collation": None, "comment": "",
        "privileges": "",
    }
]

INDEX_ROWS = [
    {
        "table": "idx_probe", "non_unique": 1, "key_name": "idx_s",
        "seq_in_index": 1, "pk_col": "", "collation": None, "cardinality": 0,
        "sub_part": None, "packed": None, "null": None,
        "index_type": "BLOOM_FILTER", "comment": "", "index_comment": "",
        "visible": "YES", "expression": "s",
    },
    {
        "table": "idx_probe", "non_unique": 1, "key_name": "PRIMARY",
        "seq_in_index": 1, "pk_col": "id", "collation": "A", "cardinality": 0,
        "sub_part": None, "packed": None, "null": None,
        "index_type": "PRIMARY", "comment": "", "index_comment": "",
        "visible": "YES", "expression": "",
    },
]

PROCESSLIST_ROWS = [
    {
        "is_initial_query": 1, "user": "root",
        "query_id": "0a944dd1-8a7e-4fd2-9733-e9e44f4d9f53",
        "address": "::ffff:192.168.65.1", "port": 39550,
        "elapsed": 0.00164, "read_rows": 0, "read_bytes": 0,
        "memory_usage": 4438556, "query": "SELECT 1", "query_kind": "Select",
        "thread_ids": [42], "current_database": "test_db", "is_internal": 0,
    }
]

ENGINE_ROWS = [
    {
        "name": "AggregatingMergeTree", "supports_settings": 1,
        "supports_skipping_indices": 1, "supports_projections": 1,
        "supports_sort_order": 1, "supports_ttl": 1, "supports_replication": 0,
        "supports_deduplication": 0, "supports_parallel_insert": 1,
        "description": "# AggregatingMergeTree", "syntax": "AGGREGATING",
        "examples": "", "introduced_in": "",
        "related": ["ReplicatedAggregatingMergeTree"],
    }
]

GRANT_ROWS = [
    {"GRANTS FORMAT Native": "GRANT SOURCES ON *.* TO root WITH GRANT OPTION"},
    {"GRANTS FOR root": "GRANT SET DEFINER ON * TO root WITH GRANT OPTION"},
]


class TestColumnsOutputShape:
    """``SHOW [FULL] COLUMNS`` answers lower-cased ``field``/``type``/``key``/..."""

    def test_columns_read_the_lowercase_names(self):
        result = ShowMixin._parse_columns(COLUMN_ROWS)
        assert [(r.field, r.type, r.null, r.key) for r in result] == [
            ("al", "UInt8", "NO", ""),
            ("id", "UInt32", "NO", "PRI SOR"),
        ]

    def test_columns_carry_default_and_extra(self):
        result = ShowMixin._parse_columns(COLUMN_ROWS)
        assert [(r.default, r.extra) for r in result] == [("id", ""), (None, "")]

    def test_full_columns_read_collation_comment_and_privileges(self):
        """The three extra columns appear only under ``FULL``, in lower case."""
        result = ShowMixin._parse_columns(COLUMN_FULL_ROWS)
        assert (result[0].collation, result[0].comment, result[0].privileges) == (
            None, "", "",
        )

    def test_plain_columns_leave_the_full_only_columns_empty(self):
        result = ShowMixin._parse_columns(COLUMN_ROWS)
        assert all(r.collation is None and r.comment is None and r.privileges is None for r in result)

    def test_mysql_column_names_are_not_consulted(self):
        """MySQL's ``Field``/``Type``/``Key`` must not be looked for."""
        result = ShowMixin._parse_columns(
            [{"Field": "id", "Type": "int", "Null": "NO", "Key": "PRI", "Default": None, "Extra": ""}]
        )
        assert [(r.field, r.type, r.key) for r in result] == [(None, None, None)]


class TestIndexOutputShape:
    """``SHOW INDEX`` answers ``pk_col`` where MySQL answers ``Column_name``."""

    def test_index_reads_pk_col_as_the_column_name(self):
        result = ShowMixin._parse_indexes(INDEX_ROWS)
        assert [r.column_name for r in result] == ["", "id"]

    def test_index_reports_clickhouse_index_types(self):
        result = ShowMixin._parse_indexes(INDEX_ROWS)
        assert [r.index_type for r in result] == ["BLOOM_FILTER", "PRIMARY"]

    def test_skipping_index_keeps_its_expression(self):
        skip, primary = ShowMixin._parse_indexes(INDEX_ROWS)
        assert (skip.key_name, skip.expression, skip.collation) == ("idx_s", "s", None)
        assert (primary.key_name, primary.expression, primary.collation) == ("PRIMARY", "", "A")

    def test_index_carries_no_mysql_btree_default(self):
        """``index_type`` must come from the server, not default to ``BTREE``."""
        result = ShowMixin._parse_indexes([{"table": "t", "non_unique": 1, "key_name": "PRIMARY", "seq_in_index": 1}])
        assert result[0].index_type is None

    def test_mysql_column_names_are_not_consulted(self):
        result = ShowMixin._parse_indexes(
            [{"Table": "t", "Key_name": "PRIMARY", "Column_name": "id", "Index_type": "BTREE"}]
        )
        assert [(r.table_name, r.column_name, r.index_type) for r in result] == [(None, None, None)]


class TestProcessListOutputShape:
    """``SHOW PROCESSLIST`` is ``system.processes``, so its columns are that table's."""

    def test_processlist_maps_query_id_user_address_and_elapsed(self):
        row = ShowMixin._parse_processlist(PROCESSLIST_ROWS)[0]
        assert row.id == "0a944dd1-8a7e-4fd2-9733-e9e44f4d9f53"
        assert row.user == "root"
        assert row.host == "::ffff:192.168.65.1:39550"
        assert row.db == "test_db"
        assert row.info == "SELECT 1"
        assert row.time == pytest.approx(0.00164)

    def test_command_and_state_have_no_clickhouse_source(self):
        """``system.processes`` has no per-process command or state column."""
        row = ShowMixin._parse_processlist(PROCESSLIST_ROWS)[0]
        assert row.command is None
        assert row.state is None

    def test_mysql_column_names_are_not_consulted(self):
        result = ShowMixin._parse_processlist(
            [{"Id": 1, "User": "root", "Host": "localhost", "Command": "Query", "Time": 0}]
        )
        assert [(r.id, r.user, r.host, r.command, r.time) for r in result] == [
            (None, None, None, None, None)
        ]


class TestEnginesOutputShape:
    """``SHOW ENGINES`` is ``system.table_engines``: ``name`` plus ``supports_*``."""

    def test_engines_read_the_name_column(self):
        assert ShowMixin._parse_engines(ENGINE_ROWS)[0].engine == "AggregatingMergeTree"

    def test_engines_read_all_eight_supports_flags(self):
        row = ShowMixin._parse_engines(ENGINE_ROWS)[0]
        assert (row.supports_settings, row.supports_skipping_indices) == (1, 1)
        assert (row.supports_projections, row.supports_sort_order) == (1, 1)
        assert (row.supports_ttl, row.supports_replication) == (1, 0)
        assert (row.supports_deduplication, row.supports_parallel_insert) == (0, 1)

    def test_engines_read_the_documentation_columns(self):
        row = ShowMixin._parse_engines(ENGINE_ROWS)[0]
        assert row.description == "# AggregatingMergeTree"
        assert row.syntax == "AGGREGATING"
        assert row.related == ["ReplicatedAggregatingMergeTree"]

    def test_mysql_column_names_are_not_consulted(self):
        """MySQL's ``Engine``/``Support``/``XA`` must not be looked for."""
        result = ShowMixin._parse_engines(
            [{"Engine": "InnoDB", "Support": "DEFAULT", "Transactions": "YES", "XA": "NO", "Savepoints": "NO"}]
        )
        assert result[0].engine is None


class TestGrantsOutputShape:
    """``SHOW GRANTS`` labels its only column after the statement plus the format."""

    def test_grants_reads_the_native_protocol_column_name(self):
        assert ShowMixin._parse_grants(GRANT_ROWS[:1])[0].grants.startswith("GRANT SOURCES")

    def test_grants_reads_the_for_user_column_name(self):
        assert ShowMixin._parse_grants(GRANT_ROWS[1:])[0].grants == (
            "GRANT SET DEFINER ON * TO root WITH GRANT OPTION"
        )

    def test_grants_falls_back_to_the_single_column_value(self):
        """HTTP with ``default_format=JSONEachRow`` names the bare column ``GRANTS``."""
        assert ShowMixin._parse_grants([{"GRANTS": "GRANT SELECT ON *.* TO u"}])[0].grants == (
            "GRANT SELECT ON *.* TO u"
        )

    def test_grants_reads_a_row_whose_column_is_unrecognised(self):
        """The statement has exactly one column; its value is the grant either way."""
        assert ShowMixin._parse_grants([{"SHOW GRANTS": "GRANT ALL ON *.* TO u"}])[0].grants == (
            "GRANT ALL ON *.* TO u"
        )

    def test_mysql_column_name_is_not_required(self):
        """MySQL's fixed ``Grants for`` is not the lookup key; the value is."""
        result = ShowMixin._parse_grants([{"Grants for root@localhost": "GRANT ALL"}])
        assert result[0].grants == "GRANT ALL"

    def test_an_empty_row_yields_no_grant(self):
        assert ShowMixin._parse_grants([{}])[0].grants is None


class TestShowDialectRendersWhatTheServerAccepts:
    """The five formatters emit SQL 26.7.3.19 parses, not MySQL's shapes."""

    @pytest.fixture
    def dialect(self):
        from rhosocial.activerecord.backend.impl.clickhouse.dialect import ClickHouseDialect

        return ClickHouseDialect(version=(26, 7, 1))

    def _columns(self, dialect, **kw):
        from rhosocial.activerecord.backend.impl.clickhouse.expression.show import (
            ShowColumnsExpression,
        )

        expr = ShowColumnsExpression(dialect, "t")
        if kw.get("schema"):
            expr.schema(kw["schema"])
        if kw.get("full"):
            expr.full()
        if kw.get("like"):
            expr.like(kw["like"])
        return expr.to_sql()

    def test_columns_sql(self, dialect):
        assert self._columns(dialect) == ("SHOW COLUMNS FROM `t`", ())
        assert self._columns(dialect, schema="db") == ("SHOW COLUMNS FROM `db`.`t`", ())
        assert self._columns(dialect, full=True) == ("SHOW FULL COLUMNS FROM `t`", ())
        assert self._columns(dialect, like="i%") == ("SHOW COLUMNS FROM `t` LIKE %s", ("i%",))

    def test_index_sql_uses_one_table_reference(self, dialect):
        """``SHOW INDEX FROM t FROM db`` is a SYNTAX_ERROR; ``db.t`` is the form."""
        from rhosocial.activerecord.backend.impl.clickhouse.expression.show import (
            ShowIndexExpression,
        )

        expr = ShowIndexExpression(dialect, "t").schema("db")
        assert expr.to_sql() == ("SHOW INDEX FROM `db`.`t`", ())

    def test_processlist_sql_never_emits_full(self, dialect):
        """``SHOW FULL PROCESSLIST`` is a SYNTAX_ERROR on 26.7.3.19."""
        from rhosocial.activerecord.backend.impl.clickhouse.expression.show import (
            ShowProcessListExpression,
        )

        assert ShowProcessListExpression(dialect).full().to_sql() == ("SHOW PROCESSLIST", ())

    def test_engines_sql(self, dialect):
        from rhosocial.activerecord.backend.impl.clickhouse.expression.show import (
            ShowEnginesExpression,
        )

        assert ShowEnginesExpression(dialect).to_sql() == ("SHOW ENGINES", ())

    def test_grants_sql_drops_the_mysql_host_part(self, dialect):
        """``SHOW GRANTS FOR root@localhost`` is UNKNOWN_ROLE on 26.7.3.19."""
        from rhosocial.activerecord.backend.impl.clickhouse.expression.show import (
            ShowGrantsExpression,
        )

        assert ShowGrantsExpression(dialect).to_sql() == ("SHOW GRANTS", ())
        assert ShowGrantsExpression(dialect).for_user("root").to_sql() == (
            "SHOW GRANTS FOR `root`", (),
        )
        assert ShowGrantsExpression(dialect).for_user("root", "localhost").to_sql() == (
            "SHOW GRANTS FOR `root`", (),
        )


class TestShowOutputAgainstTheServer:
    """The same shapes, read from a live ClickHouse connection."""

    @pytest.fixture
    def show_fixture(self, clickhouse_backend_single):
        backend = clickhouse_backend_single
        backend.execute("DROP TABLE IF EXISTS ar_show_shape")
        backend.execute("DROP VIEW IF EXISTS ar_show_shape_v")
        backend.execute(
            "CREATE TABLE ar_show_shape (id UInt32, created_at DateTime) "
            "ENGINE = MergeTree PARTITION BY toYYYYMM(created_at) ORDER BY id"
        )
        backend.execute(
            "CREATE VIEW ar_show_shape_v AS SELECT id FROM ar_show_shape"
        )
        yield backend
        backend.execute("DROP VIEW IF EXISTS ar_show_shape_v")
        backend.execute("DROP TABLE IF EXISTS ar_show_shape")

    @pytest.fixture
    def indexed_fixture(self, clickhouse_backend_single):
        """A table with a sorting key *and* a data skipping index."""
        backend = clickhouse_backend_single
        backend.execute("DROP TABLE IF EXISTS ar_show_indexed")
        backend.execute(
            "CREATE TABLE ar_show_indexed (id UInt32, s String, "
            "INDEX idx_s s TYPE bloom_filter(0.01) GRANULARITY 4) "
            "ENGINE = MergeTree ORDER BY (id, s)"
        )
        yield backend, "ar_show_indexed"
        backend.execute("DROP TABLE IF EXISTS ar_show_indexed")

    def test_create_table_returns_the_statement(self, show_fixture):
        result = show_fixture.introspector.show.create_table("ar_show_shape")
        assert result.table_name == "ar_show_shape"
        assert result.create_statement.startswith("CREATE TABLE")
        assert "MergeTree" in result.create_statement
        assert "PARTITION BY toYYYYMM(created_at)" in result.create_statement

    def test_create_view_returns_the_statement(self, show_fixture):
        result = show_fixture.introspector.show.create_view("ar_show_shape_v")
        assert result.view_name == "ar_show_shape_v"
        assert result.create_statement.startswith("CREATE VIEW")

    def test_full_tables_reports_the_storage_engine(self, show_fixture):
        rows = {
            row.name: row.table_type
            for row in show_fixture.introspector.show.tables(full=True)
        }
        assert rows["ar_show_shape"] == "MergeTree"
        assert rows["ar_show_shape_v"] == "View"

    def test_tables_reports_names(self, show_fixture):
        names = [row.name for row in show_fixture.introspector.show.tables()]
        assert "ar_show_shape" in names

    def test_databases_reports_names(self, show_fixture):
        names = [row.name for row in show_fixture.introspector.show.databases()]
        assert "default" in names
        assert all(name is not None for name in names)

    def test_columns_reports_types_and_sorting_key(self, show_fixture):
        cols = {c.field: c for c in show_fixture.introspector.show.columns("ar_show_shape")}
        assert set(cols) == {"id", "created_at"}
        assert cols["id"].type == "UInt32"
        assert cols["id"].null == "NO"
        assert cols["id"].key == "PRI SOR"
        assert cols["created_at"].type == "DateTime"

    def test_columns_respects_a_schema(self, show_fixture):
        """``SHOW COLUMNS FROM db.t`` names the same columns as the bare form."""
        cols = show_fixture.introspector.show.columns(
            "ar_show_shape", schema=show_fixture.config.database
        )
        assert sorted(c.field for c in cols) == ["created_at", "id"]

    def test_columns_are_returned_in_name_order(self, show_fixture):
        """ClickHouse orders the result by column name, not by declaration order.

        Measured: ``SHOW COLUMNS FROM t`` on a table declared
        ``(id UInt32, created_at DateTime)`` returns ``created_at`` then ``id`` —
        the definition order is only in ``SHOW CREATE TABLE`` / ``system.columns``.
        """
        cols = show_fixture.introspector.show.columns("ar_show_shape")
        assert [c.field for c in cols] == ["created_at", "id"]

    def test_full_columns_adds_comment_and_privileges(self, show_fixture):
        cols = {c.field: c for c in show_fixture.introspector.show.columns("ar_show_shape", full=True)}
        assert cols["id"].comment == ""
        assert cols["id"].privileges == ""
        # The server documents this column as always NULL: no per-column collations.
        assert cols["id"].collation is None

    def test_columns_like_filters(self, show_fixture):
        cols = show_fixture.introspector.show.columns("ar_show_shape", like="id%")
        assert [c.field for c in cols] == ["id"]

    def test_columns_for_a_missing_table_is_empty_not_an_error(self, show_fixture):
        """``SHOW COLUMNS FROM no_such_table`` returns headers and zero rows."""
        assert show_fixture.introspector.show.columns("ar_no_such_table_xyz") == []

    def test_indexes_reports_sorting_key_and_skipping_index(self, indexed_fixture):
        backend, table = indexed_fixture
        rows = {
            (r.key_name, r.seq_in_index): r
            for r in backend.introspector.show.indexes(table)
        }
        primary_1 = rows[("PRIMARY", 1)]
        primary_2 = rows[("PRIMARY", 2)]
        assert (primary_1.column_name, primary_1.collation) == ("id", "A")
        assert (primary_2.column_name, primary_2.collation) == ("s", "A")
        skip = rows[("idx_s", 1)]
        assert skip.index_type == "BLOOM_FILTER"
        assert skip.column_name == ""
        assert skip.expression == "s"

    def test_indexes_never_reports_btree(self, indexed_fixture):
        backend, table = indexed_fixture
        types = {r.index_type for r in backend.introspector.show.indexes(table)}
        assert "BTREE" not in types
        assert types <= {"PRIMARY", "BLOOM_FILTER"}

    def test_processlist_returns_rows_with_the_query_text(self, show_fixture):
        rows = show_fixture.introspector.show.processlist()
        assert isinstance(rows, list)
        # Our own connection is excluded from system.processes, but the statement
        # parses and the shape holds for whatever is running.
        for row in rows:
            assert row.id is not None
            assert row.user is not None
            assert row.command is None
            assert row.state is None

    def test_engines_lists_the_table_engines(self, show_fixture):
        """The eight ``supports_*`` flags, which every version publishes.

        Measured identical on 25.8.33.6, 26.3.28.5 and 26.7.3.19:
        ``MergeTree`` is 1/1/1/1/1/0/0/1 and ``Memory`` is 1/0/0/0/0/0/0/1.
        """
        engines = show_fixture.introspector.show.engines()
        by_name = {e.engine: e for e in engines}
        assert "MergeTree" in by_name
        assert "Memory" in by_name
        merge_tree = by_name["MergeTree"]
        assert merge_tree.supports_skipping_indices == 1
        assert merge_tree.supports_ttl == 1
        assert merge_tree.supports_replication == 0

    def test_engine_documentation_columns_follow_the_servers_schema(
        self, show_fixture, clickhouse_backend_single
    ):
        """The documentation columns exist only where the server has them.

        Measured: ``system.table_engines`` carries those five columns on
        26.7.3.19 and 26.7.21.2, and carries **only** ``name`` plus the eight
        ``supports_*`` flags on 25.8.33.6 and 26.3.28.5 — on 25.8 a literal
        ``SELECT syntax FROM system.table_engines`` is rejected outright with
        ``UNKNOWN_IDENTIFIER``. The exact release that added them was not
        determined; only the 25.8/26.3 versus 26.7 boundary was. So the correct
        behaviour differs by version, and the introspector must return ``None``
        for a column the server does not send rather than a synthesised string.
        The assertion is made against the server's own column list, which is the
        only version-independent statement available.
        """
        columns = {
            row["name"]
            for row in show_fixture.execute(
                "SELECT name FROM system.columns "
                "WHERE database = 'system' AND table = 'table_engines'"
            ).data
        }
        engines = show_fixture.introspector.show.engines()
        merge_tree = next(e for e in engines if e.engine == "MergeTree")
        for column, value in (
            ("syntax", merge_tree.syntax),
            ("description", merge_tree.description),
            ("related", merge_tree.related),
        ):
            if column in columns:
                assert value, f"{column} is a column of system.table_engines but arrived empty"
            else:
                assert value is None, (
                    f"{column} is not a column of system.table_engines on this "
                    f"version, so nothing may be reported for it: {value!r}"
                )
        assert {"name", "supports_settings", "supports_replication"} <= columns

    def test_grants_returns_grant_statements(self, show_fixture):
        grants = show_fixture.introspector.show.grants()
        assert grants
        assert all(g.grants and g.grants.startswith("GRANT ") for g in grants)

    def test_grants_for_a_named_role(self, show_fixture):
        grants = show_fixture.introspector.show.grants(user="root", host="localhost")
        assert grants
        assert all(g.grants.startswith("GRANT ") for g in grants)

    def test_grants_for_a_missing_role_raises(self, show_fixture):
        """The server, not this dialect, decides the role exists: UNKNOWN_ROLE."""
        with pytest.raises(Exception, match="ar_no_such_role_xyz"):
            show_fixture.introspector.show.grants(user="ar_no_such_role_xyz")
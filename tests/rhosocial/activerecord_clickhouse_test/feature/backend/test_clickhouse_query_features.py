# tests/rhosocial/activerecord_clickhouse_test/feature/backend/test_clickhouse_query_features.py
"""
ClickHouse query feature tests using a live database connection.

Verifies that ClickHouse-native query capabilities work end-to-end:
CTEs, window functions, advanced grouping, set operations, array
functions, ILIKE, JSON functions, and materialized views.
"""

import pytest


@pytest.fixture
def sample_table(clickhouse_backend):
    backend = clickhouse_backend
    backend.execute("DROP TABLE IF EXISTS test_ch_query")
    backend.execute("""
        CREATE TABLE test_ch_query (
            id UInt32,
            grp String,
            val Int32,
            dt DateTime
        ) ENGINE = MergeTree()
        ORDER BY id
    """)
    for i in range(6):
        backend.execute(
            "INSERT INTO test_ch_query VALUES (%s, %s, %s, %s)",
            (i, f"g{i % 2}", i * 10, "2024-01-01 00:00:00"),
        )
    yield "test_ch_query"
    backend.execute("DROP TABLE IF EXISTS test_ch_query")


class TestClickHouseQueryFeatures:
    def test_cte(self, clickhouse_backend, sample_table):
        r = clickhouse_backend.execute(
            "WITH t AS (SELECT grp, sum(val) AS s FROM test_ch_query GROUP BY grp) "
            "SELECT * FROM t ORDER BY grp"
        )
        assert len(r.data) == 2
        assert r.data[0]["grp"] == "g0"
        assert r.data[0]["s"] == 60

    def test_recursive_cte(self, clickhouse_backend, sample_table):
        r = clickhouse_backend.execute(
            "WITH RECURSIVE t AS (SELECT 1 AS n UNION ALL SELECT n + 1 FROM t WHERE n < 5) "
            "SELECT * FROM t ORDER BY n"
        )
        assert [row["n"] for row in r.data] == [1, 2, 3, 4, 5]

    def test_window_functions(self, clickhouse_backend, sample_table):
        r = clickhouse_backend.execute(
            "SELECT id, val, row_number() OVER (ORDER BY val) AS rn "
            "FROM test_ch_query ORDER BY id LIMIT 3"
        )
        assert r.data[0]["rn"] == 1
        assert r.data[2]["rn"] == 3

    def test_window_frame_clause(self, clickhouse_backend, sample_table):
        r = clickhouse_backend.execute(
            "SELECT id, val, sum(val) OVER (ORDER BY id ROWS BETWEEN 1 PRECEDING AND 1 FOLLOWING) AS s "
            "FROM test_ch_query ORDER BY id LIMIT 3"
        )
        # row 0: sum(0+10) = 10; row 1: sum(0+10+20)=30; row 2: sum(10+20+30)=60
        assert r.data[0]["s"] == 10
        assert r.data[1]["s"] == 30

    def test_group_by_rollup(self, clickhouse_backend, sample_table):
        r = clickhouse_backend.execute(
            "SELECT grp, sum(val) FROM test_ch_query GROUP BY grp WITH ROLLUP ORDER BY grp"
        )
        # rollup adds a total row with empty grp
        totals = [row for row in r.data if row["grp"] == ""]
        assert len(totals) == 1
        assert totals[0]["sum(val)"] == 150

    def test_group_by_cube(self, clickhouse_backend, sample_table):
        r = clickhouse_backend.execute(
            "SELECT grp, sum(val) FROM test_ch_query GROUP BY grp WITH CUBE ORDER BY grp"
        )
        assert len(r.data) >= 2

    def test_union_all(self, clickhouse_backend, sample_table):
        # ClickHouse UNION ALL does not guarantee global ORDER BY across branches
        r = clickhouse_backend.execute(
            "SELECT id FROM test_ch_query WHERE id < 2 "
            "UNION ALL SELECT id FROM test_ch_query WHERE id > 4 ORDER BY id"
        )
        assert sorted(row["id"] for row in r.data) == [0, 1, 5]

    def test_union_distinct(self, clickhouse_backend, sample_table):
        # ClickHouse requires explicit ALL/DISTINCT when union_default_mode is empty
        r = clickhouse_backend.execute(
            "SELECT grp FROM test_ch_query WHERE id < 3 "
            "UNION DISTINCT SELECT grp FROM test_ch_query WHERE id > 3 ORDER BY grp"
        )
        assert len(r.data) == 2

    def test_intersect(self, clickhouse_backend, sample_table):
        r = clickhouse_backend.execute(
            "SELECT id FROM test_ch_query WHERE id < 4 "
            "INTERSECT SELECT id FROM test_ch_query WHERE id > 1 ORDER BY id"
        )
        assert [row["id"] for row in r.data] == [2, 3]

    def test_except(self, clickhouse_backend, sample_table):
        r = clickhouse_backend.execute(
            "SELECT id FROM test_ch_query WHERE id < 5 "
            "EXCEPT SELECT id FROM test_ch_query WHERE id < 2 ORDER BY id"
        )
        assert [row["id"] for row in r.data] == [2, 3, 4]

    def test_array_functions(self, clickhouse_backend, sample_table):
        r = clickhouse_backend.execute("SELECT arrayMap(x -> x * 2, [1, 2, 3]) AS a")
        assert r.data[0]["a"] == [2, 4, 6]

        r = clickhouse_backend.execute("SELECT arrayFilter(x -> x > 1, [1, 2, 3]) AS f")
        assert r.data[0]["f"] == [2, 3]

    def test_ilike(self, clickhouse_backend, sample_table):
        r = clickhouse_backend.execute(
            "SELECT id FROM test_ch_query WHERE grp ILIKE 'G0' ORDER BY id"
        )
        assert len(r.data) == 3

    def test_json_functions(self, clickhouse_backend, sample_table):
        r = clickhouse_backend.execute("SELECT JSONExtractString('{\"a\": 1}', 'a') AS v")
        assert r.data[0]["v"] == "1"

    def test_qualify_clause(self, clickhouse_backend, sample_table):
        r = clickhouse_backend.execute(
            "SELECT id, val FROM test_ch_query "
            "QUALIFY row_number() OVER (ORDER BY val) <= 2 ORDER BY id"
        )
        assert len(r.data) == 2

    def test_aggregate_functions(self, clickhouse_backend, sample_table):
        r = clickhouse_backend.execute(
            "SELECT count() AS c, sum(val) AS s, avg(val) AS a, min(val) AS mn, max(val) AS mx "
            "FROM test_ch_query"
        )
        row = r.data[0]
        assert row["c"] == 6
        assert row["s"] == 150
        assert row["mn"] == 0
        assert row["mx"] == 50


class TestClickHouseDDLFeatures:
    def test_materialized_view(self, clickhouse_backend, sample_table):
        backend = clickhouse_backend
        backend.execute("DROP TABLE IF EXISTS test_ch_mv")
        backend.execute("DROP VIEW IF EXISTS test_ch_mv_agg")
        backend.execute("""
            CREATE MATERIALIZED VIEW test_ch_mv_agg
            ENGINE = SummingMergeTree()
            ORDER BY grp
            AS SELECT grp, val AS s FROM test_ch_query
        """)
        # Insert data after MV creation so it is captured by the MV
        backend.execute("INSERT INTO test_ch_query VALUES (%s, %s, %s, %s)", (10, "g0", 100, "2024-01-01 00:00:00"))
        backend.execute("OPTIMIZE TABLE test_ch_mv_agg FINAL")
        r = backend.execute("SELECT grp, sum(s) AS total FROM test_ch_mv_agg WHERE grp = 'g0' GROUP BY grp")
        assert r.data[0]["total"] >= 100
        backend.execute("DROP VIEW IF EXISTS test_ch_mv_agg")

    def test_skip_index(self, clickhouse_backend, sample_table):
        backend = clickhouse_backend
        backend.execute("ALTER TABLE test_ch_query ADD INDEX idx_val val TYPE minmax GRANULARITY 1")
        backend.execute("OPTIMIZE TABLE test_ch_query FINAL")
        r = backend.execute("SELECT id FROM test_ch_query WHERE val = 30")
        assert len(r.data) == 1
        backend.execute("ALTER TABLE test_ch_query DROP INDEX idx_val")

    def test_partition_by_ddl(self, clickhouse_backend):
        backend = clickhouse_backend
        backend.execute("DROP TABLE IF EXISTS test_ch_partitioned")
        backend.execute("""
            CREATE TABLE test_ch_partitioned (
                id UInt32,
                created_at DateTime
            ) ENGINE = MergeTree()
            PARTITION BY toYYYYMM(created_at)
            ORDER BY id
        """)
        backend.execute("INSERT INTO test_ch_partitioned VALUES (%s, %s)", (1, "2024-01-15 00:00:00"))
        backend.execute("INSERT INTO test_ch_partitioned VALUES (%s, %s)", (2, "2024-02-15 00:00:00"))
        r = backend.execute("SELECT count() FROM test_ch_partitioned")
        assert r.data[0]["count()"] == 2
        backend.execute("DROP TABLE test_ch_partitioned")

    def test_ttl_clause(self, clickhouse_backend):
        backend = clickhouse_backend
        backend.execute("DROP TABLE IF EXISTS test_ch_ttl")
        backend.execute("""
            CREATE TABLE test_ch_ttl (
                id UInt32,
                created_at DateTime
            ) ENGINE = MergeTree()
            ORDER BY id
            TTL created_at + INTERVAL 30 DAY
        """)
        # Use a recent timestamp so the row is not expired
        backend.execute("INSERT INTO test_ch_ttl VALUES (%s, %s)", (1, "2026-08-19 00:00:00"))
        assert backend.fetch_one("SELECT id FROM test_ch_ttl")["id"] == 1
        backend.execute("DROP TABLE test_ch_ttl")

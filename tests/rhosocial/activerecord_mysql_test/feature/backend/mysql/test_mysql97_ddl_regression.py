# tests/rhosocial/activerecord_clickhouse_test/feature/backend/clickhouse/test_clickhouse97_ddl_regression.py
"""
ClickHouse 9.7 DDL regression tests.

Tests Primary Key-equivalent / GIPK behavior and DDL execution
on ClickHouse 9.7 to verify dialect-generated DDL remains correct.
"""

import pytest
from rhosocial.activerecord.backend.options import ExecutionOptions
from rhosocial.activerecord.backend.schema import StatementType


def _requires_clickhouse_97(backend):
    if backend.dialect.version < (9, 7, 0):
        pytest.skip("Requires ClickHouse 9.7+")


class TestPrimaryKeyEquivalentDDL:
    """Test Primary Key-equivalent / GIPK DDL behavior on ClickHouse 9.7."""

    def test_unique_not_null_as_pk_equivalent(self, clickhouse_backend):
        backend = clickhouse_backend
        _requires_clickhouse_97(backend)
        ddl_opts = ExecutionOptions(stmt_type=StatementType.DDL)

        backend.execute("DROP TABLE IF EXISTS pk_equiv_test", (), options=ddl_opts)
        backend.execute(
            """
            CREATE TABLE pk_equiv_test (
                code VARCHAR(50) NOT NULL,
                name VARCHAR(100),
                UNIQUE KEY (code)
            )
        """,
            (),
            options=ddl_opts,
        )

        backend.execute("INSERT INTO pk_equiv_test (code, name) VALUES (%s, %s)", ("A001", "Test"))
        result = backend.execute("SELECT * FROM pk_equiv_test WHERE code = %s", ("A001",))
        assert len(result.data) == 1
        assert result.data[0]["name"] == "Test"

        backend.execute("DROP TABLE pk_equiv_test", (), options=ddl_opts)

    def test_create_table_with_invisible_column(self, clickhouse_backend):
        backend = clickhouse_backend
        _requires_clickhouse_97(backend)
        ddl_opts = ExecutionOptions(stmt_type=StatementType.DDL)

        backend.execute("DROP TABLE IF EXISTS invis_col_test", (), options=ddl_opts)
        backend.execute(
            """
            CREATE TABLE invis_col_test (
                id INT AUTO_INCREMENT PRIMARY KEY,
                name VARCHAR(100),
                internal_flag INT INVISIBLE DEFAULT 0
            )
        """,
            (),
            options=ddl_opts,
        )

        backend.execute("INSERT INTO invis_col_test (name) VALUES (%s)", ("hello",))
        result = backend.execute("SELECT * FROM invis_col_test", ())
        assert len(result.data) == 1
        assert "internal_flag" not in result.data[0]

        result2 = backend.execute("SELECT internal_flag FROM invis_col_test", ())
        assert result2.data[0]["internal_flag"] == 0

        backend.execute("DROP TABLE invis_col_test", (), options=ddl_opts)


class TestMySql97FunctionRegression:
    """Regression tests for functions/operators on ClickHouse 9.7."""

    def test_default_function(self, clickhouse_backend):
        backend = clickhouse_backend
        _requires_clickhouse_97(backend)
        ddl_opts = ExecutionOptions(stmt_type=StatementType.DDL)

        backend.execute("DROP TABLE IF EXISTS default_fn_test", (), options=ddl_opts)
        backend.execute(
            """
            CREATE TABLE default_fn_test (
                id INT AUTO_INCREMENT PRIMARY KEY,
                status VARCHAR(20) DEFAULT 'active',
                score INT DEFAULT 100
            )
        """,
            (),
            options=ddl_opts,
        )

        backend.execute("INSERT INTO default_fn_test (id) VALUES (1)", ())
        backend.execute("UPDATE default_fn_test SET status = 'inactive' WHERE id = 1", ())
        backend.execute("UPDATE default_fn_test SET status = DEFAULT(status) WHERE id = 1", ())
        result = backend.execute("SELECT status FROM default_fn_test WHERE id = 1", ())
        assert result.data[0]["status"] == "active"

        backend.execute("DROP TABLE default_fn_test", (), options=ddl_opts)

    def test_date_functions(self, clickhouse_backend):
        backend = clickhouse_backend
        _requires_clickhouse_97(backend)

        result = backend.execute("SELECT TIMEDIFF('12:00:00', '10:30:00') AS diff", ())
        assert result.data[0]["diff"] is not None

        result = backend.execute("SELECT FROM_DAYS(730669) AS d", ())
        assert result.data[0]["d"] is not None

        result = backend.execute("SELECT DAYNAME('2026-05-30') AS dn", ())
        assert result.data[0]["dn"] == "Saturday"

        result = backend.execute("SELECT ADDDATE('2026-05-30', INTERVAL 1 DAY) AS d", ())
        assert "2026-05-31" in str(result.data[0]["d"])

    def test_find_in_set(self, clickhouse_backend):
        backend = clickhouse_backend
        _requires_clickhouse_97(backend)

        result = backend.execute("SELECT FIND_IN_SET('b', 'a,b,c,d') AS pos", ())
        assert result.data[0]["pos"] == 2

        result = backend.execute("SELECT FIND_IN_SET('x', 'a,b,c') AS pos", ())
        assert result.data[0]["pos"] == 0

    def test_in_with_null(self, clickhouse_backend):
        backend = clickhouse_backend
        _requires_clickhouse_97(backend)
        ddl_opts = ExecutionOptions(stmt_type=StatementType.DDL)

        backend.execute("DROP TABLE IF EXISTS in_null_test", (), options=ddl_opts)
        backend.execute(
            """
            CREATE TABLE in_null_test (id INT, val INT)
        """,
            (),
            options=ddl_opts,
        )
        backend.execute("INSERT INTO in_null_test VALUES (1, 10), (2, NULL), (3, 30)", ())

        result = backend.execute("SELECT id FROM in_null_test WHERE val IN (10, NULL) ORDER BY id", ())
        assert len(result.data) == 1
        assert result.data[0]["id"] == 1

        backend.execute("DROP TABLE in_null_test", (), options=ddl_opts)

    def test_decimal_comparison(self, clickhouse_backend):
        backend = clickhouse_backend
        _requires_clickhouse_97(backend)
        ddl_opts = ExecutionOptions(stmt_type=StatementType.DDL)

        backend.execute("DROP TABLE IF EXISTS decimal_test", (), options=ddl_opts)
        backend.execute(
            """
            CREATE TABLE decimal_test (id INT, price DECIMAL(10,2))
        """,
            (),
            options=ddl_opts,
        )
        backend.execute("INSERT INTO decimal_test VALUES (1, 19.99), (2, 20.00), (3, 20.01)", ())

        result = backend.execute("SELECT id FROM decimal_test WHERE price > 19.999 ORDER BY id", ())
        ids = [r["id"] for r in result.data]
        assert ids == [2, 3]

        backend.execute("DROP TABLE decimal_test", (), options=ddl_opts)

    def test_intersect(self, clickhouse_backend):
        backend = clickhouse_backend
        _requires_clickhouse_97(backend)

        result = backend.execute(
            """
            SELECT 1 AS v UNION ALL SELECT 2 UNION ALL SELECT 3
            INTERSECT
            SELECT 2 AS v UNION ALL SELECT 3 UNION ALL SELECT 4
        """,
            (),
        )
        vals = sorted(r["v"] for r in result.data)
        assert 2 in vals
        assert 3 in vals

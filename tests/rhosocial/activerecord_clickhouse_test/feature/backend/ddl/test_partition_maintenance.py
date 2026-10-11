# tests/rhosocial/activerecord_clickhouse_test/feature/backend/ddl/test_partition_maintenance.py
"""
Live-server contract for ClickHouse partition maintenance.

The point of these tests is that the rendered SQL is **executable**. The
MySQL partition surface this file's module replaced (``ADD PARTITION``,
``TRUNCATE PARTITION``, ``REORGANIZE PARTITION``, ``SUBPARTITION BY``,
``PARTITION ... VALUES LESS THAN``) was the same defect class as the
``VECTOR(4)`` case: statements the backend offered that the server rejects.
Each refusal below is therefore checked against the server too, not only
against the dialect.

References:
https://clickhouse.com/docs/engines/table-engines/mergetree-family/custom-partitioning-key
https://clickhouse.com/docs/sql-reference/statements/alter/partition
"""

import pytest

from rhosocial.activerecord.backend.dialect.exceptions import UnsupportedFeatureError
from rhosocial.activerecord.backend.expression.core import Column
from rhosocial.activerecord.backend.expression.statements.ddl_partition import (
    PartitionClause,
    PartitionDefinition,
    PartitionStrategy,
)
from rhosocial.activerecord.backend.impl.clickhouse.expression import (
    ClickHouseAttachPartitionExpression,
    ClickHouseDetachPartitionExpression,
    ClickHouseDropPartitionExpression,
)

TABLE = "ar_clickhouse_partition_events"


@pytest.fixture(scope="module")
def dialect():
    from rhosocial.activerecord.backend.impl.clickhouse.dialect import ClickHouseDialect

    return ClickHouseDialect(version=(26, 7, 3))


@pytest.fixture
def partitioned_backend(clickhouse_backend_single):
    """Backend on a MergeTree table partitioned by ``toYYYYMM(created_at)``.

    ``toYYYYMM`` is how ClickHouse partitions by month: the partition key is an
    arbitrary expression, and the resulting partition ids are ``YYYYMM``
    strings. That is the whole of ClickHouse's partitioning model — there is no
    strategy keyword and no boundary list to declare.
    """
    backend = clickhouse_backend_single
    backend.execute(f"DROP TABLE IF EXISTS {TABLE}")
    backend.execute(
        f"CREATE TABLE {TABLE} (id UInt32, created_at DateTime) "
        "ENGINE = MergeTree PARTITION BY toYYYYMM(created_at) ORDER BY id"
    )
    backend.execute(
        f"INSERT INTO {TABLE} (id, created_at) VALUES (1, '2026-01-05'), (2, '2026-01-06')"
    )
    backend.execute(
        f"INSERT INTO {TABLE} (id, created_at) VALUES (3, '2026-02-05')"
    )
    yield backend
    backend.execute(f"DROP TABLE IF EXISTS {TABLE}")


def _partition_ids(backend):
    return sorted(
        row["partition_id"]
        for row in backend.fetch_all(
            f"SELECT partition_id FROM system.parts "
            f"WHERE table = '{TABLE}' AND active"
        )
    )


def _row_count(backend):
    return backend.fetch_all(f"SELECT count() AS n FROM {TABLE}")[0]["n"]


class TestClickHousePartitionKey:
    """``PARTITION BY <expr>`` is the whole of ClickHouse's declarative surface."""

    def test_partitions_appear_from_inserts_not_from_ddl(self, partitioned_backend):
        assert _partition_ids(partitioned_backend) == ["202601", "202602"]
        assert _row_count(partitioned_backend) == 3

    def test_introspection_comes_from_system_parts(self, partitioned_backend):
        """``supports_partition_metadata_introspection`` is honest about ``system.parts``."""
        assert partitioned_backend.dialect.supports_partition_metadata_introspection() is True
        rows = partitioned_backend.fetch_all(
            f"SELECT DISTINCT partition_id, partition FROM system.parts "
            f"WHERE table = '{TABLE}' AND active ORDER BY partition_id"
        )
        assert [r["partition_id"] for r in rows] == ["202601", "202602"]
        assert [r["partition"] for r in rows] == ["202601", "202602"]


class TestPartitionMaintenanceClausesExecute:
    """Each rendered clause is run against the server."""

    def test_detach_then_attach_round_trips(self, partitioned_backend):
        dialect = partitioned_backend.dialect
        detach_sql, detach_params = ClickHouseDetachPartitionExpression(
            dialect, TABLE, "202601"
        ).to_sql()
        assert detach_sql == f"ALTER TABLE `{TABLE}` DETACH PARTITION ID '202601'"
        partitioned_backend.execute(detach_sql, detach_params)
        assert _partition_ids(partitioned_backend) == ["202602"]
        assert _row_count(partitioned_backend) == 1

        attach_sql, attach_params = ClickHouseAttachPartitionExpression(
            dialect, TABLE, "202601"
        ).to_sql()
        assert attach_sql == f"ALTER TABLE `{TABLE}` ATTACH PARTITION ID '202601'"
        partitioned_backend.execute(attach_sql, attach_params)
        assert _partition_ids(partitioned_backend) == ["202601", "202602"]
        assert _row_count(partitioned_backend) == 3

    def test_drop_removes_the_partition(self, partitioned_backend):
        sql, params = ClickHouseDropPartitionExpression(
            partitioned_backend.dialect, TABLE, "202601"
        ).to_sql()
        partitioned_backend.execute(sql, params)
        assert _partition_ids(partitioned_backend) == ["202602"]
        assert _row_count(partitioned_backend) == 1


class TestMySQLPartitionStatementsAreRejectedByTheServer:
    """The statements the backend used to stub, checked against the server itself.

    This is the ``VECTOR(4)`` argument made concrete: a formatter that renders
    ``ALTER TABLE t TRUNCATE PARTITION p`` is not a fail-fast surface, it is a
    promise the server cannot keep. The error text is what proves the absence —
    ClickHouse answers with the list of clauses it *does* accept.
    """

    def _refused(self, backend, sql):
        with pytest.raises(Exception) as excinfo:
            backend.execute(sql)
        return str(excinfo.value)

    def test_add_partition_is_not_a_clickhouse_clause(self, partitioned_backend):
        message = self._refused(
            partitioned_backend,
            f"ALTER TABLE {TABLE} ADD PARTITION "
            "(PARTITION p2026_03 VALUES LESS THAN ('2026-04-01'))",
        )
        assert "Expected one of: COLUMN, INDEX, STATISTICS, PROJECTION, CONSTRAINT" in message

    def test_truncate_partition_is_not_a_clickhouse_clause(self, partitioned_backend):
        message = self._refused(partitioned_backend, f"ALTER TABLE {TABLE} TRUNCATE PARTITION p")
        # ClickHouse echoes the failing token back, so only the expectation list
        # after "Expected one of:" is evidence. It enumerates every ALTER TABLE
        # clause ClickHouse accepts, and none of them is TRUNCATE PARTITION.
        expected = message.split("Expected one of:", 1)[1]
        assert "DROP PARTITION" in expected
        assert "DETACH PARTITION" in expected
        assert "ATTACH PARTITION" in expected
        assert "DELETE" in expected
        assert "TRUNCATE" not in expected

    def test_subpartition_by_is_not_a_clickhouse_clause(self, partitioned_backend):
        message = self._refused(partitioned_backend, f"ALTER TABLE {TABLE} SUBPARTITION BY HASH(id)")
        assert "SUBPARTITION" in message
        assert "Expected one of" in message

    def test_mysql_partition_ddl_is_not_a_clickhouse_clause(self, partitioned_backend):
        message = self._refused(
            partitioned_backend,
            "CREATE TABLE ar_ch_mysql_part (id UInt32, created_at DateTime) "
            "ENGINE = MergeTree "
            "PARTITION BY RANGE COLUMNS (created_at) "
            "(PARTITION p2026_01 VALUES LESS THAN ('2026-02-01')) "
            "ORDER BY id",
        )
        assert "Syntax error" in message
        assert "COLUMNS" in message

    def test_information_schema_partitions_does_not_exist(self, partitioned_backend):
        message = self._refused(
            partitioned_backend, "SELECT * FROM information_schema.PARTITIONS LIMIT 1"
        )
        assert "information_schema.PARTITIONS" in message

    def test_delete_in_partition_is_the_truncate_substitute(self, partitioned_backend):
        """What a caller reaches for instead of ``TRUNCATE PARTITION``."""
        partitioned_backend.execute(
            f"ALTER TABLE {TABLE} DELETE IN PARTITION ID '202601' WHERE 1"
        )
        assert _row_count(partitioned_backend) == 1


class TestGenericPartitionExpressionsRefuseWithTheClickHouseAlternative:
    """The dialect-level refusal, with its suggestion naming where PARTITION BY is."""

    def test_generic_partition_clause_refuses(self, dialect):
        with pytest.raises(UnsupportedFeatureError) as excinfo:
            PartitionClause(
                dialect, PartitionStrategy.RANGE, [Column(dialect, "created_at")]
            ).to_sql()
        assert "PARTITION BY <expr>" in excinfo.value.suggestion

    def test_inline_partition_definition_refuses(self, dialect):
        with pytest.raises(UnsupportedFeatureError) as excinfo:
            dialect.format_partition_definition(PartitionDefinition(name="p1"))
        assert "PARTITION BY <expr>" in excinfo.value.suggestion
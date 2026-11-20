# tests/rhosocial/activerecord_clickhouse_test/feature/backend/construct/ddl/test_partition_maintenance_helpers.py
"""Offline contract for the backend-level partition maintenance helpers.

Everything here runs without a ClickHouse server: the dialect renders the
clause, a recording backend records what would be executed, and a recording
introspector records what would be read. The live half lives beside this file
in ``test_partition_maintenance.py`` and skips when no server is reachable.

What is pinned here:

* the three management helpers render ClickHouse's own
  ``ALTER TABLE ... DROP / DETACH / ATTACH PARTITION ID`` and hand that
  statement to ``backend.execute`` unchanged;
* a database argument qualifies the table in the catalog slot, the slot
  ClickHouse actually has;
* ``list`` is the introspector's read, so the ids it returns are the ids the
  helpers take, and ``refresh`` drops the cached answer first;
* a successful mutation invalidates the table's cached introspection, because
  the next ``list`` must not describe the partition the server just removed;
* a verb ClickHouse does not have raises ``UnsupportedFeatureError`` rather
  than becoming an ``AttributeError`` that reads like a typo;
* subpartitioning stays undeclared, and the three switches ClickHouse does
  answer stay ``True``.
"""

from typing import List, Optional, Tuple

import pytest

from rhosocial.activerecord.backend.dialect.exceptions import UnsupportedFeatureError
from rhosocial.activerecord.backend.introspection.types import IntrospectionScope
from rhosocial.activerecord.backend.result import QueryResult

from rhosocial.activerecord.backend.impl.clickhouse.backend.backend import ClickHouseBackend
from rhosocial.activerecord.backend.impl.clickhouse.config import ClickHouseConnectionConfig
from rhosocial.activerecord.backend.impl.clickhouse.dialect import ClickHouseDialect
from rhosocial.activerecord.backend.impl.clickhouse.introspection.types import (
    ClickHousePartitionInfo,
)
from rhosocial.activerecord.backend.impl.clickhouse.mixins import (
    ClickHousePartitionMaintenanceMixin,
)
from rhosocial.activerecord.backend.impl.clickhouse.partition_maintenance import (
    ClickHousePartitionMaintenance,
    MANAGEMENT_VERBS,
)

TABLE = "ar_partition_helpers"
DATABASE = "analytics"


class _RecordingIntrospector:
    """Stands in for the introspector: records reads and invalidations."""

    def __init__(self) -> None:
        self.partitions: List[ClickHousePartitionInfo] = []
        self.list_calls: List[Tuple[str, Optional[str]]] = []
        self.invalidated: List[Tuple[Optional[IntrospectionScope], Optional[str]]] = []

    def list_partitions(
        self, table_name: str, database: Optional[str] = None
    ) -> List[ClickHousePartitionInfo]:
        self.list_calls.append((table_name, database))
        return list(self.partitions)

    def invalidate_cache(
        self,
        scope: Optional[IntrospectionScope] = None,
        name: Optional[str] = None,
    ) -> None:
        self.invalidated.append((scope, name))


class _RecordingBackend:
    """Stands in for ``ClickHouseBackend``: records the SQL it would run."""

    def __init__(self, dialect: ClickHouseDialect) -> None:
        self.dialect = dialect
        self.introspector = _RecordingIntrospector()
        self.calls: List[Tuple[str, Optional[tuple]]] = []
        self.result = QueryResult(affected_rows=11)

    def execute(self, sql: str, params: Optional[tuple] = None) -> QueryResult:
        self.calls.append((sql, params))
        return self.result


@pytest.fixture(scope="module")
def dialect() -> ClickHouseDialect:
    return ClickHouseDialect(version=(26, 7, 3))


@pytest.fixture
def backend(dialect: ClickHouseDialect) -> _RecordingBackend:
    return _RecordingBackend(dialect)


@pytest.fixture
def service(backend: _RecordingBackend) -> ClickHousePartitionMaintenance:
    return ClickHousePartitionMaintenance(backend)


def _partition(partition_id: str, row_count: int = 1) -> ClickHousePartitionInfo:
    return ClickHousePartitionInfo(
        partition_id=partition_id,
        table_name=TABLE,
        database=DATABASE,
        engine="MergeTree",
        partition=partition_id,
        row_count=row_count,
    )


class TestManagementHelpers:
    """Each helper renders its expression and executes that statement."""

    @pytest.mark.parametrize(
        "method, verb",
        [("drop", "DROP"), ("detach", "DETACH"), ("attach", "ATTACH")],
    )
    def test_helper_renders_the_clickhouse_clause(self, service, backend, method, verb):
        result = getattr(service, method)(TABLE, "202601")

        assert backend.calls == [(f"ALTER TABLE `{TABLE}` {verb} PARTITION ID '202601'", ())]
        assert result is backend.result
        assert backend.introspector.invalidated == [(IntrospectionScope.TABLE, TABLE)]

    def test_database_argument_fills_the_catalog_slot(self, service, backend):
        service.drop(TABLE, "202601", database=DATABASE)

        assert backend.calls == [
            (
                f"ALTER TABLE `{DATABASE}`.`{TABLE}` DROP PARTITION ID '202601'",
                (),
            )
        ]

    def test_table_without_a_database_is_not_qualified(self, service, backend):
        service.detach(TABLE, "202601")

        assert backend.calls[0][0] == (f"ALTER TABLE `{TABLE}` DETACH PARTITION ID '202601'")
        assert backend.calls[0][1] == ()

    def test_mutations_execute_without_bind_parameters(self, service, backend):
        """The partition id is DDL-selected, not a column value, so it inlines."""
        service.attach(TABLE, "202601")

        sql, params = backend.calls[0]
        assert params == ()
        assert "'202601'" in sql


class TestList:
    """``list`` is the introspector's read, surfaced on the service."""

    def test_list_returns_the_introspector_rows(self, service, backend):
        rows = [_partition("202601", 2), _partition("202602", 1)]
        backend.introspector.partitions = rows

        assert service.list(TABLE) == rows
        assert backend.introspector.list_calls == [(TABLE, None)]
        assert backend.calls == []

    def test_list_passes_the_database_through(self, service, backend):
        service.list(TABLE, database=DATABASE)

        assert backend.introspector.list_calls == [(TABLE, DATABASE)]

    def test_refresh_invalidates_before_reading(self, service, backend):
        backend.introspector.partitions = [_partition("202602")]

        service.list(TABLE, refresh=True)

        assert backend.introspector.invalidated == [(IntrospectionScope.TABLE, TABLE)]
        assert backend.introspector.list_calls == [(TABLE, None)]

    def test_plain_list_does_not_invalidate(self, service, backend):
        service.list(TABLE)

        assert backend.introspector.invalidated == []


class TestExecuteDispatch:
    """The verb dispatcher maps names to the helpers, and refuses the rest."""

    @pytest.mark.parametrize(
        "verb, method",
        [("drop", "drop"), ("DETACH", "detach"), (" attach ", "attach")],
    )
    def test_known_verb_dispatches(self, service, backend, verb, method):
        result = service.execute(verb, TABLE, "202601")

        assert backend.calls == [
            (
                f"ALTER TABLE `{TABLE}` {method.upper()} PARTITION ID '202601'",
                (),
            )
        ]
        assert result is backend.result

    def test_database_argument_is_forwarded(self, service, backend):
        service.execute("drop", TABLE, "202601", database=DATABASE)

        assert backend.calls[0][0] == (
            f"ALTER TABLE `{DATABASE}`.`{TABLE}` DROP PARTITION ID '202601'"
        )

    def test_a_partition_id_is_required(self, service, backend):
        with pytest.raises(ValueError) as excinfo:
            service.execute("drop", TABLE)

        assert "partition_id" in str(excinfo.value)
        assert backend.calls == []

    def test_a_non_string_partition_id_is_refused(self, service, backend):
        with pytest.raises(TypeError):
            service.execute("drop", TABLE, 202601)

        assert backend.calls == []

    def test_a_verb_must_be_a_non_empty_string(self, service, backend):
        with pytest.raises(ValueError):
            service.execute("", TABLE, "202601")

        assert backend.calls == []

    @pytest.mark.parametrize(
        "verb",
        ["add", "truncate", "reorganize", "exchange", "coalesce", "subpartition"],
    )
    def test_verbs_clickhouse_lacks_raise_the_unsupported_error(self, service, backend, verb):
        with pytest.raises(UnsupportedFeatureError) as excinfo:
            service.execute(verb, TABLE, "202601")

        assert excinfo.value.feature_name == f"{verb.upper()} PARTITION"
        assert "DROP / DETACH / ATTACH" in excinfo.value.suggestion
        assert backend.calls == []


class TestInputValidation:
    """Invalid input dies before a statement reaches the backend."""

    @pytest.mark.parametrize("table", ["", "   ", None, 3])
    def test_a_table_must_be_a_non_empty_string(self, service, backend, table):
        with pytest.raises(ValueError):
            service.drop(table, "202601")

        assert backend.calls == []

    @pytest.mark.parametrize("table", ["", "   ", None, 3])
    def test_list_refuses_an_empty_table(self, service, backend, table):
        with pytest.raises(ValueError):
            service.list(table)

        assert backend.introspector.list_calls == []

    @pytest.mark.parametrize("partition_id", [None, 202601])
    def test_a_partition_id_must_be_a_string(self, service, backend, partition_id):
        with pytest.raises(TypeError):
            service.detach(TABLE, partition_id)

        assert backend.calls == []

    @pytest.mark.parametrize("partition_id", ["", "   "])
    def test_a_partition_id_must_not_be_blank(self, service, backend, partition_id):
        with pytest.raises(ValueError):
            service.attach(TABLE, partition_id)

        assert backend.calls == []


class TestCapabilityBoundary:
    """ClickHouse partitions one level; the three management switches are real."""

    def test_subpartitioning_stays_undeclared(self, dialect):
        assert dialect.supports_subpartitioning() is False

    def test_the_mysql_strategies_stay_undeclared(self, dialect):
        assert dialect.supports_range_table_partitioning() is False
        assert dialect.supports_list_table_partitioning() is False
        assert dialect.supports_hash_table_partitioning() is False

    def test_the_three_management_switches_are_true(self, dialect):
        assert dialect.supports_drop_partition() is True
        assert dialect.supports_detach_partition() is True
        assert dialect.supports_attach_partition() is True

    def test_the_service_names_exactly_the_three_verbs(self):
        assert MANAGEMENT_VERBS == ("drop", "detach", "attach")
        assert ClickHousePartitionMaintenance.verbs == MANAGEMENT_VERBS


class TestBackendEntryPoint:
    """The service hangs off the backend without opening a connection."""

    def test_backend_exposes_the_service_and_reuses_it(self):
        backend = ClickHouseBackend(
            connection_config=ClickHouseConnectionConfig(
                host="127.0.0.1",
                port=8123,
                database="test_db",
                username="root",
                password="",
            )
        )
        try:
            assert isinstance(backend, ClickHousePartitionMaintenanceMixin)

            service = backend.partition_maintenance

            assert isinstance(service, ClickHousePartitionMaintenance)
            assert service.backend is backend
            assert backend.partition_maintenance is service
            assert service.dialect is backend.dialect
            # Constructing the service (and its dialect) contacts nothing.
            assert backend._connection is None
        finally:
            backend.disconnect()

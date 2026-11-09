# tests/rhosocial/activerecord_clickhouse_test/feature/backend/clickhouse/test_partition_syntax_matrix.py
"""Offline matrix over the ClickHouse partition-syntax families.

Each test here is fed by ``partition_syntax_case`` from
``partition_syntax_fixtures.py`` and needs no ClickHouse server: the dialect
renders the SQL, a stub backend records what would be executed, and a real
``ClickHouseIntrospector`` with a stub executor records what would be read.
The live counterparts -- where the rendered clauses are actually run -- live
in ``tests/.../backend/ddl/test_partition_maintenance.py`` and
``tests/.../backend/introspection/test_introspection_partitions.py``.

What this matrix pins, family by family:

* ``PARTITION BY`` is an arbitrary key expression (a column expression or a
  ``tuple(...)``), rendered once, with no strategy keyword and no boundary
  list;
* ClickHouse partitions one level, and the dialect answers
  ``supports_subpartitioning()`` with ``False`` instead of only omitting the
  syntax;
* the three management verbs are ``DROP`` / ``DETACH`` / ``ATTACH ... PARTITION
  ID``, and the six MySQL verbs have no spelling at all;
* ``list_partitions`` aggregates active ``system.parts`` rows into
  ``ClickHousePartitionInfo``;
* a successful mutation invalidates the table's cached listing and a failed
  one leaves it alone;
* ``list(refresh=True)`` reads past the cache, ``list(refresh=False)`` does
  not;
* the service declares exactly ``drop`` / ``detach`` / ``attach``.
"""

from types import SimpleNamespace
from typing import Any, Dict, List, Optional, Tuple

import pytest

from rhosocial.activerecord.backend.dialect.exceptions import UnsupportedFeatureError
from rhosocial.activerecord.backend.impl.clickhouse.dialect import ClickHouseDialect
from rhosocial.activerecord.backend.impl.clickhouse.introspection import (
    ClickHouseIntrospector,
)
from rhosocial.activerecord.backend.impl.clickhouse.partition_maintenance import (
    MANAGEMENT_VERBS,
    ClickHousePartitionMaintenance,
)
from rhosocial.activerecord.backend.result import QueryResult

from partition_syntax_fixtures import (
    ASPECTS,
    CASES,
    DATABASE,
    PARTITION_ID,
    TABLE,
    PartitionSyntaxCase,
    partition_syntax_case,  # noqa: F401 - the fixture pytest resolves by name
)


class _RowsExecutor:
    """The introspector's executor: records questions, returns case rows.

    The rows are copied on each read, so a cached answer and a fresh read
    cannot share the dictionaries a test mutates between the two.
    """

    def __init__(self, rows: Optional[List[Dict[str, Any]]] = None) -> None:
        self.rows = [dict(row) for row in rows or []]
        self.questions: List[Tuple[str, tuple]] = []

    def execute(self, sql: str, params: tuple = ()) -> List[Dict[str, Any]]:
        self.questions.append((sql, params))
        return [dict(row) for row in self.rows]


class _MatrixBackend:
    """A backend stub: a real introspector, a recording executor.

    The introspector is the production one, so the cache being asserted is
    the cache a caller gets. Only the connection is stood in for -- and
    ``fail_with`` makes that stand-in refuse, which is how the failure half
    of the invalidation case is exercised without a server.
    """

    def __init__(
        self,
        dialect: ClickHouseDialect,
        rows: Optional[List[Dict[str, Any]]] = None,
    ) -> None:
        self.dialect = dialect
        self.config = SimpleNamespace(database=DATABASE)
        self.executor = _RowsExecutor(rows)
        self.introspector = ClickHouseIntrospector(self, self.executor)
        self.calls: List[Tuple[str, tuple]] = []
        self.result = QueryResult(affected_rows=1)
        self.fail_with: Optional[Exception] = None

    def execute(self, sql: str, params: tuple = ()) -> QueryResult:
        if self.fail_with is not None:
            raise self.fail_with
        self.calls.append((sql, params))
        return self.result


@pytest.fixture(scope="module")
def dialect() -> ClickHouseDialect:
    """The scenario server's version shape (26.7.3)."""
    return ClickHouseDialect(version=(26, 7, 3))


def _cases_for(aspect: str) -> List[PartitionSyntaxCase]:
    return [case for case in CASES if case.aspect == aspect]


def _ids(case: PartitionSyntaxCase) -> str:
    return case.name


def _render(case: PartitionSyntaxCase, dialect: ClickHouseDialect) -> str:
    """Render the case's SQL, whichever shape its builder returned."""
    built = case.builder(dialect)
    if isinstance(built, str):
        return built
    sql, params = built.to_sql()
    assert params == ()
    return sql


def _assert_fragments(case: PartitionSyntaxCase, sql: str) -> None:
    for fragment in case.expected_fragments:
        assert fragment in sql
    for fragment in case.forbidden_fragments:
        assert fragment not in sql


def _service(backend: _MatrixBackend) -> ClickHousePartitionMaintenance:
    return ClickHousePartitionMaintenance(backend)


# --------------------------------------------------------------------------- #
# The matrix itself
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize("partition_syntax_case", CASES, ids=_ids)
def test_every_case_is_well_formed(
    partition_syntax_case: PartitionSyntaxCase,  # noqa: F811 - fixture parameter
) -> None:
    """Each row names a family, its invariants and no live hook."""
    case = partition_syntax_case
    assert case.name == case.name.strip()
    assert case.description.strip()
    assert case.aspect in ASPECTS
    assert case.builder is not None
    assert set(case.expected_fragments).isdisjoint(case.forbidden_fragments)
    for fragment in case.expected_fragments + case.forbidden_fragments:
        assert isinstance(fragment, str)
        assert fragment.strip()
    # The matrix is offline by design; live hooks are for a future live run.
    assert case.live_setup is None
    assert case.live_check is None


def test_case_names_are_unique() -> None:
    names = [case.name for case in CASES]
    assert len(names) == len(set(names))


# --------------------------------------------------------------------------- #
# PARTITION BY: one clause, arbitrary key expression, one level
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    "partition_syntax_case", _cases_for("partition_by"), indirect=True, ids=_ids
)
def test_partition_by_rendering(
    partition_syntax_case: PartitionSyntaxCase,  # noqa: F811 - fixture parameter
    dialect: ClickHouseDialect,
) -> None:
    sql = _render(partition_syntax_case, dialect)

    _assert_fragments(partition_syntax_case, sql)
    assert sql.count("PARTITION BY") == 1
    assert "ENGINE = MergeTree" in sql
    assert "ORDER BY `id`" in sql


@pytest.mark.parametrize(
    "partition_syntax_case", _cases_for("single_level"), indirect=True, ids=_ids
)
def test_single_level_invariants(
    partition_syntax_case: PartitionSyntaxCase,  # noqa: F811 - fixture parameter
    dialect: ClickHouseDialect,
) -> None:
    sql = _render(partition_syntax_case, dialect)

    _assert_fragments(partition_syntax_case, sql)
    assert sql.count("PARTITION BY") == 1
    # One level is a capability answer, not just an absent keyword.
    assert dialect.supports_subpartitioning() is False
    assert dialect.supports_range_table_partitioning() is False
    assert dialect.supports_list_table_partitioning() is False
    assert dialect.supports_hash_table_partitioning() is False


# --------------------------------------------------------------------------- #
# The three management verbs ClickHouse has
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    "partition_syntax_case", _cases_for("verb"), indirect=True, ids=_ids
)
def test_supported_verb_rendering(
    partition_syntax_case: PartitionSyntaxCase,  # noqa: F811 - fixture parameter
    dialect: ClickHouseDialect,
) -> None:
    expression = partition_syntax_case.builder(dialect)
    sql, params = expression.to_sql()

    assert params == ()
    _assert_fragments(partition_syntax_case, sql)
    assert sql.startswith(f"ALTER TABLE `{TABLE}`")
    assert sql.count("PARTITION") == 1
    verb = type(expression).verb
    assert getattr(dialect, f"supports_{verb.lower()}_partition")() is True
    assert f"{verb} PARTITION ID '{PARTITION_ID}'" in sql


@pytest.mark.parametrize(
    "partition_syntax_case", _cases_for("refusal"), indirect=True, ids=_ids
)
def test_unsupported_verbs_raise(
    partition_syntax_case: PartitionSyntaxCase,  # noqa: F811 - fixture parameter
    dialect: ClickHouseDialect,
) -> None:
    backend = _MatrixBackend(dialect)
    service = _service(backend)
    verbs = partition_syntax_case.builder(dialect)

    assert len(verbs) == 6
    for verb in verbs:
        with pytest.raises(UnsupportedFeatureError) as excinfo:
            service.execute(verb, TABLE, PARTITION_ID)
        assert excinfo.value.feature_name == f"{verb.upper()} PARTITION"
        for fragment in partition_syntax_case.expected_fragments:
            assert fragment in excinfo.value.suggestion
    # Nothing was rendered, let alone sent: the refusal happens first.
    assert backend.calls == []


# --------------------------------------------------------------------------- #
# system.parts -> ClickHousePartitionInfo
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    "partition_syntax_case", _cases_for("introspection"), indirect=True, ids=_ids
)
def test_introspection_result_mapping(
    partition_syntax_case: PartitionSyntaxCase,  # noqa: F811 - fixture parameter
    dialect: ClickHouseDialect,
) -> None:
    rows = partition_syntax_case.builder(dialect)
    backend = _MatrixBackend(dialect, rows)

    partitions = backend.introspector.list_partitions(TABLE)

    assert [item.partition_id for item in partitions] == ["202601", "202602"]
    observed = {
        item.partition_id: (
            item.row_count,
            item.bytes_on_disk,
            item.active_part_count,
        )
        for item in partitions
    }
    assert observed == {"202601": (3, 300, 2), "202602": (1, 100, 1)}
    for item in partitions:
        assert item.table_name == TABLE
        assert item.database == DATABASE
        assert item.engine == "MergeTree"
        assert item.partition == item.partition_id
        assert item.min_modification_time == item.max_modification_time

    assert len(backend.executor.questions) == 1
    sql, params = backend.executor.questions[0]
    _assert_fragments(partition_syntax_case, sql)
    assert params == (DATABASE, TABLE, 1)


# --------------------------------------------------------------------------- #
# Cache behaviour, as far as it can be shown without a server
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    "partition_syntax_case", _cases_for("cache"), indirect=True, ids=_ids
)
def test_cache_invalidation_follows_success(
    partition_syntax_case: PartitionSyntaxCase,  # noqa: F811 - fixture parameter
    dialect: ClickHouseDialect,
) -> None:
    payload = partition_syntax_case.builder(dialect)
    backend = _MatrixBackend(dialect, payload["initial"])
    service = _service(backend)

    # Warm the cached listing: one read, one cache entry.
    assert [item.partition_id for item in service.list(TABLE)] == ["202601", "202602"]
    assert len(backend.introspector.cache) == 1
    questions = len(backend.executor.questions)

    # A failure leaves the server unchanged, so the cached answer stays.
    backend.fail_with = RuntimeError("server rejected the partition drop")
    with pytest.raises(RuntimeError):
        service.drop(TABLE, PARTITION_ID)
    assert backend.calls == []
    assert len(backend.introspector.cache) == 1
    assert len(backend.executor.questions) == questions
    assert [item.partition_id for item in service.list(TABLE)] == ["202601", "202602"]

    # A success invalidates it, and the next read sees the server's new state.
    backend.fail_with = None
    backend.executor.rows = [dict(row) for row in payload["changed"]]
    service.drop(TABLE, PARTITION_ID)
    assert len(backend.introspector.cache) == 0
    for fragment in partition_syntax_case.expected_fragments:
        assert fragment in backend.calls[0][0]
    assert [item.partition_id for item in service.list(TABLE)] == ["202602"]
    assert len(backend.executor.questions) == questions + 1


@pytest.mark.parametrize(
    "partition_syntax_case", _cases_for("maintenance_list"), indirect=True, ids=_ids
)
def test_list_refresh_re_reads(
    partition_syntax_case: PartitionSyntaxCase,  # noqa: F811 - fixture parameter
    dialect: ClickHouseDialect,
) -> None:
    payload = partition_syntax_case.builder(dialect)
    backend = _MatrixBackend(dialect, payload["initial"])
    service = _service(backend)

    first = service.list(TABLE)
    assert [item.partition_id for item in first] == ["202601", "202602"]
    assert len(backend.executor.questions) == 1

    # An external change (a raw ALTER) leaves the cached listing stale.
    backend.executor.rows = [dict(row) for row in payload["changed"]]
    cached = service.list(TABLE)
    assert cached is first
    assert [item.partition_id for item in cached] == ["202601", "202602"]
    assert len(backend.executor.questions) == 1

    # refresh=True is the caller saying "read the server again".
    refreshed = service.list(TABLE, refresh=True)
    assert refreshed is not first
    assert [item.partition_id for item in refreshed] == ["202602"]
    assert len(backend.executor.questions) == 2
    assert len(backend.introspector.cache) == 1


@pytest.mark.parametrize(
    "partition_syntax_case", _cases_for("maintenance_verbs"), indirect=True, ids=_ids
)
def test_maintenance_verbs_are_the_declared_triple(
    partition_syntax_case: PartitionSyntaxCase,  # noqa: F811 - fixture parameter
    dialect: ClickHouseDialect,
) -> None:
    expected = partition_syntax_case.expected_fragments

    assert expected == ("drop", "detach", "attach")
    assert MANAGEMENT_VERBS == expected
    assert ClickHousePartitionMaintenance.verbs == expected
    # list is a read; it is not a fourth verb execute could be asked to run.
    assert hasattr(ClickHousePartitionMaintenance, "list")
    assert hasattr(ClickHousePartitionMaintenance, "execute")
    for verb in expected:
        assert hasattr(ClickHousePartitionMaintenance, verb)
        assert getattr(dialect, f"supports_{verb}_partition")() is True

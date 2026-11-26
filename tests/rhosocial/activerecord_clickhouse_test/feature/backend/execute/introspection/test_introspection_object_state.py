# tests/rhosocial/activerecord_clickhouse_test/feature/backend/execute/introspection/test_introspection_object_state.py
"""The neutral object-state methods against a live ClickHouse server.

What is pinned here:

* ``list_index_states`` answers from ``system.data_skipping_indices`` with the
  engine's method name and skip expression; ``creation`` is asserted only on the
  release lines that answer it (26.3 and later -- 25.8 refuses the column);
* ``list_constraint_states`` answers from ``system.constraints`` with the
  declared ``CHECK`` constraint and its expression where that catalogue exists
  (26.7 and later), and refuses by name on the lines that do not have it (25.8
  and 26.3);
* ``list_schemas`` answers the database names the server exposes;
* ``list_derived_objects`` finds a projection and a materialized view that read
  from the table;
* ``item_exists`` answers a real ``True``/``False`` for the object classes this
  engine has, and ``False`` for the classes it has none of;
* ``get_table_state`` reports an object's kind from its engine, so a view is not
  collapsed into a regular table.

The catalogue surface differs by release line, so the expectations come from
``impl.clickhouse.catalogue`` -- the same table the SQL formatters use. The live
tests skip themselves when no server is reachable, through the same scenario
support the rest of the backend tests use.
"""

import socket

import pytest
from rhosocial.activerecord.backend.introspection import IntrospectionNotSupportedError
from rhosocial.activerecord.backend.introspection.types import ItemKind

from rhosocial.activerecord.backend.impl.clickhouse.catalogue import (
    capabilities_for_version,
)

TABLE = "test_intro_state_ch"
VIEW = "test_intro_state_mv_ch"


@pytest.fixture(scope="module")
def live_server():
    """Skip the whole live group when the configured server is not there."""
    from support.clickhouse import get_enabled_scenarios

    scenarios = get_enabled_scenarios()
    if not scenarios:
        pytest.skip("No ClickHouse scenarios configured")
    config = next(iter(scenarios.values()))
    try:
        with socket.create_connection((config["host"], int(config["port"])), timeout=2):
            pass
    except OSError as error:
        pytest.skip(f"ClickHouse unreachable at {config['host']}:{config['port']}: {error}")
    return config


@pytest.fixture
def state_backend(live_server, clickhouse_backend_single):
    """A MergeTree table with a skipping index, a CHECK constraint and a projection."""
    backend = clickhouse_backend_single
    backend.execute(f"DROP VIEW IF EXISTS {VIEW}")
    backend.execute(f"DROP TABLE IF EXISTS {TABLE}")
    backend.execute(f"""
        CREATE TABLE {TABLE} (
            id UInt32,
            s String,
            CONSTRAINT c1 CHECK id > 0,
            INDEX idx_s s TYPE bloom_filter GRANULARITY 4,
            PROJECTION p1 (SELECT id ORDER BY id)
        ) ENGINE = MergeTree()
        ORDER BY id
        """)
    backend.execute(
        f"CREATE MATERIALIZED VIEW {VIEW} ENGINE = MergeTree() ORDER BY id "
        f"AS SELECT id FROM {TABLE}"
    )
    backend.introspector.clear_cache()
    yield backend
    backend.execute(f"DROP VIEW IF EXISTS {VIEW}")
    backend.execute(f"DROP TABLE IF EXISTS {TABLE}")


class TestIndexStates:
    def test_the_skipping_index_carries_its_method_and_expression(self, state_backend):
        capabilities = capabilities_for_version(state_backend.get_server_version())
        states = state_backend.introspector.list_index_states(TABLE)

        assert [state.name for state in states] == ["idx_s"]
        state = states[0]
        assert state.table == TABLE
        assert state.schema == state_backend.config.database
        assert state.method == "bloom_filter"
        assert state.predicate == "s"
        assert state.unique is False
        assert state.visible is True
        assert state.usable is True
        assert state.backs_constraint is None
        assert state.raw["granularity"] == 4
        if "creation" in capabilities.skipping_index_columns:
            assert state.raw["creation"] == "Explicit"
        else:
            # 25.8 has no ``creation`` column; the statement did not name it, so
            # there is no value in ``raw`` and none is invented.
            assert "creation" not in state.raw


class TestConstraintStates:
    def test_the_check_constraint_is_reported_with_its_expression(self, state_backend):
        capabilities = capabilities_for_version(state_backend.get_server_version())
        if not capabilities.has_constraint_catalogue():
            # 25.8 and 26.3 have no ``system.constraints``. The method must
            # refuse by naming the catalogue, not answer an empty list: the
            # table below *does* declare a constraint, so [] would be a lie.
            with pytest.raises(IntrospectionNotSupportedError) as caught:
                state_backend.introspector.list_constraint_states(TABLE)
            assert "system.constraints" in str(caught.value)
            return

        states = state_backend.introspector.list_constraint_states(TABLE)

        assert [state.name for state in states] == ["c1"]
        state = states[0]
        assert state.kind == "CHECK"
        assert state.table == TABLE
        assert state.validated is True
        assert state.enforced is True
        assert state.deferred is False
        assert state.disabled is False
        assert state.raw["expression"] == "id > 0"


class TestSchemas:
    def test_the_answer_lists_the_exposed_databases(self, state_backend):
        names = state_backend.introspector.list_schemas()

        assert state_backend.config.database in names
        assert "system" in names
        assert names == sorted(names)


class TestDerivedObjects:
    def test_projection_and_materialized_view_belong_to_the_table(self, state_backend):
        derived = state_backend.introspector.list_derived_objects(TABLE)

        kinds = sorted((item.kind, item.name) for item in derived)
        assert kinds == [("materialized_view", VIEW), ("projection", "p1")]
        by_name = {item.name: item for item in derived}
        assert by_name["p1"].owned_by == TABLE
        assert by_name["p1"].raw["query"] == "SELECT id ORDER BY id"
        assert by_name[VIEW].owned_by == TABLE
        assert (
            by_name[VIEW].raw["as_select"]
            == f"SELECT id FROM {state_backend.config.database}.{TABLE}"
        )


class TestItemExists:
    def test_objects_the_engine_has(self, state_backend):
        introspector = state_backend.introspector
        database = state_backend.config.database

        assert introspector.item_exists(ItemKind.SCHEMA, database) is True
        assert introspector.item_exists(ItemKind.TABLE, TABLE, schema=database) is True
        assert introspector.item_exists(ItemKind.FUNCTION, "count") is True

    def test_objects_the_engine_does_not_have(self, state_backend):
        introspector = state_backend.introspector
        database = state_backend.config.database

        assert (
            introspector.item_exists(ItemKind.TABLE, "no_such_table_xyz", schema=database) is False
        )
        assert introspector.item_exists(ItemKind.FUNCTION, "no_such_function_xyz") is False
        assert introspector.item_exists(ItemKind.SCHEMA, "no_such_database_xyz") is False
        # ClickHouse has no sequences, extensions or tablespaces at all.
        assert introspector.item_exists(ItemKind.SEQUENCE, "orders_seq") is False
        assert introspector.item_exists(ItemKind.EXTENSION, "pgcrypto") is False
        assert introspector.item_exists(ItemKind.TABLESPACE, "users") is False


class TestTableKind:
    def test_a_view_is_not_reported_as_a_regular_table(self, state_backend):
        state = state_backend.introspector.get_table_state(VIEW)

        assert state.kind == "materialized_view"
        assert state.storage.engine == "MaterializedView"
        assert state.partitioning is not None
        assert state.partitioning.scheme is None

# tests/rhosocial/activerecord_clickhouse_test/feature/backend/construct/expression/test_artifact_registry.py
"""ClickHouse publishes its own artifact registry, composed with core's.

Core no longer keeps a process-global table holding every bundled backend's
kinds. Each owner publishes one frozen table:

* core's is :func:`core_registry`;
* ClickHouse's is :func:`backend_registry`, assembled with
  ``registry_for_packages(<this backend's expression package>, base=core_registry())``;
* the dialect answers with it, so ``deserialize(..., dialect)`` resolves the
  kind through the backend the caller supplied.

These tests state the ownership boundary directly: a ClickHouse kind resolves
through ``ClickHouseDialect.artifact_registry()``, another backend's kind is
refused by name, and the published table refuses mutation. The partition
maintenance nodes this backend added most recently are the ones checked by
name, because they are the kinds a reader earns by composing this backend
rather than by reading core alone.
"""

import pytest
from rhosocial.activerecord.backend.expression.core import Column, Literal
from rhosocial.activerecord.backend.expression.registry import (
    RegistryError,
    RegistryReason,
)
from rhosocial.activerecord.backend.expression.serialization import (
    ExpressionDeserializationError,
    core_registry,
    deserialize,
    serialize,
)
from rhosocial.activerecord.backend.expression.types import IntegerType
from rhosocial.activerecord.backend.impl.dummy.dialect import DummyDialect
from rhosocial.activerecord.backend.impl.dummy.expression import _DummyTypeDefinition

from rhosocial.activerecord.backend.impl.clickhouse.dialect import ClickHouseDialect
from rhosocial.activerecord.backend.impl.clickhouse.expression.partition import (
    ClickHouseClearInPartitionStatement,
    ClickHouseFreezePartitionStatement,
    ClickHouseMovePartitionStatement,
    ClickHouseOptimizePartitionStatement,
    ClickHouseReplacePartitionStatement,
    ClickHouseUnfreezePartitionStatement,
)
from rhosocial.activerecord.backend.impl.clickhouse.registry import backend_registry

#: Every partition-maintenance node this backend recently added. Each has to
#: resolve through ClickHouse's own table, or an artifact carrying it is
#: readable only by code that mutated a global -- which no longer exists.
PARTITION_NODES = (
    ClickHouseReplacePartitionStatement,
    ClickHouseMovePartitionStatement,
    ClickHouseFreezePartitionStatement,
    ClickHouseUnfreezePartitionStatement,
    ClickHouseClearInPartitionStatement,
    ClickHouseOptimizePartitionStatement,
)


def _dialect() -> ClickHouseDialect:
    """A dialect with a version bound, like the matrix fixture uses."""
    dialect = ClickHouseDialect()
    dialect.version = (24, 3, 1, 0)
    return dialect


@pytest.fixture
def clickhouse_matrix_dialect():
    """The bound dialect the matrix and the registry tests share."""
    return _dialect()


def test_the_dialect_answers_with_the_clickhouse_registry():
    """The dialect exposes ClickHouse's composed table, not core's and not a copy."""
    registry = _dialect().artifact_registry()

    assert registry is backend_registry()
    assert registry.is_frozen
    assert registry.node_kinds() != core_registry().node_kinds()


@pytest.mark.parametrize("node", PARTITION_NODES, ids=lambda node: node.__name__)
def test_partition_maintenance_kinds_resolve_through_the_dialect(node):
    """Every partition node resolves through ClickHouse's own table."""
    registry = _dialect().artifact_registry()

    kind = node.kind()
    assert kind.startswith("clickhouse_"), kind
    assert registry.resolve_node(kind) is node


def test_a_partition_node_roundtrips_through_the_dialect():
    """A ClickHouse-only kind is read back through the dialect's own table."""
    dialect = _dialect()
    original = ClickHouseReplacePartitionStatement(
        dialect,
        "visits",
        "202601",
        "archive_visits",
        schema="analytics",
        source_schema="backup",
    )

    restored = deserialize(serialize(original), dialect)
    assert isinstance(restored, ClickHouseReplacePartitionStatement)
    assert restored.get_params() == original.get_params()
    assert restored.to_sql() == original.to_sql()

    # Without a dialect the selection falls back to core, which refuses the
    # backend kind by name instead of guessing.
    with pytest.raises(ExpressionDeserializationError) as caught:
        deserialize(serialize(original))
    assert original.kind() in str(caught.value)


def _foreign_node():
    """A neutral dummy node: owned by no other concrete backend's impl tree."""
    dummy = DummyDialect()
    return _DummyTypeDefinition(dummy, IntegerType(dummy))


def test_another_backends_kind_is_refused():
    """ClickHouse's table is core plus ClickHouse: a foreign kind is not included."""
    dialect = _dialect()
    registry = dialect.artifact_registry()

    foreign_kind = _foreign_node().kind()
    assert foreign_kind not in registry.node_kinds()
    with pytest.raises(RegistryError) as caught:
        registry.resolve_node(foreign_kind)
    assert caught.value.reason is RegistryReason.KIND_NOT_REGISTERED
    assert foreign_kind in str(caught.value)

    artifact = serialize(_foreign_node())
    with pytest.raises(ExpressionDeserializationError) as caught:
        deserialize(artifact, dialect)
    assert foreign_kind in str(caught.value)


def test_the_published_registry_is_frozen():
    """A published table is a value; widening it means building a new one."""
    registry = backend_registry()
    assert registry.is_frozen

    with pytest.raises(RegistryError) as caught:
        registry.register_node(ClickHouseReplacePartitionStatement)
    assert caught.value.reason is RegistryReason.REGISTRY_FROZEN
    assert ClickHouseReplacePartitionStatement.kind() in str(caught.value)

    # A twin is the mutable workspace, and it cannot change the source.
    twin = registry.twin()
    assert not twin.is_frozen
    twin.register_node(_DummyTypeDefinition)
    assert _DummyTypeDefinition.kind() in twin.node_kinds()
    assert _DummyTypeDefinition.kind() not in registry.node_kinds()


def test_trusted_opt_in_kinds_come_from_a_twin_never_the_published_table():
    """Raw SQL nodes are admitted per caller, in a copy of the backend's table.

    ``RawSQL`` / ``RawSQLPredicate`` render caller-vouched text, so an
    assembled table leaves them out by default (``REGISTER_BY_DEFAULT = False``).
    A caller that trusts its artifacts registers them into
    ``backend_registry().twin()``; the published table stays as it was.
    """
    from rhosocial.activerecord.backend.expression.operators import (
        RawSQL,
        RawSQLPredicate,
    )

    published = backend_registry()
    for cls in (RawSQL, RawSQLPredicate):
        assert cls.kind() not in published.node_kinds()

    trusted = published.twin()
    for cls in (RawSQL, RawSQLPredicate):
        trusted.register_node(cls)
        assert cls.kind() in trusted.node_kinds()
        assert cls.kind() not in published.node_kinds()


def test_the_expression_roundtrip_matrix_still_round_trips(
    clickhouse_matrix_dialect,
):
    """Core and ClickHouse kinds both read back through the dialect's table."""
    from rhosocial.activerecord.backend.expression.predicates import (
        ComparisonPredicate,
    )

    d = clickhouse_matrix_dialect
    registry = d.artifact_registry()
    cases = (
        Column(d, "id"),
        Literal(d, 1),
        ComparisonPredicate(d, "=", Column(d, "a"), Literal(d, 1)),
        ClickHouseReplacePartitionStatement(d, "visits", "202601", "archive"),
        ClickHouseMovePartitionStatement(d, "visits", "202601", "TABLE", "archive"),
        ClickHouseFreezePartitionStatement(d, "visits", "202601", "backup"),
        ClickHouseUnfreezePartitionStatement(d, "visits", "202601", "backup"),
        ClickHouseClearInPartitionStatement(d, "visits", "COLUMN", "total", "202601"),
        ClickHouseOptimizePartitionStatement(d, "visits", "202601"),
    )
    for instance in cases:
        restored = deserialize(serialize(instance), d, registry=registry)
        assert type(restored) is type(instance)
        assert serialize(restored) == serialize(instance), type(instance).__name__
        assert restored.to_sql() == instance.to_sql(), type(instance).__name__

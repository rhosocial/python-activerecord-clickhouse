# tests/test_expression_registry_contract.py
"""Construct-level contract for ClickHouse's expression table and ``Parameter``.

The table is data: core's kinds merged with this backend's own, frozen, and
resolving a kind to a class without any dialect in the loop. Rendering, on the
other hand, is the dialect's business: a value binds by default, and an
``inline=True`` value becomes text through ClickHouse's ``format_literal``.
No live server or emulator is involved in any of it.
"""

import pytest

from rhosocial.activerecord.backend.expression import (
    Column,
    ComparisonPredicate,
    Parameter,
)
from rhosocial.activerecord.backend.expression.coerce import value_expression
from rhosocial.activerecord.backend.expression_registry import (
    CORE_EXPRESSIONS,
    RegistryError,
    RegistryReason,
)
from rhosocial.activerecord.backend.impl.clickhouse.dialect import ClickHouseDialect
from rhosocial.activerecord.backend.impl.clickhouse.expression import ClickHouseArrayType
from rhosocial.activerecord.backend.impl.clickhouse.expression_registry import (
    CLICKHOUSE_EXPRESSIONS,
    CLICKHOUSE_EXPRESSION_REGISTRY,
)

_CORE_PREFIX = "rhosocial.activerecord.backend.expression."
_CLICKHOUSE_PREFIX = "rhosocial.activerecord.backend.impl.clickhouse.expression."

#: A kind owned by a sibling backend (SQLite's VACUUM statement): knowing how
#: to render a kind elsewhere is not the same as publishing it here.
_SIBLING_ONLY_KIND = "sqlite_vacuum_statement"


@pytest.fixture
def dialect():
    return ClickHouseDialect()


# ---------------------------------------------------------------------------
# The published table
# ---------------------------------------------------------------------------


def test_clickhouse_registry_is_frozen() -> None:
    registry = CLICKHOUSE_EXPRESSION_REGISTRY
    assert registry.is_frozen
    with pytest.raises(RegistryError) as caught:
        registry.register_node(Column)
    assert caught.value.reason is RegistryReason.REGISTRY_FROZEN


def test_clickhouse_kinds_are_core_kinds_union_clickhouse_own() -> None:
    kinds = set(CLICKHOUSE_EXPRESSION_REGISTRY.node_kinds())
    assert kinds == set(CORE_EXPRESSIONS) | set(CLICKHOUSE_EXPRESSIONS)
    # A real merge, not one side swallowing the other.
    assert set(CLICKHOUSE_EXPRESSIONS) - set(CORE_EXPRESSIONS)
    assert set(CORE_EXPRESSIONS) - set(CLICKHOUSE_EXPRESSIONS)


def test_no_sibling_backend_kind_is_published() -> None:
    kinds = set(CLICKHOUSE_EXPRESSION_REGISTRY.node_kinds())
    assert _SIBLING_ONLY_KIND not in kinds
    with pytest.raises(RegistryError) as caught:
        CLICKHOUSE_EXPRESSION_REGISTRY.resolve_node(_SIBLING_ONLY_KIND)
    assert caught.value.reason is RegistryReason.KIND_NOT_REGISTERED

    # Every target belongs to core or to this backend: no third owner, and in
    # particular no sibling backend's expression package, contributes a kind.
    targets = dict(CORE_EXPRESSIONS)
    targets.update(CLICKHOUSE_EXPRESSIONS)
    foreign = [
        f"{kind} -> {fqn}"
        for kind, fqn in targets.items()
        if not (
            fqn.startswith(_CORE_PREFIX) or fqn.startswith(_CLICKHOUSE_PREFIX)
        )
    ]
    assert not foreign, "\n".join(foreign)


# ---------------------------------------------------------------------------
# Resolution: a kind is a key into the table, never a module path
# ---------------------------------------------------------------------------


def test_parameter_kind_resolves_to_cores_parameter() -> None:
    assert CORE_EXPRESSIONS["parameter"] == (
        f"{Parameter.__module__}.{Parameter.__qualname__}"
    )
    assert CLICKHOUSE_EXPRESSION_REGISTRY.resolve_node("parameter") is Parameter


def test_clickhouse_owned_kind_resolves_to_its_class() -> None:
    kind = "clickhouse_array_type"
    assert kind in CLICKHOUSE_EXPRESSIONS
    assert kind not in CORE_EXPRESSIONS
    assert CLICKHOUSE_EXPRESSION_REGISTRY.resolve_node(kind) is ClickHouseArrayType


# ---------------------------------------------------------------------------
# Rendering: one position, one decision (bind or text)
# ---------------------------------------------------------------------------


def test_parameter_binds_by_default(dialect: ClickHouseDialect) -> None:
    sql, params = Parameter(dialect, "abc").to_sql()
    assert sql == "%s" == dialect.get_parameter_placeholder()
    assert params == ("abc",)


def test_inline_parameter_renders_clickhouse_text_with_no_params(
    dialect: ClickHouseDialect,
) -> None:
    sql, params = Parameter(dialect, "O'Reilly", inline=True).to_sql()
    assert sql == "'O''Reilly'"
    assert params == ()

    # ClickHouse's own tier-2 literal spelling, not a generic one: bytes go
    # through ``unhex()`` because the dialect really rendered this value.
    assert Parameter(dialect, b"\x01\x02", inline=True).to_sql() == (
        "unhex('0102')",
        (),
    )


def test_raw_value_at_a_value_position_binds(dialect: ClickHouseDialect) -> None:
    coerced = value_expression(dialect, 42)
    assert isinstance(coerced, Parameter)
    assert coerced.to_sql() == ("%s", (42,))

    predicate = ComparisonPredicate(dialect, "=", Column(dialect, "id"), "42")
    assert isinstance(predicate.right, Parameter)
    sql, params = predicate.to_sql()
    assert sql == "`id` = %s"
    assert "42" not in sql
    assert params == ("42",)

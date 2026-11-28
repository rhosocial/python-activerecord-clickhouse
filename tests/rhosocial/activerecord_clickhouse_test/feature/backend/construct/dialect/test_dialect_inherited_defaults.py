# tests/rhosocial/activerecord_clickhouse_test/feature/backend/construct/dialect/test_dialect_inherited_defaults.py
"""Switches a core mixin defaults to True must not answer for ClickHouse.

The dialect is composed from generic mixins plus backend overrides, and Python
takes the first class in the MRO that defines a name. A backend override placed
after the generic mixin is dead code; a name the backend never overrides answers
with the generic default. That default is True for three ``ReturningMixin``
members and two ``ConstraintMixin`` referential-action probes, which advertised
clauses the engine rejects -- and the INSERT formatter rendered the RETURNING
one anyway.

Three guards:

* the set of True answers inherited from outside this package is pinned, so a
  new generic default cannot leak in silently;
* a family whose head switch answers False must answer False for every member
  (foreign keys, RETURNING, sequences);
* the INSERT formatter refuses a RETURNING clause instead of rendering it.
"""

import pytest

from rhosocial.activerecord.backend.dialect.exceptions import UnsupportedFeatureError
from rhosocial.activerecord.backend.expression.core import Column, Parameter
from rhosocial.activerecord.backend.expression.objects import Table
from rhosocial.activerecord.backend.expression.statements.dml import (
    InsertStatement,
    ReturningClause,
    ValuesSource,
)
from rhosocial.activerecord.backend.impl.clickhouse.dialect import ClickHouseDialect

#: True answers ClickHouse inherits rather than declares. Each one is a
#: capability of the engine itself (CREATE/DROP, joins, EXPLAIN, microsecond
#: timestamps), so the generic default is the answer.
INHERITED_TRUE = (
    "supports_alter_table",
    "supports_create_table",
    "supports_create_table_as",
    "supports_create_view",
    "supports_cross_join",
    "supports_derived_table",
    "supports_drop_table",
    "supports_drop_view",
    "supports_explain_plan",
    "supports_inner_join",
    "supports_json_path",
    "supports_left_join",
    "supports_microsecond_timestamp",
    "supports_unconditional_cte_order_by",
)

FOREIGN_KEY_FAMILY = (
    "supports_foreign_key_constraint",
    "supports_foreign_key_on_delete",
    "supports_foreign_key_on_update",
    "supports_fk_on_delete",
    "supports_fk_on_update",
    "supports_fk_match",
)

RETURNING_FAMILY = (
    "supports_returning_insert",
    "supports_returning_update",
    "supports_returning_delete",
    "supports_returning_expressions",
    "supports_returning_alias",
    "supports_returning_wildcard",
    "supports_returning_single_row",
    "supports_returning_old_new",
    "supports_returning_into",
)

SEQUENCE_FAMILY = (
    "supports_create_sequence",
    "supports_drop_sequence",
    "supports_sequence_owned_by",
)


@pytest.fixture()
def dialect():
    return ClickHouseDialect(version=(26, 7, 3))


def _defining_class(dialect, name: str):
    for cls in type(dialect).__mro__:
        if name in cls.__dict__:
            return cls
    return None


def _inherited_true(dialect) -> set:
    found = set()
    for name in dir(dialect):
        if not name.startswith("supports_"):
            continue
        attr = getattr(dialect, name)
        if not callable(attr):
            continue
        owner = _defining_class(dialect, name)
        module = owner.__module__ if owner is not None else ""
        if attr() is True and "impl.clickhouse" not in module:
            found.add(name)
    return found


def test_only_the_pinned_switches_inherit_a_true_default(dialect) -> None:
    inherited = _inherited_true(dialect)
    assert inherited == set(INHERITED_TRUE), (
        "a core mixin now answers True for ClickHouse without an override: "
        f"{sorted(inherited - set(INHERITED_TRUE))}"
    )


@pytest.mark.parametrize("name", FOREIGN_KEY_FAMILY)
def test_the_foreign_key_family_is_all_false(dialect, name) -> None:
    assert getattr(dialect, name)() is False, f"{name} advertised a foreign key clause"


@pytest.mark.parametrize("name", RETURNING_FAMILY)
def test_the_returning_family_is_all_false(dialect, name) -> None:
    assert getattr(dialect, name)() is False, f"{name} advertised a RETURNING clause"


@pytest.mark.parametrize("name", SEQUENCE_FAMILY)
def test_the_sequence_family_is_all_false(dialect, name) -> None:
    assert getattr(dialect, name)() is False, f"{name} advertised a sequence object"


def test_the_insert_formatter_refuses_a_returning_clause(dialect) -> None:
    table = Table(dialect, "t")
    source = ValuesSource(dialect, [[Parameter(dialect, 1)]])
    returning = ReturningClause(dialect, [Column(dialect, "id")])
    statement = InsertStatement(dialect, table, source, returning=returning)
    with pytest.raises(UnsupportedFeatureError, match="RETURNING"):
        dialect.format_insert_statement(statement)

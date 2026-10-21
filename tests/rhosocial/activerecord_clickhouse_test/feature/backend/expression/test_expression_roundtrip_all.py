# tests/rhosocial/activerecord_clickhouse_test/feature/backend/expression/test_expression_roundtrip_all.py
"""
Serialization coverage for every expression class ClickHouse can render.

For each constructible expression class:
  1. dict round-trip  : deserialize(serialize(e)).get_params() == e.get_params()
  2. JSON round-trip  : deserialize_json(serialize_json(e)).get_params() == ...
  3. XML round-trip   : deserialize_xml(serialize_xml(e)).get_params() == ...
  4. SQL consistency  : classified, never swallowed -- see below.

Why this exists
===============

Five backends had a matrix of this shape; ClickHouse had none, and core had none
for its own package either. That is not a neutral gap. This matrix replaces a
convention the other five follow, which is
``rhosocial.activerecord.testsuite.utils.expression.sql_consistent``:

    try:
        expected = instance.to_sql()
    except Exception:
        return          # any exception at all counts as a pass

Together with a ``pytest.skip`` when ``make_instance`` returns ``None``, that
convention cannot distinguish "this dialect does not support the feature" from
"this formatter reads a field that no longer exists". Both are green. Measured
against core's expression package it turned 74 real errors into 74 passes. A
backend whose formatter is broken in a way no assertion can see is a backend
whose formatters are untested.

So every outcome here is named and asserted:

* **renders** -- all three encodings must restore byte-identical SQL *and*
  byte-identical bind parameters.
* ``UnsupportedFeatureError`` from a probe inside a formatter -- this dialect
  does not model the feature. Asserted as exactly that type, so a different
  failure cannot hide behind it.
* ``UnsupportedFeatureError`` from the dispatch -- the dialect's base list
  names no ``format_*`` method for the class at all, which is a wiring fact
  about this backend rather than a capability answer. The method the dispatch
  names must be a row in :data:`UNMODELLED_FORMATTERS`, so the gap is a
  decision with a reason rather than an omission; see
  :func:`_dispatched_formatter`.
* a member of :data:`LEGITIMATE_NON_RENDERS` -- a class that cannot render for a
  reason belonging to its own tree. Each entry pins the exception type *and* a
  message fragment, so a class that starts failing differently fails here.
* **anything else** -- a failure naming the class and the exception.

The first two branches overlap on purpose
=========================================

``BaseExpression.to_sql()`` reports a missing formatter as
``UnsupportedFeatureError``, so every class ClickHouse simply has no formatter for
lands in that branch whether or not it is named below. Naming them anyway is the
point: the blanket branch says *some* formatter is missing, and the entry says
*which one*, for this class, on purpose. Without the entry a formatter added for
one of these features would silently turn a documented gap into a passing render,
and nothing in this file would report that the decision had been reversed.
:func:`test_pinned_non_render_really_does_not_render` is what makes the entry
load-bearing in both directions.

The same incident is also why the blanket branch itself was split in two
=======================================================================

A probe inside a formatter and the dispatch naming a missing formatter raise the
same type, and for a long time this file allowed both identically -- which let a
class whose formatter this dialect never mixed in read as "ClickHouse lacks the
feature" and pass. Core turning ``trim``/``lpad``/``rpad``/``repeat`` into
dedicated nodes made the hole load-bearing: a backend shipping no formatter for
one of them would answer every ``.lpad(...)`` with that refusal, and nothing here
could tell it apart from a genuine "not on this engine". The exception itself
records who is refusing: a probe names the feature, while the dispatch frames
the formatting method it could not find as ``the '<method>' statement`` -- see
:func:`_dispatched_formatter`. Only the dispatch's refusal is a wiring fact
about this backend, so only it must be accounted for:
:meth:`TestMatrixIntegrity.test_unmodelled_formatter_list_is_exact` pins
:data:`UNMODELLED_FORMATTERS` in both directions, and a method nobody listed
fails the run.

And what happens when a class cannot be constructed
===================================================

``make_instance(...) is None`` becomes a skip, but only for a class named in
:data:`UNCONSTRUCTIBLE`, and :func:`test_unconstructible_list_is_exact` pins that
tuple in both directions. A class that starts needing an exemption fails CI
instead of turning into a skip, and a stale entry fails too. There is no ceiling
assertion: "no more than N" absorbs new gaps silently, which is the failure mode
this file exists to remove.

Both expression packages are collected
======================================

:data:`CORE_EXPR_PKG` *and* :data:`CH_EXPR_PKG`. The five existing matrices
collect only the backend's own package, so core's classes have no systematic
coverage anywhere except inside core -- which is how postgres's
``comment.py:42`` read a field core had removed months earlier and stayed green.
Discovery walks both package trees; it never reads the serialization class
index, which is process-global and grows as sibling modules import other
backends, so the matrix's contents would otherwise depend on which files
pytest imported first.

No database is involved. The matrix drives the dialect, which is where SQL
generation happens; nothing here opens a connection.

The baseline this table was last reconciled against
===================================================

Core ``debde516`` (following ``679d9817``, which made a node's kind its identity
and its payload plain JSON). Every number in the tables below is a statement
about that tree: :func:`test_unmodelled_formatter_list_is_exact`,
:func:`test_unconstructible_list_is_exact`,
:func:`test_pinned_non_render_really_does_not_render` and
:func:`test_pinned_non_roundtrip_refuses_as_pinned` all fail when core moves
underneath, which is the point -- they are what make a core change visible here
instead of on the backend that has to answer for it. Where core moved between
the two baselines, this file says which direction:

* ``debde516`` gave NaN and the infinities value kinds of their own, so the
  closed set :class:`TestLiteralValueKinds` pins is sixteen, not fourteen
  (see :attr:`TestLiteralValueKinds._CASES`).
* ``ComparisonPredicate`` began normalising its operator, so the introspective
  constructor's placeholder stopped satisfying it and the class took a
  registered constructor rather than an UNCONSTRUCTIBLE exemption.
* ``CustomType``'s ``raw`` became keyword-only, and the type root's refusal now
  carries the generic dispatch's own spelling.
* ``ForUpdateClause`` began normalising the word it stores, so its entry left
  :data:`LEGITIMATE_NON_ROUNDTRIPS` rather than the table holding a reason that
  no longer exists.

Coverage at that baseline: 515 registered, 510 constructible, 5 pinned
unconstructible, 61 pinned non-render; rendered 327, unsupported 121,
unmodelled 32, non-render 30.
:func:`TestMatrixIntegrity.test_coverage_report` prints the current figures on
every run.
"""

import datetime
import decimal
import enum
import inspect
import math
import uuid
from typing import Dict

import pytest

from rhosocial.activerecord.backend.dialect.exceptions import UnsupportedFeatureError
from rhosocial.activerecord.backend.expression.advanced_functions import (
    CaseExpression,
    WindowClause,
    WindowDefinition,
    WindowSpecification,
)
from rhosocial.activerecord.backend.expression.bases import BaseExpression
from rhosocial.activerecord.backend.expression.core import Column, Literal
from rhosocial.activerecord.backend.expression.datetime import (
    ExtractFieldExpression,
    TemporalOptionsExpression,
    _ExtractBase,
)
from rhosocial.activerecord.backend.expression.functions.string import (
    ChrFunction,
    LeftFunction,
    OverlayExpression,
    RightFunction,
    SpaceFunction,
    SubstringExpression,
)
from rhosocial.activerecord.backend.expression.objects import (
    Database,
    Function,
    Index,
    MaterializedView,
    Procedure,
    Table,
    View,
)
from rhosocial.activerecord.backend.expression.operators import ArithmeticOperation
from rhosocial.activerecord.backend.expression.predicates import (
    LikeOperator,
    ComparisonPredicate,
    ILikePredicate,
    LikePredicate,
)
from rhosocial.activerecord.backend.expression.query_parts import JoinClause
from rhosocial.activerecord.backend.expression.query_sources import SetOperation
from rhosocial.activerecord.backend.expression.serialization import (
    deserialize,
    deserialize_json,
    deserialize_xml,
    serialize,
    serialize_json,
    serialize_xml,
)
from rhosocial.activerecord.backend.expression.sources import NamedRelationRef
from rhosocial.activerecord.backend.expression.statements import (
    CreateTableStatement,
    CreateTableLikeStatement,
    CreateViewStatement,
    DropViewStatement,
    InsertStatement,
    TruncateStatement,
    ValuesSource,
    ddl_alter,
    ddl_comment,
    ddl_database,
    ddl_table,
    dml,
)
from rhosocial.activerecord.backend.expression.statements.ddl_database import (
    AlterDatabaseAction,
    AlterDatabaseStatement,
    CreateDatabaseStatement,
    DropDatabaseStatement,
)
from rhosocial.activerecord.backend.expression.statements.ddl_alter import (
    AddTableConstraintAction,
)
from rhosocial.activerecord.backend.expression.statements.ddl_table import (
    CreateTableCloneStatement,
    TableConstraint,
    TableForeignKeyConstraint,
)
from rhosocial.activerecord.backend.expression.statements.ddl_view import (
    CreateMaterializedViewStatement,
    DropMaterializedViewStatement,
    RefreshMaterializedViewStatement,
)
from rhosocial.activerecord.backend.expression.statements.dql import QueryStatement
from rhosocial.activerecord.backend.expression.types import IntegerType, VarCharType
from rhosocial.activerecord.backend.impl.clickhouse.dialect import ClickHouseDialect
from rhosocial.activerecord.backend.impl.clickhouse.mixins.namespace import (
    ClickHouseNamespaceMixin,
)
from rhosocial.activerecord.backend.impl.clickhouse.expression import (
    ClickHouseModifyMaterializedViewRefreshExpression,
    ClickHouseRefreshSchedule,
    admin as admin_module,
    alter_column,
    column as chexpr_column,
    dml as chexpr_dml,
    maintenance,
    materialized_view,
    partition,
    rename_table,
    routine,
)
from rhosocial.activerecord.backend.impl.clickhouse.expression import (
    types as chexpr_types,
)
from expression_roundtrip_harness import (
    collect_expression_classes,
    make_instance,
    register_all,
    register_special_constructor,
)

CORE_EXPR_PKG = "rhosocial.activerecord.backend.expression"
CH_EXPR_PKG = "rhosocial.activerecord.backend.impl.clickhouse.expression"


#: The two packages this matrix covers. Core's own classes are here on purpose:
#: no other ClickHouse test exercises them through the ClickHouse dialect, and a
#: formatter reading a stale core field is exactly the defect this matrix exists
#: to catch.
COVERED_PACKAGES = (CORE_EXPR_PKG, CH_EXPR_PKG)


def assert_params_equal(a, b, path="params"):
    """Deep-compare two ``get_params()`` dicts, structurally.

    Nested ``BaseExpression`` instances compare by their own params; dataclasses
    compare field by field. Anything else compares by value, with a path so a
    mismatch names the field rather than the whole expression.
    """
    if isinstance(a, BaseExpression) and isinstance(b, BaseExpression):
        assert_params_equal(a.get_params(), b.get_params(), path + ".<expr>")
        return
    assert type(a) is type(b) or (
        isinstance(a, (list, tuple, dict)) and isinstance(b, (list, tuple, dict))
    ), f"{path}: type mismatch {type(a).__name__} vs {type(b).__name__}"
    if isinstance(a, dict):
        assert set(a) == set(b), f"{path}: keys differ {set(a) ^ set(b)}"
        for k in a:
            assert_params_equal(a[k], b[k], f"{path}.{k}")
        return
    if isinstance(a, (list, tuple)):
        assert len(a) == len(b), f"{path}: lengths differ"
        for i, (x, y) in enumerate(zip(a, b, strict=True)):
            assert_params_equal(x, y, f"{path}[{i}]")
        return
    assert a == b, f"{path}: {a!r} != {b!r}"


def _channel_builders(instance, dialect):
    """One lazy builder per encoding channel.

    Lazy on purpose: an eager tuple evaluated all three round-trips up front,
    so a refusal on the first channel stopped the others from ever being
    attempted -- and a pin that names one channel must leave the other two
    demonstrably working, not merely unexamined.
    """
    return (
        ("dict", lambda: deserialize(serialize(instance), dialect)),
        ("json", lambda: deserialize_json(serialize_json(instance), dialect)),
        ("xml", lambda: deserialize_xml(serialize_xml(instance), dialect)),
    )


def _roundtrip_pin(fqn: str, channel: str):
    """The pin for one class on one channel, or ``None`` when it travels free."""
    entry = LEGITIMATE_NON_ROUNDTRIPS.get(fqn)
    if entry is None:
        return None
    return entry["channels"].get(channel)


def _assert_pinned_channel(fqn, channel, build, instance, pin):
    """Assert one pinned channel, in the shape its entry names.

    ``raises`` -- the channel refuses outright. ``word`` / ``enum-str`` -- the
    restore succeeds but is type-lossy, asserted both ways: the strict params
    comparison must fail (so the pin stays load-bearing; a core fix makes the
    entry stale and this assertion demands its removal), and the normalised
    comparison must hold (so the loss is exactly the member/word spelling and
    nothing else moved).
    """
    if pin[0] == "raises":
        _, expected_type, fragment = pin
        try:
            build()
        except Exception as exc:
            assert isinstance(exc, expected_type), (
                f"{fqn}: the {channel} channel was pinned as refusing with "
                f"{expected_type.__name__}, but it raised "
                f"{type(exc).__name__}: {exc}"
            )
            assert fragment in str(exc), (
                f"{fqn}: expected the {channel} refusal to mention "
                f"{fragment!r}, but it said: {exc}"
            )
        else:
            raise AssertionError(
                f"{fqn}: the {channel} channel is pinned in "
                f"LEGITIMATE_NON_ROUNDTRIPS but the round-trip now succeeds. "
                f"The reason it was pinned is gone -- remove the entry rather "
                f"than leave a lie in the table."
            )
        return
    mode = pin[0]
    restored = build()
    try:
        assert_params_equal(restored.get_params(), instance.get_params(), fqn)
    except AssertionError:
        pass  # expected: the type loss is the pin's whole subject
    else:
        raise AssertionError(
            f"{fqn}: the {channel} channel is pinned as type-lossy in "
            f"LEGITIMATE_NON_ROUNDTRIPS but the round-trip is now exact; "
            f"remove the stale entry."
        )
    _enum_word_params_equal(
        restored.get_params(), instance.get_params(), mode, f"{fqn}.{channel}"
    )


def _sql_params_equal(a, b) -> bool:
    """Bind-parameter sequences compared as sequences.

    The artifact carries a tuple as an array (§4.8: JSON draws no distinction,
    the kind does, and a constructor normalises on the way back), so a
    round-tripped render may hand back a list where the original handed a
    tuple. ``Subquery`` is the case in the tree: its ``query_params`` arrive
    as a list on restore and its formatter passes them through. The values are
    the contract; the container is not. Order still matters -- this is a
    sequence comparison, not a set comparison.
    """
    if isinstance(a, (list, tuple)) and isinstance(b, (list, tuple)):
        return len(a) == len(b) and all(
            _sql_params_equal(x, y) for x, y in zip(a, b, strict=True)
        )
    return a == b


def _enum_word_params_equal(a, b, mode: str, path: str = "params") -> None:
    """``assert_params_equal``, with a ``(str, Enum)`` member read as its word.

    The two modes are the two spellings an artifact can hand back for a
    member:

    * ``"word"`` -- the member's own value, which is what the JSON channel
      writes and what the XML channel writes when the enum sets
      ``__str__ = str.__str__``;
    * ``"enum-str"`` -- ``str(member)`` under the default ``Enum.__str__``,
      the ``"EnumClass.MEMBER"`` spelling an enum without that assignment
      produces on the XML channel.

    Asserts rather than returns, mirroring :func:`assert_params_equal`; a
    difference beyond the member/word spelling fails here by name.
    """

    def _norm(x):
        if isinstance(x, enum.Enum):
            return str(x) if mode == "enum-str" else x.value
        return x

    if isinstance(a, BaseExpression) and isinstance(b, BaseExpression):
        _enum_word_params_equal(
            a.get_params(), b.get_params(), mode, path + ".<expr>"
        )
        return
    # No strict type check here, on purpose: the type difference between a
    # member and the word that replaced it is exactly what this comparison
    # exists to accept. Everything else still fails by name below.
    if isinstance(a, dict):
        assert set(a) == set(b), f"{path}: keys differ {set(a) ^ set(b)}"
        for k in a:
            _enum_word_params_equal(a[k], b[k], mode, f"{path}.{k}")
        return
    if isinstance(a, (list, tuple)):
        assert len(a) == len(b), f"{path}: lengths differ"
        for i, (x, y) in enumerate(zip(a, b, strict=True)):
            _enum_word_params_equal(x, y, mode, f"{path}[{i}]")
        return
    assert _norm(a) == _norm(b), f"{path}: {a!r} != {b!r}"


def _collect_matrix_classes() -> Dict[str, type]:
    """Every concrete expression class the two covered packages define.

    Walked from the package, not read from the serialization class index: that index
    is process-global and *grows* as other test modules import their own
    backends, so reading it makes this matrix's contents depend on which files
    pytest happened to import first. The matrix passed standalone and failed run
    beside the statement tests, because it had picked up classes from another
    backend -- classes that were then rendered with the ClickHouse dialect, which
    is not a meaningful thing to assert.

    Several modules export aliases of one class (``ddl_alter`` used to spell
    ``AlterConstraintAction`` and ``ValidateConstraintAction`` two ways
    each). The same object collected twice would be tested twice and
    reported twice, so the first name wins and identity does the
    deduplication.
    """
    found: Dict[str, type] = {}
    for package in COVERED_PACKAGES:
        found.update(collect_expression_classes(package))
    by_identity: Dict[int, str] = {}
    for fqn, cls in sorted(found.items()):
        by_identity.setdefault(id(cls), fqn)
    return {
        fqn: cls
        for cls in found.values()
        if not inspect.isabstract(cls)
        for fqn in [by_identity[id(cls)]]
    }


REGISTERED = _collect_matrix_classes()

# Deserialization resolves a kind to its class through the framework's
# default registry. Core's own packages auto-populate it; the ClickHouse
# package's classes do not, so they are registered here or every round-trip
# of a backend class refuses by kind before it can compare anything. That
# is the whole registration surface: core 679d9817 made an artifact plain
# JSON, the registry owns the kind -> class table and nothing else, and the
# enum / dataclass vocabulary tables are gone -- a str enum is a JSON
# scalar, and every other conversion lives in the constructor that
# receives it. Core's artifact-contract test pins the absence.
register_all(REGISTERED)


# ---------------------------------------------------------------------------
# Special constructors: a real value where the introspective guess is a lie
# ---------------------------------------------------------------------------
#
# ``make_instance`` reads each required parameter's annotation and guesses:
# ``"x"`` for a string, ``[]`` for a list, ``IntegerType()`` for a type. That is
# right for a name and wrong for every parameter that wants a catalogue object --
# a Table, an Index, a PropertyGraph -- because a bare ``"x"`` is not one, and
# the formatter now refuses it by name. It is also wrong for the containers that
# require at least one member (CASE, WINDOW, JOIN, temporal options), for the
# predicates that must render without bind parameters (DDL cannot carry a bind
# parameter), and for the ClickHouse classes whose parameters are keyword-only
# behind defaulted positionals.
#
# Every registration below replaces a guess that would otherwise produce an
# instance the dialect cannot render. Suffixes are spelled relative to the
# expression package because ``make_instance`` matches with ``str.endswith`` and
# several modules export identically named classes.


def _table(dialect, name="t"):
    """A table with a bare name and no namespace."""
    return Table(dialect, name)


def _column_predicate(dialect):
    """A predicate comparing two columns, so it renders with no bind parameters."""
    return ComparisonPredicate(dialect, "=", Column(dialect, "a"), Column(dialect, "b"))


def _operand(dialect, name):
    """A value expression with no bind parameters, for arithmetic operands."""
    return Column(dialect, name)


def _ddl_dml_query(dialect, table):
    """A minimal SELECT, the operand a set operation needs."""
    return QueryStatement(
        dialect, select=[Column(dialect, "id")], from_=Table(dialect, table)
    )


def _integer_column(dialect, name="col"):
    """A column definition carrying a *dialect-bound* type.

    The binding is load-bearing: ``to_sql()`` dispatches on the type through its
    own dialect, so an unbound ``IntegerType()`` raises the moment anything
    renders it.
    """
    return ddl_table.ColumnDefinition(dialect, name, IntegerType(dialect))


def register_specials():
    """Replace every introspective guess that would cost a real assertion."""
    # -- the object a statement names, and the source that reads it ----------
    register_special_constructor(
        "sources.relation.NamedRelationRef",
        lambda d: NamedRelationRef(d, _table(d)),
    )
    register_special_constructor(
        "query_parts.JoinClause",
        lambda d: JoinClause(
            d,
            left_table=NamedRelationRef(d, _table(d, "a")),
            right_table=NamedRelationRef(d, _table(d, "b")),
            condition=_column_predicate(d),
        ),
    )

    # -- tables --------------------------------------------------------------
    register_special_constructor(
        "statements.ddl_table.CreateTableStatement",
        lambda d: ddl_table.CreateTableStatement(d, _table(d), [_integer_column(d)]),
    )
    register_special_constructor(
        "statements.ddl_table.ColumnDefinition", _integer_column
    )
    register_special_constructor(
        "statements.ddl_alter.AddColumnAction",
        lambda d: ddl_alter.AddColumnAction(d, _integer_column(d)),
    )
    register_special_constructor(
        "statements.ddl_alter.ModifyColumnAction",
        lambda d: ddl_alter.ModifyColumnAction(d, _integer_column(d)),
    )
    # ``old_name`` comes first here, so the guess's positional order is wrong:
    # it built the column definition into ``old_name`` and the string into
    # ``column``, and the failure surfaced as an AttributeError at render time.
    register_special_constructor(
        "statements.ddl_alter.ChangeColumnAction",
        lambda d: ddl_alter.ChangeColumnAction(d, "old", _integer_column(d)),
    )
    register_special_constructor(
        "statements.ddl_comment.CommentOnStatement",
        lambda d: ddl_comment.CommentOnStatement(d, "table", _table(d), comment="c"),
    )

    # -- databases -----------------------------------------------------------
    # ``RENAME TO`` is the action core's enum names; without it the guess picks
    # whatever sorts first.
    register_special_constructor(
        "statements.ddl_database.AlterDatabaseStatement",
        lambda d: ddl_database.AlterDatabaseStatement(
            d,
            Database(d, "db"),
            action=AlterDatabaseAction.RENAME_TO,
            target="renamed_db",
        ),
    )

    # -- closed word sets the guesser cannot satisfy --------------------------
    # Both nodes validate their operation word at construction and refuse
    # anything outside a fixed set. ``make_instance`` guesses a string for the
    # ``op`` parameter, so both are refused before they can be rendered -- and
    # both are among the nodes worth rendering, so a real word is supplied here
    # rather than a new entry in UNCONSTRUCTIBLE.
    register_special_constructor(
        "operators.ArithmeticOperation",
        lambda d: ArithmeticOperation(
            d, "add", _operand(d, "a"), _operand(d, "b")
        ),
    )
    register_special_constructor(
        "query_sources.SetOperation",
        lambda d: SetOperation(
            d,
            op="union",
            left=_ddl_dml_query(d, "t1"),
            right=_ddl_dml_query(d, "t2"),
        ),
    )

    # -- containers that need at least one member ----------------------------
    register_special_constructor(
        "advanced_functions.CaseExpression",
        lambda d: CaseExpression(
            d, cases=[(_column_predicate(d), Literal(d, 1))], else_result=Literal(d, 0)
        ),
    )
    register_special_constructor(
        "advanced_functions.WindowSpecification",
        lambda d: WindowSpecification(d, partition_by=["a"]),
    )
    register_special_constructor(
        "advanced_functions.WindowDefinition",
        lambda d: WindowDefinition(d, "w", WindowSpecification(d, partition_by=["a"])),
    )
    register_special_constructor(
        "advanced_functions.WindowClause",
        lambda d: WindowClause(
            d, [WindowDefinition(d, "w", WindowSpecification(d, partition_by=["a"]))]
        ),
    )
    # An empty options dict is refused by the formatter, so a time-travel clause
    # needs an actual option.
    register_special_constructor(
        "datetime.TemporalOptionsExpression",
        lambda d: TemporalOptionsExpression(d, {"as_of": "2020-01-01"}),
    )

    # -- constraints and column pieces ---------------------------------------
    # The branch is a required keyword now, and an introspective constructor
    # cannot guess one: ``branch=`` takes a node, not a value the guesser can
    # read off the signature. ``ColumnNotNullConstraint`` is the cheapest branch
    # that still renders, so it is what the round trip builds.
    register_special_constructor(
        "statements.ddl_table.ColumnConstraint",
        lambda d: ddl_table.ColumnConstraint(
            d, branch=ddl_table.ColumnNotNullConstraint(d), name="c"
        ),
    )
    # TABLE CHECK. The guesser's condition carries a binding ``Literal``, and a
    # DDL position refuses bind parameters outright now (there is no lift
    # pass any more -- the caller states ``inline=True`` where a position
    # cannot bind). Two columns compose the same predicate with nothing that
    # binds in it.
    register_special_constructor(
        "statements.ddl_table.TableCheckConstraint",
        lambda d: ddl_table.TableCheckConstraint(d, _column_predicate(d)),
    )
    # REFERENCES needs at least one referenced column, or the clause is not a
    # clause; the guess supplies an empty list.
    register_special_constructor(
        "statements.ddl_table.ReferencesClause",
        lambda d: ddl_table.ReferencesClause(d, Table(d, "other"), ["b"]),
    )
    # ADD CONSTRAINT takes a constraint node, and the guess supplies a bare
    # string, which reaches the formatter as ``constraint.branch`` and raises
    # AttributeError. A PRIMARY KEY table branch is the cheapest one this
    # dialect renders in that position.
    register_special_constructor(
        "statements.ddl_alter.AddTableConstraintAction",
        lambda d: AddTableConstraintAction(
            d,
            ddl_table.TableConstraint(
                d, branch=ddl_table.TablePrimaryKeyConstraint(d, ["a"])
            ),
        ),
    )
    # -- declared-result annotations: the source must be aliasable ------------
    # ``format_declared_result`` reads the alias of both the annotation and
    # the node it annotates, and the rewritten ``Literal`` is deliberately
    # not aliasable -- the guesser's Literal source reaches the formatter and
    # dies on ``source.alias``. A Column source is what the node is for: a
    # statement whose result type the caller declares, rendered unchanged
    # with the knowledge attached.
    from rhosocial.activerecord.backend.expression import declared as declared_module

    for _name in (
        "TextAnnotation",
        "NumberAnnotation",
        "IntegerAnnotation",
        "BooleanAnnotation",
        "TemporalAnnotation",
        "BinaryAnnotation",
        "UUIDAnnotation",
        "JSONAnnotation",
        "XMLAnnotation",
        "ArrayAnnotation",
    ):
        register_special_constructor(
            f"declared.{_name}",
            lambda d, _n=_name: getattr(declared_module, _n)(d, _operand(d, "c")),
        )

    # -- predicates whose operands are value nodes ---------------------------
    # The generic guess hands the operand slot a bare string, which the
    # formatter then calls ``.to_sql()`` on. Both constructors spell operands
    # the way the round-trip contract requires; ``Literal`` for the pattern
    # rather than a string, because a bare string is not a value node.
    register_special_constructor(
        "predicates.LikePredicate",
        lambda d: LikePredicate(d, LikeOperator.LIKE, Column(d, "a"), Literal(d, "%x%")),
    )
    register_special_constructor(
        "predicates.ILikePredicate",
        lambda d: ILikePredicate(d, Column(d, "a"), "%x%"),
    )
    # COMPARISON. Core normalised ``op`` through ``normalize_comparison_operator``
    # after this matrix was reconciled, and the guess hands ``Any`` the literal
    # ``"x"`` -- not a comparison word, so the constructor refuses and the class
    # drops to a quiet skip. A real operator word builds it, and the node then
    # renders through the same entry every other predicate uses.
    register_special_constructor(
        "predicates.ComparisonPredicate",
        lambda d: ComparisonPredicate(d, "=", Column(d, "a"), Literal(d, 1)),
    )

    # -- DML -----------------------------------------------------------------
    register_special_constructor(
        "statements.dml.MergeStatement",
        lambda d: dml.MergeStatement(
            d,
            target_table=_table(d),
            source=NamedRelationRef(d, Table(d, "src")),
            on_condition=_column_predicate(d),
            when_matched=[
                dml.MergeAction(
                    d,
                    dml.MergeActionType.UPDATE,
                    {"a": Literal(d, 1)},
                    _column_predicate(d),
                    "matched",
                )
            ],
        ),
    )
    register_special_constructor(
        "statements.dml.MergeAction",
        lambda d: dml.MergeAction(
            d,
            dml.MergeActionType.UPDATE,
            {"a": Literal(d, 1)},
            _column_predicate(d),
            "matched",
        ),
    )

    # -- types ---------------------------------------------------------------
    # ArrayType's element type is keyword-only now, so the guesser -- and the
    # positional call this used to be -- both miss it.
    register_special_constructor(
        "types.array.ArrayType", lambda d: __import__(
            "rhosocial.activerecord.backend.expression.types.array",
            fromlist=["ArrayType"],
        ).ArrayType(d, element_type=VarCharType(d, 10))
    )
    register_special_constructor(
        "types.ClickHouseDecimalType",
        lambda d: chexpr_types.ClickHouseDecimalType(d, precision=10, scale=2),
    )
    register_special_constructor(
        "types.ClickHouseFixedStringType",
        lambda d: chexpr_types.ClickHouseFixedStringType(d, length=8),
    )
    register_special_constructor(
        "types.ClickHouseEnum8Type",
        lambda d: chexpr_types.ClickHouseEnum8Type(d, values=[("a", 1)]),
    )
    register_special_constructor(
        "types.ClickHouseEnum16Type",
        lambda d: chexpr_types.ClickHouseEnum16Type(d, values=[("a", 1)]),
    )
    register_special_constructor(
        "types.ClickHouseTupleType",
        lambda d: chexpr_types.ClickHouseTupleType(
            d, element_types=[IntegerType(d)], element_names=["a"]
        ),
    )
    register_special_constructor(
        "types.ClickHouseArrayType",
        lambda d: chexpr_types.ClickHouseArrayType(d, element_type=IntegerType(d)),
    )
    register_special_constructor(
        "types.ClickHouseAggregateFunctionType",
        lambda d: chexpr_types.ClickHouseAggregateFunctionType(
            d, function_name="sum", arg_types=[IntegerType(d)]
        ),
    )
    register_special_constructor(
        "types.ClickHouseSimpleAggregateFunctionType",
        lambda d: chexpr_types.ClickHouseSimpleAggregateFunctionType(
            d, function_name="max", arg_types=[IntegerType(d)]
        ),
    )

    # -- datetime extracts: the field must name a DateTimeField --------------
    # Both the private shape base and the field-named extraction validate the
    # field word at construction; the guesser's "x" is not one of the six.
    # "YEAR" is, and renders EXTRACT(YEAR FROM `ts`).
    register_special_constructor(
        "datetime._ExtractBase",
        lambda d: _ExtractBase(d, "YEAR", _operand(d, "ts")),
    )
    register_special_constructor(
        "datetime.ExtractFieldExpression",
        lambda d: ExtractFieldExpression(d, "YEAR", _operand(d, "ts")),
    )

    # -- string functions whose parameters the guesser fills with bare names --
    # Every operand slot is annotated ``SQLValue`` -- a string annotation
    # naming the base every value class shares -- and the guesser falls
    # through to its bare-name fallback, so construction refuses. Real
    # operands construct, and the renderings go through the shared scalar
    # defaults ClickHouse agrees with (CHR, LEFT, RIGHT, SPACE are the
    # standard spellings this engine accepts; SUBSTRING and OVERLAY render
    # through their own entry points).
    register_special_constructor(
        "functions.string.ChrFunction",
        lambda d: ChrFunction(d, Literal(d, 65)),
    )
    register_special_constructor(
        "functions.string.LeftFunction",
        lambda d: LeftFunction(d, _operand(d, "name"), Literal(d, 1)),
    )
    register_special_constructor(
        "functions.string.RightFunction",
        lambda d: RightFunction(d, _operand(d, "name"), Literal(d, 1)),
    )
    register_special_constructor(
        "functions.string.SpaceFunction",
        lambda d: SpaceFunction(d, Literal(d, 3)),
    )
    register_special_constructor(
        "functions.string.SubstringExpression",
        lambda d: SubstringExpression(
            d, _operand(d, "name"), Literal(d, 1), Literal(d, 2)
        ),
    )
    register_special_constructor(
        "functions.string.OverlayExpression",
        lambda d: OverlayExpression(
            d,
            _operand(d, "name"),
            _operand(d, "replacement"),
            Literal(d, 1),
            Literal(d, 2),
        ),
    )

    # -- admin selectors: the enums validate their words at construction now --
    # The guesser fills a required enum-annotated parameter with "x", which
    # the constructor refuses once it normalises (the word must name a
    # member). Real members construct, and the renderings refuse on their own
    # -- this dialect spells no RESET / HANDLER at all -- which the pinned
    # renders above assert.
    register_special_constructor(
        "admin.ClickHouseResetExpression",
        lambda d: admin_module.ClickHouseResetExpression(d, admin_module.ResetOption.MASTER),
    )
    register_special_constructor(
        "admin.ClickHouseHandlerReadExpression",
        lambda d: admin_module.ClickHouseHandlerReadExpression(
            d, Table(d, "t"), admin_module.HandlerReadMode.FIRST
        ),
    )

    # -- ClickHouse partitions ----------------------------------------------
    # The MySQL-style declarative partitioning family was deleted outright:
    # ClickHouse declares partitioning as an arbitrary expression in CREATE
    # TABLE, not as PARTITION ... VALUES statements. What remains are the
    # three system.parts-addressed statements, each taking the table name
    # and the partition id, and each rendering through one shared base.
    for _name in (
        "ClickHouseDropPartitionExpression",
        "ClickHouseDetachPartitionExpression",
        "ClickHouseAttachPartitionExpression",
    ):
        register_special_constructor(
            f"partition.{_name}",
            lambda d, _n=_name: getattr(partition, _n)(d, "t", "p2024"),
        )

    # -- ClickHouse maintenance, routines, materialized views ----------------
    for _name in (
        "ClickHouseAnalyzeTableExpression",
        "ClickHouseCheckTableExpression",
        "ClickHouseChecksumTableExpression",
        "ClickHouseOptimizeTableExpression",
        "ClickHouseRepairTableExpression",
        "ClickHouseTableMaintenanceExpression",
    ):
        register_special_constructor(
            f"maintenance.{_name}",
            lambda d, _n=_name: getattr(maintenance, _n)(d, [_table(d)]),
        )
    register_special_constructor(
        "routine.ClickHouseRoutineExpression",
        lambda d: routine.ClickHouseRoutineExpression(d, Procedure(d, "proc")),
    )
    register_special_constructor(
        "routine.ClickHouseCreateProcedureExpression",
        lambda d: routine.ClickHouseCreateProcedureExpression(d, Procedure(d, "proc")),
    )
    register_special_constructor(
        "routine.ClickHouseDropProcedureExpression",
        lambda d: routine.ClickHouseDropProcedureExpression(d, Procedure(d, "proc")),
    )
    register_special_constructor(
        "routine.ClickHouseCreateFunctionExpression",
        lambda d: routine.ClickHouseCreateFunctionExpression(
            d, Function(d, "fn"), returns="integer"
        ),
    )
    register_special_constructor(
        "routine.ClickHouseDropFunctionExpression",
        lambda d: routine.ClickHouseDropFunctionExpression(d, Function(d, "fn")),
    )
    register_special_constructor(
        "routine.ClickHouseCallExpression",
        lambda d: routine.ClickHouseCallExpression(d, Procedure(d, "proc")),
    )
    register_special_constructor(
        "materialized_view.ClickHouseCreateMaterializedViewExpression",
        lambda d: materialized_view.ClickHouseCreateMaterializedViewExpression(
            d, MaterializedView(d, "mv"), "SELECT 1", to_table=Table(d, "target")
        ),
    )
    register_special_constructor(
        "materialized_view.ClickHouseModifyMaterializedViewRefreshExpression",
        lambda d: materialized_view.ClickHouseModifyMaterializedViewRefreshExpression(
            d,
            MaterializedView(d, "mv"),
            # The schedule is an expression node now, so it binds to the
            # dialect it renders through -- first argument, like every node.
            materialized_view.ClickHouseRefreshSchedule(d, every="1 HOUR"),
        ),
    )

    # -- ClickHouse columns, DML, renames ------------------------------------
    register_special_constructor(
        "column.ClickHouseColumnDefinition",
        lambda d: chexpr_column.ClickHouseColumnDefinition(
            d, "id", IntegerType(d)
        ),
    )
    register_special_constructor(
        "dml.ClickHouseInsertExpression",
        lambda d: chexpr_dml.ClickHouseInsertExpression(
            d, into=_table(d), source=dml.ValuesSource(d, [[Literal(d, 1)]])
        ),
    )
    register_special_constructor(
        "alter_column.ClickHouseAddColumnAction",
        # ``after`` is given a value on purpose: it is a declared constructor
        # parameter, so the artifact has to carry it. The render half -- that
        # the clause reaches the SQL -- is test_add_column_action.py's job.
        lambda d: alter_column.ClickHouseAddColumnAction(
            d, _integer_column(d), after="name"
        ),
    )
    register_special_constructor(
        "rename_table.ClickHouseRenameTableExpression",
        lambda d: rename_table.ClickHouseRenameTableExpression(d, [("a", "b")]),
    )
    # CUSTOM. Its ``raw`` slot exists to carry the SQL type name and defaults
    # to the empty string, which the filler skips and the class refuses while
    # constructing. Handed a real name it builds -- and then the dialect
    # refuses it, which is what the existing LEGITIMATE_NON_RENDERS pin below
    # asserts. A constructor rather than a skip, so the pin has something to
    # assert against. ``raw`` is keyword-only now, so the name is spelled.
    def _custom_type(dialect):
        from rhosocial.activerecord.backend.expression.types.custom import (
            CustomType,
        )

        return CustomType(dialect, raw="String")

    register_special_constructor("types.custom.CustomType", _custom_type)


register_specials()


# ---------------------------------------------------------------------------
# Lists that cannot grow or shrink silently
# ---------------------------------------------------------------------------

#: Classes the generic introspective constructor cannot build.
#:
#: Each is a real coverage gap, named here so it is visible rather than lost.
#: :func:`test_unconstructible_list_is_exact` pins the tuple in both directions,
#: so a class that gains a constructor fails here until this entry is removed, and
#: a class that starts failing to build fails here too -- neither can become a
#: quiet skip.
#:
#: The registered constructors above bring this down to four. What remains is
#: either a shape the introspective guess cannot satisfy -- keyword-only
#: parameters hidden behind defaulted positionals -- or a class that needs a
#: renderable member to exist at all. Registering a constructor for any of them
#: is the way to retire an entry.
#:
#: A second cause is a misread annotation, and that one belongs to testsuite rather
#: than here: a parameter typed ``Sequence[X]`` was read as the Sequence *object*
#: because the alias' own name carries the word. That retired four XML entries
#: once the harness was fixed, which is the better outcome -- no exemption at all.
#:
#: Sorted, because the integrity test compares this against a sorted tuple of
#: what it observes. The reasons below are grouped by cause.
UNCONSTRUCTIBLE = (
    # ALTER CONSTRAINT. ``name`` and ``constraint_type`` sit behind defaulted
    # positionals and are keyword-only, so the introspective constructor skips
    # them and the class refuses an incomplete action.
    "rhosocial.activerecord.backend.expression.statements.ddl_alter.AlterConstraintAction",
    # VALIDATE CONSTRAINT used to sit here with the same shape as
    # AlterConstraint. Core moved ``constraint_name`` into the positional
    # required slot, so the guesser's "x" builds it now -- and the built
    # instance is what the graph of pinned renders asserts against.
    # ADD DOMAIN CHECK. Widens a SQLPredicate into a DomainCheckConstraint and
    # needs one; the guess supplies a bare comparison whose literal would have
    # to render as a bind parameter, which DDL cannot carry.
    "rhosocial.activerecord.backend.expression.statements.ddl_domain.AddDomainCheckAction",
    # The three UUID nodes refuse in __init__, not in to_sql(): ClickHouse
    # spells no UUID SQL, so the answer is the same for every argument and no
    # registered constructor can change it. Measured with a valid ``which`` --
    # an invalid one raises ValueError first and hides the dialect's answer.
    "rhosocial.activerecord.backend.expression.uuid.UUIDCastFunction",
    "rhosocial.activerecord.backend.expression.uuid.UUIDConstantExpression",
    "rhosocial.activerecord.backend.expression.uuid.UUIDGenerationExpression",
)
# Four XML classes used to be entries here, and retiring them is what the pin
# demands rather than a loss of coverage: each named a gap that no longer exists.
# Their list-valued parameters are annotated ``Sequence[XMLAttribute]``,
# ``Sequence[BaseExpression]``, ``Sequence[XMLForestItem]`` and
# ``Sequence[XMLTableColumn]``, and the introspective constructor read that alias'
# own name -- "Sequence" -- as the catalogue object Sequence, handing a directory
# object to a parameter asking for a list. testsuite now decides a parameterised
# alias before it tests for a relation name, so the constructor gets [] and builds
# each class. They construct but still do not render -- ClickHouse mixes in no
# SQL/XML formatter at all -- so they are pinned by name in LEGITIMATE_NON_RENDERS
# below instead, which is the stronger position: the gap is recorded against the
# formatter it is actually about.
#
# ENUM TYPE used to be an entry here too, with a keyword-only ``values`` list the
# constructor skipped. Core moved the members into the constructor's reach, so it
# builds now -- and renders into the type map's refusal, which is the
# LEGITIMATE_NON_RENDERS pin the constructed instance makes assertable.


#: Classes that construct but cannot render, for a reason belonging to their own
#: tree rather than to a defect. Each entry pins the exception type and a message
#: fragment, so a class that starts failing for a *different* reason fails here
#: instead of passing quietly.
#:
#: Three kinds of entry live here, and the grouping below is what makes the table
#: readable: a base that names no formatter at all, a dialect that has no formatter
#: for a feature, and a type whose generic name ClickHouse does not spell.
_NO_FORMATTER = "does not declare its dialect formatting method name"


def _no_dialect_formatter(format_method: str) -> str:
    """The fragment ``to_sql()`` says when the dialect has no such formatter.

    ``BaseExpression.to_sql()`` raises ``UnsupportedFeatureError`` naming the
    method it wanted, so pinning ``"format_pivot"`` here records *which*
    formatter is absent -- the blanket ``UnsupportedFeatureError`` branch in
    :func:`assert_sql_roundtrip_classified` already allows the type on its own.

    The name is passed in literally at each call site rather than read off the
    class on purpose: if a class changed the formatter it dispatches on, the
    fragment here would stop matching the message and the entry would fail
    instead of drifting along with it.
    """
    return f"does not support the '{format_method}' statement"


LEGITIMATE_NON_RENDERS = {
    # ---- bases that name an expression category, not a renderable thing ----
    # Each is a base class that deliberately declares no ``format_method``, so
    # ``to_sql()`` reports that there is nothing to dispatch. They are not
    # ``inspect.isabstract`` -- they are concrete enough to construct -- so the
    # walk keeps them, and each is pinned to its exact message so a base that
    # started rendering fails here instead of passing quietly.
    "rhosocial.activerecord.backend.expression.bases.SQLPredicate": (
        NotImplementedError,
        _NO_FORMATTER,
    ),
    "rhosocial.activerecord.backend.expression.bases.SQLValue": (
        NotImplementedError,
        _NO_FORMATTER,
    ),
    # The column-definition clause base. Its subclasses each name their own
    # formatter; the base names only what every column clause has in common.
    "rhosocial.activerecord.backend.expression.statements.ddl_table.ColumnClause": (
        NotImplementedError,
        _NO_FORMATTER,
    ),
    # The constraint-branch bases, new with core's two-level constraint nodes.
    # A branch names which alternative of the constraint production this is;
    # rendering the branch is the clause dispatcher's job, so the bases name no
    # formatter of their own and each concrete branch overrides ``format_method``.
    "rhosocial.activerecord.backend.expression.statements.ddl_table.ColumnConstraintBranch": (
        NotImplementedError,
        _NO_FORMATTER,
    ),
    "rhosocial.activerecord.backend.expression.statements.ddl_table.TableConstraintBranch": (
        NotImplementedError,
        _NO_FORMATTER,
    ),
    "rhosocial.activerecord.backend.expression.datetime._TemporalValue": (
        NotImplementedError,
        _NO_FORMATTER,
    ),
    # The declared-result shape base. It names ``format_declared_result`` and
    # the dialect has one, but the base carries none of the surface state the
    # formatter reads (``alias`` lives on the DeclaredValueType half); the ten
    # concrete annotations each render through the source they annotate.
    "rhosocial.activerecord.backend.expression.declared._Annotation": (
        AttributeError,
        "no attribute 'alias'",
    ),
    "rhosocial.activerecord.backend.expression.introspection.IntrospectionExpression": (
        NotImplementedError,
        _NO_FORMATTER,
    ),
    # The shared base of the three ``ALTER TABLE ... PARTITION ID`` clauses.
    # Each concrete subclass declares its own ``format_method``; the base names
    # the convention and refuses, which is the same answer as the category
    # bases above rather than a construction gap.
    "rhosocial.activerecord.backend.impl.clickhouse.expression.partition._ClickHousePartitionIdExpression": (
        NotImplementedError,
        "must declare its format_method property",
    ),
    # An expression-category base whose concrete members each name their own
    # formatter: an ALTER TABLE action, an INSERT row source, a transaction step,
    # and the roots of the object, type and routine trees.
    "rhosocial.activerecord.backend.expression.statements.ddl_alter.AlterTableAction": (
        NotImplementedError,
        _NO_FORMATTER,
    ),
    "rhosocial.activerecord.backend.expression.statements.dml.InsertDataSource": (
        NotImplementedError,
        _NO_FORMATTER,
    ),
    "rhosocial.activerecord.backend.expression.objects.base.SchemaObject": (
        NotImplementedError,
        _NO_FORMATTER,
    ),
    "rhosocial.activerecord.backend.expression.objects.relation.RelationObject": (
        NotImplementedError,
        _NO_FORMATTER,
    ),
    "rhosocial.activerecord.backend.expression.objects.routine.RoutineObject": (
        NotImplementedError,
        _NO_FORMATTER,
    ),
    "rhosocial.activerecord.backend.expression.objects.type_.TypeObject": (
        NotImplementedError,
        _NO_FORMATTER,
    ),
    "rhosocial.activerecord.backend.expression.transaction.TransactionExpression": (
        NotImplementedError,
        _NO_FORMATTER,
    ),
    # Introspection query bases: each concrete subclass names its own
    # ``format_*_query``. The message differs from the group above only in
    # spelling, which is why each entry pins its own fragment.
    "rhosocial.activerecord.backend.expression.introspection.TableInfoExpression": (
        NotImplementedError,
        "Subclass must implement format_table_info_query",
    ),
    # The ClickHouse roots, same shape as the core ones above: a base holding
    # what every subclass shares, with no formatting method of its own.
    "rhosocial.activerecord.backend.impl.clickhouse.expression.routine.ClickHouseRoutineExpression": (
        NotImplementedError,
        _NO_FORMATTER,
    ),
    "rhosocial.activerecord.backend.impl.clickhouse.expression.show.ShowExpression": (
        NotImplementedError,
        "Subclasses must implement to_sql() method",
    ),
    "rhosocial.activerecord.backend.impl.clickhouse.expression.table_statement.ClickHouseBaseTableStatement": (
        NotImplementedError,
        _NO_FORMATTER,
    ),
    # The root of the row-source tree and the root of the type tree, both
    # structurally incomplete. No concrete source renders through
    # ``format_table_source`` -- each concrete subclass names its own formatter
    # instead -- so ClickHouse declaring no ``format_table_source`` is the dialect
    # reporting a capability it never claimed, the same thing the XML and graph
    # groups below report, and it says so in the same spelling. The type root is
    # the other kind: every concrete type declares its own generic ``name`` for
    # ``format_data_type`` to dispatch on, and this one declares none, so there is
    # no name to look up at all. It now says so in the dispatch's own spelling --
    # "does not support the generic type None (no format_data_type_None)" -- the
    # same message every other undeclared name produces, so the pin follows the
    # class from its own refusal to the generic one. TypeError rather than
    # UnsupportedFeatureError, because there the class is incomplete rather than
    # the dialect being unable.
    "rhosocial.activerecord.backend.expression.sources.base.TableSource": (
        UnsupportedFeatureError,
        _no_dialect_formatter("format_table_source"),
    ),
    "rhosocial.activerecord.backend.expression.types._base.DataType": (
        TypeError,
        "does not support the generic type None (no format_data_type_None)",
    ),

    # ---- core features ClickHouse does not declare a protocol for ---------
    # Each raises UnsupportedFeatureError naming the formatter it wanted, which
    # is how the tree reports a capability the dialect never declared. ClickHouse's
    # dialect does not mix in the pivot, ILIKE, COMMENT, schema-DDL or SQL/XML
    # mixins, so ``isinstance(dialect, PivotSupport)`` and its siblings are all
    # False -- a caller is expected to ask first, and this records what happens
    # when one does not. Pinned rather than fixed because the feature genuinely
    # is not ClickHouse's; adding a formatter to render SQL the server would
    # reject would be worse than the refusal.
    #
    # These twenty-three, plus ``TableSource`` above, were this table's reason to
    # exist -- twenty-four classes in all. Before ``to_sql()`` learned to tell a
    # missing formatter from a broken one, this dialect's gaps came out as
    # ``AttributeError`` while every other backend reported
    # ``UnsupportedFeatureError`` through its capability probes -- the same gap in
    # two spellings, so a caller could not tell "ClickHouse does not have this"
    # from "this backend is broken". Core made it one spelling, and these entries
    # now say so while naming the specific formatter that is missing.
    "rhosocial.activerecord.backend.expression.pivot.Pivot": (
        UnsupportedFeatureError,
        _no_dialect_formatter("format_pivot"),
    ),
    "rhosocial.activerecord.backend.expression.pivot.Unpivot": (
        UnsupportedFeatureError,
        _no_dialect_formatter("format_unpivot"),
    ),
    "rhosocial.activerecord.backend.expression.predicates.ILikePredicate": (
        UnsupportedFeatureError,
        _no_dialect_formatter("format_ilike_predicate"),
    ),
    "rhosocial.activerecord.backend.expression.statements.ddl_comment.CommentOnStatement": (
        UnsupportedFeatureError,
        _no_dialect_formatter("format_comment_statement"),
    ),
    # ClickHouse has a database and no inner schema, so CREATE/DROP SCHEMA is
    # not in its grammar at all. These two are the direct consequence of that
    # decision, which is stated once in the namespace mixin.
    "rhosocial.activerecord.backend.expression.statements.ddl_schema.CreateSchemaStatement": (
        UnsupportedFeatureError,
        _no_dialect_formatter("format_create_schema_statement"),
    ),
    "rhosocial.activerecord.backend.expression.statements.ddl_schema.DropSchemaStatement": (
        UnsupportedFeatureError,
        _no_dialect_formatter("format_drop_schema_statement"),
    ),
    # SEQUENCE. ClickHouse has no sequence object, so these three are the same
    # declared gap as the schema rows above: the base list names no formatter for
    # them. They rendered until core's SequenceMixin was taken out of that list,
    # and what they rendered was the defect -- the inherited formatters never
    # consult supports_sequence(), so "CREATE SEQUENCE `s` NO CYCLE" came back out
    # of a dialect that had itself declared the feature absent. Naming a sequence
    # is a separate capability and is untouched: SequenceNameMixin stays, so
    # Sequence(dialect, "s").to_sql() still renders.
    "rhosocial.activerecord.backend.expression.statements.ddl_sequence.CreateSequenceStatement": (
        UnsupportedFeatureError,
        _no_dialect_formatter("format_create_sequence_statement"),
    ),
    "rhosocial.activerecord.backend.expression.statements.ddl_sequence.DropSequenceStatement": (
        UnsupportedFeatureError,
        _no_dialect_formatter("format_drop_sequence_statement"),
    ),
    "rhosocial.activerecord.backend.expression.statements.ddl_sequence.AlterSequenceStatement": (
        UnsupportedFeatureError,
        _no_dialect_formatter("format_alter_sequence_statement"),
    ),
    # SQL/XML. Not mixed in; thirteen XML-family expressions each want their
    # own formatter. The last four were UNCONSTRUCTIBLE until the harness
    # stopped reading ``Sequence[X]`` as the Sequence catalogue object; they
    # now build with an empty item list and fail on the missing formatter,
    # which is the gap being named rather than worked around.
    "rhosocial.activerecord.backend.expression.xml.XMLAggExpression": (
        UnsupportedFeatureError,
        _no_dialect_formatter("format_xmlagg_expression"),
    ),
    "rhosocial.activerecord.backend.expression.xml.XMLAttributesExpression": (
        UnsupportedFeatureError,
        _no_dialect_formatter("format_xmlattributes_expression"),
    ),
    "rhosocial.activerecord.backend.expression.xml.XMLCommentExpression": (
        UnsupportedFeatureError,
        _no_dialect_formatter("format_xmlcomment_expression"),
    ),
    "rhosocial.activerecord.backend.expression.xml.XMLConcatExpression": (
        UnsupportedFeatureError,
        _no_dialect_formatter("format_xmlconcat_expression"),
    ),
    "rhosocial.activerecord.backend.expression.xml.XMLElementExpression": (
        UnsupportedFeatureError,
        _no_dialect_formatter("format_xmlelement_expression"),
    ),
    "rhosocial.activerecord.backend.expression.xml.XMLExistsPredicate": (
        UnsupportedFeatureError,
        _no_dialect_formatter("format_xmlexists_predicate"),
    ),
    "rhosocial.activerecord.backend.expression.xml.XMLForestExpression": (
        UnsupportedFeatureError,
        _no_dialect_formatter("format_xmlforest_expression"),
    ),
    "rhosocial.activerecord.backend.expression.xml.XMLPIExpression": (
        UnsupportedFeatureError,
        _no_dialect_formatter("format_xmlpi_expression"),
    ),
    "rhosocial.activerecord.backend.expression.xml.XMLParseExpression": (
        UnsupportedFeatureError,
        _no_dialect_formatter("format_xmlparse_expression"),
    ),
    "rhosocial.activerecord.backend.expression.xml.XMLQueryExpression": (
        UnsupportedFeatureError,
        _no_dialect_formatter("format_xmlquery_expression"),
    ),
    "rhosocial.activerecord.backend.expression.xml.XMLRootExpression": (
        UnsupportedFeatureError,
        _no_dialect_formatter("format_xmlroot_expression"),
    ),
    "rhosocial.activerecord.backend.expression.xml.XMLSerializeExpression": (
        UnsupportedFeatureError,
        _no_dialect_formatter("format_xmlserialize_expression"),
    ),
    "rhosocial.activerecord.backend.expression.xml.XMLTableExpression": (
        UnsupportedFeatureError,
        _no_dialect_formatter("format_xmltable_expression"),
    ),
    # SQL/PGQ. ClickHouse mixes in GraphMixin, whose MATCH formatters exist and
    # refuse with UnsupportedFeatureError; the GRAPH_TABLE and CREATE/DROP/ALTER
    # PROPERTY GRAPH half lives in GraphTableMixin, which is not mixed in. These
    # are the GRAPH_TABLE half plus the three graph sub-clauses it needs, so the
    # graph tree reports its two halves the same way it always did.
    "rhosocial.activerecord.backend.expression.graph.GraphTableExpression": (
        UnsupportedFeatureError,
        _no_dialect_formatter("format_graph_table_expression"),
    ),
    "rhosocial.activerecord.backend.expression.graph.VertexTable": (
        UnsupportedFeatureError,
        _no_dialect_formatter("format_vertex_table"),
    ),
    # The edge-table definition of CREATE PROPERTY GRAPH, the same declared
    # gap as the graph rows around it: the DDL half of SQL/PGQ lives in
    # mixins this dialect does not compose. (The clause core used to call
    # ``EdgeTable`` is ``EdgeTableDefinition`` now -- one name, two contracts,
    # and the relation object kept the old one.)
    "rhosocial.activerecord.backend.expression.graph.EdgeTableDefinition": (
        UnsupportedFeatureError,
        _no_dialect_formatter("format_edge_table_definition"),
    ),
    "rhosocial.activerecord.backend.expression.graph.ColumnsClause": (
        UnsupportedFeatureError,
        _no_dialect_formatter("format_graph_columns_clause"),
    ),
    "rhosocial.activerecord.backend.expression.graph.TablePropertiesClause": (
        UnsupportedFeatureError,
        _no_dialect_formatter("format_table_properties_clause"),
    ),
    "rhosocial.activerecord.backend.expression.graph.CreatePropertyGraphStatement": (
        UnsupportedFeatureError,
        _no_dialect_formatter("format_create_property_graph_statement"),
    ),
    "rhosocial.activerecord.backend.expression.graph.DropPropertyGraphStatement": (
        UnsupportedFeatureError,
        _no_dialect_formatter("format_drop_property_graph_statement"),
    ),
    "rhosocial.activerecord.backend.expression.graph.AlterPropertyGraphStatement": (
        UnsupportedFeatureError,
        _no_dialect_formatter("format_alter_property_graph_statement"),
    ),

    # ---- core types ClickHouse has no equivalent for ----------------------
    # Each dispatches on a generic type name ClickHouse declares no formatter
    # for, so the type system reports the gap. ClickHouse spells these
    # differently or not at all: there is no BINARY, no JSONB (its JSON type is
    # ``JSON``), and no ``INT`` -- ClickHouse's integers are sized and signed
    # explicitly. A real gap in the type map, not a defect in the class.
    "rhosocial.activerecord.backend.expression.types.binary.BinaryType": (
        TypeError,
        "does not support the generic type 'binary'",
    ),
    "rhosocial.activerecord.backend.expression.types.binary.VarBinaryType": (
        TypeError,
        "does not support the generic type 'varbinary'",
    ),
    "rhosocial.activerecord.backend.expression.types.custom.CustomType": (
        TypeError,
        "does not support the generic type 'custom'",
    ),
    "rhosocial.activerecord.backend.expression.types.datetime_.IntervalType": (
        TypeError,
        "does not support the generic type 'interval'",
    ),
    # ENUM. ClickHouse's own enum types are sized and signed
    # (ClickHouseEnum8Type / ClickHouseEnum16Type, registered above); the
    # generic name has no formatter here, so the type map reports the
    # substitute. It constructs -- the members are in the constructor's
    # reach now -- and the constructed instance is what makes this pin
    # assertable.
    "rhosocial.activerecord.backend.expression.types.enum_.EnumType": (
        TypeError,
        "does not support the generic type 'enum'",
    ),
    "rhosocial.activerecord.backend.expression.types.datetime_.TimeTzType": (
        TypeError,
        "does not support the generic type 'timetz'",
    ),
    "rhosocial.activerecord.backend.expression.types.datetime_.TimestampTzType": (
        TypeError,
        "does not support the generic type 'timestamptz'",
    ),
    "rhosocial.activerecord.backend.expression.types.json_.JsonBType": (
        TypeError,
        "does not support the generic type 'jsonb'",
    ),
    "rhosocial.activerecord.backend.expression.types.xml_.XmlType": (
        TypeError,
        "does not support the generic type 'xml'",
    ),
}


# ---------------------------------------------------------------------------
# Classes whose own tree refuses their round-trip
# ---------------------------------------------------------------------------
#
# A fourth verdict, needed by core ``679d9817``: the artifact is plain JSON
# now, and the contract (组织规则 §10) puts one conversion in one place --
# "构造函数接受该参数的序列化形式并归一成宿主类型；反序列化器只按名字传参".
# Every entry below is a class whose *own* tree breaks that contract, so the
# restore is refused or comes back as something the original never was. The
# reason belongs to the tree that defines the class, not to this backend.
#
# Each entry pins the failing channels, and each channel pins one of three
# shapes:
#
# * ``("raises", Exc, fragment)`` -- the channel refuses outright.
# * ``("word",)`` -- the restore succeeds but is type-lossy: a
#   ``(str, Enum)`` member comes back as its plain word (the JSON channel
#   writes a member's underlying string; the XML channel writes
#   ``str(member)``, which equals the word when the enum sets
#   ``__str__ = str.__str__``). The constructor stores it raw instead of
#   normalising, so the restored params differ in type and agree in value.
#   Asserted both ways: strictly different (so the pin stays load-bearing --
#   a core fix makes this entry stale) and equal under member-≡-word
#   normalisation (so the loss is exactly the spelling, nothing else moved).
# * ``("enum-str",)`` -- the same, but the enum lacks ``__str__ =
#   str.__str__``, so the XML channel writes ``"EnumClass.MEMBER"``: neither
#   the member nor its word. Asserted equal under member-≡-``Enum.__str__``
#   normalisation, which pins the corrupted spelling itself -- the moment
#   core spells the enum properly, this entry goes.
#
# A channel an entry does not name must still round-trip; that is asserted per
# class, so a pin can never quietly swallow a whole class.
LEGITIMATE_NON_ROUNDTRIPS: Dict[str, Dict[str, object]] = {
    # -- the datetime family: ``DateTimeField`` / ``IntervalUnit`` were
    #    ``(str, Enum)`` without ``__str__ = str.__str__``, so the XML
    #    channel wrote ``"DateTimeField.YEAR"`` and the constructor's own
    #    normaliser refused it. Core gave the nine families the missing
    #    ``__str__``, so the XML channel now writes "year" / "day" and all
    #    three channels round-trip exactly. No rows left here; the block
    #    stays to say which family this used to be about.
    # -- ``mode`` is declared ``CreateTableCloneMode`` with a member default;
    #    the JSON and XML channels write the word (``"CLONE"``), and the
    #    constructor demands the member -- the ``isinstance`` half of the
    #    contract without the normalise half.
    "rhosocial.activerecord.backend.expression.statements.ddl_table.CreateTableCloneStatement": {
        "channels": {
            "json": ("raises", TypeError, "mode must be a CreateTableCloneMode"),
            "xml": ("raises", TypeError, "mode must be a CreateTableCloneMode"),
        },
    },
    # -- ``options`` is a ``ViewOptions`` *instance*, a plain class in a
    #    parameter slot: the codec writes nodes, scalars, and containers of
    #    those two, and a bare ``options or ViewOptions()`` puts one in every
    #    CREATE VIEW. Serialization refuses before any round-trip can start.
    "rhosocial.activerecord.backend.expression.statements.ddl_view.CreateViewStatement": {
        "channels": {
            "dict": ("raises", TypeError, "ViewOptions is not one of the value kinds"),
            "json": ("raises", TypeError, "ViewOptions is not one of the value kinds"),
            "xml": ("raises", TypeError, "ViewOptions is not one of the value kinds"),
        },
    },
    # -- ``ColumnsClause`` carries ``GraphColumn`` instances, another plain
    #    class in a parameter slot (GraphTableExpression holds the clause, so
    #    the refusal propagates to it too; ColumnsClause itself is only built
    #    with a Literal child here and travels fine).
    "rhosocial.activerecord.backend.expression.graph.GraphTableExpression": {
        "channels": {
            "dict": ("raises", TypeError, "GraphColumn is not one of the value kinds"),
            "json": ("raises", TypeError, "GraphColumn is not one of the value kinds"),
            "xml": ("raises", TypeError, "GraphColumn is not one of the value kinds"),
        },
    },
    # -- ``storage_type`` defaults to a ``GeneratedColumnType`` member. It was
    #    a plain (non-str) enum the artifact refused outright; core made it a
    #    str enum, so the writer carries it and the dict channel passes the
    #    member through untouched. JSON and XML hand back the word, which the
    #    constructor stores raw -- value-faithful, type-lossy.
    "rhosocial.activerecord.backend.expression.statements.ddl_table.ColumnGeneratedConstraint": {
        "channels": {"json": ("word",), "xml": ("word",)},
    },
    # -- ``on_delete`` / ``on_update`` default to ``ReferentialAction``
    #    members. Same shape as ``storage_type`` above: core made the enum a
    #    str enum, the writer carries it, the dict channel keeps the member,
    #    and JSON / XML come back with the word.
    "rhosocial.activerecord.backend.expression.statements.ddl_table.ForeignKeyConstraint": {
        "channels": {"json": ("word",), "xml": ("word",)},
    },
    # -- the word-form family: ``(str, Enum)`` members spelled properly
    #    (``__str__ = str.__str__``), carried by constructors that store the
    #    serialized word raw. The JSON and XML channels each hand back the
    #    word; the restore is value-faithful and type-lossy.
    "rhosocial.activerecord.backend.expression.graph.GraphEdge": {
        "channels": {"json": ("word",), "xml": ("word",)},
    },
    "rhosocial.activerecord.backend.expression.statements.ddl_database.AlterDatabaseStatement": {
        "channels": {"json": ("word",), "xml": ("word",)},
    },
    "rhosocial.activerecord.backend.expression.statements.ddl_trigger.CreateTriggerStatement": {
        "channels": {"json": ("word",), "xml": ("word",)},
    },
    "rhosocial.activerecord.backend.expression.statements.dml.MergeAction": {
        "channels": {"json": ("word",), "xml": ("word",)},
    },
    "rhosocial.activerecord.backend.expression.statements.dml.MergeStatement": {
        # The loss sits one level down, in the ``MergeAction`` child.
        "channels": {"json": ("word",), "xml": ("word",)},
    },
    # -- ``XMLParseDocumentType`` / ``XMLSerializeDocumentType`` are
    #    ``(str, Enum)`` and now set ``__str__ = str.__str__`` too, so both
    #    JSON and XML write the word ("DOCUMENT") and the constructor stores
    #    it raw: value-faithful, type-lossy on both channels.
    "rhosocial.activerecord.backend.expression.xml.XMLParseExpression": {
        "channels": {"json": ("word",), "xml": ("word",)},
    },
    "rhosocial.activerecord.backend.expression.xml.XMLSerializeExpression": {
        "channels": {"json": ("word",), "xml": ("word",)},
    },
}


# ---------------------------------------------------------------------------
# The dispatch gap: a missing formatter is a decision, not an omission
# ---------------------------------------------------------------------------
#
# ``to_sql()`` reports a dialect that names no formatter for a class through
# the same ``UnsupportedFeatureError`` a capability probe uses, so the type
# alone cannot say "this backend never wired the feature in". The frame the
# dispatch puts around the method name can, and it is the only place in the
# tree that opens it -- see :func:`_dispatched_formatter`.

#: The two ends of the frame ``to_sql()`` puts around a formatting method name
#: in the ``feature_name`` of the ``UnsupportedFeatureError`` it raises for a
#: dialect that has no such formatter.
_DISPATCH_FEATURE_PREFIX = "the '"
_DISPATCH_FEATURE_SUFFIX = "' statement"


def _dispatched_formatter(exc):
    """The formatting method *exc* says the dialect does not have, or ``None``.

    ``None`` means *exc* is not the dispatch reporting a missing formatter --
    it is a probe inside a formatter that refused a feature, which is the
    ``"unsupported"`` branch and needs no row anywhere.

    Args:
        exc: An :class:`UnsupportedFeatureError` raised out of ``to_sql()``.

    Returns:
        The method name out of the ``feature_name`` frame, or ``None`` when
        *exc* came from a probe rather than from the dispatch.
    """
    feature = exc.feature_name
    if not feature.startswith(_DISPATCH_FEATURE_PREFIX):
        return None
    if not feature.endswith(_DISPATCH_FEATURE_SUFFIX):
        return None
    method = feature[len(_DISPATCH_FEATURE_PREFIX) : len(feature) - len(_DISPATCH_FEATURE_SUFFIX)]
    return method if method else None


#: Formatters ClickHouse declares no implementation of, grouped by the feature
#: that is absent, each group naming every method the matrix's classes need.
#:
#: A class needing one of these fails with ``UnsupportedFeatureError`` naming
#: the method it wanted, and :func:`assert_sql_roundtrip_classified` asserts
#: that method is a row here. :meth:`TestMatrixIntegrity.\
#: test_unmodelled_formatter_list_is_exact` pins the table in both directions:
#: a formatter that starts existing moves its classes out of the table and the
#: pin fails until the entry goes, and a class that starts needing a method
#: outside the table fails outright instead of passing as "unsupported".
#:
#: These are not defects: they are features ClickHouse does not have, which the
#: shared renderer reports by naming the method it could not find. The grouping
#: is the point -- "31 methods" says nothing, "no SQL/XML, no property-graph
#: DDL, no schema, no sequence, no COMMENT ON, no ILIKE, no PIVOT" says what
#: the dialect is. ClickHouse does spell the new pad/repeat/trim nodes -- LPAD,
#: RPAD and REPEAT natively, and TRIM through ClickHouseTrimMixin's
#: ``trimBoth``/``trimLeft``/``trimRight`` -- so none of the four appears here.
UNMODELLED_FORMATTERS = {
    "SQL/XML (ClickHouse mixes in no SQL/XML formatter at all)": (
        "format_passing_clause",
        "format_xmlagg_expression",
        "format_xmlattributes_expression",
        "format_xmlcomment_expression",
        "format_xmlconcat_expression",
        "format_xmlelement_expression",
        "format_xmlexists_predicate",
        "format_xmlforest_expression",
        "format_xmlpi_expression",
        "format_xmlparse_expression",
        "format_xmlquery_expression",
        "format_xmlroot_expression",
        "format_xmlserialize_expression",
        "format_xmltable_expression",
    ),
    "SQL/PGQ (ClickHouse mixes in GraphMixin, whose MATCH formatters exist "
    "and refuse; the GRAPH_TABLE half lives in GraphTableMixin, which is not "
    "mixed in)": (
        "format_graph_table_expression",
        "format_vertex_table",
        "format_edge_table_definition",
        "format_graph_columns_clause",
        "format_table_properties_clause",
        "format_create_property_graph_statement",
        "format_drop_property_graph_statement",
        "format_alter_property_graph_statement",
    ),
    "COMMENT ON (the dialect mixes in no comment-DDL mixin; ClickHouse "
    "comments ride on table and column definitions)": ("format_comment_statement",),
    "SCHEMA (ClickHouse has a database and no inner schema, so CREATE/DROP "
    "SCHEMA is not in its grammar at all)": (
        "format_create_schema_statement",
        "format_drop_schema_statement",
    ),
    "SEQUENCE (ClickHouse has no sequence object; naming a sequence is a "
    "separate capability and is untouched -- SequenceNameMixin stays)": (
        "format_create_sequence_statement",
        "format_drop_sequence_statement",
        "format_alter_sequence_statement",
    ),
    "ILIKE (the dialect mixes in no ILIKE mixin; case-insensitive matching "
    "is ClickHouse's positionCaseInsensitive)": ("format_ilike_predicate",),
    "the core PIVOT / UNPIVOT expressions (the dialect mixes in no pivot "
    "mixin)": (
        "format_pivot",
        "format_unpivot",
    ),
    "the TableSource root (every concrete row source overrides its "
    "formatter; the root carries nothing but an alias and is never "
    "rendered)": ("format_table_source",),
}


def _unmodelled_methods():
    """The flat set of formatter names in :data:`UNMODELLED_FORMATTERS`."""
    return {method for methods in UNMODELLED_FORMATTERS.values() for method in methods}


# ---------------------------------------------------------------------------
# The local SQL assertion: classify the outcome instead of swallowing it
# ---------------------------------------------------------------------------


def assert_sql_roundtrip_classified(fqn, instance, dialect):
    """Assert an expression's SQL survives the round-trip, or say precisely why not.

    Four outcomes, each asserted:

    * **renders** -- all three encodings must restore byte-identical SQL *and*
      byte-identical bind parameters.
    * ``UnsupportedFeatureError`` from a probe inside a formatter -- the
      dialect does not model the feature. Asserted as exactly that type, so a
      formatter raising it for an unrelated reason is still visible as that
      type rather than as a pass.
    * ``UnsupportedFeatureError`` from the dispatch -- the dialect's base list
      names no ``format_*`` method for the class at all, which is a wiring
      fact about this backend rather than a capability answer. The method must
      be in :data:`UNMODELLED_FORMATTERS`; the table entry is the reason.
    * a member of :data:`LEGITIMATE_NON_RENDERS` -- unrenderable by design,
      asserted as its exact type *and* message fragment.
    * **anything else** -- a failure naming the class and the exception.

    The first, third and fourth overlap: a pinned entry may itself raise
    ``UnsupportedFeatureError``, in which case the dispatch branch above takes
    it and this function does not look at the pin. That is fine -- the pin's
    job for those classes is to name the specific missing formatter, and that
    is asserted by :meth:`TestMatrixIntegrity.test_pinned_non_render_really_does_not_render`.

    Returns:
        A short string naming the branch taken, so a caller can report the
        classification distribution.

    Raises:
        AssertionError: On a round-trip mismatch, on an unexpected exception
            type, or when a class's rendering outcome changed.
    """
    try:
        expected_sql, expected_params = instance.to_sql()
    except UnsupportedFeatureError as exc:
        assert type(exc) is UnsupportedFeatureError, fqn
        method = _dispatched_formatter(exc)
        if method is not None:
            assert method in _unmodelled_methods(), (
                f"{fqn}: to_sql() reported that {exc.dialect_name} declares no "
                f"{method!r}, which is not in UNMODELLED_FORMATTERS.\n"
                f"  Either ClickHouse now needs that formatter -- in which case "
                f"the class should render and this entry should go -- or the "
                f"feature is absent and the method belongs in that table with "
                f"its reason."
            )
            return "unmodelled"
        return "unsupported"
    except Exception as exc:
        if fqn not in LEGITIMATE_NON_RENDERS:
            raise AssertionError(
                f"{fqn}: to_sql() raised {type(exc).__name__}, which is neither a "
                f"render nor a classified non-render, and this is a defect.\n"
                f"  UnsupportedFeatureError means the dialect lacks the feature and "
                f"is always allowed.\n"
                f"  A class that cannot render for a reason belonging to its own "
                f"tree belongs in LEGITIMATE_NON_RENDERS.\n"
                f"  Exception: {exc}"
            ) from exc
        expected_type, fragment = LEGITIMATE_NON_RENDERS[fqn]
        assert type(exc) is expected_type, (
            f"{fqn}: LEGITIMATE_NON_RENDERS pins this class as a legitimate "
            f"non-render raising {expected_type.__name__}, but it raised "
            f"{type(exc).__name__}: {exc}"
        )
        assert fragment in str(exc), (
            f"{fqn}: expected {expected_type.__name__} and was expected to say "
            f"{fragment!r}, but it said: {exc}"
        )
        return "non-render"

    for channel, build in _channel_builders(instance, dialect):
        pin = _roundtrip_pin(fqn, channel)
        if pin is not None:
            _assert_pinned_channel(fqn, channel, build, instance, pin)
            continue
        decoded = build()
        decoded_sql, decoded_params = decoded.to_sql()
        assert decoded_sql == expected_sql, (
            f"{fqn}: {channel} round-trip changed the SQL.\n"
            f"  original: {expected_sql!r}\n"
            f"  {channel}: {decoded_sql!r}"
        )
        assert _sql_params_equal(decoded_params, expected_params), (
            f"{fqn}: {channel} round-trip changed the bind parameters.\n"
            f"  original: {expected_params!r}\n"
            f"  {channel}: {decoded_params!r}"
        )
    return "rendered"


@pytest.fixture
def clickhouse_matrix_dialect():
    """A dialect with a version bound.

    A ``ClickHouseDialect()`` with no version leaves ``self.version`` unset, and
    the version-gated formatters read it. Every ``supports_*`` comparison against
    it would then compare against whatever the base class initialised, so the
    version is set explicitly rather than left to chance.
    """
    dialect = ClickHouseDialect()
    dialect.version = (24, 3, 1, 0)
    return dialect


@pytest.fixture(params=sorted(REGISTERED), ids=sorted(REGISTERED))
def expr_case(request, clickhouse_matrix_dialect):
    fqn = request.param
    cls = REGISTERED[fqn]
    instance, source = make_instance(cls, clickhouse_matrix_dialect)
    if instance is None:
        assert fqn in UNCONSTRUCTIBLE, (
            f"{fqn} cannot be built by the generic constructor ({source}) and is "
            f"not in UNCONSTRUCTIBLE. Either register a special constructor for "
            f"it or add it to the tuple with a reason -- do not let it disappear "
            f"into a skip."
        )
        pytest.skip(f"{fqn}: pinned in UNCONSTRUCTIBLE, cannot be constructed ({source})")
    return fqn, instance


class TestExpressionRoundtripAll:
    """All constructible expression classes round-trip through all encodings."""

    def test_get_params_roundtrip_across_encodings(
        self, expr_case, clickhouse_matrix_dialect
    ):
        fqn, instance = expr_case

        for channel, build in _channel_builders(instance, clickhouse_matrix_dialect):
            pin = _roundtrip_pin(fqn, channel)
            if pin is not None:
                # The refusal is asserted per channel right here, so the pin
                # cannot go stale without this test failing.
                _assert_pinned_channel(fqn, channel, build, instance, pin)
                continue
            assert_params_equal(
                build().get_params(),
                instance.get_params(),
                f"{fqn}.{channel}",
            )

    def test_to_sql_roundtrip_classified(self, expr_case, clickhouse_matrix_dialect):
        """A render must survive the round-trip; a non-render must be classified."""
        fqn, instance = expr_case
        assert_sql_roundtrip_classified(fqn, instance, clickhouse_matrix_dialect)


class TestClickHouseShape:
    """Facts about this dialect's own name rendering.

    These are the assertions a matrix over SQL text cannot make. The matrix
    proves a render survives a round-trip; it says nothing about *what* the
    render says. ClickHouse has one namespace level and it is the database, so
    the qualified spelling is a fact about the engine worth stating directly --
    and worth stating with the database value absent from the object name, since
    a test whose parameter is a substring of the expected SQL proves nothing if
    the formatter drops it.
    """

    def _dialect(self):
        return ClickHouseDialect()

    def test_qualified_name_is_the_database_then_the_name(self):
        """The database occupies the outer slot, and the name never contains it.

        ``users`` and ``analytics`` are chosen so that neither appears inside the
        other: a formatter that ignored ``catalog_name`` would produce ``users``
        and this fails, rather than passing because the expected SQL happened to
        contain the value it was given.
        """
        d = self._dialect()
        assert d.format_table_object(
            Table(d, "users", catalog_name="analytics")
        ) == ("`analytics`.`users`", ())

    def test_unqualified_name_carries_no_namespace(self):
        d = self._dialect()
        assert d.format_table_object(Table(d, "users")) == ("`users`", ())

    def test_every_object_kind_spells_one_level(self):
        """Not just tables: each kind's own formatter goes through the same path."""
        d = self._dialect()
        for obj, expected in (
            (Table(d, "t", catalog_name="analytics"), "`analytics`.`t`"),
            (View(d, "v", catalog_name="analytics"), "`analytics`.`v`"),
            (MaterializedView(d, "mv", catalog_name="analytics"), "`analytics`.`mv`"),
        ):
            assert obj.to_sql() == (expected, ()), type(obj).__name__

    def test_the_dialect_states_its_own_spelling(self):
        """The one-level shape is ClickHouse's, not an accident of core's defaults.

        Core's ``NamespaceMixin`` walks three slots in a fixed order; ClickHouse
        has one level and says so. If this ever resolves to core's method again,
        the rendering happens to stay the same -- which is exactly why the
        position needs a test of its own rather than an assertion on the SQL.
        """
        assert (
            ClickHouseDialect.format_qualified_name.__qualname__
            == "ClickHouseNamespaceMixin.format_qualified_name"
        )

    def test_separator_is_stated_rather_than_defaulted(self):
        assert ClickHouseNamespaceMixin.separator == "."

    def test_an_inner_schema_is_reported_not_rendered(self):
        """There is no second level, so a carried schema is refused."""
        d = self._dialect()
        with pytest.raises(UnsupportedFeatureError) as exc_info:
            d.format_table_object(Table(d, "users", schema_name="reporting"))
        assert "schema-qualified names" in str(exc_info.value)

    def test_quote_flags_are_honoured_per_level(self):
        """Each level quotes independently -- that is what the split bought."""
        d = self._dialect()
        assert Table(
            d, "users", catalog_name="analytics", catalog_need_quote=False
        ).to_sql() == ("analytics.`users`", ())
        assert Table(
            d, "users", catalog_name="analytics", name_need_quote=False
        ).to_sql() == ("`analytics`.users", ())


class TestLiteralValueKinds:
    """The one ``Literal`` class carries sixteen value kinds, named flatly.

    Core ``679d9817`` made the artifact plain JSON and folded the value classes
    into a single ``Literal`` whose kind comes from the host value -- so the
    matrix's per-class rows now cover the *class*, and this test covers the
    *kinds*: each one travels as one flat JSON scalar under its own wire name,
    with no marker, no wrapper and no second table. Binary is base64 text, an
    interval is its ISO 8601 spelling, a decimal its exact text -- the
    language-neutral spellings spec 4.8 asks for -- and every kind comes back
    as the host type it left as, through all three channels.

    ``debde516`` added the two non-finite floats as kinds of their own
    (``nan_value``, ``infinity_value``) rather than letting them ride on
    ``float_value``, which is why the set is sixteen and not fourteen: NaN is not
    equal to itself and JSON has no NaN literal, so a round-trip that stored it
    as a number could not tell "read back" from "read back wrong". Both travel as
    their spelling, and ``infinity_value`` carries its sign in the text.

    The cases are written out per kind rather than generated because each is a
    statement about what the wire must carry, and a generated case makes no
    statement. Rendering is deliberately not asserted here: whether a kind
    binds or spells inline, and what text this dialect writes, is the
    literal-values file's question -- this is the artifact's.
    """

    #: (wire kind, host value, artifact scalar, restored host type), in
    #: :class:`LiteralKind` declaration order -- the order ``of()`` tries them,
    #: which is why ``boolean_value`` precedes ``integer_value``, ``nan_value``
    #: precedes ``decimal_value`` and ``timestamp_value`` precedes ``date_value``.
    _CASES = (
        ("null_value", None, None, type(None)),
        ("boolean_value", True, True, bool),
        ("integer_value", 7, 7, int),
        ("float_value", 0.5, 0.5, float),
        ("nan_value", float("nan"), "nan", float),
        ("infinity_value", float("inf"), "+inf", float),
        ("decimal_value", decimal.Decimal("1.25"), "1.25", decimal.Decimal),
        ("string_value", "hi", "hi", str),
        ("binary_value", b"\x01\x02", "AQI=", bytes),
        (
            "timestamp_value",
            datetime.datetime(2020, 1, 2, 3, 4, 5),
            "2020-01-02 03:04:05",
            datetime.datetime,
        ),
        ("date_value", datetime.date(2020, 1, 2), "2020-01-02", datetime.date),
        ("time_value", datetime.time(3, 4, 5), "03:04:05", datetime.time),
        (
            "interval_value",
            datetime.timedelta(days=1, hours=2),
            "P1DT2H",
            datetime.timedelta,
        ),
        ("list_value", [1, "a"], [1, "a"], list),
        ("tuple_value", (1, "a"), [1, "a"], tuple),
        ("uuid_value", uuid.UUID(int=7), "00000000-0000-0000-0000-000000000007", uuid.UUID),
    )

    def test_the_kind_set_is_exactly_these_sixteen(self):
        """A seventeenth kind must be added here deliberately, not discovered.

        The closed set is the contract: the wire names every value kind there
        is, and a reader builds its allow-list from it. A kind that appears in
        :class:`LiteralKind` without a case here has no stated artifact shape.
        """
        from rhosocial.activerecord.backend.expression.values import LiteralKind

        assert tuple(kind.wire for kind in LiteralKind) == tuple(
            wire for wire, *_ in self._CASES
        )

    @pytest.mark.parametrize(
        ("wire", "host", "flat", "host_type"),
        _CASES,
        ids=[wire for wire, *_ in _CASES],
    )
    def test_each_kind_travels_as_one_flat_scalar(
        self, clickhouse_matrix_dialect, wire, host, flat, host_type
    ):
        d = clickhouse_matrix_dialect
        instance = Literal(d, host)
        assert serialize(instance) == {
            "kind": wire,
            "params": {"value": flat, "inline": False},
        }, wire
        for channel, build in _channel_builders(instance, d):
            restored = build()
            assert type(restored.value) is host_type, (
                f"{wire}/{channel}: came back as {type(restored.value).__name__}"
            )
            # NaN is the one host value that is not equal to itself, so ``==``
            # would fail on a perfectly faithful round-trip. Both non-finite
            # kinds are compared by their spelling, which is what the wire
            # actually carries.
            if isinstance(host, float) and math.isnan(host):
                assert isinstance(restored.value, float) and math.isnan(
                    restored.value
                ), f"{wire}/{channel}: {restored.value!r}"
                continue
            assert restored.value == host, wire

    @pytest.mark.parametrize("host", [float("-inf")], ids=["negative_infinity"])
    def test_negative_infinity_carries_its_sign_in_the_text(
        self, clickhouse_matrix_dialect, host
    ):
        """One wire kind, two spellings: the sign is the payload.

        ``infinity_value`` is a single kind for both directions, so the text is
        what tells them apart -- ``+inf`` and ``-inf``. Pinning only the
        positive direction would leave ``-inf`` free to come back as ``+inf``.
        """
        d = clickhouse_matrix_dialect
        instance = Literal(d, host)
        assert serialize(instance) == {
            "kind": "infinity_value",
            "params": {"value": "-inf", "inline": False},
        }
        for channel, build in _channel_builders(instance, d):
            restored = build()
            assert restored.value == host, f"negative infinity/{channel}"


class TestObjectKindChecks:
    """A statement handed the wrong object kind must be refused while rendering.

    The check lives in the formatter, not the constructor, and that placement is
    the point. Objects are routinely constructed before their slots are filled
    and before the dialect is settled -- the testsuite's foreign-key fixture is
    ``Table(None, "ddl_spec_orders")`` -- so a construction-time check would fire
    on valid objects and miss invalid ones. More importantly, a wrong kind does
    not fail on its own: the object carries its own ``format_method``, so the
    dialect asks *that* formatter and gets valid SQL for a different object kind.
    ``CreateSequenceExpression(d, Table(d, "users"))`` produced a well-formed
    CREATE SEQUENCE naming a table, with no error and no warning. These tests
    assert the refusal, and they assert it at the only point where the value is
    actually consumed.

    Every wrong-kind value below is a real object of another kind rather than a
    ``MagicMock``: a mock would pass for anything and would prove the check
    rejects mocks, not wrong kinds.
    """

    def _dialect(self):
        return ClickHouseDialect()

    def test_create_table_refuses_a_view(self):
        d = self._dialect()
        expr = CreateTableStatement(
            d, View(d, "users"), [ddl_table.ColumnDefinition(d, "id", IntegerType(d))]
        )
        with pytest.raises(TypeError, match="must be a Table, got View"):
            expr.to_sql()

    def test_create_table_like_refuses_an_index(self):
        d = self._dialect()
        expr = CreateTableLikeStatement(d, Index(d, "i"), Table(d, "users"))
        with pytest.raises(TypeError, match="must be a Table, got Index"):
            expr.to_sql()

    def test_create_table_clone_refuses_a_view_source(self):
        d = self._dialect()
        expr = CreateTableCloneStatement(d, Table(d, "t"), View(d, "v"))
        with pytest.raises(TypeError, match="source_table must be a Table, got View"):
            expr.to_sql()

    def test_create_view_refuses_a_materialized_view(self):
        d = self._dialect()
        expr = CreateViewStatement(
            d, MaterializedView(d, "mv"), "SELECT 1"
        )
        with pytest.raises(TypeError, match="CreateViewStatement.view must be a View"):
            expr.to_sql()

    def test_drop_view_refuses_a_table(self):
        d = self._dialect()
        with pytest.raises(TypeError, match="DropViewStatement.view must be a View"):
            DropViewStatement(d, Table(d, "t")).to_sql()

    def test_generic_materialized_view_ddl_refuses_a_table(self):
        """The generic expression has no kind check of its own, so the formatter's is the only one."""
        d = self._dialect()
        with pytest.raises(TypeError, match="must be a MaterializedView"):
            CreateMaterializedViewStatement(d, Table(d, "t"), "SELECT 1").to_sql()
        with pytest.raises(TypeError, match="must be a MaterializedView"):
            DropMaterializedViewStatement(d, Table(d, "t")).to_sql()
        with pytest.raises(TypeError, match="must be a MaterializedView"):
            RefreshMaterializedViewStatement(d, Table(d, "t")).to_sql()

    def test_refresh_schedule_refuses_a_non_view_upstream(self):
        """``DEPENDS ON`` renders each entry through its own ``to_sql()``.

        A Table there would be named in a list documented as materialized views,
        and nothing about the SQL would look wrong.
        """
        d = self._dialect()
        schedule = ClickHouseRefreshSchedule(d, every="1 HOUR")
        expr = ClickHouseModifyMaterializedViewRefreshExpression(
            d, MaterializedView(d, "mv"), schedule
        )
        # Mutated *after* construction on purpose. The schedule validates in
        # its own constructor path, so the only way a wrong kind reaches the
        # renderer is a later assignment. The formatter is where the value is
        # consumed, so that is where it is checked -- a constructor check
        # would already have been bypassed.
        schedule.depends_on = (Table(d, "t"),)
        with pytest.raises(TypeError, match="depends_on must hold MaterializedView"):
            expr.to_sql()

    def test_database_ddl_refuses_a_table(self):
        d = self._dialect()
        for expr in (
            CreateDatabaseStatement(d, Table(d, "t")),
            DropDatabaseStatement(d, Table(d, "t")),
            AlterDatabaseStatement(
                d, Table(d, "t"), action=AlterDatabaseAction.RENAME_TO, target="x"
            ),
        ):
            with pytest.raises(TypeError, match="must be a Database, got Table"):
                expr.to_sql()

    def test_alter_database_reports_an_action_it_has_no_form_for(self):
        """An action ClickHouse cannot spell is reported, not silently dropped.

        The alternative was worse and is worth naming: this formatter used to
        compare against ``AlterDatabaseAction.MODIFY_COMMENT``, which core's enum
        has no such member of, so *every* ALTER DATABASE raised AttributeError
        before reaching any clause.
        """
        d = self._dialect()
        expr = AlterDatabaseStatement(
            d, Database(d, "db"), action=AlterDatabaseAction.SET_PROPERTY, target="x"
        )
        with pytest.raises(UnsupportedFeatureError):
            expr.to_sql()

    def test_alter_database_refuses_rename_to(self):
        """ClickHouse has no ``ALTER DATABASE ... RENAME TO``.

        The server's own answer to that spelling is a syntax error -- "Expected
        one of: ON, a list of ALTER commands, ALTER command, MODIFY SETTING,
        MODIFY COMMENT" -- and a database is renamed with ``RENAME DATABASE
        <old> TO <new>``, which is a different statement.  So the action is
        refused by name, and the refusal names the spelling that does work.
        """
        d = self._dialect()
        expr = AlterDatabaseStatement(
            d, Database(d, "db"), action=AlterDatabaseAction.RENAME_TO, target="renamed"
        )
        with pytest.raises(UnsupportedFeatureError) as excinfo:
            expr.to_sql()
        message = str(excinfo.value)
        assert "ALTER DATABASE ... RENAME TO" in message, message
        assert "RENAME DATABASE" in message, message

    def test_truncate_refuses_a_view(self):
        d = self._dialect()
        with pytest.raises(TypeError, match="TruncateStatement.table must be a Table"):
            TruncateStatement(d, View(d, "v")).to_sql()

    def test_insert_refuses_an_index(self):
        d = self._dialect()
        expr = InsertStatement(
            d, into=Index(d, "i"), source=ValuesSource(d, [[Literal(d, 1)]])
        )
        with pytest.raises(TypeError, match="InsertStatement.into must be a Table"):
            expr.to_sql()

    def test_foreign_key_target_must_be_a_table(self):
        """Checked before the kind dispatch, so the error names the type.

        Otherwise a caller who passed the wrong object is told FOREIGN KEY is
        unsupported -- a true statement about a different mistake, and one that
        sends them looking in the wrong place.

        The branch carries the references, so the check reads
        ``TableForeignKeyConstraint.references`` rather than the production's
        (deleted) ``foreign_key_table`` field.
        """
        d = self._dialect()
        constraint = TableConstraint(
            d,
            branch=TableForeignKeyConstraint(d, ["a"], (View(d, "other"), None)),
        )
        with pytest.raises(
            TypeError,
            match="TableForeignKeyConstraint.references must pair a Table with its columns, got View",
        ):
            self._dialect().format_table_constraint(constraint)

    def test_column_definition_type_must_be_a_data_type(self):
        d = self._dialect()
        column = ddl_table.ColumnDefinition(d, "id", IntegerType(d))
        column.data_type = "Int32"
        with pytest.raises(TypeError, match="data_type must be a DataType, got str"):
            d.format_column_definition(column)


class TestMatrixIntegrity:
    """Guards on the matrix and its lists, so neither can quietly change."""

    def test_unconstructible_list_is_exact(self, clickhouse_matrix_dialect):
        """Pin the unconstructible tuple against what the constructor really skips.

        Both directions are checked. A class named here that now builds has gained
        a constructor and the entry is stale; a class that fails to build without
        being named would become a silent skip. Both fail here.
        """
        actual = tuple(
            sorted(
                fqn
                for fqn in REGISTERED
                if make_instance(REGISTERED[fqn], clickhouse_matrix_dialect)[0] is None
            )
        )
        assert actual == tuple(sorted(UNCONSTRUCTIBLE)), (
            "the set of expression classes the generic constructor cannot build "
            "changed.\n"
            f"  now skipped but not named: "
            f"{sorted(set(actual) - set(UNCONSTRUCTIBLE))}\n"
            f"  named but now built: "
            f"{sorted(set(UNCONSTRUCTIBLE) - set(actual))}\n"
            "Each new entry needs a reason in the comment above UNCONSTRUCTIBLE."
        )

    def test_unconstructible_entries_are_real_classes(self):
        """Every entry names a class that was actually collected.

        A typo would otherwise exempt nothing while still reading as a
        deliberate decision.
        """
        unknown = set(UNCONSTRUCTIBLE) - set(REGISTERED)
        assert not unknown, (
            f"UNCONSTRUCTIBLE names classes that were not registered: {sorted(unknown)}"
        )

    def test_legitimate_non_renders_are_real_classes(self):
        """Every pinned non-render names a class that was actually collected."""
        unknown = set(LEGITIMATE_NON_RENDERS) - set(REGISTERED)
        assert not unknown, (
            f"LEGITIMATE_NON_RENDERS names classes that were not registered: "
            f"{sorted(unknown)}"
        )

    def test_legitimate_non_roundtrips_are_real_classes(self):
        """Every pinned round-trip entry names a collected class, a real
        channel, and a shape the assertions know how to check."""
        unknown = set(LEGITIMATE_NON_ROUNDTRIPS) - set(REGISTERED)
        assert not unknown, (
            f"LEGITIMATE_NON_ROUNDTRIPS names classes that were not "
            f"registered: {sorted(unknown)}"
        )
        for fqn, entry in LEGITIMATE_NON_ROUNDTRIPS.items():
            bad = set(entry["channels"]) - {"dict", "json", "xml"}
            assert not bad, f"{fqn}: pins unknown channels {sorted(bad)}"
            for channel, pin in entry["channels"].items():
                assert pin[0] in ("raises", "word", "enum-str"), (
                    f"{fqn}/{channel}: unknown pin shape {pin[0]!r}"
                )

    def test_pinned_non_roundtrip_refuses_as_pinned(self, clickhouse_matrix_dialect):
        """Each pinned round-trip entry still refuses exactly as it claims.

        Three directions, per entry: every pinned channel fails in its pinned
        shape; every channel the pin does NOT name still round-trips (so a
        pin can never quietly swallow a whole class); and the class still
        constructs, so what is pinned is the restore and not the constructor.
        """
        for fqn, entry in LEGITIMATE_NON_ROUNDTRIPS.items():
            instance, source = make_instance(REGISTERED[fqn], clickhouse_matrix_dialect)
            assert instance is not None, (
                f"{fqn} is pinned as a round-trip refusal but could not be "
                f"constructed ({source})"
            )
            for channel, build in _channel_builders(instance, clickhouse_matrix_dialect):
                pin = entry["channels"].get(channel)
                if pin is not None:
                    _assert_pinned_channel(fqn, channel, build, instance, pin)
                else:
                    restored = build()
                    assert_params_equal(
                        restored.get_params(), instance.get_params(), f"{fqn}.{channel}"
                    )

    def test_pinned_non_render_really_does_not_render(self, clickhouse_matrix_dialect):
        """Each pinned entry still raises what it claims, for the stated reason.

        Without this, an entry could sit in the dict for a class that renders
        perfectly well, and the matrix would be asserting nothing about it.
        """
        for fqn, (expected_type, fragment) in LEGITIMATE_NON_RENDERS.items():
            instance, source = make_instance(REGISTERED[fqn], clickhouse_matrix_dialect)
            assert instance is not None, (
                f"{fqn} is pinned as a non-render but could not be constructed "
                f"({source})"
            )
            with pytest.raises(expected_type) as exc_info:
                instance.to_sql()
            assert fragment in str(exc_info.value), (
                f"{fqn}: expected the message to mention {fragment!r}, got: "
                f"{exc_info.value}"
            )

    def test_unmodelled_formatter_list_is_exact(self, clickhouse_matrix_dialect):
        """Pin the unmodelled-formatter table against what the dialect lacks.

        Observed rather than assumed: for each class the matrix covers, either
        it renders or it fails, and every dispatch refusal is attributed to the
        method it named -- including the classes pinned in
        :data:`LEGITIMATE_NON_RENDERS`, whose dispatch failures those pins
        record class by class. Then the table is compared with the set
        observed, in both directions, so:

        * a method in the table that ClickHouse now implements fails here,
          because its classes render and are no longer attributed to it --
          which is the moment to delete the entry rather than leave a lie in
          the table;
        * a class that starts needing a method outside the table fails the
          per-class assertion in :func:`assert_sql_roundtrip_classified`
          instead of being absorbed into "unsupported".

        This is the regression test for the pad/trim incident. Core turned
        ``trim``/``lpad``/``rpad``/``repeat`` into dedicated nodes; ClickHouse
        spells all four -- LPAD, RPAD and REPEAT natively, TRIM through
        ClickHouseTrimMixin -- so none of the four is a gap here, and this test
        is what would have said so loudly if a fifth node of that family had
        arrived without a ClickHouse formatter.
        """
        observed = set()
        for fqn in sorted(REGISTERED):
            instance, source = make_instance(REGISTERED[fqn], clickhouse_matrix_dialect)
            if instance is None:
                continue
            try:
                instance.to_sql()
            except UnsupportedFeatureError as exc:
                method = _dispatched_formatter(exc)
                if method is not None:
                    observed.add(method)
                continue
            except Exception:
                continue

        declared = _unmodelled_methods()
        assert not (observed - declared), (
            "classes need formatters that are not in UNMODELLED_FORMATTERS: "
            f"{sorted(observed - declared)}. Add each with the feature that is "
            f"absent and why -- or mix the formatter in, in which case the "
            f"classes render and the entry is not needed."
        )
        assert not (declared - observed), (
            "UNMODELLED_FORMATTERS names formatters no class actually needs: "
            f"{sorted(declared - observed)}. ClickHouse may have gained one of "
            f"these, in which case the classes needing it now render and the "
            f"entry should go."
        )

    def test_matrix_covers_both_packages(self):
        """The matrix covers every concrete class in the two packages.

        Re-walked here rather than trusting the module-level collection, so a
        class that appeared after import is caught. The package walk is used
        rather than the registry because the registry also holds whatever
        backends other test modules happened to import.
        """
        expected = set(_collect_matrix_classes())
        assert expected == set(REGISTERED), (
            "the set of expression classes the covered packages define changed "
            "after collection.\n"
            f"  now defined but not covered: "
            f"{sorted(expected - set(REGISTERED))}\n"
            f"  covered but no longer defined: "
            f"{sorted(set(REGISTERED) - expected)}"
        )
        # A floor, not a ceiling. It catches a walk that stopped early -- an
        # import error part way through the package would quietly halve the
        # count -- and it cannot absorb a gap, which a "no more than N" ceiling
        # can.
        assert len(REGISTERED) > 300, (
            f"only {len(REGISTERED)} classes collected across "
            f"{len(COVERED_PACKAGES)} packages; the walk may have stopped early"
        )

    def test_every_covered_class_is_registered_for_deserialization(self):
        """A class in the matrix can be found again when deserializing.

        Deserialization resolves a kind to its class through the framework's
        default registry, so a class the matrix renders but the registry
        cannot resolve would round-trip into the wrong thing or nothing at
        all. The kind is the only identity the artifact carries, so the check
        resolves each class's own kind and compares what comes back.
        """
        from rhosocial.activerecord.backend.expression.registry import kind_of
        from rhosocial.activerecord.backend.expression.serialization import (
            default_registry,
        )

        registry = default_registry()
        unresolved = []
        for fqn, cls in REGISTERED.items():
            try:
                resolved = registry.resolve_node(kind_of(cls))
            except Exception:
                unresolved.append(fqn)
                continue
            if resolved is not cls:
                unresolved.append(fqn)
        unresolved.sort()
        assert not unresolved, (
            f"the matrix covers classes the registry cannot resolve: {unresolved}"
        )

    def test_coverage_report(self, clickhouse_matrix_dialect):
        """Surface what the matrix covers, so coverage stays transparent."""
        branches: Dict[str, int] = {}
        constructible = 0
        for fqn in sorted(REGISTERED):
            instance, _ = make_instance(REGISTERED[fqn], clickhouse_matrix_dialect)
            if instance is None:
                continue
            constructible += 1
            branch = assert_sql_roundtrip_classified(
                fqn, instance, clickhouse_matrix_dialect
            )
            branches[branch] = branches.get(branch, 0) + 1
        assert constructible
        print(
            f"\nexpression matrix: {len(REGISTERED)} registered, "
            f"{constructible} constructible, {len(UNCONSTRUCTIBLE)} "
            f"pinned-unconstructible, {len(LEGITIMATE_NON_RENDERS)} "
            f"pinned-non-render; rendered={branches.get('rendered', 0)}, "
            f"unsupported={branches.get('unsupported', 0)}, "
            f"unmodelled={branches.get('unmodelled', 0)} (pinned in "
            f"UNMODELLED_FORMATTERS), "
            f"non-render={branches.get('non-render', 0)}"
        )
        for fqn in UNCONSTRUCTIBLE:
            print(f"  not constructible: {fqn}")
        for feature, methods in sorted(UNMODELLED_FORMATTERS.items()):
            print(f"  not modelled: {feature} ({len(methods)} formatters)")

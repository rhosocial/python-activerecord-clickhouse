# tests/rhosocial/activerecord_clickhouse_test/feature/backend/test_clickhouse_constraint_capabilities.py
"""ClickHouse constraint capability switches, pinned to live measurements.

Every value asserted here was measured against the instance
``tests/config/clickhouse_scenarios.yaml`` names ``clickhouse_http``:
**ClickHouse 26.7.3.19 (official build)**, HTTP on ``127.0.0.1:18682``,
database ``test_db``. The statements, error codes and catalog reads behind each
value are recorded in the docstrings of
``rhosocial.activerecord.backend.impl.clickhouse.mixins.constraint``; this
module pins the values and checks that they are load-bearing.

Three guards beyond the values themselves:

* **declared here, not inherited.** Every switch must be declared by a class in
  *this* package, so a change to a core default cannot silently move
  ClickHouse's contract. That matters more here than elsewhere: core's
  ``ConstraintMixin`` defaults most constraint switches to ``True``, which is
  the opposite of what a live ClickHouse says about almost all of them.
* **the engine has two constraint kinds, not five.** ``CHECK`` and ``ASSUME``
  are the complete set -- the parser prints ``Expected one of: CHECK, ASSUME``
  for every third kind. The table below asserts that PK / UNIQUE / FK are
  ``False`` at *both* levels while table CHECK is ``True``, because a reader
  who only saw the flat switch could easily assume the opposite.
* **the primary key is an engine parameter, not a constraint.** Asserted
  separately because it is the one verdict that looks like a mistake.

Not covered here, on purpose: what the *renderers* do with these values. Two
known gaps are named in the notes below rather than encoded as assertions,
because a test that pins today's wrong behaviour is worse than no test.
"""

import pytest
from rhosocial.activerecord.backend.dialect.exceptions import UnsupportedFeatureError
from rhosocial.activerecord.backend.expression.core import Column
from rhosocial.activerecord.backend.expression.predicates import ComparisonPredicate
from rhosocial.activerecord.backend.expression.statements.ddl_alter import (
    AddTableConstraint,
    AlterConstraint,
    DropTableConstraint,
    ValidateConstraint,
)
from rhosocial.activerecord.backend.expression.statements.ddl_table import (
    ColumnCheckConstraint,
    ColumnPrimaryKeyConstraint,
    ConstraintValidation,
    TableCheckConstraint,
    TableConstraint,
)

from rhosocial.activerecord.backend.impl.clickhouse.dialect import ClickHouseDialect

#: The exact release every verdict below was measured on. Hard-coded on
#: purpose: reading it back from the dialect would let a version bump silently
#: re-label the evidence.
MEASURED_VERSION = (26, 7, 3)

#: Every capability this package declares must come from this package.
BACKEND_PACKAGE = "rhosocial.activerecord.backend.impl.clickhouse."

#: (switch name, measured value) pairs. The value is hard-coded on purpose:
#: reading it back from the dialect would make the test unable to see a
#: moved default.
#:
#: Grouped the way the engine groups them, because that grouping *is* the
#: finding: ClickHouse's column level has no constraints at all, its table
#: level has exactly one enforced kind, and the ALTER grammar carries exactly
#: three constraint commands.
MEASURED_SWITCHES = (
    # -- constraint kinds, table level ------------------------------------
    # Only CHECK is in the grammar. The other three are the "Expected one of:
    # CHECK, ASSUME." rejections, at ADD CONSTRAINT time and at CREATE TABLE
    # time alike.
    ("supports_table_check_constraint", True),
    ("supports_table_primary_key_constraint", False),
    ("supports_table_unique_constraint", False),
    ("supports_table_foreign_key_constraint", False),
    ("supports_table_exclude_constraint", False),
    # The second kind. NOT enforced -- a violating row is stored -- so it gets
    # its own opt-in switch and must never share a name implying enforcement.
    ("supports_assume_constraint", True),
    # -- constraint kinds, flat switches ----------------------------------
    # Flat ``supports_check_constraint`` is False even though table CHECK is
    # real: on this core it is the switch the *column-level* renderer
    # consults, and a column cannot carry a CHECK (Code 62). See the
    # docstring of ``supports_check_constraint``.
    ("supports_check_constraint", False),
    # The primary key is ``ENGINE = MergeTree PRIMARY KEY id ORDER BY id``.
    # system.constraints holds 0 rows for a table built with ``PRIMARY KEY``;
    # system.tables.primary_key / system.columns.is_in_primary_key hold it.
    # The flat switch is True anyway, and that is not a transposition: on this
    # core it gates the ``PRIMARY KEY`` column *modifier* (core's
    # format_column_primary_key_constraint consults exactly this probe), and
    # that modifier is measured accepted in the column grammar. Answering
    # False would refuse to render a CREATE TABLE for any model with a
    # single-column primary key -- core's model layer appends a
    # ColumnPrimaryKeyConstraint to every non-composite ``__primary_key__``
    # field, so the refusal would fire on every such table.
    ("supports_primary_key_constraint", True),
    ("supports_unique_constraint", False),
    ("supports_foreign_key_constraint", False),
    ("supports_not_null_constraint", True),
    # -- constraint kinds, column level -----------------------------------
    # ClickHouse constraints are TABLE-LEVEL ONLY. Both spellings --
    # ``c Int32 CHECK c > 0`` and ``c Int32 CONSTRAINT cc CHECK (c > 0)`` --
    # are Code 62, and the expected-token list the server prints is the whole
    # column-modifier grammar, which contains neither CHECK nor CONSTRAINT.
    ("supports_column_check_constraint", False),
    ("supports_column_primary_key_constraint", False),
    ("supports_column_unique_constraint", False),
    ("supports_column_foreign_key_constraint", False),
    ("supports_column_nullable_constraint", True),
    # -- column value expressions -----------------------------------------
    # The neighbouring capability, and the one with the sharpest edge: a
    # column DEFAULT accepts a comparison and silently evaluates it to 0/1,
    # so ``True`` here is not licence to render one.
    ("supports_default_column_value_expression", True),
    ("supports_generated_column", False),
    # -- FK actions and SQL-standard clauses (no FK exists to carry them) ---
    ("supports_fk_on_delete", False),
    ("supports_fk_on_update", False),
    ("supports_fk_match", False),
    ("supports_deferrable_constraint", False),
    ("supports_constraint_enforced", False),
    ("supports_exclude_constraint", False),
    # -- ALTER TABLE constraint lifecycle ----------------------------------
    # The ALTER grammar enumerates exactly three constraint commands: ADD
    # CONSTRAINT, MODIFY CONSTRAINT, DROP CONSTRAINT. Everything else is a
    # Code 62 whose error message lists that set verbatim.
    ("supports_add_constraint", True),
    ("supports_drop_constraint", True),
    ("supports_drop_constraint_if_exists", True),
    ("supports_alter_constraint", False),
    ("supports_alter_constraint_enforced", False),
    ("supports_validate_constraint", False),
    ("supports_constraint_novalidate", False),
    ("supports_rename_constraint", False),
    ("supports_enable_disable_constraint", False),
)


def _dialect():
    return ClickHouseDialect(MEASURED_VERSION)


def _declaring_class(switch_name):
    """The first class in the dialect's MRO that declares ``switch_name``."""
    for cls in ClickHouseDialect.__mro__:
        if switch_name in cls.__dict__:
            return cls
    raise AssertionError(f"no class in the MRO declares {switch_name}()")


def _predicate(d):
    return ComparisonPredicate(d, "=", Column(d, "a"), Column(d, "b"))


def _check(d, **kwargs):
    """A named table-level CHECK -- the one kind ClickHouse enforces."""
    return TableConstraint(
        d,
        branch=TableCheckConstraint(d, _predicate(d)),
        name="ck",
        **kwargs,
    )


class TestMeasuredConstraintSwitchValues:
    @pytest.mark.parametrize(
        "switch_name,expected", MEASURED_SWITCHES, ids=[s for s, _ in MEASURED_SWITCHES]
    )
    def test_matches_measurement(self, switch_name, expected):
        dialect = _dialect()
        assert getattr(dialect, switch_name)() is expected, (
            f"{switch_name}() no longer matches the 26.7.3.19 measurement; see "
            f"the docstring in mixins/constraint.py for the statement that decided it."
        )

    @pytest.mark.parametrize(
        "switch_name,_expected", MEASURED_SWITCHES, ids=[s for s, _ in MEASURED_SWITCHES]
    )
    def test_declared_by_this_backend(self, switch_name, _expected):
        """A moved core default must not move ClickHouse's contract silently.

        Core's ``ConstraintMixin`` defaults ``supports_primary_key_constraint``,
        ``supports_unique_constraint``, ``supports_check_constraint``,
        ``supports_fk_match``, ``supports_deferrable_constraint``,
        ``supports_constraint_enforced``, ``supports_add_constraint`` and
        ``supports_drop_constraint`` to ``True``. Four of those are wrong for a
        live ClickHouse, so an inherited answer is not an acceptable answer.
        """
        declaring = _declaring_class(switch_name)
        assert declaring.__module__.startswith(BACKEND_PACKAGE), (
            f"{switch_name} is inherited from {declaring.__module__}; declare it "
            f"in this backend's mixins so the measured value is explicit."
        )

    def test_version_does_not_move_the_values(self):
        """The values are statement-level facts, not version gates.

        Measured on 26.7.3.19 only. Asserting they hold on 24.x or 25.x would
        be a claim this backend has not made, so the check is just that no
        version branch exists for them.
        """
        for version in ((24, 8, 0), MEASURED_VERSION, (27, 0, 0)):
            dialect = ClickHouseDialect(version)
            for switch_name, expected in MEASURED_SWITCHES:
                assert (
                    getattr(dialect, switch_name)() is expected
                ), f"{switch_name} moved with version {version}"


class TestTheTwoConstraintKindsAreTheWholeSet:
    """The finding the whole matrix hangs on, asserted on its own.

    Every rejected third kind gets the same answer from the parser, so the
    switch values above are not a list of independent verdicts -- they are one
    verdict (``CHECK, ASSUME``) applied five times. If core S3 ever splits these
    switches per kind, this is the test that catches a kind accidentally
    answering ``True``.
    """

    def test_only_check_and_assume_are_advertised_as_kinds(self):
        dialect = _dialect()
        advertised = {
            name: getattr(dialect, name)()
            for name in (
                "supports_table_check_constraint",
                "supports_table_primary_key_constraint",
                "supports_table_unique_constraint",
                "supports_table_foreign_key_constraint",
                "supports_table_exclude_constraint",
                "supports_assume_constraint",
            )
        }
        assert advertised == {
            "supports_table_check_constraint": True,
            "supports_table_primary_key_constraint": False,
            "supports_table_unique_constraint": False,
            "supports_table_foreign_key_constraint": False,
            "supports_table_exclude_constraint": False,
            "supports_assume_constraint": True,
        }

    def test_assume_is_not_offered_as_an_enforcing_kind(self):
        """``ASSUME`` must stay separable from ``CHECK``.

        Measured: with ``ak ASSUME c > 1000`` the only constraint on a table,
        ``INSERT INTO probe_t (id, c) VALUES (3, -5)`` is accepted and stored;
        with ``ck CHECK c > 0`` the same INSERT is Code 469
        ``VIOLATED_CONSTRAINT``. An expression that cannot reject a row is not
        a constraint, so it must never be folded into the CHECK switch -- and
        ``supports_constraint_enforced`` must stay ``False`` so there is no way
        to ask for "a CHECK that is not enforced" and be handed an ASSUME.
        """
        dialect = _dialect()
        assert dialect.supports_table_check_constraint() is True
        assert dialect.supports_assume_constraint() is True
        # There is no spelling that silently turns one into the other.
        assert dialect.supports_constraint_enforced() is False


class TestPrimaryKeyIsNotAConstraint:
    def test_the_constraint_claim_stays_on_the_per_level_switches(self):
        """The one verdict that reads like a mistake, so it is spelled out.

        ClickHouse *has* primary keys. What it does not have is a primary-key
        **constraint**: ``system.constraints`` for a table built with
        ``PRIMARY KEY (id)`` measures 0 rows, ``system.tables.primary_key``
        reads ``(id)``, ``sorting_key`` reads ``id`` and
        ``system.columns.is_in_primary_key`` reads 1 for ``id``. ``ADD
        CONSTRAINT ... PRIMARY KEY`` is Code 62.

        The flat switch is the exception and is ``True`` on purpose: it gates
        the ``PRIMARY KEY`` column *modifier*, which the server accepts, not
        the constraint. See :meth:`supports_primary_key_constraint` in
        ``mixins/constraint.py`` for the full measurement.
        """
        dialect = _dialect()
        assert dialect.supports_table_primary_key_constraint() is False
        assert dialect.supports_column_primary_key_constraint() is False

    def test_primary_key_renders_the_column_modifier(self):
        """The consequence of the flat ``True`` above.

        Core's ``format_column_primary_key_constraint`` consults
        ``supports_primary_key_constraint()`` and, with ``True``, renders the
        ``PRIMARY KEY`` column modifier -- the one spelling the server
        accepts (``ALTER TABLE ... ADD COLUMN y Int32 PRIMARY KEY`` is
        accepted on 26.7.3.19; the modifier is in the parser's expected-token
        list for a column).

        The formatter takes the *branch* now, not the production -- core's S3
        split moved the dispatch onto the branch's own ``format_method``.
        """
        d = _dialect()
        from rhosocial.activerecord.backend.expression.statements.ddl_table import (
            ColumnConstraint,
        )

        branch = ColumnPrimaryKeyConstraint(d)
        assert d.format_column_primary_key_constraint(branch) == (" PRIMARY KEY", ())
        sql, params = d.format_column_constraint(
            ColumnConstraint(d, branch=branch, name="pk")
        )
        assert "PRIMARY KEY" in sql
        assert params == ()


class TestConstraintsAreTableLevelOnly:
    def test_column_check_is_refused_by_name(self):
        """A column cannot carry a CHECK, in either spelling.

        The ``False`` on ``supports_check_constraint`` is what makes this
        refusal happen, and it is the correct outcome even though table-level
        CHECK is real (``supports_table_check_constraint`` is ``True``): both
        ``c Int32 CHECK c > 0`` and ``c Int32 CONSTRAINT cc CHECK (c > 0)`` are
        Code 62 on 26.7.3.19.
        """
        d = _dialect()
        from rhosocial.activerecord.backend.expression.statements.ddl_table import (
            ColumnConstraint,
        )

        branch = ColumnCheckConstraint(d, _predicate(d))
        with pytest.raises(UnsupportedFeatureError):
            d.format_column_check_constraint(branch)
        with pytest.raises(UnsupportedFeatureError):
            d.format_column_constraint(ColumnConstraint(d, branch=branch))


class TestDropConstraintRenders:
    """The one ALTER-side operation whose renderer this backend re-spells."""

    def test_drop_constraint_renders(self):
        d = _dialect()
        sql, params = DropTableConstraint(d, "ck").to_sql()
        assert sql == "DROP CONSTRAINT `ck`"
        assert params == ()

    def test_drop_constraint_if_exists_is_the_idempotent_path(self):
        """The plain form is Code 36; ``IF EXISTS`` is a silent no-op.

        Measured on 26.7.3.19::

            ALTER TABLE probe_t DROP CONSTRAINT nope
            -> Code: 36. DB::Exception: Wrong constraint name.
               Cannot find constraint `nope` to drop. (BAD_ARGUMENTS)
            ALTER TABLE probe_t DROP CONSTRAINT IF EXISTS nope
            -- accepted; system.constraints unchanged

        Core both reads this switch and renders the clause, as of its
        ``4875ea3b`` fix. Before that fix core read the switch but never spelled
        the two words, and this backend carried an override to add them; that
        override is gone, because keeping it now splices a second ``IF EXISTS``
        (``DROP CONSTRAINT IF EXISTS IF EXISTS <name>``). The assertion below is
        therefore also the regression guard for the duplicate clause.
        """
        d = _dialect()
        assert d.supports_drop_constraint_if_exists() is True
        assert DropTableConstraint(d, "ck").to_sql()[0] == "DROP CONSTRAINT `ck`"
        assert (
            DropTableConstraint(d, "ck", if_exists=True).to_sql()[0]
            == "DROP CONSTRAINT IF EXISTS `ck`"
        )


class TestAlterSideRefusals:
    """The lifecycle verbs ClickHouse's grammar does not contain.

    All are refused by name before any SQL is produced, which is what the
    ``False`` switches are for. ``AlterConstraint`` takes ``constraint_kind=``
    (the branch class) rather than the deleted ``constraint_type=`` tag.

    The branch class and not the SQL spelling, on this core: ``AlterConstraint``
    resolves a string ``constraint_kind`` by comparing it against
    ``branch.__name__.replace("Table", "").upper()``, which is
    ``"CHECKCONSTRAINT"``, so ``"CHECK"`` does not match and raises
    ``ValueError``. That is core's business and not this repository's to fix;
    the branch class is the form that works.
    """

    def test_validate_constraint_refused(self):
        d = _dialect()
        with pytest.raises(UnsupportedFeatureError):
            ValidateConstraint(d, "ck").to_sql()

    def test_alter_constraint_enforced_refused(self):
        d = _dialect()
        action = AlterConstraint(d, "ck", enforced=True, constraint_kind=TableCheckConstraint)
        with pytest.raises(UnsupportedFeatureError):
            action.to_sql()

    def test_alter_constraint_not_enforced_refused(self):
        d = _dialect()
        action = AlterConstraint(d, "ck", not_enforced=True, constraint_kind=TableCheckConstraint)
        with pytest.raises(UnsupportedFeatureError):
            action.to_sql()

    def test_add_constraint_not_valid_refused(self):
        d = _dialect()
        action = AddTableConstraint(d, _check(d, validation=ConstraintValidation.NOVALIDATE))
        with pytest.raises(UnsupportedFeatureError):
            action.to_sql()


class TestAddConstraintRenders:
    """``ALTER TABLE ... ADD CONSTRAINT`` is accepted for CHECK, so it renders.

    ``supports_add_constraint()`` was ``False`` before the switch-correction pass
    and is now ``True`` on the strength of two accepted statements on 26.7.3.19::

        ALTER TABLE probe_t ADD CONSTRAINT ck CHECK c > 0      -- accepted
        ALTER TABLE probe_t ADD CONSTRAINT ak ASSUME c > 1000  -- accepted

    while the ClickHouse override of ``format_add_table_constraint_action`` still
    raised unconditionally with "ClickHouse does not support table constraints" --
    a message that had stopped being true. The override is gone: core's
    implementation renders the production through the ClickHouse
    ``format_table_constraint``, which is where the kind is narrowed.

    Only CHECK is reachable. ``ASSUME`` is not one of core's five table-constraint
    branches, so it has no node and no spelling here; that is recorded in
    ``supports_assume_constraint``'s docstring as a deliberate consequence, not
    as a gap.
    """

    def test_add_constraint_renders_check(self):
        d = _dialect()
        assert d.supports_add_constraint() is True
        sql, params = AddTableConstraint(d, _check(d)).to_sql()
        assert sql == "ADD CONSTRAINT `ck` CHECK (`a` = `b`)"
        assert params == ()

    def test_add_constraint_refuses_unique(self):
        """The table-level narrowing, reached through the ALTER path.

        ``format_table_constraint`` refuses the branch by name, so the ALTER
        action inherits the refusal rather than needing its own.
        """
        from rhosocial.activerecord.backend.expression.statements.ddl_table import (
            TableConstraint,
            TableUniqueConstraint,
        )

        d = _dialect()
        constraint = TableConstraint(d, branch=TableUniqueConstraint(d, ["a"]))
        with pytest.raises(UnsupportedFeatureError):
            AddTableConstraint(d, constraint).to_sql()

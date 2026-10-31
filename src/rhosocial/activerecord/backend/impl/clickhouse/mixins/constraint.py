# src/rhosocial/activerecord/backend/impl/clickhouse/mixins/constraint.py
"""ClickHouse constraint capability declarations.

Every switch here is declared **in this package**, even where core's
``ConstraintMixin`` already defaults it to the same value.  That is deliberate:
those mixins are shared with the dummy dialect and are exactly the kind of
default that can move, and a silent move of a core default would move
ClickHouse's measured contract with it.  A declaration here is the pin.

The measurements behind every value were taken against the instance
``tests/config/clickhouse_scenarios.yaml`` names ``clickhouse_http``:

* **ClickHouse 26.7.3.19 (official build)**, HTTP interface on
  ``127.0.0.1:18682``, database ``test_db``.

Every refusal quoted below is the server's own error -- code and message text --
so a claim can be re-checked without re-measuring the family.

Three things about ClickHouse are worth reading before the individual
docstrings, because the first two invert what most SQL backends do and the
third is a trap a naive renderer falls into without any error at all.

**1. ClickHouse has exactly two constraint kinds, and one of them is not a
constraint.**  ``ADD CONSTRAINT`` accepts ``CHECK`` and ``ASSUME`` and nothing
else -- the parser says so itself::

    ALTER TABLE probe_t ADD CONSTRAINT ck CHECK c > 0      -- accepted
    ALTER TABLE probe_t ADD CONSTRAINT ak ASSUME c > 1000  -- accepted
    ALTER TABLE probe_t ADD CONSTRAINT pk PRIMARY KEY (id)
    -> Code: 62. DB::Exception: Syntax error: failed at position 41 (PRIMARY):
       PRIMARY KEY (id). Expected one of: CHECK, ASSUME. (SYNTAX_ERROR)
    ALTER TABLE probe_t ADD CONSTRAINT uq UNIQUE (id)
    -> Code: 62 ... Expected one of: CHECK, ASSUME. (SYNTAX_ERROR)
    ALTER TABLE probe_t ADD CONSTRAINT fk FOREIGN KEY (id) REFERENCES probe_t(id)
    -> Code: 62 ... Expected one of: CHECK, ASSUME. (SYNTAX_ERROR)

``CHECK`` is enforced at write time.  ``ASSUME`` is **not**: it is an assertion
handed to the query planner, so no row is ever rejected for violating it::

    -- table carries ASSUME ak CHECK... (ASSUME c > 1000), nothing else
    INSERT INTO probe_t (id, c) VALUES (3, -5);   -- accepted, row stored

    -- same table carrying CHECK ck (c > 0)
    INSERT INTO probe_t (id, c) VALUES (1, -5);
    -> Code: 469. DB::Exception: Constraint `ck` for table test_db.probe_cc
       (...) is violated at row 1. Expression: (c > 0). Column values:
       c = -5: While executing WaitForAsyncInsert. (VIOLATED_CONSTRAINT)

So ``ASSUME`` is deliberately **not** routed through the ``CHECK`` capability:
it must stay a separate opt-in (:meth:`ClickHouseConstraintMixin.supports_assume_constraint`)
and must never be rendered under a name that implies enforcement.

**2. Constraints are TABLE-LEVEL ONLY.  A column cannot carry one.**  Both the
bare and the named column-level spelling are syntax errors, and the expected-token
list the server prints is the whole column-modifier grammar::

    ALTER TABLE probe_t ADD COLUMN e1 Int32 CHECK e1 > 0
    ALTER TABLE probe_t ADD COLUMN e2 Int32 CONSTRAINT cc CHECK (e2 > 0)
    -> Code: 62. DB::Exception: Syntax error: failed at position 42 (CHECK):
       ... Expected one of: SIGNED, UNSIGNED, COLLATE, NOT, NULL, DEFAULT,
       MATERIALIZED, ALIAS, EPHEMERAL, AUTO_INCREMENT, COMMENT, CODEC,
       STATISTICS, TTL, PRIMARY KEY, SETTINGS, FIRST, AFTER, token, Comma,
       INTO OUTFILE, FORMAT, ParallelWithClause, PARALLEL WITH, end of query.

The same list rejects column-level ``UNIQUE`` and ``REFERENCES`` (Code 62).
The modifiers that *are* in it (``NOT NULL``, ``DEFAULT``, ``MATERIALIZED``,
``ALIAS``, ``EPHEMERAL``, ``COMMENT``, ``CODEC``, ``STATISTICS``, ``TTL``,
``PRIMARY KEY``, ``SETTINGS``) may be written **in any order, each at most
once** -- a second ``COMMENT`` is refused with Code 62 and an expected-token
list that no longer contains ``COMMENT``.

This is why the column-level switches below are ``False`` -- with the one
exception of the flat ``supports_primary_key_constraint``, which answers
``True`` because the thing it gates on this core is the ``PRIMARY KEY``
**modifier** (accepted; see its docstring) rather than a constraint -- while
the table-level CHECK switch is ``True``: the asymmetry is the engine's, not a
mistake in the declarations.

**3. The primary key is NOT a constraint.**  It is an ENGINE parameter --
``ENGINE = MergeTree PRIMARY KEY id ORDER BY id``, or just ``ORDER BY id`` --
and it never appears in the constraint catalog::

    CREATE TABLE probe_pk (id Int32, c Int32, PRIMARY KEY (id))
        ENGINE = MergeTree ORDER BY id;                 -- accepted
    SELECT count() FROM system.constraints
        WHERE database='test_db' AND table='probe_pk';  -- 0
    SELECT primary_key, sorting_key FROM system.tables
        WHERE database='test_db' AND name='probe_pk';   -- '(id)', 'id'
    SELECT name, is_in_primary_key FROM system.columns
        WHERE database='test_db' AND table='probe_pk';  -- id -> 1, c -> 0

``SHOW CREATE TABLE`` agrees: the primary key comes back inside the ENGINE
block, with no ``CONSTRAINT`` clause anywhere.  A column may also carry
``PRIMARY KEY`` as a *modifier* (it is in the expected-token list above), and
that modifier feeds the same engine parameters -- it still does not create a
row in ``system.constraints``.

**Catalog shape, measured on 26.7.3.19** (``DESCRIBE TABLE system.constraints``).
This is worth stating because it is easy to assume a boolean column here:

    database              String
    table                 String
    name                  String
    type                  Enum8('CHECK' = 0, 'ASSUME' = 1)
    expression            String

There is **no ``is_assume`` column**.  The CHECK/ASSUME discriminator is the
``type`` enum's value, so a reader of ``system.constraints`` filters with
``type = 'ASSUME'`` rather than on a flag::

    SELECT name, type, expression FROM system.constraints
        WHERE database='test_db' AND table='probe_t' ORDER BY name;
    -- ak | ASSUME | c > 1000
    -- ck | CHECK  | c > 0

**4. The ``DEFAULT`` trap -- a constraint can be smuggled in as a column
default, and the server accepts it.**  A column default is an arbitrary
expression, so a comparison in that position parses and is silently evaluated
to 0/1::

    ALTER TABLE probe_pk ADD COLUMN d Int32 DEFAULT c > 0;  -- accepted
    INSERT INTO probe_pk (id, c) VALUES (1, 7), (2, -7);
    SELECT id, c, d FROM probe_pk ORDER BY id;
    -- (1, 7, 1)   (2, -7, 0)

Nothing is rejected and nothing is warned about: the intended constraint check
becomes a boolean default column.  **The render path must reject this
construction itself** -- it cannot be delegated to the server, because the
server accepts it.  That gate is a render-path concern and is not part of the
switch declarations below; the ``True`` here records only that the *server*
accepts an expression in the ``DEFAULT`` position.

Naming note: the switches that core's protocol does not own --
``supports_rename_constraint``, ``supports_alter_constraint``,
``supports_enable_disable_constraint``, the per-level
``supports_{column,table}_*_constraint`` family and
``supports_assume_constraint`` -- are ClickHouse's own, named from
``.claude/plan/2026-10-11/clickhouse-constraint-coverage.md``.  Core's S3 wave
moved the constraint **nodes** (the fat ``ColumnConstraint`` /
``TableConstraint`` became a production plus a branch class) and deleted the
``ColumnConstraintType`` / ``TableConstraintType`` tags; it did not add a
protocol for these switches and did not take the ``REFERENCES`` clause or the
ALTER lifecycle verbs away.  So they keep their names, and the measured value is
what the tests pin.

**Where the narrowing went.**  Core's S3 removed the kind enum, so the places
that used to branch on a ``constraint_type`` tag now branch on the branch
node's class, and they land on *public* formatters of this dialect:

* column level -- no override.  Core's own branch formatters read this
  module's probes: ``format_column_check_constraint`` refuses on
  ``supports_check_constraint`` (Code 62; a column cannot carry a CHECK), and
  ``format_column_primary_key_constraint`` renders the ``PRIMARY KEY`` modifier
  on ``supports_primary_key_constraint``, which is ``True`` because the
  modifier is measured accepted while the per-level constraint switches stay
  ``False``.
* table level, CREATE position -- :meth:`ClickHouseTableMixin.format_table_constraint`
  narrows on the branch class: ``TablePrimaryKeyConstraint`` /
  ``TableCheckConstraint`` render (both measured accepted in a column list),
  and ``TableUniqueConstraint`` / ``TableForeignKeyConstraint`` /
  ``TableExcludeConstraint`` refuse by name, measurement quoted.
* table level, ADD position -- :meth:`ClickHouseTableMixin.format_add_table_constraint_action`
  narrows before delegating to core: ``ALTER TABLE ... ADD CONSTRAINT`` accepts
  only ``CHECK`` and ``ASSUME``, so every other branch refuses there even
  though the same branch renders in the column list.  That asymmetry is the
  engine's, not an inconsistency: ``ADD CONSTRAINT pk PRIMARY KEY (id)`` is
  Code 62 while ``CREATE TABLE ... PRIMARY KEY (id)`` is accepted.

No ``_require_*`` helper is needed on this backend, and the reason is a
measurement rather than an omission: every switch below is a statement-level
fact that does not move with the version (asserted by
``test_version_does_not_move_the_values``), so there is no kind x version matrix
for such a helper to carry.  The per-kind judgement a helper would otherwise
hold lives in the two formatters above, where the branch class is in scope.
"""

#: The engine every verdict in this module was measured on. Kept as a constant
#: so the docstrings and the tests cannot drift onto different releases.
MEASURED_ENGINE = "ClickHouse 26.7.3.19"


class ClickHouseConstraintMixin:
    """ClickHouse constraint capability declarations.

    Every value below is a live measurement against ClickHouse 26.7.3.19; see
    the module docstring for the instance, for the constraint catalog shape,
    and for the three engine facts the individual docstrings assume.
    """

    # ------------------------------------------------------------------
    # Constraint kinds
    #
    # Note the deliberate asymmetry with every other SQL backend: ClickHouse's
    # column level has no constraints at all -- the one exception is the
    # ``PRIMARY KEY`` column *modifier*, which is an engine parameter rather
    # than a constraint and is measured accepted (see
    # ``supports_primary_key_constraint``) -- while its table level has one
    # enforced kind (CHECK) plus one non-enforcing kind (ASSUME). Read this
    # section top to bottom before assuming a value was transposed.
    # ------------------------------------------------------------------

    def supports_primary_key_constraint(self) -> bool:
        """True -- the switch is about the column modifier, and that parses.

        Read this together with :meth:`supports_table_primary_key_constraint`
        and :meth:`supports_column_primary_key_constraint`, which are ``False``:
        ClickHouse has no primary-key **constraint** (no catalog row, no
        ``ADD CONSTRAINT ... PRIMARY KEY``), but it does accept a ``PRIMARY
        KEY`` **column modifier**, and on this core the flat switch is consulted
        in exactly one place -- core's ``format_column_primary_key_constraint``,
        which emits that modifier into a column definition.  The measured answer
        for the thing this switch gates is therefore ``True``.

        What is measured, on 26.7.3.19.  A primary key built through the
        constraint-shaped spellings does not exist::

            CREATE TABLE probe_pk (id Int32, c Int32, PRIMARY KEY (id))
                ENGINE = MergeTree ORDER BY id;                -- accepted
            SELECT count() FROM system.constraints
                WHERE database='test_db' AND table='probe_pk'; -- 0
            SELECT primary_key, sorting_key FROM system.tables
                WHERE database='test_db' AND name='probe_pk';  -- '(id)', 'id'

            ALTER TABLE probe_pk ADD CONSTRAINT pk1 PRIMARY KEY (id)
            -> Code: 62. DB::Exception: Syntax error: failed at position 41
               (PRIMARY): PRIMARY KEY (id).
               Expected one of: CHECK, ASSUME. (SYNTAX_ERROR)

        ``system.constraints`` on this release has no ``PRIMARY KEY`` value at
        all -- its ``type`` enum is ``Enum8('CHECK' = 0, 'ASSUME' = 1)`` -- so a
        primary key cannot be one, and the constraint claim is carried by the
        two per-level switches above, both ``False``.

        The column modifier, in contrast, is accepted, and it feeds the same
        engine parameters::

            ALTER TABLE probe_pk ADD COLUMN y Int32 PRIMARY KEY   -- accepted

        ``SHOW CREATE TABLE`` puts the key inside the ENGINE block with no
        ``CONSTRAINT`` clause anywhere.  So the keyword parses in the column
        grammar, and the resulting column reads back as
        ``system.columns.is_in_primary_key = 1``.

        Why the distinction is load-bearing rather than pedantic: core's model
        layer appends a ``ColumnPrimaryKeyConstraint`` to the column constraints
        of every non-composite ``__primary_key__`` field, and this package's own
        fixtures declare a PRIMARY KEY column constraint on each table's ``id``
        column.  Answering ``False`` here would refuse to render a CREATE TABLE
        for any model with a primary key -- a statement the server accepts --
        while claiming nothing the measurements support.  The refusal the
        measurements do support happens one level up: ``ADD CONSTRAINT ...
        PRIMARY KEY`` is Code 62, so
        :meth:`ClickHouseTableMixin.format_add_table_constraint_action`
        narrows the ADD position to CHECK before core renders it.
        """
        return True

    def supports_unique_constraint(self) -> bool:
        """False: ClickHouse has no UNIQUE constraint, at either level.

        ClickHouse 26.7.3.19::

            ALTER TABLE probe_t ADD CONSTRAINT uq1 UNIQUE (id)
            -> Code: 62. DB::Exception: Syntax error: failed at position 41
               (UNIQUE): UNIQUE (id).
               Expected one of: CHECK, ASSUME. (SYNTAX_ERROR)
            ALTER TABLE probe_t ADD COLUMN e3 Int32 UNIQUE
            -> Code: 62 ... Expected one of: SIGNED, UNSIGNED, COLLATE, NOT,
               NULL, DEFAULT, MATERIALIZED, ALIAS, EPHEMERAL, AUTO_INCREMENT,
               COMMENT, CODEC, STATISTICS, TTL, PRIMARY KEY, SETTINGS, FIRST,
               AFTER, token, Comma, ...
            CREATE TABLE probe_u (id Int32, c Int32, CONSTRAINT u1 UNIQUE (c))
                ENGINE = MergeTree ORDER BY id;   -- Code: 62, same message

        Uniqueness in ClickHouse is not a constraint but an *engine
        characteristic*: a ``ReplacingMergeTree`` / ``MergeTree`` deduplicates
        on the sorting key eventually, at merge time, and never rejects a row.
        A caller asking for a UNIQUE constraint wants rejection at write time,
        which no ClickHouse engine offers -- so this is a real ``False``, not a
        "not implemented yet".
        """
        return False

    def supports_not_null_constraint(self) -> bool:
        """True: ``NOT NULL`` is accepted as a column modifier.

        ClickHouse 26.7.3.19::

            ALTER TABLE probe_t ADD COLUMN x Int32 NOT NULL    -- accepted

        ``NOT NULL`` appears in the parser's own expected-token list for a
        column definition, alongside ``NULL``.  What the switch must not be
        read as claiming is that nullability is stored as a constraint: in
        ClickHouse nullability is part of the *type* (``Nullable(T)`` versus
        ``T``), and ``system.columns`` reports it there rather than in any
        constraint catalog. The keyword parses and the resulting column is not
        nullable, which is what the capability means.
        """
        return True

    def supports_check_constraint(self) -> bool:
        """False -- and the reason is the column level, not CHECK.

        **A table-level CHECK is real, enforced, and supported on this
        backend** (see :meth:`supports_table_check_constraint`, which is
        ``True``).  What does not exist is a *column-level* CHECK, and this
        switch is the one core's column-level branch formatter consults::

            # backend/dialect/mixins/ddl_column.py,
            # format_column_check_constraint(ColumnCheckConstraint)
            if not self.supports_check_constraint():
                raise UnsupportedFeatureError(self.name, "CHECK column constraint")

        so answering ``True`` here would make that formatter emit ``CHECK
        (...)`` into a column definition -- which ClickHouse rejects::

            ALTER TABLE probe_t ADD COLUMN e1 Int32 CHECK e1 > 0
            ALTER TABLE probe_t ADD COLUMN e2 Int32 CONSTRAINT cc CHECK (e2 > 0)
            -> Code: 62. DB::Exception: Syntax error: failed at position 42
               (CHECK): CHECK e1 > 0. Expected one of: SIGNED, UNSIGNED,
               COLLATE, NOT, NULL, DEFAULT, MATERIALIZED, ALIAS, EPHEMERAL,
               AUTO_INCREMENT, COMMENT, CODEC, STATISTICS, TTL, PRIMARY KEY,
               SETTINGS, FIRST, AFTER, token, Comma, INTO OUTFILE, FORMAT,
               ParallelWithClause, PARALLEL WITH, end of query.

        The value is ``False`` so that the column path refuses the constraint
        by name, which is the truthful outcome; the table path is covered by
        :meth:`supports_table_check_constraint`.

        Core's S3 already split the constraint **nodes**, so the kind is now a
        branch class (``ColumnCheckConstraint``) rather than a tag -- but it did
        not split this *switch*.  Both halves stay answerable and only this pair
        of names tells them apart, which is why ``supports_check_constraint``
        (``False``) and ``supports_table_check_constraint`` (``True``) coexist.
        """
        return False

    def supports_foreign_key_constraint(self) -> bool:
        """False: ClickHouse has no FOREIGN KEY, at either level.

        ClickHouse 26.7.3.19::

            ALTER TABLE probe_t ADD CONSTRAINT fk1 FOREIGN KEY (id)
                REFERENCES probe_t(id)
            -> Code: 62. DB::Exception: Syntax error: failed at position 41
               (FOREIGN): FOREIGN KEY (id) REFERENCES probe_t(id).
               Expected one of: CHECK, ASSUME. (SYNTAX_ERROR)
            ALTER TABLE probe_t ADD COLUMN e4 Int32 REFERENCES probe_t(id)
            -> Code: 62 ... Expected one of: SIGNED, UNSIGNED, COLLATE, ...

        There is no referential-integrity mechanism to build on, so this is
        not an "unsupported for now": ``REFERENCES`` is absent from both the
        table-constraint grammar and the column-modifier grammar.
        """
        return False

    def supports_fk_on_delete(self) -> bool:
        """False: there is no foreign key to attach a referential action to.

        ClickHouse 26.7.3.19 rejects ``FOREIGN KEY`` itself with Code 62
        ("Expected one of: CHECK, ASSUME."), so the ``ON DELETE`` spelling is
        unreachable rather than merely unimplemented -- see
        :meth:`supports_foreign_key_constraint` for the measured statement.

        Declared here so the ``False`` is a measurement rather than an
        inherited default that a core change could quietly flip.
        """
        return False

    def supports_fk_on_update(self) -> bool:
        """False: same reason as :meth:`supports_fk_on_delete`.

        ClickHouse 26.7.3.19 rejects ``FOREIGN KEY`` at the parser (Code 62,
        "Expected one of: CHECK, ASSUME."), so ``ON UPDATE`` -- the clause even
        the SQL-standard front runners such as Oracle 21c lack -- has nothing
        to attach to here.
        """
        return False

    def supports_exclude_constraint(self) -> bool:
        """False: ``EXCLUDE`` is not among the two kinds ClickHouse has.

        ClickHouse 26.7.3.19 enumerates the complete accepted set whenever a
        third kind is attempted::

            Expected one of: CHECK, ASSUME.

        No ``EXCLUDE`` appears, and neither PostgreSQL 19beta4 nor any other
        measured sibling would accept it at this position either.  Core already
        defaults this to ``False``; the declaration records the measurement.
        """
        return False

    # ------------------------------------------------------------------
    # Column level: ClickHouse has no column constraints at all.
    #
    # These five are the per-level names from the coverage plan. They are
    # declared rather than left to be inferred so that "ClickHouse has no
    # column constraints" is stated once, explicitly, next to the evidence,
    # instead of being a reader's job to deduce from the table-level values.
    # Core's S3 wave moved the constraint *nodes* and did not add a protocol
    # for these per-level switches, so they keep their names.
    # ------------------------------------------------------------------

    def supports_column_primary_key_constraint(self) -> bool:
        """False: a column's ``PRIMARY KEY`` is an engine modifier, not a constraint.

        ClickHouse 26.7.3.19 accepts ``ALTER TABLE ... ADD COLUMN y Int32
        PRIMARY KEY`` -- ``PRIMARY KEY`` is in the parser's expected-token list
        for a column -- but the result is not a constraint: ``y`` simply reads
        back as ``is_in_primary_key = 1`` in ``system.columns`` and
        ``system.tables.primary_key`` moves; ``system.constraints`` stays empty
        (measured ``count() = 0`` on a table created with ``PRIMARY KEY (id)``).

        The switch is about the *constraint*, so it answers ``False``.

        Note the deliberate split with the flat
        :meth:`supports_primary_key_constraint`, which is ``True`` on the same
        release: that switch gates the ``PRIMARY KEY`` column *modifier* (which
        renders), this one names the per-level *constraint* (which does not
        exist). One boolean cannot carry both halves, which is why the two
        coexist; see the flat switch's docstring for the full measurement.
        """
        return False

    def supports_column_unique_constraint(self) -> bool:
        """False: column-level ``UNIQUE`` is not in the column grammar.

        ClickHouse 26.7.3.19::

            ALTER TABLE probe_t ADD COLUMN e3 Int32 UNIQUE
            -> Code: 62. DB::Exception: Syntax error: failed at position 42
               (UNIQUE): UNIQUE. Expected one of: SIGNED, UNSIGNED, COLLATE,
               NOT, NULL, DEFAULT, MATERIALIZED, ALIAS, EPHEMERAL,
               AUTO_INCREMENT, COMMENT, CODEC, STATISTICS, TTL, PRIMARY KEY,
               SETTINGS, FIRST, AFTER, token, Comma, ...

        The expected-token list is the entire column-modifier set, and
        ``UNIQUE`` is not in it.
        """
        return False

    def supports_column_check_constraint(self) -> bool:
        """False: a column cannot carry a CHECK, in either spelling.

        ClickHouse 26.7.3.19 rejects both ``c Int32 CHECK c > 0`` and
        ``c Int32 CONSTRAINT cc CHECK (c > 0)`` with Code 62, listing the whole
        accepted column-modifier set -- ``SIGNED, UNSIGNED, COLLATE, NOT, NULL,
        DEFAULT, MATERIALIZED, ALIAS, EPHEMERAL, AUTO_INCREMENT, COMMENT,
        CODEC, STATISTICS, TTL, PRIMARY KEY, SETTINGS, FIRST, AFTER, token,
        Comma, ...`` -- which contains neither ``CHECK`` nor ``CONSTRAINT``.

        Constraints are table-level only on this engine; see
        :meth:`supports_table_check_constraint` for the kind that does exist.
        """
        return False

    def supports_column_foreign_key_constraint(self) -> bool:
        """False: ``REFERENCES`` is not in the column-modifier grammar.

        ClickHouse 26.7.3.19::

            ALTER TABLE probe_t ADD COLUMN e4 Int32 REFERENCES probe_t(id)
            -> Code: 62. DB::Exception: Syntax error: failed at position 42
               (REFERENCES): REFERENCES probe_t(id). Expected one of: SIGNED,
               UNSIGNED, COLLATE, NOT, NULL, DEFAULT, MATERIALIZED, ALIAS,
               EPHEMERAL, AUTO_INCREMENT, COMMENT, CODEC, STATISTICS, TTL,
               PRIMARY KEY, SETTINGS, FIRST, AFTER, token, Comma, ...
        """
        return False

    def supports_column_nullable_constraint(self) -> bool:
        """True: ``NULL`` / ``NOT NULL`` are accepted column modifiers.

        ClickHouse 26.7.3.19 lists both ``NULL`` and ``NOT`` among the tokens a
        column definition may carry (``ALTER TABLE ... ADD COLUMN x Int32 NOT
        NULL`` is accepted), and :meth:`supports_not_null_constraint` carries
        the measurement.  Declared separately because the coverage plan treats
        the nullable and not-null halves as two switches.

        The underlying fact is still that nullability lives in the type
        (``Nullable(T)``), not in a constraint catalog.
        """
        return True

    # ------------------------------------------------------------------
    # Column value expressions -- the neighbouring capability, and the one
    # with the sharpest edge on this engine.
    # ------------------------------------------------------------------

    def supports_default_column_value_expression(self) -> bool:
        """True: a column ``DEFAULT`` may be an arbitrary expression.

        ClickHouse 26.7.3.19 accepts any expression in the ``DEFAULT`` position
        of a column definition -- ``DEFAULT now()``, ``DEFAULT if(a, b, c)``,
        ``DEFAULT a + b`` -- and evaluates it per row on write.

        **This is also the backend's sharpest trap, and it is why the ``True``
        here must not be read as licence to render anything.**  A column default
        is an arbitrary expression, so a *comparison* parses in that position
        too, is accepted, and is silently evaluated to 0/1::

            ALTER TABLE probe_pk ADD COLUMN d Int32 DEFAULT c > 0;  -- accepted
            INSERT INTO probe_pk (id, c) VALUES (1, 7), (2, -7);
            SELECT id, c, d FROM probe_pk ORDER BY id;
            -- (1,  7, 1)
            -- (2, -7, 0)

        No error, no warning: an intended constraint check has become a boolean
        default column.  A renderer that turns a CHECK-shaped predicate into a
        column ``DEFAULT`` will therefore *succeed* and produce a table that
        stores the violating row.  The refusal has to happen in the render path
        before the SQL is emitted -- the server will not do it.  That gate is a
        render-path concern rather than a switch value, so this declaration
        records only that the server accepts an expression here.
        """
        return True

    def supports_generated_column(self) -> bool:
        """False: no SQL-standard ``GENERATED ... AS (...)`` computed column.

        ClickHouse has no generated-column clause; the nearest spellings are
        its own four default kinds -- ``MATERIALIZED`` / ``ALIAS`` /
        ``EPHEMERAL`` / ``DEFAULT`` -- which are rendered from
        :class:`~rhosocial.activerecord.backend.impl.clickhouse.expression.column.ClickHouseColumnDefinition`
        rather than from a ``GENERATED`` constraint.  ``ALIAS`` in particular is
        not stored at all and ``EPHEMERAL`` is not visible after INSERT, so
        neither should be reached through a generic "generated column" request.

        Measured on 26.7.3.19: the parser prints the complete column-modifier
        set when any column definition is rejected, and ``GENERATED`` is not in
        it (see :meth:`supports_column_check_constraint` for the list quoted in
        full -- ``SIGNED, UNSIGNED, COLLATE, NOT, NULL, DEFAULT, MATERIALIZED,
        ALIAS, EPHEMERAL, AUTO_INCREMENT, COMMENT, CODEC, STATISTICS, TTL,
        PRIMARY KEY, SETTINGS, FIRST, AFTER, token, Comma, ...``).

        Distinct from :meth:`supports_default_column_value_expression`, which is
        ``True``: a generated column and a defaulted column are different
        mechanisms even where both carry an expression.
        """
        return False

    # ------------------------------------------------------------------
    # Table level: CHECK is the one enforced kind, ASSUME the one that is not.
    # ------------------------------------------------------------------

    def supports_table_check_constraint(self) -> bool:
        """True: ``CONSTRAINT <name> CHECK <expr>`` is accepted and enforced.

        ClickHouse 26.7.3.19, at both statement shapes::

            ALTER TABLE probe_t ADD CONSTRAINT ck CHECK c > 0
                -- accepted; SELECT name, type, expression FROM system.constraints
                --   ck | CHECK | c > 0
            CREATE TABLE probe_ct (id Int32, c Int32,
                                   CONSTRAINT ckc CHECK c > 0)
                ENGINE = MergeTree ORDER BY id;                 -- accepted

        Enforcement is real, at write time, with a dedicated error code::

            INSERT INTO probe_t (id, c) VALUES (1, -5);
            -> Code: 469. DB::Exception: Constraint `ck` for table
               test_db.probe_cc (...) is violated at row 1. Expression: (c > 0).
               Column values: c = -5: While executing WaitForAsyncInsert.
               (VIOLATED_CONSTRAINT)

        The expression is **not** restricted to a comparison grammar the way
        some siblings' ``CHECK`` is; ``MODIFY CONSTRAINT ck CHECK c > 100``
        re-reads as ``expression = 'c > 100'`` in ``system.constraints``, so an
        arbitrary expression is stored and evaluated.  Performance note: every
        INSERT is evaluated against every CHECK expression, so a table carrying
        several of them pays for all of them on every write.

        Table-level only -- see :meth:`supports_check_constraint` for why the
        flat switch answers ``False`` on this release.
        """
        return True

    def supports_table_primary_key_constraint(self) -> bool:
        """False: the primary key lives in the ENGINE parameter block.

        ClickHouse 26.7.3.19, ``CREATE TABLE probe_pk (id Int32, c Int32,
        PRIMARY KEY (id)) ENGINE = MergeTree ORDER BY id`` is accepted, but
        ``system.constraints`` for that table holds **0 rows** while
        ``system.tables.primary_key`` reads ``(id)``, ``sorting_key`` reads
        ``id`` and ``system.columns.is_in_primary_key`` reads ``1`` for ``id``
        and ``0`` for ``c``.  ``SHOW CREATE TABLE`` puts the key back inside
        the ENGINE block with no ``CONSTRAINT`` clause anywhere.

        ``ADD CONSTRAINT ... PRIMARY KEY`` is Code 62 ("Expected one of: CHECK,
        ASSUME."), so there is no ALTER-side spelling either.  See
        :meth:`supports_primary_key_constraint` for the full measurement.
        """
        return False

    def supports_table_unique_constraint(self) -> bool:
        """False: only CHECK and ASSUME are in the table-constraint grammar.

        ClickHouse 26.7.3.19 states the complete set itself, twice::

            ALTER TABLE probe_t ADD CONSTRAINT uq1 UNIQUE (id)
            -> Code: 62 ... Expected one of: CHECK, ASSUME. (SYNTAX_ERROR)
            CREATE TABLE probe_u (id Int32, c Int32, CONSTRAINT u1 UNIQUE (c))
                ENGINE = MergeTree ORDER BY id;   -- Code: 62, same message
        """
        return False

    def supports_table_foreign_key_constraint(self) -> bool:
        """False: only CHECK and ASSUME are in the table-constraint grammar.

        ClickHouse 26.7.3.19::

            ALTER TABLE probe_t ADD CONSTRAINT fk1 FOREIGN KEY (id)
                REFERENCES probe_t(id)
            -> Code: 62 ... Expected one of: CHECK, ASSUME. (SYNTAX_ERROR)
            CREATE TABLE probe_f (id Int32, c Int32,
                CONSTRAINT f1 FOREIGN KEY (c) REFERENCES probe_ct(id))
                ENGINE = MergeTree ORDER BY id;   -- Code: 62, same message
        """
        return False

    def supports_table_exclude_constraint(self) -> bool:
        """False: ``EXCLUDE`` is absent from the two accepted kinds.

        ClickHouse 26.7.3.19 answers every rejected third kind with the same
        enumeration -- ``Expected one of: CHECK, ASSUME.`` -- and ``EXCLUDE``
        is not in it. Core already defaults this to ``False``; the declaration
        records the measurement.
        """
        return False

    def supports_assume_constraint(self) -> bool:
        """True: ClickHouse's second constraint kind, ``ASSUME <expr>``.

        ClickHouse 26.7.3.19, accepted at both statement shapes::

            ALTER TABLE probe_t ADD CONSTRAINT ak ASSUME c > 1000
            CREATE TABLE probe_ta (id Int32, c Int32,
                                   CONSTRAINT akc ASSUME c > 0)
                ENGINE = MergeTree ORDER BY id;
            ALTER TABLE probe_t MODIFY CONSTRAINT ak ASSUME c > 0   -- accepted

        and visible in the catalog through the ``type`` enum::

            SELECT name, type, expression FROM system.constraints
                WHERE table='probe_t';
            -- ak | ASSUME | c > 1000

        **It is not enforced.**  With ``ak`` the only constraint on a table::

            INSERT INTO probe_t (id, c) VALUES (3, -5);   -- accepted, stored

        That is the whole reason this switch exists and is separate from
        :meth:`supports_table_check_constraint`: an expression that can never
        reject a row is not a constraint, and rendering it under a CHECK-shaped
        node would tell the caller their predicate is being enforced when the
        server will happily store the violating row.  Callers opt in explicitly.

        Name note: this is the backend-only switch from
        ``.claude/plan/2026-10-11/clickhouse-constraint-coverage.md``.  There is
        no core protocol for it and no core branch class for it -- core's
        table-constraint branches are PRIMARY KEY, UNIQUE, CHECK, FOREIGN KEY
        and EXCLUDE -- so it survives S3 with its name and its measured value.
        A renderer must never spell ``ASSUME`` where ``CHECK`` is implied.
        """
        return True

    # ------------------------------------------------------------------
    # SQL-standard clauses ClickHouse has no spelling for
    # ------------------------------------------------------------------

    def supports_fk_match(self) -> bool:
        """False: no ``MATCH {SIMPLE|PARTIAL|FULL}``, and no foreign key to carry it.

        ClickHouse 26.7.3.19 rejects ``FOREIGN KEY`` itself at the parser (Code
        62, "Expected one of: CHECK, ASSUME."), so ``MATCH`` is unreachable
        rather than unimplemented.  Unlike MySQL 8, which parses ``MATCH FULL``
        and then silently drops it, there is nothing here that would be
        accepted-and-ignored.
        """
        return False

    def supports_constraint_naming(self) -> bool:
        """True: ``CONSTRAINT <name>`` is accepted on both constraint kinds.

        ClickHouse 26.7.3.19, at the table level and inside a column list::

            ALTER TABLE probe_t ADD CONSTRAINT ck CHECK c > 0   -- accepted
            ALTER TABLE probe_t ADD CONSTRAINT ak ASSUME c > 1000  -- accepted
            CREATE TABLE probe_ct (id Int32, c Int32,
                                   CONSTRAINT ckc CHECK c > 0)
                ENGINE = MergeTree ORDER BY id;                 -- accepted

        and the name is what the constraint catalog is keyed by, so it is not
        merely tolerated::

            SELECT name, type, expression FROM system.constraints
                WHERE database='test_db' AND table='probe_ct';
            -- ckc | CHECK | c > 0

        Declared here rather than left to core's default of ``True``: core's
        default is shared with the dummy dialect and is exactly the kind of
        value that can move, and on this backend the answer is *load-bearing*
        rather than cosmetic -- the name is how a later
        ``ALTER TABLE ... DROP CONSTRAINT`` or ``MODIFY CONSTRAINT`` reaches
        the constraint again.

        The column level has no constraint to name at all (Code 62; see
        :meth:`supports_column_check_constraint`), so this switch speaks only
        about the table-level ``CONSTRAINT <name>`` prefix.  Core consults it in
        ``format_table_constraint``; this backend renders the prefix itself, so
        the value is pinned by test rather than by a render.
        """
        return True

    def supports_deferrable_constraint(self) -> bool:
        """False: no ``DEFERRABLE`` / ``INITIALLY``, and nothing to defer.

        ClickHouse 26.7.3.19 prints the same two-token expectation for a third
        constraint kind and a deferral clause alike (``Expected one of: CHECK,
        ASSUME.``); more fundamentally there is no transaction to defer to --
        ClickHouse mutations are asynchronous and are not rolled back, which is
        why even the enforced ``CHECK`` fails the INSERT itself (Code 469)
        instead of the COMMIT.

        Oracle 21c is the one measured backend where ``DEFERRABLE`` is real;
        that does not carry over.
        """
        return False

    def supports_constraint_enforced(self) -> bool:
        """False: no ``ENFORCED`` / ``NOT ENFORCED`` clause.

        ClickHouse 26.7.3.19 accepts ``ADD CONSTRAINT name CHECK <expr>`` only
        in that spelling -- the expectation list is ``CHECK, ASSUME`` and
        nothing follows the expression, so a trailing ``ENFORCED`` /
        ``NOT ENFORCED`` is not part of the grammar.

        Enforcement is not a clause to be spelled here either: it is decided by
        *which kind* you picked.  ``CHECK`` enforces (Code 469 at write time),
        ``ASSUME`` does not (the violating row is stored).  So a caller asking
        for ``NOT ENFORCED`` on a CHECK is asking for the ASSUME behaviour and
        must ask for it as ASSUME, not as a modifier -- see
        :meth:`supports_assume_constraint`.
        """
        return False

    # ------------------------------------------------------------------
    # ALTER TABLE constraint lifecycle
    #
    # Measured: the ALTER command grammar contains exactly three constraint
    # commands -- ADD CONSTRAINT, MODIFY CONSTRAINT, DROP CONSTRAINT. Every
    # other lifecycle verb is a Code 62 syntax error, and for VALIDATE /
    # ENABLE / DISABLE the error message enumerates that list verbatim.
    # ------------------------------------------------------------------

    def supports_add_constraint(self) -> bool:
        """True: ``ALTER TABLE ... ADD CONSTRAINT`` exists -- for CHECK and ASSUME.

        ClickHouse 26.7.3.19::

            ALTER TABLE probe_t ADD CONSTRAINT ck CHECK c > 0      -- accepted
            ALTER TABLE probe_t ADD CONSTRAINT ak ASSUME c > 1000  -- accepted

        and for every other kind the parser names the complete accepted set::

            ALTER TABLE probe_t ADD CONSTRAINT pk1 PRIMARY KEY (id)
            ALTER TABLE probe_t ADD CONSTRAINT uq1 UNIQUE (id)
            ALTER TABLE probe_t ADD CONSTRAINT fk1 FOREIGN KEY (id) REFERENCES ...
            -> Code: 62. DB::Exception: Syntax error: ... Expected one of:
               CHECK, ASSUME. (SYNTAX_ERROR)

        So this switch is ``True`` while
        :meth:`supports_primary_key_constraint`,
        :meth:`supports_unique_constraint` and
        :meth:`supports_foreign_key_constraint` are ``False``: the *operation*
        exists, and it exists only for two *kinds*.  A single boolean cannot
        carry both halves, which is precisely why the core S3 split asks for
        one switch per kind.
        """
        return True

    def supports_drop_constraint(self) -> bool:
        """True: ``ALTER TABLE ... DROP CONSTRAINT name`` is accepted.

        ClickHouse 26.7.3.19::

            ALTER TABLE probe_t ADD CONSTRAINT ck CHECK c > 0   -- accepted
            ALTER TABLE probe_t DROP CONSTRAINT ck               -- accepted
            SELECT count() FROM system.constraints
                WHERE table='probe_t' AND name='ck';             -- 0

        Dropping a constraint that is not there is an **error**, not a no-op::

            ALTER TABLE probe_t DROP CONSTRAINT nope
            -> Code: 36. DB::Exception: Wrong constraint name.
               Cannot find constraint `nope` to drop. (BAD_ARGUMENTS)

        So the idempotent path is ``DROP CONSTRAINT IF EXISTS``, declared by
        :class:`ClickHouseDDLColumnMixin` -- catching Code 36 instead would be
        the wrong shape here, and would not be portable to MySQL at all (which
        has no ``DROP CONSTRAINT IF EXISTS`` and fails at the parser).

        Note the namespace consequence: because the primary key is not a
        constraint, it cannot be named here.  Changing a ClickHouse primary key
        is an ENGINE change, not a constraint drop.
        """
        return True

    def supports_alter_constraint(self) -> bool:
        """False: SQL's ``ALTER CONSTRAINT`` verb is not in ClickHouse's grammar.

        ClickHouse 26.7.3.19::

            ALTER TABLE probe_t ALTER CONSTRAINT ak CHECK c > 0
            -> Code: 62. DB::Exception: Syntax error: failed at position 28
               (CONSTRAINT): CONSTRAINT ak CHECK c > 0.
               Expected COLUMN. (SYNTAX_ERROR)

        The parser wanted the ``COLUMN`` of ``RENAME COLUMN``, which is what
        ``ALTER TABLE ... ALTER`` accepts.  **ClickHouse does have a way to
        redefine an existing constraint**, and it is a different keyword::

            ALTER TABLE probe_t MODIFY CONSTRAINT ck CHECK c > 100
            -- accepted; system.constraints re-reads expression = 'c > 100'
            ALTER TABLE probe_t MODIFY CONSTRAINT ak ASSUME c > 0
            -- accepted

        ``MODIFY`` is not the ``ALTER`` this switch is named after -- it cannot
        add enforcement control, only replace the expression in place -- so the
        answer is ``False`` and the ``MODIFY`` spelling is described here rather
        than being claimed by this switch.

        The probe takes no argument (pattern 1 of the reconciliation rules): a
        probe answers "is this capability family present on this server", and
        the kind is not part of that question.
        """
        return False

    def supports_alter_constraint_enforced(self) -> bool:
        """False: there is no ``ALTER CONSTRAINT`` to hang enforcement control on.

        ClickHouse 26.7.3.19 rejects the verb itself -- ``ALTER TABLE ... ALTER
        CONSTRAINT`` is Code 62 ("Expected COLUMN."), see
        :meth:`supports_alter_constraint` -- and the ADD side has no
        ``ENFORCED`` / ``NOT ENFORCED`` to carry either
        (:meth:`supports_constraint_enforced`).

        The probe takes no argument (pattern 1).  ClickHouse's answer does not
        vary by kind, and the reason it used to be written as a per-kind probe
        was a signature core no longer calls: neither CHECK nor ASSUME has an
        enforcement flag to flip.  It is the choice of *kind* that decides
        enforcement, and that choice is not revisable after the fact.

        Where the per-kind half lives: nowhere, on this backend -- see
        :meth:`supports_constraint_enforced`, whose answer is the same for every
        kind, and the module docstring's "Where the narrowing went".
        """
        return False

    def supports_validate_constraint(self) -> bool:
        """False: ``VALIDATE CONSTRAINT`` is not in the ALTER TABLE grammar.

        ClickHouse 26.7.3.19 is unusually explicit about this -- the error for
        an unrecognised ALTER command enumerates the entire accepted command
        set, and the constraint commands in it are exactly three::

            ALTER TABLE probe_t VALIDATE CONSTRAINT ak
            -> Code: 62. DB::Exception: Syntax error: failed at position 22
               (VALIDATE): ... Expected one of: ON, a list of ALTER commands,
               ALTER command, ADD COLUMN, RENAME COLUMN, MATERIALIZE COLUMN,
               DROP PARTITION, ... ADD CONSTRAINT, MODIFY CONSTRAINT,
               DROP CONSTRAINT, DETACH PARTITION, ...

        So there is nothing to validate *with* -- and nothing that needs to be:
        a CHECK is enforced on every INSERT as it happens (Code 469), so the
        rows already in the table were checked when they were written.  Adding
        a CHECK does not re-examine history.
        """
        return False

    def supports_constraint_novalidate(self) -> bool:
        """False: no ``NOT VALID`` clause, on the ADD path or anywhere else.

        ClickHouse 26.7.3.19, against a table-level CHECK::

            ALTER TABLE probe_t ADD CONSTRAINT ck CHECK c > 0 NOT VALID
            -> Code: 62. DB::Exception: Syntax error: ... Expected one of:
               CHECK, ASSUME. (SYNTAX_ERROR)

        The expectation list is emitted right after ``CONSTRAINT <name>``, so
        the only continuations are the two kinds.  Nothing about a ClickHouse
        CHECK needs an unvalidated state -- it is evaluated per INSERT and
        there is no DDL-time backfill to defer -- but that is an observation,
        not a substitute for the rejection: the clause is simply not spelled.
        """
        return False

    def supports_rename_constraint(self) -> bool:
        """False: no ``RENAME CONSTRAINT ... TO ...``.

        ClickHouse 26.7.3.19::

            ALTER TABLE probe_t RENAME CONSTRAINT ak TO ak2
            -> Code: 62. DB::Exception: Syntax error: failed at position 29
               (CONSTRAINT): CONSTRAINT ak TO ak2.
               Expected COLUMN. (SYNTAX_ERROR)

        The parser wanted the ``COLUMN`` of ``RENAME COLUMN``; the constraint
        commands in the ALTER grammar are ADD / MODIFY / DROP only (enumerated
        verbatim by :meth:`supports_validate_constraint`).  SQL Server's
        stored-procedure escape hatch has no ClickHouse equivalent either.

        Name note: this is one of the switches core's protocol does not own, so
        core S3 -- which moved the constraint nodes, not the ALTER lifecycle --
        left it alone.
        """
        return False

    def supports_enable_disable_constraint(self) -> bool:
        """False: ``ENABLE`` / ``DISABLE CONSTRAINT`` are not ClickHouse keywords.

        ClickHouse 26.7.3.19, against a live constraint::

            ALTER TABLE probe_t ENABLE  CONSTRAINT ak
            -> Code: 62. DB::Exception: Syntax error: failed at position 22
               (ENABLE): ... Expected one of: ON, a list of ALTER commands,
               ALTER command, ADD COLUMN, RENAME COLUMN, ... ADD CONSTRAINT,
               MODIFY CONSTRAINT, DROP CONSTRAINT, ...
            ALTER TABLE probe_t DISABLE CONSTRAINT ak
            -> Code: 62 ... same expectation list, failed at (DISABLE)

        The listed expectation is the complete ALTER command set, and it holds
        no ENABLE or DISABLE.  This is not a near miss: of the backends
        measured this session only Oracle spells these two, and PostgreSQL's
        similar-looking ``ENABLE TRIGGER`` is a different object.

        What to reach for instead: ``DROP CONSTRAINT`` then ``ADD CONSTRAINT``.
        Name note: this is one of the switches core's protocol does not own, so
        core S3 -- which moved the constraint nodes, not the ALTER lifecycle --
        left it alone.
        """
        return False

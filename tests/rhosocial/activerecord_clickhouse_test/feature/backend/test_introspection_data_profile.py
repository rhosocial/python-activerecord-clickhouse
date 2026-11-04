# tests/rhosocial/activerecord_clickhouse_test/feature/backend/test_introspection_data_profile.py
"""The data-profile family, measured against a real server.

Rendering these statements proves only that they are well-formed. What needs
checking is whether ClickHouse accepts them, and whether the arithmetic the
parser performs -- turning ``null_count / row_count`` into a fraction, reading
``COUNT(DISTINCT ...)`` as a count, carrying the ``source`` label, and attaching
the runtime types -- lands on values a hand count agrees with. That is only
answerable against a server.

The table is a hundred rows, built so every figure is arithmetic rather than
guesswork:

    id      Int32 NOT NULL          i, unique               -> 100 distinct, no nulls
    code    String NOT NULL         "a"/"b"/"c" by i % 3    -> 3 distinct, no nulls
    amount  Decimal(10,2) NOT NULL  i, unique               -> 100 distinct, no nulls
    note    Nullable(String)        "x" when i % 5 == 0, "y" when i % 5 == 1,
                                    NULL otherwise          -> 2 distinct, 60% null

The size is modest on purpose: the rows are aggregated, so nothing depends on a
sample being large. It only has to be big enough that a duplicate silently
dropped by ``COUNT(DISTINCT ...)``, or a NULL miscounted by the ``SUM(CASE ...)``
arm, would move a number off its hand-counted value -- which a hundred rows does.

Three shapes differ from the PostgreSQL test and are pinned here rather than
left to be discovered. First, the rows are aggregated, so every figure is
``aggregate`` and exact, while PostgreSQL reads ``pg_stats`` and answers
``estimate``. Second, the endpoints arrive as text: ClickHouse refuses a
``UNION ALL`` whose arms disagree on a column's type, so ``min_value`` and
``max_value`` are cast to ``Nullable(String)`` in every arm, and a numeric
endpoint is read back through ``Decimal`` rather than compared to a number.
Third, and only here, each profile carries ``runtime_types`` -- the type names
the engine grouped over ``typeof(column)`` -- which is a fact about the data
that no other engine in this family will answer.

The listing and the coverage measurement are ordinary aggregates: ClickHouse
groups NULLs into a real row, so a column holding NULLs has a NULL entry in its
listing, and coverage is counted over distinct non-NULL values on both sides.

The one thing this file can settle with no server at all is the *spelling* of
the function names, because the failure it guards against -- an upper-cased
camelCase name the server then reports as not existing -- is visible in the
rendered SQL. ``TestFunctionNameCase`` pins that: every name that reaches SQL is
written the way ClickHouse's function factories register it, so a future edit
that hands a camelCase name back to the shared renderer's ``.upper()`` fails
here instead of on five CI jobs.
"""

from decimal import Decimal

import pytest
from rhosocial.activerecord.backend.expression.introspection import (
    ColumnDataProfileQueryStatement,
    ColumnValueSampleQueryStatement,
    JoinCoverageQueryStatement,
)

from rhosocial.activerecord.backend.impl.clickhouse.dialect import ClickHouseDialect
from rhosocial.activerecord.backend.impl.clickhouse.introspection.introspector import (
    ClickHouseIntrospectorMixin,
)

TABLE = "intro_profile_orders"
CUSTOMERS = "intro_profile_customers"
CODES = ("a", "b", "c")

ROWS = 100

#: ``note`` is NULL on 60 of the 100 rows, "x" on 20 and "y" on 20.
NULL_SHARE = 0.6
NOTE_COUNT = 20


def _rows():
    rows = []
    for i in range(1, ROWS + 1):
        if i % 5 == 0:
            note = "x"
        elif i % 5 == 1:
            note = "y"
        else:
            note = None
        rows.append((i, CODES[i % 3], Decimal(i), note))
    return rows


def _setup(backend):
    backend.execute(f"DROP TABLE IF EXISTS `{TABLE}`")
    backend.execute(f"DROP TABLE IF EXISTS `{CUSTOMERS}`")
    backend.execute(
        f"CREATE TABLE `{TABLE}` ("
        "`id` Int32, "
        "`code` String, "
        "`amount` Decimal(10,2), "
        "`note` Nullable(String)"
        ") ENGINE = MergeTree ORDER BY id"
    )
    backend.execute_many(
        f"INSERT INTO `{TABLE}` (`id`, `code`, `amount`, `note`) " "VALUES (%s, %s, %s, %s)",
        _rows(),
    )
    # The right side of every coverage measurement: four codes and one NULL.
    # The NULL is the point -- it is not a value of the domain, so right
    # coverage is 3/4 and not 3/5.
    backend.execute(
        f"CREATE TABLE `{CUSTOMERS}` ("
        "`id` Int32, "
        "`code` Nullable(String)"
        ") ENGINE = MergeTree ORDER BY id"
    )
    backend.execute_many(
        f"INSERT INTO `{CUSTOMERS}` (`id`, `code`) VALUES (%s, %s)",
        [(1, "a"), (2, "b"), (3, "c"), (4, "d"), (5, None)],
    )


def _teardown(backend):
    backend.execute(f"DROP TABLE IF EXISTS `{TABLE}`")
    backend.execute(f"DROP TABLE IF EXISTS `{CUSTOMERS}`")


class TestColumnDataProfile:
    """What the rows hold, counted by the server rather than declared."""

    def test_profile_matches_a_hand_count(self, clickhouse_backend):
        _setup(clickhouse_backend)
        try:
            profiles = {
                profile.column_name: profile
                for profile in clickhouse_backend.introspector.list_column_data_profiles(TABLE)
            }
            assert set(profiles) == {"id", "code", "amount", "note"}

            # A unique key: 100 distinct values, none of them NULL.
            assert profiles["id"].null_fraction == 0.0
            assert profiles["id"].distinct_count == ROWS
            assert Decimal(str(profiles["id"].min_value)) == Decimal(1)
            assert Decimal(str(profiles["id"].max_value)) == Decimal(ROWS)

            # Three values, none null. COUNT(DISTINCT ...) skips NULL on its
            # own, so the count agrees with the listing below.
            assert profiles["code"].null_fraction == 0.0
            assert profiles["code"].distinct_count == len(CODES)
            assert profiles["code"].min_value == "a"
            assert profiles["code"].max_value == "c"

            # The endpoint is text because the union's arms must agree on a
            # type; the figure is exact and only the Python type is the
            # union's, which is why this reads it through Decimal.
            assert profiles["amount"].null_fraction == 0.0
            assert profiles["amount"].distinct_count == ROWS
            assert Decimal(str(profiles["amount"].min_value)) == Decimal("1")
            assert Decimal(str(profiles["amount"].max_value)) == Decimal("100")

            # 60 of 100 rows are NULL, so a profile that dropped the figure
            # or clamped it would still look plausible.
            assert profiles["note"].null_fraction == pytest.approx(NULL_SHARE)
            assert profiles["note"].distinct_count == 2
            assert profiles["note"].min_value == "x"
            assert profiles["note"].max_value == "y"
        finally:
            _teardown(clickhouse_backend)

    def test_every_profile_says_it_was_aggregated(self, clickhouse_backend):
        """The label rides the row, so a consumer never has to guess.

        There is no statistics catalogue to read, so every figure here is an
        exact count of the rows -- and the answer says so in ``source`` rather
        than leaving a caller to infer it from which engine answered. There is
        no ``collected_at``: an aggregate is current by construction, and
        inventing a timestamp would make it look like a stale estimate.
        """
        _setup(clickhouse_backend)
        try:
            profiles = clickhouse_backend.introspector.list_column_data_profiles(TABLE)
            assert profiles
            assert {profile.source for profile in profiles} == {"aggregate"}
            for profile in profiles:
                assert profile.collected_at is None
                assert profile.row_count == ROWS
        finally:
            _teardown(clickhouse_backend)

    def test_the_runtime_types_are_reported(self, clickhouse_backend):
        """The declared type is not the whole story, and this says so.

        ``id`` is declared ``Int32`` and every value in it is an ``Int32``, so
        the set holds one name. ``note`` is declared ``Nullable(String)``: some
        rows hold a string and some hold NULL, and the engine names the type of
        the expression it evaluated. The test asserts that the engine reported
        a name at all and that it is the string family's; it does not pin
        ``Nullable(String)`` against a bare ``String``, because the field's
        contract is the engine's own spelling and which one it chose for a
        nullable column is the server's answer, not this test's expectation.
        """
        _setup(clickhouse_backend)
        try:
            profiles = {
                profile.column_name: profile
                for profile in clickhouse_backend.introspector.list_column_data_profiles(TABLE)
            }
            assert profiles["id"].runtime_types == ["Int32"]
            assert profiles["note"].runtime_types
            assert all("String" in name for name in profiles["note"].runtime_types)
            # Every profile is the backend's own type, so the slot is a named
            # field rather than a dictionary key a caller has to discover.
            assert all(hasattr(profile, "runtime_types") for profile in profiles.values())
        finally:
            _teardown(clickhouse_backend)

    def test_empty_table_answers_with_zero_rows_and_no_fraction(self, clickhouse_backend):
        """A profile of nothing is a row count of zero, not a fabricated 0.0.

        The endpoints are ``minOrNull``/``maxOrNull`` rather than ``min``/
        ``max`` for this case: the plain aggregates answer the type's default
        over no rows, and reporting ``0`` or ``''`` would let a reader mistake
        an empty table for one holding a zero.
        """
        clickhouse_backend.execute(f"DROP TABLE IF EXISTS `{TABLE}`")
        clickhouse_backend.execute(
            f"CREATE TABLE `{TABLE}` (`id` Nullable(Int32)) " "ENGINE = MergeTree ORDER BY tuple()"
        )
        try:
            profiles = clickhouse_backend.introspector.list_column_data_profiles(TABLE)
            assert len(profiles) == 1
            profile = profiles[0]
            assert profile.column_name == "id"
            assert profile.row_count == 0
            assert profile.distinct_count == 0
            assert profile.null_fraction is None
            assert profile.min_value is None
            assert profile.max_value is None
            assert profile.source == "aggregate"
            assert profile.runtime_types == []
        finally:
            _teardown(clickhouse_backend)


class TestColumnValueSample:
    """The grouped scan, which can contain NULL."""

    def test_listing_is_ordered_by_frequency(self, clickhouse_backend):
        _setup(clickhouse_backend)
        try:
            samples = clickhouse_backend.introspector.sample_column_values(TABLE, "code", limit=10)
            # CODES[i % 3] puts "b" on 34 rows (i % 3 == 1) and "a"/"c" on 33
            # each, so the order is frequency first and then the tie-break by
            # value -- which is why "a" precedes "c" despite equal counts.
            assert [item.value for item in samples] == ["b", "a", "c"]
            assert [item.count for item in samples] == [34, 33, 33]
            # The engine reports a count, not a fraction. A formatter that
            # divided for it would have had to assume the row count.
            assert all(item.frequency is None for item in samples)
        finally:
            _teardown(clickhouse_backend)

    def test_limit_bounds_the_listing(self, clickhouse_backend):
        _setup(clickhouse_backend)
        try:
            assert (
                len(clickhouse_backend.introspector.sample_column_values(TABLE, "code", limit=2))
                == 2
            )
        finally:
            _teardown(clickhouse_backend)

    def test_null_is_a_value_of_the_domain(self, clickhouse_backend):
        """A grouped listing has a NULL row, and here it is the first one.

        This is the shape that differs from PostgreSQL, whose most-common list
        never contains NULL because ``null_frac`` holds that fact separately. A
        caller reading a listing for "what is in this column" must therefore not
        assume every entry is a value; the profile's ``null_fraction`` is the
        cross-engine answer, and this test is what says so for ClickHouse.
        """
        _setup(clickhouse_backend)
        try:
            samples = clickhouse_backend.introspector.sample_column_values(TABLE, "note", limit=10)
            # NULL at 60 rows, then "x" and "y" at 20 each.
            assert samples[0].value is None
            assert samples[0].count == ROWS - 2 * NOTE_COUNT
            assert {item.value for item in samples if item.value is not None} == {
                "x",
                "y",
            }
            assert sum(item.count for item in samples) == ROWS
        finally:
            _teardown(clickhouse_backend)


class TestJoinCoverage:
    """Overlap measured over distinct values, on both sides."""

    def test_coverage_is_measured_over_distinct_values(self, clickhouse_backend):
        """3 of orders' 3 codes exist among customers' 4 non-null codes.

        Row counts would say something else entirely: 100 order rows map onto
        4 customer rows. Counting distinct values is what makes the number a
        statement about the domains rather than about repetition.
        """
        _setup(clickhouse_backend)
        try:
            coverage = clickhouse_backend.introspector.estimate_join_coverage(
                TABLE, "code", CUSTOMERS, "code"
            )
            assert coverage is not None
            assert coverage.left_coverage == pytest.approx(1.0)
            assert coverage.right_coverage == pytest.approx(0.75)
            assert coverage.left_table == TABLE
            assert coverage.right_table == CUSTOMERS
        finally:
            _teardown(clickhouse_backend)

    def test_the_measurement_is_not_symmetric(self, clickhouse_backend):
        """Reversing the sides swaps the fractions, it does not copy them."""
        _setup(clickhouse_backend)
        try:
            coverage = clickhouse_backend.introspector.estimate_join_coverage(
                CUSTOMERS, "code", TABLE, "code"
            )
            assert coverage is not None
            assert coverage.left_coverage == pytest.approx(0.75)
            assert coverage.right_coverage == pytest.approx(1.0)
        finally:
            _teardown(clickhouse_backend)

    def test_an_empty_domain_is_no_measurement_rather_than_zero(self, clickhouse_backend):
        """``NULLIF(..., 0)`` is the difference between "none" and "unmeasurable".

        With no customer rows there is nothing to divide by, and answering
        ``0.0`` would read as "none of these values join" -- a different claim.
        The left side still has a real denominator, so its 0.0 is a genuine
        zero and must survive.
        """
        _setup(clickhouse_backend)
        try:
            clickhouse_backend.execute(f"TRUNCATE TABLE `{CUSTOMERS}`")
            coverage = clickhouse_backend.introspector.estimate_join_coverage(
                TABLE, "code", CUSTOMERS, "code"
            )
            assert coverage is not None
            assert coverage.left_coverage == pytest.approx(0.0)
            assert coverage.right_coverage is None
        finally:
            _teardown(clickhouse_backend)


class TestFunctionNameCase:
    """Every function name is spelled the way ClickHouse registers it.

    No connection is used, because the failure this guards against is visible
    in the text: the shared function renderer upper-cases every name, and
    ClickHouse resolves a name through its function factories by exact match
    first and then a *lowercased* match against a map that holds only the names
    registered ``Case::Insensitive``. An upper-cased camelCase name therefore
    matches neither and the server answers ``Function with name `MINORNULL`
    does not exist`` -- which is what five CI jobs did, before
    ``groupUniqArray``/``typeof`` were given their engine spelling and the
    endpoints fell back to ``MIN``/``MAX``.

    The scan is over the *rendered SQL*, not over the source, so it also covers
    a name introduced through some other path than the one this class knows
    about.
    """

    def _statement(self, statement):
        return statement.to_sql()[0]

    def test_the_profile_names_every_function_the_engine_accepts(self):
        sql = self._statement(
            ColumnDataProfileQueryStatement(
                ClickHouseDialect(version=(26, 7, 1)),
                table_name=TABLE,
                schema="analytics",
                columns=("id", "note"),
            )
        )

        # ``groupUniqArray`` and ``typeof`` are registered ``Case::Sensitive``,
        # so the camelCase spelling is the only one that resolves.
        assert "groupUniqArray(typeof(`id`))" in sql
        assert "groupUniqArray(typeof(`note`))" in sql

        # The endpoints are the upper-case-safe SQL-standard spellings, which
        # is the whole cost of the ``*OrNull`` fallback: see the docstring of
        # the profile mixin's endpoint helper.
        assert "CAST(MIN(`id`)" in sql
        assert "CAST(MAX(`note`)" in sql

        # No camelCase name may reach SQL upper-cased.
        assert "MINORNULL" not in sql
        assert "MAXORNULL" not in sql
        assert "GROUPUNIQARRAY" not in sql
        assert "TYPEOF" not in sql

    def test_no_upper_cased_camel_case_name_survives_anywhere(self):
        """A guard over all three statements, not only the one that broke.

        ClickHouse's function words are camelCase where they are not the SQL
        standard, so an all-caps run of letters inside a call is either a
        standard name or a name the server will refuse. This asserts the
        rendered statements carry no camelCase name upper-cased -- the exact
        shape of ``MINORNULL``.

        ``NULLIF`` is deliberately absent from the rejected list: ClickHouse
        registers ``nullIf`` ``Case::Insensitive``, so the upper-case spelling
        is the one it documents and the shared renderer happens to be right
        about it. The others are all ``Case::Sensitive`` registrations.
        """
        statements = [
            ColumnDataProfileQueryStatement(
                ClickHouseDialect(version=(26, 7, 1)),
                table_name=TABLE,
                schema="analytics",
                columns=("id",),
            ),
            ColumnValueSampleQueryStatement(
                ClickHouseDialect(version=(26, 7, 1)),
                table_name=TABLE,
                schema="analytics",
                column_name="code",
                limit=5,
            ),
            JoinCoverageQueryStatement(
                ClickHouseDialect(version=(26, 7, 1)),
                schema="analytics",
                left_table=TABLE,
                left_column="id",
                right_table=CUSTOMERS,
                right_column="id",
            ),
        ]
        for statement in statements:
            sql = self._statement(statement)
            for rejected in (
                "MINORNULL",
                "MAXORNULL",
                "GROUPUNIQARRAY",
                "TOTYPENAME",
                "CURRENTUSER",
            ):
                assert rejected not in sql, (
                    f"{rejected} is an upper-cased name the shared renderer "
                    "would emit for a camelCase function; ClickHouse resolves "
                    "names by exact match first and by a lowercased match "
                    "against the Case::Insensitive map only, so it answers "
                    "'Function with name ... does not exist'."
                )

        # The coverage statement's NULLIF is the documented upper-case
        # spelling of a Case::Insensitive registration, so it stays as the
        # shared renderer writes it.
        assert "NULLIF(COUNT(DISTINCT `l`.`id`)" in self._statement(statements[2])

    def test_the_status_queries_name_the_engine_functions(self):
        """``currentUser`` is camelCase and registered ``Case::Sensitive``.

        The same renderer broke the data-profile family; these two status reads
        carry camelCase names too, and ``currentUser`` upper-cased is exactly
        the ``MINORNULL`` shape.
        """
        from rhosocial.activerecord.backend.impl.clickhouse.expression.status import (
            ClickHouseCurrentUserQuery,
            ClickHouseVersionQuery,
        )

        user_sql = self._statement(ClickHouseCurrentUserQuery(ClickHouseDialect(version=(26, 7, 1))))
        assert user_sql == "SELECT currentUser()"
        assert "CURRENTUSER" not in user_sql

        version_sql = self._statement(ClickHouseVersionQuery(ClickHouseDialect(version=(26, 7, 1))))
        assert version_sql == "SELECT version()"
        assert "CURRENTUSER" not in version_sql


class TestProjectionShape:
    """The statement's projection and the row shape the parser reads.

    No connection is used. That is enough to pin the two things a server cannot
    show in a portable way: the shape of the ``UNION ALL`` -- every arm has the
    same seven core cells plus the runtime types, which is what ClickHouse
    requires of a union -- and that the parser rebuilds the row as this
    backend's own profile type.
    """

    def test_every_arm_projects_the_same_cells(self):
        sql, params = ColumnDataProfileQueryStatement(
            ClickHouseDialect(version=(26, 7, 1)),
            table_name="orders",
            schema="analytics",
            columns=("id", "code"),
        ).to_sql()
        arms = sql.split(" UNION ALL ")
        assert len(arms) == 2
        assert params == ()
        for arm in arms:
            assert "AS `column_name`" in arm
            assert "AS `null_count`" in arm
            assert "AS `distinct_count`" in arm
            assert "AS `min_value`" in arm
            assert "AS `max_value`" in arm
            assert "AS `row_count`" in arm
            assert "AS `source`" in arm
            assert "AS `runtime_types`" in arm
        # The endpoints are the union's one forced cast: ClickHouse refuses
        # arms whose types disagree, so both are Nullable(String) everywhere.
        assert "CAST(MIN(`id`)" in sql
        assert "CAST(MAX(`id`)" in sql
        assert "AS Nullable(String))" in sql

    def test_the_parser_attaches_the_runtime_types(self):
        profiles = ClickHouseIntrospectorMixin().parse_column_data_profiles(
            [
                {
                    "column_name": "note",
                    "null_count": 60,
                    "distinct_count": 2,
                    "min_value": "x",
                    "max_value": "y",
                    "row_count": 100,
                    "source": "aggregate",
                    "runtime_types": ["String", "LowCardinality(String)"],
                }
            ],
            "analytics",
            TABLE,
        )
        assert len(profiles) == 1
        profile = profiles[0]
        assert profile.null_fraction == pytest.approx(0.6)
        assert profile.distinct_count == 2
        assert profile.runtime_types == ["LowCardinality(String)", "String"]
        # The runtime types are a named field, not an entry a caller has to
        # know the key of.
        assert profile.extra == {}

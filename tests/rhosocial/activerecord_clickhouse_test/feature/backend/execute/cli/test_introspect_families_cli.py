# tests/rhosocial/activerecord_clickhouse_test/feature/backend/execute/cli/test_introspect_families_cli.py
"""The families this change adds, as the CLI asks for them.

No server is needed here. What is checked is the wiring the CLI owns: that
each type reaches its introspector method, that NAME and the type-specific
flags arrive as arguments rather than being parsed and dropped, and that a
family the connected server refuses is refused. Whether the answer is right is
the introspector's question, and the live tests carry it.

The stub introspector records one call per run, so a branch that calls two
methods, or calls the right one with a dropped argument, fails here rather
than showing up as a plausible-looking listing.

Five of the eight are families this dialect cannot answer -- the switch is
inherited as ``False`` -- so the gate is what the run meets, and the tests
hold both sides of it: the refusal before anything connects, and the branch
that does run once a stub dialect answers ``True``. Five families answering
``False`` is the honest state of this backend: ClickHouse has no statistics
collector and no dependency graph, so a CLI that ran those branches anyway
would render a statement on a catalogue it does not have. DDL extraction is
not offered at all, because the dialect carries no reader for it.

Every type is driven through the real parser rather than a hand-built
namespace, so a flag the subparser does not declare fails here rather than
reading as an argument the branch silently ignored.
"""

import argparse
import json
from typing import List, Optional

import pytest

from rhosocial.activerecord.backend.impl.clickhouse.cli import introspect as introspect_cli
from rhosocial.activerecord.backend.impl.clickhouse.dialect import ClickHouseDialect
from rhosocial.activerecord.backend.impl.clickhouse.introspection.types import (
    ClickHouseColumnDataProfile,
)
from rhosocial.activerecord.backend.introspection.types import (
    ColumnDataProfile,
    ColumnValueFrequency,
    JoinCoverage,
)

#: The eight families this change wires, and the switch that gates each. The
#: dialect declares the three data families and inherits the other five as
#: ``False``, so the three are asked and the five are refused -- both of which
#: the CLI must be able to do.
NEW_FAMILIES = {
    "unused-indexes": "supports_unused_indexes_detection",
    "table-stats": "supports_table_stats",
    "runtime": "supports_runtime_stats",
    "index-stats": "supports_index_stats",
    "dependencies": "supports_object_dependencies",
    "column-profiles": "supports_column_data_profile",
    "value-samples": "supports_column_value_sample",
    "join-coverage": "supports_join_coverage",
}

#: The families that answer for the whole database's scope and take no NAME.
WHOLE_SCOPE_FAMILIES = (
    "unused-indexes",
    "table-stats",
    "runtime",
    "index-stats",
)

#: The families this dialect cannot answer, so the gate refuses them. The
#: remaining three read the rows themselves and are the ones whose branch
#: runs against a real dialect.
GATED_FAMILIES = (
    "unused-indexes",
    "table-stats",
    "runtime",
    "index-stats",
    "dependencies",
)

#: The families a real dialect answers, so their branch is reachable live.
ANSWERED_FAMILIES = (
    "column-profiles",
    "value-samples",
    "join-coverage",
)

#: Connection arguments every argv needs. ClickHouse names its one namespace
#: level a database, so neither flag is a capability answer.
CONNECTION = ["--database", "app"]


class _RecordingIntrospector:
    """Records each introspection call, and returns what the test declared.

    ``__getattr__`` is the whole implementation: a test names the method once,
    in the assertion, and a branch that reaches a different one fails on the
    recorded name rather than on an attribute error that would hide the typo.
    """

    def __init__(self, results: Optional[dict] = None) -> None:
        self.results = results or {}
        self.calls = []

    def __getattr__(self, name: str):
        def call(*args, **kwargs):
            self.calls.append((name, args, kwargs))
            return self.results.get(name)

        return call


class _AsyncRecordingIntrospector(_RecordingIntrospector):
    """The async shape of the same recorder: methods are awaited, calls are not."""

    def __getattr__(self, name: str):
        async def call(*args, **kwargs):
            self.calls.append((name, args, kwargs))
            return self.results.get(name)

        return call


class _AllTrueDialect:
    """Every capability switch answers True, so the gate never refuses.

    A run against a real server answers the switch from the live dialect;
    offline, the gate is exercised directly with a dialect of its own.
    """

    def __getattr__(self, name: str):
        if name.startswith("supports_"):
            return lambda: True
        raise AttributeError(name)


class _RecordingProvider:
    """An output provider that records instead of printing."""

    def __init__(self) -> None:
        self.results: List[object] = []

    def display_results(self, data, title=None):
        self.results.append((title, data))

    def display_connection_error(self, error):
        pass

    def display_query_error(self, error):
        pass


def build_parser():
    """Build the top-level parser with the real introspect subparser."""
    top = argparse.ArgumentParser()
    subparsers = top.add_subparsers(dest="command")
    introspect_cli.create_parser(subparsers)
    return top


def _patch_backend(monkeypatch, introspector, dialect=None, use_async=False):
    """Install a stub backend class whose instances carry *introspector*.

    The class name written into the module is the one ``handle()`` looks up,
    so the sync and the async chains are each installed separately. A
    *dialect* other than the answer-everything stub is what the gate tests
    need -- a real ``ClickHouseDialect`` answers the six switches ``False``,
    which is the refusal path.
    """
    target = (
        introspect_cli.AsyncClickHouseBackend.__name__
        if use_async
        else introspect_cli.ClickHouseBackend.__name__
    )
    chosen = _AllTrueDialect if dialect is None else dialect

    class _Backend:
        def __init__(self, connection_config=None):
            self.connection_config = connection_config
            self.introspector = introspector
            self.dialect = chosen()
            self._connection = object()
            self.disconnected = False

        def introspect_and_adapt(self):
            """The real backend learns the server version here before rendering."""
            pass

        def disconnect(self):
            self.disconnected = True

    if use_async:
        async def connect(self):
            pass

        async def disconnect(self):
            self.disconnected = True

        async def introspect_and_adapt(self):
            pass

        _Backend.connect = connect
        _Backend.disconnect = disconnect
        _Backend.introspect_and_adapt = introspect_and_adapt
    else:
        def connect(self):
            pass

        _Backend.connect = connect

    monkeypatch.setattr(introspect_cli, target, _Backend)
    monkeypatch.setattr(
        introspect_cli, "resolve_connection_config_from_args", lambda _args: None
    )
    return _Backend


def _run_sync(monkeypatch, introspector, argv, dialect=None):
    """Drive a full run through the real parser and dispatch chain."""
    monkeypatch.setattr(
        introspect_cli,
        "create_provider",
        lambda fmt, ascii_borders=False: _RecordingProvider(),
    )
    _patch_backend(monkeypatch, introspector, dialect=dialect)
    introspect_cli.handle(build_parser().parse_args(argv))


def _run_async(monkeypatch, introspector, argv, dialect=None):
    """Drive the async chain the same way, through the same parser.

    ``AsyncClickHouseBackend`` is a fail-fast placeholder in the real tree,
    so the class is replaced here: the async handler is kept correct even
    though the CLI refuses ``--async``, and that is the thing worth testing.
    """
    monkeypatch.setattr(
        introspect_cli,
        "create_provider",
        lambda fmt, ascii_borders=False: _RecordingProvider(),
    )
    _patch_backend(monkeypatch, introspector, dialect=dialect, use_async=True)
    introspect_cli.handle(build_parser().parse_args(argv + ["--async"]))


def _run_with_real_provider(monkeypatch, introspector, argv):
    """A run that keeps the real providers, so stdout is the serialised rows."""
    _patch_backend(monkeypatch, introspector)
    introspect_cli.handle(build_parser().parse_args(argv))


def _name_required_argv(type_, extra=()):
    return ["introspect", type_, "events"] + list(extra) + CONNECTION


class TestTheSchemaWideFamilies:
    """The counters and listings describe the database, so NAME is refused."""

    @pytest.mark.parametrize(
        "type_, method",
        [
            ("unused-indexes", "list_unused_indexes"),
            ("table-stats", "list_table_usage_stats"),
            ("runtime", "list_runtime_metrics"),
            ("index-stats", "list_index_usage_stats"),
        ],
    )
    def test_the_family_asks_its_method_for_the_whole_scope(
        self, type_, method, monkeypatch
    ):
        introspector = _RecordingIntrospector({method: []})

        _run_sync(monkeypatch, introspector, ["introspect", type_] + CONNECTION)

        assert introspector.calls == [(method, (), {"schema": None})]

    @pytest.mark.parametrize("type_", WHOLE_SCOPE_FAMILIES)
    def test_a_name_is_refused(self, type_, capsys):
        with pytest.raises(SystemExit) as excinfo:
            introspect_cli._validate_name(
                build_parser().parse_args(["introspect", type_, "events"] + CONNECTION)
            )
        assert excinfo.value.code == 2
        assert "takes no name" in capsys.readouterr().err

    @pytest.mark.parametrize("type_", WHOLE_SCOPE_FAMILIES)
    def test_the_refusal_happens_before_anything_connects(self, type_, monkeypatch):
        """The refusal is a statement about the command line, not the server."""
        introspector = _RecordingIntrospector()

        with pytest.raises(SystemExit):
            _run_sync(monkeypatch, introspector, ["introspect", type_, "events"] + CONNECTION)

        assert introspector.calls == []


class TestTheDependenciesBranch:
    """One optional NAME narrows the graph; omitting it asks for all of it."""

    def test_a_named_object_is_asked_for_by_name(self, monkeypatch):
        introspector = _RecordingIntrospector({"list_object_dependencies": []})

        _run_sync(monkeypatch, introspector, ["introspect", "dependencies", "events"] + CONNECTION)

        assert introspector.calls == [
            ("list_object_dependencies", (), {"object_name": "events", "schema": None})
        ]

    def test_an_unnamed_run_asks_for_the_whole_graph(self, monkeypatch):
        introspector = _RecordingIntrospector({"list_object_dependencies": []})

        _run_sync(monkeypatch, introspector, ["introspect", "dependencies"] + CONNECTION)

        assert introspector.calls == [
            ("list_object_dependencies", (), {"object_name": None, "schema": None})
        ]


class TestTheColumnProfilesBranch:
    """The aggregate label and the runtime types both reach the reader."""

    def _profile(self) -> ClickHouseColumnDataProfile:
        return ClickHouseColumnDataProfile(
            schema="app",
            table_name="events",
            column_name="code",
            null_fraction=0.6,
            distinct_count=3,
            row_count=100,
            source="aggregate",
            runtime_types=["LowCardinality(String)", "String"],
        )

    def test_the_table_is_asked_for_by_name(self, monkeypatch):
        introspector = _RecordingIntrospector(
            {"list_column_data_profiles": [self._profile()]}
        )

        _run_sync(monkeypatch, introspector, _name_required_argv("column-profiles"))

        assert introspector.calls == [
            ("list_column_data_profiles", ("events",), {"schema": None})
        ]

    def test_the_run_says_the_numbers_are_aggregated(self, monkeypatch, capsys):
        """Exact and expensive, on stderr so the JSON on stdout stays parseable."""
        introspector = _RecordingIntrospector(
            {"list_column_data_profiles": [self._profile()]}
        )

        _run_sync(monkeypatch, introspector, _name_required_argv("column-profiles"))

        captured = capsys.readouterr()
        assert "aggregate" in captured.err
        assert "full scan" in captured.err

    def test_the_source_rides_the_row_rather_than_a_note(self, monkeypatch, capsys):
        """``source`` is a column of the answer, so a machine reader sees it."""
        introspector = _RecordingIntrospector(
            {"list_column_data_profiles": [self._profile()]}
        )

        _run_with_real_provider(
            monkeypatch, introspector, _name_required_argv("column-profiles", ["-o", "json"])
        )

        payload = json.loads(capsys.readouterr().out)
        assert payload[0]["source"] == "aggregate"

    def test_the_runtime_types_reach_the_reader(self, monkeypatch, capsys):
        """The backend's own fact rides the row and is not silently dropped.

        ``runtime_types`` is the cell no other engine in this family can fill,
        and the CLI prints the profile row as the introspector returns it: the
        field is on the backend's own dataclass rather than in a shared
        column, so it reaches a caller who asked ClickHouse and nobody else
        has to ignore it.
        """
        introspector = _RecordingIntrospector(
            {"list_column_data_profiles": [self._profile()]}
        )

        _run_with_real_provider(
            monkeypatch, introspector, _name_required_argv("column-profiles", ["-o", "json"])
        )

        payload = json.loads(capsys.readouterr().out)
        assert payload[0]["runtime_types"] == ["LowCardinality(String)", "String"]

    def test_a_core_profile_carries_no_runtime_types(self, monkeypatch, capsys):
        """The shared type simply does not have the field, and that is not a bug.

        Core keeps the slot out on purpose, so a plain ``ColumnDataProfile``
        answers with the seven shared cells and the CLI reports exactly that
        rather than inventing an empty list for a column the engine did not
        describe.
        """
        introspector = _RecordingIntrospector(
            {
                "list_column_data_profiles": [
                    ColumnDataProfile(
                        schema="app",
                        table_name="events",
                        column_name="code",
                        source="aggregate",
                    )
                ]
            }
        )

        _run_with_real_provider(
            monkeypatch, introspector, _name_required_argv("column-profiles", ["-o", "json"])
        )

        payload = json.loads(capsys.readouterr().out)
        assert "runtime_types" not in payload[0]


class TestTheValueSamplesBranch:
    """A table and a column, and a limit that the introspector receives."""

    def test_the_table_column_and_limit_reach_the_introspector(self, monkeypatch):
        introspector = _RecordingIntrospector(
            {"sample_column_values": [ColumnValueFrequency(value="paid", count=7)]}
        )

        _run_sync(
            monkeypatch,
            introspector,
            _name_required_argv("value-samples", ["--column", "code", "--limit", "20"]),
        )

        assert introspector.calls == [
            (
                "sample_column_values",
                ("events", "code"),
                {"limit": 20, "schema": None},
            )
        ]

    def test_no_limit_is_sent_when_the_flag_is_omitted(self, monkeypatch):
        introspector = _RecordingIntrospector({"sample_column_values": []})

        _run_sync(
            monkeypatch,
            introspector,
            _name_required_argv("value-samples", ["--column", "code"]),
        )

        # Absent ``--limit`` means absent from the call: the introspector's own
        # signature answers with its own default, and the CLI does not restate
        # it. A number here would fail the day the signature's default moved.
        assert "limit" not in introspector.calls[0][2]

    def test_the_value_null_is_not_silently_dropped(self, monkeypatch, capsys):
        """A NULL is a legal member of a value domain, often the most interesting."""
        introspector = _RecordingIntrospector(
            {"sample_column_values": [ColumnValueFrequency(value=None, count=5)]}
        )

        _run_with_real_provider(
            monkeypatch,
            introspector,
            _name_required_argv("value-samples", ["--column", "code", "-o", "json"]),
        )

        payload = json.loads(capsys.readouterr().out)
        assert payload[0]["value"] is None
        assert payload[0]["count"] == 5


class TestTheJoinCoverageBranch:
    """Four names, both sides of the measurement, in the order they are asked."""

    def _coverage(self) -> JoinCoverage:
        return JoinCoverage(
            left_schema="app",
            left_table="events",
            left_column="buyer_id",
            right_schema="app",
            right_table="customers",
            right_column="id",
            left_coverage=1.0,
            right_coverage=0.75,
        )

    _right_flags = ["--right-table", "customers", "--right-column", "id"]

    def test_the_four_names_reach_the_introspector(self, monkeypatch):
        introspector = _RecordingIntrospector(
            {"estimate_join_coverage": self._coverage()}
        )

        _run_sync(
            monkeypatch,
            introspector,
            _name_required_argv(
                "join-coverage", ["--column", "buyer_id"] + self._right_flags
            ),
        )

        assert introspector.calls == [
            (
                "estimate_join_coverage",
                ("events", "buyer_id", "customers", "id"),
                {"schema": None},
            )
        ]

    def test_both_fractions_are_reported(self, monkeypatch, capsys):
        introspector = _RecordingIntrospector(
            {"estimate_join_coverage": self._coverage()}
        )

        _run_with_real_provider(
            monkeypatch,
            introspector,
            _name_required_argv(
                "join-coverage",
                ["--column", "buyer_id"] + self._right_flags + ["-o", "json"],
            ),
        )

        payload = json.loads(capsys.readouterr().out)
        assert payload[0]["left_coverage"] == 1.0
        assert payload[0]["right_coverage"] == 0.75

    def test_an_unmeasurable_pair_is_an_error(self, monkeypatch, capsys):
        """``None`` is "not measured", which is not a zero-overlap answer.

        ClickHouse compares by type, so two columns whose types do not agree
        measure as zero overlap rather than failing. That zero is a correct
        statement about a join that would not match -- but ``None`` is what
        the CLI reports when nothing was measured at all, and the two must
        not collapse into one answer.
        """
        introspector = _RecordingIntrospector({"estimate_join_coverage": None})

        with pytest.raises(SystemExit) as excinfo:
            _run_sync(
                monkeypatch,
                introspector,
                _name_required_argv(
                    "join-coverage", ["--column", "buyer_id"] + self._right_flags
                ),
            )

        assert excinfo.value.code == 1
        assert "no coverage could be measured" in capsys.readouterr().err


class TestTheNameRuleTable:
    """The NAME rule is a table, and a table nobody asserts is a guess.

    Three pinning levels: the whole table as data (so editing one type's rule
    is a visible change to a literal, not a drift), the set (so a type cannot
    be advertised without someone deciding what NAME means for it), and the
    behaviour (so the table is what a run actually applies rather than text
    that happens to sit beside the code that ignores it). The set-level one
    is what the cross-repository clause of ``.claude/rules/constants.md``
    asks for: a private table read in several places earns its name because
    the readings are asserted.
    """

    def test_every_advertised_type_has_a_rule(self):
        assert set(introspect_cli._NAME_RULE) == set(introspect_cli.INTROSPECT_TYPES)

    def test_the_table_says_what_each_types_name_means(self):
        assert introspect_cli._NAME_RULE == {
            "tables": "forbidden",
            "views": "optional",
            "columns": "required",
            "indexes": "required",
            "partitions": "required",
            "table-engine": "required",
            "functions": "optional",
            "dictionaries": "optional",
            "clusters": "optional",
            "quotas": "optional",
            "users": "optional",
            "roles": "optional",
            "unused-indexes": "forbidden",
            "table-stats": "forbidden",
            "runtime": "forbidden",
            "index-stats": "forbidden",
            "dependencies": "optional",
            "column-profiles": "required",
            "value-samples": "required",
            "join-coverage": "required",
            "database": "forbidden",
        }

    def test_the_table_covers_no_type_the_parser_does_not_offer(self):
        assert set(introspect_cli._NAME_RULE) - set(introspect_cli.INTROSPECT_TYPES) == set()

    @pytest.mark.parametrize("type_", ["tables", "database"] + list(WHOLE_SCOPE_FAMILIES))
    def test_a_refused_type_is_refused_by_the_table(self, type_, capsys):
        with pytest.raises(SystemExit) as excinfo:
            introspect_cli._validate_name(
                build_parser().parse_args(["introspect", type_, "events"] + CONNECTION)
            )

        assert excinfo.value.code == 2
        assert "takes no name" in capsys.readouterr().err

    @pytest.mark.parametrize(
        "type_",
        ["columns", "indexes", "partitions", "table-engine",
         "column-profiles", "value-samples", "join-coverage"],
    )
    def test_a_required_name_is_required_by_the_table(self, type_, capsys):
        """A missing required NAME is an incomplete invocation, not a refusal."""
        with pytest.raises(SystemExit) as excinfo:
            introspect_cli._validate_name(
                build_parser().parse_args(["introspect", type_] + CONNECTION)
            )

        assert excinfo.value.code == 1
        assert "required" in capsys.readouterr().err

    @pytest.mark.parametrize("type_", ["views", "dependencies"])
    def test_an_optional_name_may_be_given_or_not(self, type_):
        introspect_cli._validate_name(
            build_parser().parse_args(["introspect", type_] + CONNECTION)
        )
        introspect_cli._validate_name(
            build_parser().parse_args(["introspect", type_, "events"] + CONNECTION)
        )


class TestTheArgumentRules:
    """The rules the CLI owns: a NAME and a flag are read, refused or required."""

    @pytest.mark.parametrize(
        "type_", ["column-profiles", "value-samples", "join-coverage"]
    )
    def test_a_missing_name_is_an_incomplete_invocation(self, type_, capsys, monkeypatch):
        """A NAME the type cannot do without is refused by the rule table."""
        with pytest.raises(SystemExit) as excinfo:
            _run_sync(monkeypatch, _RecordingIntrospector(), ["introspect", type_] + CONNECTION)
        assert excinfo.value.code == 1
        assert "required" in capsys.readouterr().err

    def test_a_missing_column_exits_one(self, capsys, monkeypatch):
        with pytest.raises(SystemExit) as excinfo:
            _run_sync(monkeypatch, _RecordingIntrospector(), _name_required_argv("value-samples"))
        assert excinfo.value.code == 1
        assert "--column is required" in capsys.readouterr().err

    def test_a_missing_right_pair_exits_one(self, capsys, monkeypatch):
        with pytest.raises(SystemExit) as excinfo:
            _run_sync(
                monkeypatch,
                _RecordingIntrospector(),
                _name_required_argv("join-coverage", ["--column", "buyer_id"]),
            )
        assert excinfo.value.code == 1
        err = capsys.readouterr().err
        assert "--right-table" in err
        assert "--right-column" in err

    def test_a_flag_the_type_does_not_read_is_refused(self, capsys, monkeypatch):
        with pytest.raises(SystemExit) as excinfo:
            _run_sync(
                monkeypatch,
                _RecordingIntrospector(),
                ["introspect", "tables", "--column", "code"] + CONNECTION,
            )
        assert excinfo.value.code == 2
        assert "takes no --column" in capsys.readouterr().err

    def test_the_join_flags_are_refused_outside_join_coverage(self, capsys, monkeypatch):
        with pytest.raises(SystemExit) as excinfo:
            _run_sync(
                monkeypatch,
                _RecordingIntrospector(),
                ["introspect", "tables", "--right-table", "customers"] + CONNECTION,
            )
        assert excinfo.value.code == 2
        assert "takes no --right-table" in capsys.readouterr().err

    def test_the_stray_flag_is_refused_before_the_connection(self, monkeypatch):
        """A refused flag never reaches the introspector, so nothing is rendered."""
        introspector = _RecordingIntrospector()

        with pytest.raises(SystemExit):
            _run_sync(
                monkeypatch,
                introspector,
                ["introspect", "tables", "--column", "code"] + CONNECTION,
            )

        assert introspector.calls == []


class TestTheCapabilityGate:
    """The switch is what the run consults, and it is consulted before the work.

    Five of the eight families are ones this dialect cannot answer, and the
    earlier behaviour was to run the branch anyway -- which produced an empty
    listing that read as "this database has none". Refusing first is what makes
    the two answers distinguishable, so the gate is asserted against the live
    dialect and against a stub whose switch answers ``False``.
    """

    @pytest.mark.parametrize("type_", list(NEW_FAMILIES))
    def test_every_type_names_a_switch_the_dialect_declares(self, type_):
        switch = introspect_cli._TYPE_CAPABILITIES[type_]
        assert switch == NEW_FAMILIES[type_]
        assert hasattr(ClickHouseDialect, switch)

    @pytest.mark.parametrize("type_", GATED_FAMILIES)
    def test_a_family_this_dialect_cannot_answer_exits_two(self, type_, capsys):
        """The live dialect answers the switch, and the gate follows it."""
        import argparse as _argparse

        class _Backend:
            dialect = ClickHouseDialect()

        with pytest.raises(SystemExit) as excinfo:
            introspect_cli._require_capability(_argparse.Namespace(type=type_), _Backend())

        assert excinfo.value.code == 2
        assert "not supported by this server" in capsys.readouterr().err

    @pytest.mark.parametrize("type_", list(NEW_FAMILIES))
    def test_a_family_the_server_refuses_is_refused(self, type_, capsys):
        """A switch that answers ``False`` refuses, whatever the family."""
        import argparse as _argparse

        class _Dialect:
            pass

        setattr(_Dialect, NEW_FAMILIES[type_], staticmethod(lambda: False))

        class _Backend:
            dialect = _Dialect()

        with pytest.raises(SystemExit) as excinfo:
            introspect_cli._require_capability(_argparse.Namespace(type=type_), _Backend())

        assert excinfo.value.code == 2
        assert "not supported by this server" in capsys.readouterr().err

    @pytest.mark.parametrize("type_", GATED_FAMILIES)
    def test_the_gate_never_reaches_the_introspector(self, type_, monkeypatch):
        """A refused family is not asked, so no statement is ever rendered.

        A real dialect sits behind the run this time, so the inherited
        ``False`` is what the gate reads -- the stub above answers everything,
        and this is the assertion that a live run refuses before it reaches
        the introspector rather than rendering a statement on a catalogue
        ClickHouse does not have.
        """
        introspector = _RecordingIntrospector()

        argv = ["introspect", type_] + CONNECTION
        if type_ in ("column-profiles", "value-samples", "join-coverage"):
            argv += ["events"]
        if type_ in ("value-samples", "join-coverage"):
            argv += ["--column", "buyer_id"]
        if type_ == "join-coverage":
            argv += ["--right-table", "customers", "--right-column", "id"]

        with pytest.raises(SystemExit):
            _run_sync(monkeypatch, introspector, argv, dialect=ClickHouseDialect)

        assert introspector.calls == []

    @pytest.mark.parametrize("type_", ANSWERED_FAMILIES)
    def test_the_families_the_dialect_answers_pass_the_real_gate(
        self, type_, monkeypatch
    ):
        """The three families are genuinely answerable, so the gate lets them by.

        This is the one place the branch's reachability is asserted against
        the real dialect rather than an answer-everything stub: the switch
        answers ``True`` here, so the run gets as far as the introspector.
        """
        introspector = _RecordingIntrospector(
            {
                "list_column_data_profiles": [],
                "sample_column_values": [],
                "estimate_join_coverage": None,
            }
        )

        argv = ["introspect", type_, "events"] + CONNECTION
        if type_ in ("value-samples", "join-coverage"):
            argv += ["--column", "buyer_id"]
        if type_ == "join-coverage":
            argv += ["--right-table", "customers", "--right-column", "id"]

        try:
            _run_sync(monkeypatch, introspector, argv, dialect=ClickHouseDialect)
        except SystemExit as exc:
            # ``join-coverage`` answers ``None`` with the stub's result, and
            # that is the family's own "cannot be measured", exit 1 -- the
            # capability refusal would have been exit 2.
            assert exc.code == 1

        assert len(introspector.calls) == 1


class TestTheAsyncPath:
    """The second dispatch chain must ask the same question the first one does."""

    @pytest.mark.parametrize(
        "type_, method, extra, expected",
        [
            ("unused-indexes", "list_unused_indexes", [], ((), {"schema": None})),
            ("table-stats", "list_table_usage_stats", [], ((), {"schema": None})),
            ("runtime", "list_runtime_metrics", [], ((), {"schema": None})),
            ("index-stats", "list_index_usage_stats", [], ((), {"schema": None})),
            (
                "dependencies",
                "list_object_dependencies",
                ["events"],
                ((), {"object_name": "events", "schema": None}),
            ),
            (
                "column-profiles",
                "list_column_data_profiles",
                ["events"],
                (("events",), {"schema": None}),
            ),
            (
                "value-samples",
                "sample_column_values",
                ["events", "--column", "code", "--limit", "5"],
                (("events", "code"), {"limit": 5, "schema": None}),
            ),
            (
                "join-coverage",
                "estimate_join_coverage",
                [
                    "events",
                    "--column",
                    "buyer_id",
                    "--right-table",
                    "customers",
                    "--right-column",
                    "id",
                ],
                (("events", "buyer_id", "customers", "id"), {"schema": None}),
            ),
        ],
    )
    def test_the_async_branch_calls_the_same_method_with_the_same_arguments(
        self, type_, method, extra, expected, monkeypatch
    ):
        # The one family whose answer is a single row rather than a listing
        # needs an actual result, because the branch reads a field off it.
        results = {method: []}
        if method == "estimate_join_coverage":
            results[method] = JoinCoverage(
                left_schema="app",
                left_table="events",
                left_column="buyer_id",
                right_schema="app",
                right_table="customers",
                right_column="id",
                left_coverage=1.0,
                right_coverage=0.75,
            )
        introspector = _AsyncRecordingIntrospector(results)

        _run_async(monkeypatch, introspector, ["introspect", type_] + extra + CONNECTION)

        assert introspector.calls == [(method, expected[0], expected[1])]


class TestTheTypeSurfaceExtension:
    def test_the_advertised_types_are_the_capability_mapping(self):
        """One source for the list: the mapping, not a second hand-written copy."""
        assert list(introspect_cli._TYPE_CAPABILITIES) == introspect_cli.INTROSPECT_TYPES

    @pytest.mark.parametrize("type_", list(NEW_FAMILIES))
    def test_every_listed_type_parses(self, type_):
        assert (
            build_parser().parse_args(["introspect", type_] + CONNECTION).type == type_
        )

    def test_the_help_lists_every_new_family(self, capsys):
        with pytest.raises(SystemExit):
            build_parser().parse_args(["introspect", "--help"])
        out = capsys.readouterr().out
        for type_ in NEW_FAMILIES:
            assert type_ in out

    def test_the_new_flags_parse_only_for_their_own_types(self):
        args = build_parser().parse_args(
            ["introspect", "value-samples", "events", "--column", "code", "--limit", "3"]
            + CONNECTION
        )
        assert (args.column, args.limit) == ("code", 3)

    def test_ddl_stays_out_of_the_vocabulary(self):
        """DDL extraction is not offered, because the dialect cannot read it.

        A type the CLI refuses to name never reaches the capability gate: the
        parser rejects the word as an invalid choice, which is exit 2.
        """
        assert "ddl" not in introspect_cli.INTROSPECT_TYPES
        with pytest.raises(SystemExit) as excinfo:
            build_parser().parse_args(["introspect", "ddl", "events"] + CONNECTION)
        assert excinfo.value.code == 2

    def test_foreign_keys_and_triggers_stay_out_of_the_vocabulary(self):
        """Their absence is "this engine has no such object", not a switch.

        Adding these families is not an invitation to add every family core
        names: the two this engine does not have at all stay out of the
        parser's choices, and argparse refuses the word.
        """
        assert "foreign-keys" not in introspect_cli.INTROSPECT_TYPES
        assert "triggers" not in introspect_cli.INTROSPECT_TYPES
        with pytest.raises(SystemExit):
            build_parser().parse_args(["introspect", "foreign-keys", "users"] + CONNECTION)
        with pytest.raises(SystemExit):
            build_parser().parse_args(["introspect", "triggers", "users"] + CONNECTION)

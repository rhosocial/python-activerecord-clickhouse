# tests/rhosocial/activerecord_clickhouse_test/feature/backend/cli/test_catalog_families_cli.py
"""The six server-wide catalogue families, as the CLI asks for them.

No server is needed here. The test pins the wiring the CLI owns: that each
type parses, reaches its introspector method, passes NAME through as a
narrowing filter, and is offered rather than refused. Whether the rows are
right is the introspector's question, and the offline parser tests carry it.

The same distinction the older families keep holds here: a type absent from
``INTROSPECT_TYPES`` is one this backend never asks (``constraints``,
``tablespaces``, ``foreign-keys``, ``triggers``), while a type that is offered
carries a capability switch and is refused with exit 2 if the connected server
answers ``False``.
"""

import argparse
import json
from typing import List

import pytest

from rhosocial.activerecord.backend.impl.clickhouse.cli import introspect as introspect_cli
from rhosocial.activerecord.backend.impl.clickhouse.dialect import ClickHouseDialect
from rhosocial.activerecord.backend.impl.clickhouse.introspection.types import (
    ClickHouseClusterInfo,
    ClickHouseDictionaryInfo,
    ClickHouseFunctionInfo,
    ClickHouseQuotaInfo,
    ClickHouseRoleInfo,
    ClickHouseUserInfo,
)

#: The six families this change wires, and the switch that gates each.
CATALOG_FAMILIES = {
    "functions": "supports_function_introspection",
    "dictionaries": "supports_dictionary_introspection",
    "clusters": "supports_cluster_introspection",
    "quotas": "supports_quota_introspection",
    "users": "supports_user_introspection",
    "roles": "supports_role_introspection",
}

#: The introspector method each family reaches.
METHODS = {
    "functions": "list_functions",
    "dictionaries": "list_dictionaries",
    "clusters": "list_clusters",
    "quotas": "list_quotas",
    "users": "list_users",
    "roles": "list_roles",
}

#: The families this engine does not expose, so they are absent from the
#: parser's vocabulary rather than offered and refused.
ABSENT_FAMILIES = ("constraints", "tablespaces", "foreign-keys", "triggers")

CONNECTION = ["--database", "app"]


class _RecordingIntrospector:
    """Records one call per run; a branch that calls two methods fails."""

    def __init__(self, results=None):
        self.results = results or {}
        self.calls = []

    def __getattr__(self, name):
        def call(*args, **kwargs):
            self.calls.append((name, args, kwargs))
            return self.results.get(name)

        return call


class _AsyncRecordingIntrospector(_RecordingIntrospector):
    """The asynchronous shape of the same recorder."""

    def __getattr__(self, name):
        async def call(*args, **kwargs):
            self.calls.append((name, args, kwargs))
            return self.results.get(name)

        return call


class _AllTrueDialect:
    """Every capability switch answers True, so the gate never refuses."""

    def __getattr__(self, name):
        if name.startswith("supports_"):
            return lambda: True
        raise AttributeError(name)


class _RecordingProvider:
    """An output provider that records instead of printing."""

    def __init__(self):
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

        def connect(self):
            pass

        def introspect_and_adapt(self):
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

    monkeypatch.setattr(introspect_cli, target, _Backend)
    monkeypatch.setattr(
        introspect_cli, "resolve_connection_config_from_args", lambda _args: None
    )
    return _Backend


def _run_sync(monkeypatch, introspector, argv, dialect=None):
    monkeypatch.setattr(
        introspect_cli,
        "create_provider",
        lambda fmt, ascii_borders=False: _RecordingProvider(),
    )
    _patch_backend(monkeypatch, introspector, dialect=dialect)
    introspect_cli.handle(build_parser().parse_args(argv))


def _run_async(monkeypatch, introspector, argv, dialect=None):
    monkeypatch.setattr(
        introspect_cli,
        "create_provider",
        lambda fmt, ascii_borders=False: _RecordingProvider(),
    )
    _patch_backend(monkeypatch, introspector, dialect=dialect, use_async=True)
    introspect_cli.handle(build_parser().parse_args(argv + ["--async"]))


def _run_with_real_provider(monkeypatch, introspector, argv):
    _patch_backend(monkeypatch, introspector)
    introspect_cli.handle(build_parser().parse_args(argv))


def _results_for(type_):
    """One representative result for a family, so the JSON has a row."""
    return {
        "functions": [ClickHouseFunctionInfo(name="f", origin="System")],
        "dictionaries": [ClickHouseDictionaryInfo(name="d", database="app")],
        "clusters": [
            ClickHouseClusterInfo(cluster="c", shard_num=1, replica_num=1)
        ],
        "quotas": [ClickHouseQuotaInfo(name="q")],
        "users": [ClickHouseUserInfo(name="alice")],
        "roles": [ClickHouseRoleInfo(name="reader")],
    }[type_]


class TestTheTypeSurface:
    @pytest.mark.parametrize("type_", list(CATALOG_FAMILIES))
    def test_the_type_is_offered(self, type_):
        assert type_ in introspect_cli.INTROSPECT_TYPES

    @pytest.mark.parametrize("type_", list(CATALOG_FAMILIES))
    def test_every_type_names_its_switch(self, type_):
        assert introspect_cli._TYPE_CAPABILITIES[type_] == CATALOG_FAMILIES[type_]
        assert hasattr(ClickHouseDialect, CATALOG_FAMILIES[type_])

    @pytest.mark.parametrize("type_", list(CATALOG_FAMILIES))
    def test_every_type_parses(self, type_):
        assert (
            build_parser().parse_args(["introspect", type_] + CONNECTION).type
            == type_
        )

    def test_the_help_lists_every_catalogue_family(self, capsys):
        with pytest.raises(SystemExit):
            build_parser().parse_args(["introspect", "--help"])
        out = capsys.readouterr().out
        for type_ in CATALOG_FAMILIES:
            assert type_ in out

    @pytest.mark.parametrize("type_", ABSENT_FAMILIES)
    def test_the_absent_families_stay_out_of_the_vocabulary(self, type_):
        """An object this engine does not have is absent, not offered empty."""
        assert type_ not in introspect_cli.INTROSPECT_TYPES
        with pytest.raises(SystemExit):
            build_parser().parse_args(["introspect", type_] + CONNECTION)


class TestTheNameRule:
    @pytest.mark.parametrize("type_", list(CATALOG_FAMILIES))
    def test_a_name_is_optional(self, type_):
        introspect_cli._validate_name(
            build_parser().parse_args(["introspect", type_] + CONNECTION)
        )
        introspect_cli._validate_name(
            build_parser().parse_args(["introspect", type_, "member"] + CONNECTION)
        )


class TestTheSyncBranch:
    @pytest.mark.parametrize("type_", list(CATALOG_FAMILIES))
    def test_an_unnamed_run_asks_for_the_whole_catalogue(self, type_, monkeypatch):
        introspector = _RecordingIntrospector({METHODS[type_]: []})

        _run_sync(monkeypatch, introspector, ["introspect", type_] + CONNECTION)

        assert introspector.calls == [(METHODS[type_], (), {"name": None})]

    @pytest.mark.parametrize("type_", list(CATALOG_FAMILIES))
    def test_a_name_reaches_the_method_as_a_filter(self, type_, monkeypatch):
        introspector = _RecordingIntrospector({METHODS[type_]: []})

        _run_sync(
            monkeypatch,
            introspector,
            ["introspect", type_, "member"] + CONNECTION,
        )

        assert introspector.calls == [(METHODS[type_], (), {"name": "member"})]

    @pytest.mark.parametrize("type_", list(CATALOG_FAMILIES))
    def test_the_family_the_dialect_answers_passes_the_real_gate(
        self, type_, monkeypatch
    ):
        """A real dialect answers True, so the branch is reached."""
        introspector = _RecordingIntrospector({METHODS[type_]: _results_for(type_)})

        _run_sync(
            monkeypatch,
            introspector,
            ["introspect", type_] + CONNECTION,
            dialect=ClickHouseDialect,
        )

        assert len(introspector.calls) == 1

    @pytest.mark.parametrize("type_", list(CATALOG_FAMILIES))
    def test_a_switch_that_answers_false_refuses(self, type_, capsys):
        class _Dialect:
            pass

        setattr(_Dialect, CATALOG_FAMILIES[type_], staticmethod(lambda: False))

        class _Backend:
            dialect = _Dialect()

        with pytest.raises(SystemExit) as excinfo:
            introspect_cli._require_capability(
                argparse.Namespace(type=type_), _Backend()
            )

        assert excinfo.value.code == 2
        assert "not supported by this server" in capsys.readouterr().err


class TestTheAsyncBranch:
    @pytest.mark.parametrize(
        "type_, method",
        [(type_, METHODS[type_]) for type_ in CATALOG_FAMILIES],
    )
    def test_the_async_branch_calls_the_same_method_and_argument(
        self, type_, method, monkeypatch
    ):
        introspector = _AsyncRecordingIntrospector({method: _results_for(type_)})

        _run_async(
            monkeypatch,
            introspector,
            ["introspect", type_, "member"] + CONNECTION,
        )

        assert introspector.calls == [(method, (), {"name": "member"})]


class TestTheJsonShape:
    """The stable fields reach a machine reader unchanged."""

    def test_function_origin_and_user_defined_ride_the_row(self, monkeypatch, capsys):
        introspector = _RecordingIntrospector(
            {
                "list_functions": [
                    ClickHouseFunctionInfo(name="f", origin="SQLUserDefined")
                ]
            }
        )

        _run_with_real_provider(
            monkeypatch,
            introspector,
            ["introspect", "functions"] + CONNECTION + ["-o", "json"],
        )

        payload = json.loads(capsys.readouterr().out)
        assert payload[0]["name"] == "f"
        assert payload[0]["origin"] == "SQLUserDefined"

    def test_dictionary_lists_survive_serialisation(self, monkeypatch, capsys):
        introspector = _RecordingIntrospector(
            {
                "list_dictionaries": [
                    ClickHouseDictionaryInfo(
                        name="d",
                        database="app",
                        key_names=["id"],
                        attribute_names=["value"],
                    )
                ]
            }
        )

        _run_with_real_provider(
            monkeypatch,
            introspector,
            ["introspect", "dictionaries"] + CONNECTION + ["-o", "json"],
        )

        payload = json.loads(capsys.readouterr().out)
        assert payload[0]["database"] == "app"
        assert payload[0]["key_names"] == ["id"]
        assert payload[0]["attribute_names"] == ["value"]

    def test_cluster_members_keep_their_numbers(self, monkeypatch, capsys):
        introspector = _RecordingIntrospector(
            {
                "list_clusters": [
                    ClickHouseClusterInfo(cluster="c", shard_num=1, replica_num=2)
                ]
            }
        )

        _run_with_real_provider(
            monkeypatch,
            introspector,
            ["introspect", "clusters"] + CONNECTION + ["-o", "json"],
        )

        payload = json.loads(capsys.readouterr().out)
        assert payload[0]["cluster"] == "c"
        assert payload[0]["shard_num"] == 1
        assert payload[0]["replica_num"] == 2

    def test_users_serialise_without_a_credential_field(self, monkeypatch, capsys):
        introspector = _RecordingIntrospector(
            {
                "list_users": [
                    ClickHouseUserInfo(name="alice", auth_type=["no_password"])
                ]
            }
        )

        _run_with_real_provider(
            monkeypatch,
            introspector,
            ["introspect", "users"] + CONNECTION + ["-o", "json"],
        )

        payload = json.loads(capsys.readouterr().out)
        assert payload[0]["name"] == "alice"
        assert payload[0]["auth_type"] == ["no_password"]
        assert "auth_params" not in payload[0]

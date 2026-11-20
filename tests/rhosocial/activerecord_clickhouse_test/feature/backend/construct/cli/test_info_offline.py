# tests/rhosocial/activerecord_clickhouse_test/feature/backend/construct/cli/test_info_offline.py
"""Offline unit tests for the ClickHouse ``info`` CLI module.

All tests are pure-mock: no server, no socket.  The dialect, backend and rich
console are fakes.  ClickHouse is synchronous only, so no async class is used.
"""

import argparse
import json
import sys
import types
from unittest.mock import MagicMock, patch

import pytest

from rhosocial.activerecord.backend.impl.clickhouse.cli import info as mod


def _make_parser():
    subs = argparse.ArgumentParser(prog="clickhouse").add_subparsers(dest="command")
    return mod.create_parser(subs)


# ---------------------------------------------------------------------------
# create_parser
# ---------------------------------------------------------------------------


class TestInfoParser:
    def test_defaults(self):
        args = _make_parser().parse_args([])
        assert args.output == "table"
        assert args.verbose == 0
        assert args.rich_ascii is False
        assert args.version is None
        assert args.is_async is False
        assert args.named_connection is None

    @pytest.mark.parametrize("fmt", mod.INFO_OUTPUT_CHOICES)
    def test_output_choices(self, fmt):
        assert _make_parser().parse_args(["-o", fmt]).output == fmt

    @pytest.mark.parametrize("fmt", ["csv", "tsv", "xml"])
    def test_output_rejects_unsupported(self, fmt):
        with pytest.raises(SystemExit):
            _make_parser().parse_args(["-o", fmt])

    def test_verbosity_is_counted(self):
        assert _make_parser().parse_args(["-vv"]).verbose == 2

    def test_version_override(self):
        assert _make_parser().parse_args(["--version", "26.7.1"]).version == "26.7.1"

    def test_rich_ascii_flag(self):
        assert _make_parser().parse_args(["--rich-ascii"]).rich_ascii is True

    @pytest.mark.parametrize("mode", ["auto", "require", "verify-ca", "verify-full", "disabled"])
    def test_ssl_choices(self, mode):
        assert _make_parser().parse_args(["--ssl", mode]).ssl == mode

    def test_connection_flags(self):
        args = _make_parser().parse_args(
            ["--host", "h", "--port", "9000", "--database", "d", "--user", "u"]
        )
        assert (args.host, args.port, args.database, args.user) == ("h", 9000, "d", "u")


# ---------------------------------------------------------------------------
# parse_version
# ---------------------------------------------------------------------------


class TestParseVersion:
    @pytest.mark.parametrize(
        "text,expected",
        [
            ("26.7.1", (26, 7, 1)),
            ("26.7", (26, 7, 0)),
            ("26", (26, 0, 0)),
            ("1.2.3.4", (1, 2, 3)),
        ],
    )
    def test_parse(self, text, expected):
        assert mod.parse_version(text) == expected

    def test_empty_string_raises(self):
        with pytest.raises(ValueError):
            mod.parse_version("")


# ---------------------------------------------------------------------------
# get_protocol_support_methods / check_protocol_support
# ---------------------------------------------------------------------------


class _Proto:
    def supports_alpha(self):
        return True

    def supports_beta(self):
        return False

    def is_gamma_available(self):
        return True

    def unrelated(self):
        return True

    not_callable = "value"


class _SupportProto:
    def supports_yes(self):
        return True

    def supports_no(self):
        return False

    def supports_raises(self):
        raise RuntimeError("boom")

    def supports_unlisted(self, arg):
        return True

    def supports_explain_format(self, fmt):
        if fmt in ("TEXT", "JSON"):
            return True
        raise ValueError("unsupported format")


class _SupportDialect:
    def supports_yes(self):
        return True

    def supports_no(self):
        return False

    def supports_raises(self):
        raise RuntimeError("boom")

    def supports_unlisted(self, arg):
        return True

    def supports_explain_format(self, fmt):
        if fmt in ("TEXT", "JSON"):
            return True
        raise ValueError("unsupported format")


class TestProtocolIntrospection:
    def test_support_methods_detected_and_sorted(self):
        assert mod.get_protocol_support_methods(_Proto) == [
            "is_gamma_available",
            "supports_alpha",
            "supports_beta",
        ]

    def test_real_protocol_class_has_methods(self):
        from rhosocial.activerecord.backend.dialect.protocols import WindowFunctionSupport

        assert mod.get_protocol_support_methods(WindowFunctionSupport)

    def test_check_support_bool_and_exceptions(self):
        results = mod.check_protocol_support(_SupportDialect(), _SupportProto)
        assert results["supports_yes"] is True
        assert results["supports_no"] is False
        assert results["supports_raises"] is False

    def test_check_support_unlisted_param_method_is_false(self):
        results = mod.check_protocol_support(_SupportDialect(), _SupportProto)
        assert results["supports_unlisted"] is False

    def test_check_support_known_param_method_tests_all_args(self):
        results = mod.check_protocol_support(_SupportDialect(), _SupportProto)
        detail = results["supports_explain_format"]
        assert detail["supported"] == 2
        assert detail["total"] == 6
        assert detail["args"]["TEXT"] is True
        assert detail["args"]["JSON"] is True
        assert detail["args"]["TREE"] is False

    def test_check_support_missing_method_on_dialect_is_false(self):
        class EmptyDialect:
            pass

        results = mod.check_protocol_support(EmptyDialect(), _Proto)
        assert results == {
            "is_gamma_available": False,
            "supports_alpha": False,
            "supports_beta": False,
        }


# ---------------------------------------------------------------------------
# _calculate_protocol_stats
# ---------------------------------------------------------------------------


class TestCalculateProtocolStats:
    @pytest.mark.parametrize(
        "methods,expected",
        [
            ({}, (0, 0)),
            ({"a": True, "b": False}, (1, 2)),
            ({"a": {"supported": 2, "total": 5}}, (2, 5)),
            ({"a": True, "b": {"supported": 1, "total": 3}, "c": False}, (2, 5)),
        ],
    )
    def test_stats(self, methods, expected):
        assert mod._calculate_protocol_stats(methods) == expected


# ---------------------------------------------------------------------------
# _build_protocol_info
# ---------------------------------------------------------------------------


class TestBuildProtocolInfo:
    def _build(self, verbose):
        with patch.object(
            mod,
            "check_protocol_support",
            return_value={"m": True, "p": {"supported": 1, "total": 2}},
        ):
            return mod._build_protocol_info(object(), "Group", [_Proto], verbose)["_Proto"]

    def test_stats_and_percentage(self):
        info = self._build(0)
        assert info["supported"] == 2
        assert info["total"] == 3
        assert info["percentage"] == 66.7

    @pytest.mark.parametrize("verbose", [0, 1])
    def test_methods_omitted_below_verbose_two(self, verbose):
        assert "methods" not in self._build(verbose)

    def test_methods_included_at_verbose_two(self):
        info = self._build(2)
        assert info["methods"] == {"m": True, "p": {"supported": 1, "total": 2}}

    def test_all_supported_is_100(self):
        with patch.object(mod, "check_protocol_support", return_value={"m": True}):
            info = mod._build_protocol_info(object(), "g", [_Proto], 0)["_Proto"]
        assert info["percentage"] == 100.0

    def test_none_supported_is_zero(self):
        with patch.object(mod, "check_protocol_support", return_value={}):
            info = mod._build_protocol_info(object(), "g", [_Proto], 0)["_Proto"]
        assert info["percentage"] == 0


# ---------------------------------------------------------------------------
# display helpers (fake console, no rich needed)
# ---------------------------------------------------------------------------


class TestDisplayHelpers:
    @pytest.mark.parametrize(
        "pct,expected",
        [
            (100, ("green", "[OK]")),
            (75, ("yellow", "[~]")),
            (50, ("yellow", "[~]")),
            (25, ("red", "[~]")),
            (0, ("red", "[X]")),
        ],
    )
    def test_status_style(self, pct, expected):
        assert mod._get_status_style(pct) == expected

    @pytest.mark.parametrize(
        "method,expected",
        [
            ("supports_window_functions", "window functions"),
            ("supports_json_function", "json function"),
            ("is_x_available", "is x available"),
            ("supports_", ""),
        ],
    )
    def test_format_method_display(self, method, expected):
        assert mod._format_method_display(method) == expected

    def test_method_details_bool(self):
        console = MagicMock()
        mod._display_method_details(console, "supports_alpha", True)
        out = " ".join(str(c.args[0]) for c in console.print.call_args_list)
        assert "[green][OK][/green]" in out
        assert "alpha" in out

    def test_method_details_dict(self):
        console = MagicMock()
        mod._display_method_details(
            console,
            "supports_explain_format",
            {"supported": 1, "total": 2, "args": {"TEXT": True, "TREE": False}},
        )
        out = " ".join(str(c.args[0]) for c in console.print.call_args_list)
        assert "TEXT" in out and "TREE" in out
        assert "[green][OK][/green]" in out and "[red][X][/red]" in out

    def test_protocol_item_progress_bar(self):
        console = MagicMock()
        mod._display_protocol_item(
            console, "MyProto", {"percentage": 50, "supported": 1, "total": 2}, 0
        )
        out = str(console.print.call_args.args[0])
        assert "##########----------" in out
        assert "50% (1/2)" in out

    def test_protocol_group_dialect_specific_label(self):
        console = MagicMock()
        mod._display_protocol_group(console, "ClickHouse-specific", {}, 0)
        out = str(console.print.call_args.args[0])
        assert "dialect-specific" in out

    def test_protocol_group_plain_label(self):
        console = MagicMock()
        mod._display_protocol_group(console, "Query Features", {}, 0)
        out = str(console.print.call_args.args[0])
        assert "dialect-specific" not in out


# ---------------------------------------------------------------------------
# _display_info_rich (fake rich injected into sys.modules)
# ---------------------------------------------------------------------------


class FakeConsole:
    printed = []

    def __init__(self, *args, **kwargs):
        pass

    def print(self, *items, **kwargs):
        FakeConsole.printed.extend(str(item) for item in items)


@pytest.fixture
def fake_rich():
    console_mod = types.ModuleType("rich.console")
    console_mod.Console = FakeConsole
    rich_mod = types.ModuleType("rich")
    rich_mod.console = console_mod
    FakeConsole.printed = []
    with patch.dict(sys.modules, {"rich": rich_mod, "rich.console": console_mod}):
        yield FakeConsole.printed


def _rich_info():
    return {
        "clickhouse": {"type": "clickhouse", "version": "26.7.1", "connected": True},
        "protocols": {
            "Query Features": {
                "MyProto": {"supported": 1, "total": 1, "percentage": 100.0},
            }
        },
    }


class TestDisplayInfoRich:
    def test_header_and_connected_label(self, fake_rich):
        mod._display_info_rich(_rich_info(), 0, "26.7.1", True)
        out = " ".join(fake_rich)
        assert "ClickHouse Environment Information" in out
        assert "from actual connection" in out
        assert "Family Overview" in out

    def test_disconnected_label(self, fake_rich):
        mod._display_info_rich(_rich_info(), 0, "25.8.0", False)
        out = " ".join(fake_rich)
        assert "default value - no database connection" in out

    def test_detailed_label_at_verbose_two(self, fake_rich):
        mod._display_info_rich(_rich_info(), 2, "26.7.1", True)
        assert "Detailed" in " ".join(fake_rich)

    def test_group_and_protocol_rendered(self, fake_rich):
        mod._display_info_rich(_rich_info(), 0, "26.7.1", True)
        out = " ".join(fake_rich)
        assert "Query Features" in out
        assert "MyProto" in out


# ---------------------------------------------------------------------------
# handle: dispatch / output
# ---------------------------------------------------------------------------


def _args(**overrides):
    values = dict(
        output="json",
        verbose=0,
        rich_ascii=False,
        version=None,
        database=None,
        named_connection=None,
        is_async=False,
    )
    values.update(overrides)
    return MagicMock(**values)


def _patch_common():
    """Patch the seams shared by every handle test."""
    return (
        patch.object(mod, "create_provider"),
        patch.object(mod, "check_protocol_support", return_value={"m": True}),
        patch("rhosocial.activerecord.backend.impl.clickhouse.dialect.ClickHouseDialect"),
    )


class TestHandle:
    def test_no_connection_uses_default_version(self, capsys):
        p_provider, p_support, p_dialect = _patch_common()
        with p_provider, p_support, p_dialect as dialect_cls:
            dialect_cls.return_value.version = (25, 8, 0)
            mod.handle(_args())

        payload = json.loads(capsys.readouterr().out)
        assert payload["database"] == {
            "type": "clickhouse",
            "version": "25.8.0",
            "version_tuple": [25, 8, 0],
            "connected": False,
        }
        assert "Query Features" in payload["protocols"]
        dialect_cls.assert_called_once_with(version=(25, 8, 0))

    def test_version_override_used_when_offline(self, capsys):
        p_provider, p_support, p_dialect = _patch_common()
        with p_provider, p_support, p_dialect as dialect_cls:
            dialect_cls.return_value.version = (26, 7, 1)
            mod.handle(_args(version="26.7.1"))

        payload = json.loads(capsys.readouterr().out)
        assert payload["database"]["version"] == "26.7.1"
        dialect_cls.assert_called_once_with(version=(26, 7, 1))

    def test_connected_uses_server_version(self, capsys):
        p_provider, p_support, p_dialect = _patch_common()
        backend_cls = patch(
            "rhosocial.activerecord.backend.impl.clickhouse.backend.ClickHouseBackend"
        )
        with p_provider, p_support, p_dialect, backend_cls as b_cls:
            backend = b_cls.return_value
            backend.dialect.version = (26, 7, 1)
            backend.get_server_version.return_value = (26, 7, 1)
            mod.handle(_args(database="mydb"))

        payload = json.loads(capsys.readouterr().out)
        assert payload["database"]["connected"] is True
        assert payload["database"]["version"] == "26.7.1"
        backend.connect.assert_called_once_with()
        backend.introspect_and_adapt.assert_called_once_with()
        backend.disconnect.assert_called_once_with()

    def test_connection_failure_falls_back_to_defaults(self, capsys):
        p_provider, p_support, p_dialect = _patch_common()
        backend_cls = patch(
            "rhosocial.activerecord.backend.impl.clickhouse.backend.ClickHouseBackend"
        )
        with p_provider, p_support, p_dialect as dialect_cls, backend_cls as b_cls:
            b_cls.return_value.connect.side_effect = RuntimeError("no server")
            dialect_cls.return_value.version = (25, 8, 0)
            mod.handle(_args(database="mydb"))

        payload = json.loads(capsys.readouterr().out)
        assert payload["database"]["connected"] is False
        dialect_cls.assert_called_once()

    def test_verbose_two_includes_methods(self, capsys):
        p_provider, p_support, p_dialect = _patch_common()
        with p_provider, p_support, p_dialect as dialect_cls:
            dialect_cls.return_value.version = (25, 8, 0)
            mod.handle(_args(verbose=2))

        payload = json.loads(capsys.readouterr().out)
        proto = next(iter(payload["protocols"]["Query Features"].values()))
        assert "methods" in proto

    def test_rich_output_uses_display_helper(self):
        p_provider, p_support, p_dialect = _patch_common()
        with (
            p_provider as provider,
            p_support,
            p_dialect as dialect_cls,
            patch.object(mod, "RICH_AVAILABLE", True),
            patch.object(mod, "_display_info_rich") as display,
        ):
            dialect_cls.return_value.version = (25, 8, 0)
            mod.handle(_args(output="table"))

        provider.assert_called_once_with("table", ascii_borders=False)
        display.assert_called_once()
        legacy, verbose, version, connected = display.call_args.args
        assert legacy["clickhouse"]["version"] == "25.8.0"
        assert verbose == 0 and version == "25.8.0" and connected is False

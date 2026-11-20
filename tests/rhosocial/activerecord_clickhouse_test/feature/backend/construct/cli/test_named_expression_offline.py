# tests/rhosocial/activerecord_clickhouse_test/feature/backend/construct/cli/test_named_expression_offline.py
"""Offline unit tests for the ClickHouse ``named-expression`` CLI adapter.

The adapter wires the shared named-expression helper to ClickHouse-specific
factories.  All collaborators are mocks; no server is contacted and no async
class is exercised.
"""

import argparse
import os
from unittest.mock import MagicMock, patch

import pytest

from rhosocial.activerecord.backend.impl.clickhouse.cli import named_expression as mod


def _make_parser():
    subs = argparse.ArgumentParser(prog="clickhouse").add_subparsers(dest="command")
    with patch.dict(os.environ, {}, clear=True):
        return mod.create_parser(subs)


# ---------------------------------------------------------------------------
# create_parser
# ---------------------------------------------------------------------------


class TestNamedExpressionParser:
    def test_parser_name_and_defaults(self):
        parser = _make_parser()
        args = parser.parse_args([])
        assert parser.prog.endswith("named-expression")
        assert args.qualified_name is None
        assert args.output == "table"
        assert args.rich_ascii is False
        assert args.dialect_version is None
        assert args.is_async is False
        assert args.host == "localhost"
        assert args.port == 8123
        assert args.user == "root"

    def test_dialect_version_option(self):
        args = _make_parser().parse_args(["app.q", "--dialect-version", "26.7"])
        assert args.dialect_version == "26.7"

    @pytest.mark.parametrize("fmt", ["table", "json", "csv", "tsv"])
    def test_inherited_output_choices(self, fmt):
        assert _make_parser().parse_args(["-o", fmt]).output == fmt

    def test_inherited_connection_flags(self):
        args = _make_parser().parse_args(
            [
                "--host",
                "h",
                "--port",
                "9000",
                "--database",
                "d",
                "--user",
                "u",
                "--password",
                "p",
                "--ssl",
                "require",
            ]
        )
        assert (args.host, args.port, args.database, args.user, args.password, args.ssl) == (
            "h",
            9000,
            "d",
            "u",
            "p",
            "require",
        )

    def test_shared_named_expression_flags(self):
        args = _make_parser().parse_args(
            [
                "app.queries.orders",
                "--describe",
                "--dry-run",
                "--list",
                "--force",
                "--explain",
                "--param",
                "days=7",
                "-e",
                "orders",
            ]
        )
        assert args.qualified_name == "app.queries.orders"
        assert args.describe is True
        assert args.dry_run is True
        assert args.list_queries is True
        assert args.force is True
        assert args.explain is True
        assert args.params == ["days=7"]
        assert args.example == "orders"

    def test_shared_helper_receives_connection_parent(self):
        subs = MagicMock()
        fake_parser = MagicMock()
        with patch(
            "rhosocial.activerecord.backend.named_expression.cli.create_named_expression_parser",
            return_value=fake_parser,
        ) as create:
            result = mod.create_parser(subs)

        assert result is fake_parser
        create.assert_called_once()
        parent = create.call_args.args[1]
        options = [opt for action in parent._actions for opt in action.option_strings]
        for expected in ("--host", "--port", "--database", "-o", "--rich-ascii"):
            assert expected in options
        fake_parser.add_argument.assert_called_once()
        assert fake_parser.add_argument.call_args.args[0] == "--dialect-version"


# ---------------------------------------------------------------------------
# handle (synchronous path only)
# ---------------------------------------------------------------------------


def _args(**overrides):
    values = dict(
        output="table",
        rich_ascii=True,
        dialect_version="26.7",
        database="mydb",
        named_connection=None,
        connection_params=[],
        is_async=False,
    )
    values.update(overrides)
    return MagicMock(**values)


@pytest.fixture
def seams():
    """Keep every seam patched for the whole test so closures stay mocked."""
    with (
        patch.object(mod, "create_provider") as create_provider,
        patch.object(mod, "resolve_connection_config_from_args", return_value=object()) as resolve,
        patch.object(mod, "ClickHouseBackend") as backend_cls,
        patch(
            "rhosocial.activerecord.backend.impl.clickhouse.dialect.ClickHouseDialect"
        ) as dialect_cls,
        patch(
            "rhosocial.activerecord.backend.named_expression.cli.handle_named_expression"
        ) as handle_ne,
    ):
        dialect_cls.return_value.version = (26, 7)
        yield {
            "create_provider": create_provider,
            "resolve": resolve,
            "backend_cls": backend_cls,
            "dialect_cls": dialect_cls,
            "handle_ne": handle_ne,
        }


def _dispatch(args, seams):
    mod.handle(args)
    seams["create_provider"].assert_called_once_with(args.output, ascii_borders=args.rich_ascii)
    seams["handle_ne"].assert_called_once()
    return seams["handle_ne"].call_args.kwargs


class TestHandleSync:
    def test_creates_provider_and_delegates_sync(self, seams):
        kwargs = _dispatch(_args(), seams)
        for key in (
            "backend_factory",
            "get_dialect",
            "execute_query",
            "disconnect",
            "create_dialect",
        ):
            assert key in kwargs
        assert "backend_async_factory" not in kwargs

    def test_create_dialect_uses_requested_version(self, seams):
        kwargs = _dispatch(_args(dialect_version="25.8"), seams)
        result = kwargs["create_dialect"]()
        seams["dialect_cls"].assert_called_with(version=(25, 8))
        assert result is seams["dialect_cls"].return_value

    def test_create_dialect_without_version_uses_none(self, seams):
        kwargs = _dispatch(_args(dialect_version=None), seams)
        kwargs["create_dialect"]()
        seams["dialect_cls"].assert_called_with(version=None)

    def test_backend_factory_connects_and_introspects(self, seams):
        kwargs = _dispatch(_args(), seams)
        backend = kwargs["backend_factory"]()
        assert backend is seams["backend_cls"].return_value
        backend.connect.assert_called_once_with()
        backend.introspect_and_adapt.assert_called_once_with()

    def test_backend_factory_resolves_config(self, seams):
        args = _args()
        kwargs = _dispatch(args, seams)
        kwargs["backend_factory"]()
        seams["resolve"].assert_called_once_with(args)
        seams["backend_cls"].assert_called_once_with(
            connection_config=seams["resolve"].return_value
        )

    def test_backend_factory_overrides_dialect_version_when_requested(self, seams):
        kwargs = _dispatch(_args(dialect_version="26.7.1"), seams)
        backend = kwargs["backend_factory"]()
        assert backend._dialect.version == (26, 7, 1)

    def test_backend_factory_keeps_server_version_without_override(self, seams):
        kwargs = _dispatch(_args(dialect_version=None), seams)
        backend = kwargs["backend_factory"]()
        backend._dialect.version = "unchanged"
        backend2 = kwargs["backend_factory"]()
        assert backend2 is backend

    def test_get_dialect_returns_backend_dialect(self, seams):
        kwargs = _dispatch(_args(), seams)
        backend = MagicMock()
        assert kwargs["get_dialect"](backend) is backend.dialect

    def test_execute_query_uses_execution_options(self, seams):
        kwargs = _dispatch(_args(), seams)
        backend = kwargs["backend_factory"]()
        kwargs["execute_query"]("SELECT 1", {"x": 1}, "DQL")
        call = backend.execute.call_args
        assert call.args == ("SELECT 1", {"x": 1})
        assert call.kwargs["options"].stmt_type == "DQL"

    def test_disconnect_skipped_without_connection(self, seams):
        kwargs = _dispatch(_args(), seams)
        backend = kwargs["backend_factory"]()
        backend._connection = None
        kwargs["disconnect"]()
        backend.disconnect.assert_not_called()

    def test_disconnect_called_with_connection(self, seams):
        kwargs = _dispatch(_args(), seams)
        backend = kwargs["backend_factory"]()
        backend._connection = object()
        kwargs["disconnect"]()
        backend.disconnect.assert_called_once_with()

# tests/conftest.py
"""
This is the root pytest configuration file for the rhosocial-activerecord-clickhouse package's test suite.

Its primary responsibility is to configure the environment so that the external
`rhosocial-activerecord-testsuite` can find and use the backend-specific
implementations (Providers) defined within this project.
"""

import os
import sys
import asyncio
import pytest

# Set the environment variable that the testsuite uses to locate the provider registry.
# The testsuite is a generic package and doesn't know the specific location of the
# provider implementations for this backend (ClickHouse). This environment variable
# acts as a bridge, pointing the testsuite to the correct import path.
#
# `setdefault` is used to ensure that this value is set only if it hasn't been
# set already, allowing for overrides in different environments if needed.
os.environ.setdefault("TESTSUITE_PROVIDER_REGISTRY", "providers.registry:provider_registry")

# Early-parse --scenarios from sys.argv and set CLICKHOUSE_ACTIVE_SCENARIOS env var.
# This must happen before providers.scenarios is imported (it filters its
# SCENARIO_MAP at import time).
_argv_scenarios = None
for _i, _arg in enumerate(sys.argv):
    if _arg.startswith("--scenarios="):
        _argv_scenarios = _arg.split("=", 1)[1]
    elif _arg == "--scenarios" and _i + 1 < len(sys.argv):
        _argv_scenarios = sys.argv[_i + 1]

if _argv_scenarios:
    os.environ["CLICKHOUSE_ACTIVE_SCENARIOS"] = _argv_scenarios


@pytest.fixture(scope="session", autouse=True)
def setup_asyncio_broken_pipe_handler():
    """
    Set up asyncio event loop exception handler to suppress BrokenPipeError.

    In ClickHouse 5.6 + Python 3.8 asyncio combination, writes to dead connections
    may raise BrokenPipeError through the asyncio transport layer via the
    event loop's exception handler rather than through normal try/except.

    This fixture sets up the handler at session start and restores it at end.
    """

    def handler(loop, context):
        exc = context.get("exception")
        if isinstance(exc, BrokenPipeError):
            return  # suppress BrokenPipeError
        loop.default_exception_handler(context)

    # Set up handler for any existing loop
    try:
        loop = asyncio.get_running_loop()
        original_handler = loop.get_exception_handler()
        loop.set_exception_handler(handler)
    except RuntimeError:
        # No running loop yet
        original_handler = None

    yield

    # Restore original handler if we modified one
    try:
        loop = asyncio.get_running_loop()
        if original_handler:
            loop.set_exception_handler(original_handler)
    except RuntimeError:
        pass


# The scenario-parallel scheduling plugin lives in providers/scenario_parallel.py
# so it can be loaded with `-p providers.scenario_parallel` when running the
# external testsuite tests (where this conftest is not on the collection path).
#
# Usage (ClickHouse project's own tests):
#   pytest --scenario-parallel -n 7 --dist=loadgroup tests/
pytest_plugins = ["providers.scenario_parallel"]


def pytest_addoption(parser):
    # The generic --scenarios option is registered by the testsuite conftest
    # (loaded via ``addopts``); register it here only when it is not already
    # present so the two conftests can coexist.
    try:
        parser.addoption(
            "--scenarios",
            default=None,
            help="Comma-separated list of scenario names to run (e.g., --scenarios=clickhouse_97,clickhouse_80). "
            "Compatible with pytest -k '<scenario_name>' as a native alternative.",
        )
    except ValueError:
        pass


def pytest_collection_modifyitems(config, items):
    """Skip tests that depend on transaction semantics (unsupported in ClickHouse).

    ClickHouse does not support ACID transactions.  The ``transaction()``
    context manager degrades to a no-op, but tests that assert rollback /
    savepoint / isolation semantics are inapplicable and are skipped.

    ClickHouse-specific backend transaction tests (``feature/backend/``) are
    excluded because they verify the explicit fast-fail behavior.

    Async tests from the generic testsuite are also skipped because
    ``clickhouse-connect`` is a synchronous-only library.
    """
    skip_transaction = pytest.mark.skip(reason="ClickHouse does not support ACID transactions")
    skip_async = pytest.mark.skip(reason="clickhouse-connect is sync-only; async unsupported")
    for item in items:
        nodeid = item.nodeid.lower()
        is_backend = "/feature/backend/" in nodeid
        # Skip only generic testsuite transaction tests, not the backend's own
        if not is_backend:
            if any(kw in nodeid for kw in ("transaction", "savepoint", "rollback")):
                item.add_marker(skip_transaction)
            # Skip async testsuite tests (class names containing "async")
            cls = getattr(item, "cls", None)
            if cls and "async" in cls.__name__.lower():
                item.add_marker(skip_async)

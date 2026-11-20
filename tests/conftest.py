# tests/conftest.py
"""Root configuration for the ClickHouse backend's test tree.

The backend knows its own classes and how a scenario maps to a connection, so
no declaration table is needed here: the scenario is exposed as a parameterized
pytest fixture that the testsuite environment consumes.  Everything else --
directory contracts, the per-directory logical database, and per-scenario
pinning -- belongs to the testsuite plugin.

ClickHouse-specific collection rules remain here: the engine has no ACID
transactions and clickhouse-connect is synchronous-only, so the shared
transaction and async tests are skipped before their fixtures are set up.
"""

import asyncio
import inspect

import pytest

import support.clickhouse

_SCENARIOS = [support.clickhouse.scenario(name) for name in support.clickhouse.SCENARIOS]


@pytest.fixture(scope="session", params=_SCENARIOS, ids=lambda scenario: scenario.name)
def backend_scenario(request):
    """Return the scenario the tests run against; its id is the scenario name."""
    return request.param


@pytest.fixture(scope="session", autouse=True)
def setup_asyncio_broken_pipe_handler():
    """
    Set up asyncio event loop exception handler to suppress BrokenPipeError.

    Writing to a connection the server has already dropped raises
    BrokenPipeError, and under asyncio that arrives through the event loop's
    exception handler rather than through a normal try/except around the write.
    The exception comes from the socket layer, not from a server release, so it
    is suppressed regardless of which ClickHouse version is connected.

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
            # Skip async testsuite tests.  Detecting the coroutine is more
            # reliable than reading the class name: a module-level `async def
            # test_...` has no class, and the suite ships both shapes.
            cls = getattr(item, "cls", None)
            if cls and "async" in cls.__name__.lower():
                item.add_marker(skip_async)
            elif inspect.iscoroutinefunction(getattr(item, "function", None)):
                item.add_marker(skip_async)

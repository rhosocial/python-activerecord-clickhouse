"""Conftest for ActiveRecord bulk benchmark bridge tests."""

from rhosocial.activerecord.testsuite.benchmark.conftest import (  # noqa: F401
    benchmark_size,
)
from rhosocial.activerecord.testsuite.benchmark.crud.conftest import (  # noqa: F401
    crud_sync_context,
    crud_async_context,
)


def pytest_addoption(parser):
    try:
        parser.addoption(
            "--benchmark-size",
            action="store",
            default="small",
            choices=("small", "medium", "large"),
            help="Data size for rhosocial benchmark scenarios.",
        )
    except ValueError:
        pass


def pytest_configure(config):
    config.addinivalue_line("markers", "benchmark: Mark tests as performance benchmarks")
    config.addinivalue_line("markers", "benchmark_crud: Mark CRUD benchmark tests")
    config.addinivalue_line("markers", "benchmark_sync: Mark synchronous benchmark tests")
    config.addinivalue_line("markers", "benchmark_async: Mark asynchronous benchmark tests")
    config.addinivalue_line("markers", "benchmark_write: Mark write-oriented benchmark tests")

# tests/rhosocial/activerecord_clickhouse_test/feature/rules/backend/conftest.py
"""Fixtures for ClickHouse's own backend-layer rule suite.

The shared testsuite modules supply the assertions; this conftest selects the
subject: only ``backend/impl/clickhouse`` and this repository's tests. Every
path is derived from importable packages, never from a hardcoded worktree path.
"""

from __future__ import annotations

import importlib
from pathlib import Path
from typing import List, Tuple

import pytest
from rhosocial.activerecord.testsuite.feature.rules.backend.conftest import *  # noqa: F401,F403
from rhosocial.activerecord.testsuite.feature.rules.backend.conftest import python_files_in
from rhosocial.activerecord.testsuite.pytest_plugin import Declaration

DECLARATION = Declaration(
    uses_database=False,
    parallel=False,
    purpose="Executable assertions of the ClickHouse backend's formal constraints",
    passes_means="ClickHouse source obeys the mechanical and structural rule",
    fails_means="ClickHouse source introduces a forbidden construct or dependency",
)


def clickhouse_expression_package() -> object:
    """The installed ClickHouse expression package."""
    return importlib.import_module("rhosocial.activerecord.backend.impl.clickhouse.expression")


def clickhouse_impl_root() -> Path:
    """The installed ``backend/impl/clickhouse`` directory."""
    package = clickhouse_expression_package()
    for search_path in vars(package).get("__path__", ()):
        current = Path(search_path).resolve()
        for candidate in [current] + list(current.parents):
            if candidate.name == "impl" and candidate.parent.name == "backend":
                return candidate / current.relative_to(candidate).parts[0]
    pytest.skip("ClickHouse impl root is not discoverable from the installed package")


def clickhouse_project_root() -> Path:
    """Project root inferred from the installed ClickHouse package layout."""
    impl_root = clickhouse_impl_root()
    for candidate in [impl_root] + list(impl_root.parents):
        if (candidate / "src").is_dir() and (candidate / "tests").is_dir():
            return candidate
    pytest.skip("ClickHouse project root is not discoverable from the installed package")


@pytest.fixture
def backend_expression_package() -> object:
    """ClickHouse's expression package."""
    return clickhouse_expression_package()


@pytest.fixture
def backend_dialect() -> object:
    """An instantiated ClickHouse dialect."""
    from rhosocial.activerecord.backend.impl.clickhouse.dialect import ClickHouseDialect

    return ClickHouseDialect()


@pytest.fixture
def backend_prefix() -> str:
    """ClickHouse's own naming prefix."""
    return "ClickHouse"


@pytest.fixture
def backend_impl_root() -> Path:
    """The ClickHouse ``impl`` root used by the file-driven shared rules."""
    return clickhouse_impl_root()


@pytest.fixture
def source_roots() -> List[Tuple[str, Path]]:
    """One pair only: this backend's implementation tree, never another's."""
    return [("clickhouse", clickhouse_impl_root())]


@pytest.fixture
def backend_project_root() -> Path:
    """Project root for ClickHouse's tests."""
    return clickhouse_project_root()


@pytest.fixture
def backend_test_files() -> List[Path]:
    """Every Python test file in this repository."""
    files = list(python_files_in(clickhouse_project_root() / "tests"))
    assert files, "no test files under the ClickHouse project's tests directory"
    return files


@pytest.fixture
def backend_matrix_files(backend_test_files: List[Path]) -> List[Path]:
    """Round-trip matrices that declare the refusal-marker list.

    The marker is spelled from two literals so this conftest is not itself
    mistaken for a matrix file by the shared rule's text scan.
    """
    marker = "UN" + "CONSTRUCTIBLE"
    return [path for path in backend_test_files if marker in path.read_text(encoding="utf-8")]


@pytest.fixture
def minimum_observed_calls() -> int:
    """ClickHouse source has no reflective attribute reads left to grandfather.

    Every former ``getattr``/``hasattr`` call was replaced with declared
    attribute access or an explicit dispatch table. The shared guard compares
    with a strict ``>``, so ``-1`` is the floor that accepts zero observations;
    the scan itself stays enabled and any new call is still reported.
    """
    return -1

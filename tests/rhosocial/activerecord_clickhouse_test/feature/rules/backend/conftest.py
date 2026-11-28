# tests/rhosocial/activerecord_clickhouse_test/feature/rules/backend/conftest.py
from __future__ import annotations

import importlib

import pytest

from rhosocial.activerecord.testsuite.feature.rules.backend.support import impl_root_of
from rhosocial.activerecord.testsuite.feature.rules.contracts.subject import (
    ExpressionSubject,
    Root,
)

IMPL = "rhosocial.activerecord.backend.impl.clickhouse"
PREFIX = "ClickHouse"


@pytest.fixture
def subject() -> ExpressionSubject:
    """clickhouse's namespace, described without spelling its root."""
    expression = importlib.import_module(f"{IMPL}.expression")
    root = impl_root_of(expression)
    return ExpressionSubject(
        label="clickhouse",
        roots=(Root("clickhouse", root, IMPL),),
        prefix=PREFIX,
        open_package_root=root,
        impl_module_prefix=IMPL,
    )

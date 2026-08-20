# tests/rhosocial/activerecord_clickhouse_test/feature/query/clickhouse/conftest.py
"""
Pytest configuration for ClickHouse-specific query tests.

This file imports fixtures from the parent conftest, making them
available to the tests in this directory.
"""

from rhosocial.activerecord.testsuite.feature.query.conftest import *  # noqa: F403

# tests/rhosocial/activerecord_clickhouse_test/feature/events/test_handlers.py
"""
Event Handler Test Module for ClickHouse backend.

This module imports and runs the shared tests from the testsuite package,
ensuring ClickHouse backend compatibility.
"""
# Import shared tests from testsuite package (sync only — clickhouse-connect
# is a synchronous-only library, so async tests are skipped by the conftest).
# DO NOT import test_handlers_async: its module-level async coroutines have
# the same names as the sync functions and would override them.
from rhosocial.activerecord.testsuite.feature.events.test_handlers import *  # noqa: F403
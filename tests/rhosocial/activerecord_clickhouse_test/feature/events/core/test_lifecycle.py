# tests/rhosocial/activerecord_clickhouse_test/feature/events/core/test_lifecycle.py
"""
Event Lifecycle Test Module for ClickHouse backend.

This module imports and runs the shared tests from the testsuite package,
ensuring ClickHouse backend compatibility.
"""
# The fixtures and the tests come from the shared suite; the root conftest
# exposes the backend scenario the suite environment consumes, and this
# module's own conftest imports them for this directory.

# Import shared tests from testsuite package (sync only — clickhouse-connect
# is a synchronous-only library, so async tests are skipped by the conftest).
# DO NOT import test_lifecycle_async: its module-level async coroutines have
# the same names as the sync functions and would override them.
from rhosocial.activerecord.testsuite.feature.events.core.test_lifecycle import *  # noqa: F403

